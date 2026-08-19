#!/usr/bin/env bash
# supabase/tests/run_migration_tests.sh
# Fase 2 — data-model
#
# Aplica TODAS las migraciones de `supabase/migrations/` sobre un contenedor
# Postgres EFIMERO y descartable, corre las suites de pruebas de comportamiento
# y destruye el contenedor.
#
# Regla del proyecto: esto NUNCA se ejecuta contra el proyecto Supabase real ni
# lee `.env.local`. La unica forma de validar SQL antes de que el usuario
# confirme es este contenedor de usar y tirar.
#
#   uso:  supabase/tests/run_migration_tests.sh
#   sale con codigo 1 si algun aserto falla (apto para CI).

set -euo pipefail

IMAGE="${SUPABASE_PG_IMAGE:-supabase/postgres:17.6.1.063}"
CONTAINER="compras-migrations-test-$$"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

cleanup() { docker rm -f "$CONTAINER" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "==> Levantando contenedor efimero ($IMAGE)"
docker run -d --name "$CONTAINER" -e POSTGRES_PASSWORD=postgres "$IMAGE" >/dev/null

# No basta con pg_isready: la imagen arranca un servidor temporal para su propia
# inicializacion, acepta el socket local antes de escuchar en TCP y todavia no
# tiene el esquema `auth`. Se espera a las tres cosas.
echo -n "==> Esperando a Postgres"
ready=0
for _ in $(seq 1 90); do
  if docker exec -e PGPASSWORD=postgres "$CONTAINER" \
       psql -U postgres -h 127.0.0.1 -tAc "select 1 from information_schema.tables where table_schema='auth' and table_name='users'" \
       2>/dev/null | grep -q 1; then
    ready=1; break
  fi
  echo -n "."; sleep 1
done
echo ""
if [ "$ready" -ne 1 ]; then
  echo "!! El contenedor no llego a estar listo; se aborta." >&2
  exit 1
fi

psql_file() {
  docker exec -i -e PGOPTIONS='-c client_min_messages=warning' "$CONTAINER" \
    psql -U postgres -q -v ON_ERROR_STOP=1 < "$1" >/dev/null
}

# `storage` pertenece a supabase_admin y viene VACIO en la imagen de BD, asi que
# el stub de storage.buckets/objects tiene que existir ANTES de aplicar 0011.
# Ambas cosas son andamiaje del contenedor de prueba, no del proyecto real.
docker exec -e PGPASSWORD=postgres "$CONTAINER" \
  psql -U supabase_admin -h 127.0.0.1 -d postgres -q \
  -c "grant create, usage on schema storage to postgres;" >/dev/null
psql_file "$ROOT/supabase/tests/sql/_storage_stub.sql"

echo "==> Aplicando migraciones"
for f in "$ROOT"/supabase/migrations/*.sql; do
  printf '    %s\n' "$(basename "$f")"
  psql_file "$f"
done

echo "==> Cargando arnes y fixtures"
psql_file "$ROOT/supabase/tests/sql/00_helpers.sql"
psql_file "$ROOT/supabase/tests/sql/01_fixtures.sql"

echo "==> Aplicando seed.sql dos veces (tiene que ser idempotente)"
psql_file "$ROOT/supabase/seed.sql"
psql_file "$ROOT/supabase/seed.sql"

# Las suites se incluyen entre si con \i, asi que necesitan estar dentro del
# contenedor en la misma ruta relativa.
docker cp "$ROOT/supabase" "$CONTAINER:/tmp/supabase" >/dev/null

total_pass=0
total_fail=0
for suite in "$ROOT"/supabase/tests/sql/[0-9][0-9]_*.sql; do
  name="$(basename "$suite")"
  case "$name" in 00_helpers.sql|01_fixtures.sql) continue ;; esac
  out="$(docker exec -i "$CONTAINER" psql -U postgres -q < "$suite" 2>&1 | grep -E 'PASS |FAIL |^ERROR' || true)"
  pass=$(printf '%s\n' "$out" | grep -c 'PASS ' || true)
  fail=$(printf '%s\n' "$out" | grep -c 'FAIL ' || true)
  err=$(printf '%s\n' "$out" | grep -c '^ERROR' || true)
  printf '==> %-38s PASS=%-3s FAIL=%s ERROR=%s\n' "$name" "$pass" "$fail" "$err"
  if [ "$fail" != "0" ] || [ "$err" != "0" ]; then
    printf '%s\n' "$out" | grep -E 'FAIL |^ERROR' | sed 's/^/      /'
  fi
  total_pass=$((total_pass + pass))
  total_fail=$((total_fail + fail + err))
done

echo "==> TOTAL: $total_pass asertos correctos, $total_fail fallidos"
[ "$total_fail" -eq 0 ]
