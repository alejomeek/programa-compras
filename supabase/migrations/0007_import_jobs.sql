-- 0007_import_jobs.sql
-- Fase 2 — data-model
-- `import_jobs` e `import_issues`: cabecera transaccional de toda importacion
-- y su registro estructurado de incidencias (contrato §6.2, §6.3, §7, §9.3).
--
-- Regla de 0006 aplicada sin excepcion: esta migracion concede privilegios de
-- tabla EXPLICITOS a `authenticated` y a `service_role`. No se asume ningun
-- privilegio por defecto. RLS filtra filas; sin GRANT, Postgres deniega antes
-- de evaluar RLS (bug real observado en produccion tras la Fase 1).

-- ---------------------------------------------------------------------------
-- Enums
-- ---------------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from pg_type where typname = 'import_type') then
    create type public.import_type as enum ('sdos_inventory', 'inveptos_sales', 'supplier_price_list');
  end if;
end
$$;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'import_status') then
    create type public.import_status as enum ('pending', 'processing', 'completed', 'failed');
  end if;
end
$$;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'issue_severity') then
    -- 'info' incluido porque `engine/validation.py` (import-backend) ya lo
    -- emite: sin el valor, una incidencia informativa tumbaria la importacion
    -- entera al insertarse.
    create type public.issue_severity as enum ('error', 'warning', 'info');
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- import_jobs
-- ---------------------------------------------------------------------------
create table if not exists public.import_jobs (
  id             uuid primary key default gen_random_uuid(),
  type           public.import_type not null,
  -- Nullable: una importacion de inventario/ventas no pertenece a un proveedor.
  supplier_id    uuid references public.suppliers (id) on delete restrict,
  file_id        uuid not null references public.files (id) on delete restrict,
  status         public.import_status not null default 'pending',
  -- `date` y no `timestamptz` (contrato §6.1): un cambio de zona horaria no
  -- debe mover el periodo de negocio.
  period_start   date,
  period_end     date,
  period_days    integer generated always as (period_end - period_start + 1) stored,
  rows_total     integer not null default 0 check (rows_total    >= 0),
  rows_valid     integer not null default 0 check (rows_valid    >= 0),
  rows_rejected  integer not null default 0 check (rows_rejected >= 0),
  error_message  text,
  started_at     timestamptz,
  finished_at    timestamptz,
  created_by     uuid references public.profiles (id) on delete set null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  -- Periodo inclusivo con piso 1 (contrato §3.4). Fechas invertidas dan <= 0 y
  -- la fila se rechaza aqui: nunca puede llegar a la BD el `period_days = 1`
  -- silencioso del motor viejo.
  constraint import_jobs_period_days_positive_check check (period_days > 0),
  constraint import_jobs_period_pair_check
    check ((period_start is null) = (period_end is null)),
  -- Una lista de precios sin proveedor no es procesable.
  constraint import_jobs_price_list_supplier_check
    check (type <> 'supplier_price_list' or supplier_id is not null),
  -- Contrato §9.3: un fallo SIEMPRE queda con motivo legible.
  constraint import_jobs_failed_needs_message_check
    check (status <> 'failed' or length(btrim(coalesce(error_message, ''))) > 0)
);

comment on table public.import_jobs is
  'Cabecera de cada importacion. Ningun consumidor debe leer datos de un job que no este en status = completed (contrato §9.3).';
comment on column public.import_jobs.period_days is
  'Generada: period_end - period_start + 1 (inclusivo). El CHECK > 0 bloquea fechas invertidas en la capa de datos.';
comment on column public.import_jobs.error_message is
  'Motivo legible del fallo. Obligatorio cuando status = failed.';

create index if not exists import_jobs_status_created_at_idx
  on public.import_jobs (status, created_at desc);
create index if not exists import_jobs_type_created_at_idx
  on public.import_jobs (type, created_at desc);
create index if not exists import_jobs_supplier_id_idx on public.import_jobs (supplier_id);
create index if not exists import_jobs_file_id_idx     on public.import_jobs (file_id);

drop trigger if exists import_jobs_set_updated_at on public.import_jobs;
create trigger import_jobs_set_updated_at
  before update on public.import_jobs
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- import_issues
-- ---------------------------------------------------------------------------
create table if not exists public.import_issues (
  id             uuid primary key default gen_random_uuid(),
  import_job_id  uuid not null references public.import_jobs (id) on delete cascade,
  file_id        uuid references public.files (id) on delete set null,
  severity       public.issue_severity not null default 'error',
  code           text not null check (code ~ '^[a-z][a-z0-9_]*$'),
  source         text,
  row_number     integer check (row_number > 0),
  -- Sin check de digitos a proposito: aqui se registra precisamente el EAN
  -- invalido tal como venia en el archivo.
  ean            text,
  sku            text,
  product_name   text,
  -- Sin check de "no vacio" a proposito: una incidencia con detalle vacio es
  -- un defecto de mensaje, no una razon para abortar una importacion completa.
  detail         text not null,
  created_at     timestamptz not null default now()
);

comment on table public.import_issues is
  'Incidencias estructuradas de una importacion (contrato §5.2). Append-only en la practica: no hay policy de update ni delete.';
comment on column public.import_issues.code is
  'Codigo snake_case. Es text y no enum para que el motor pueda agregar codigos sin una migracion por codigo. Los 9 que emite hoy engine/validation.py: los 6 del contrato §6.3 (ean_invalido, ean_duplicado, costo_invalido, comodin_invalido, fecha_invalida, tisuc_desconocido) mas columna_faltante, total_inconsistente y cantidad_invalida (inventario negativo).';
comment on column public.import_issues.ean is
  'Valor crudo del archivo, sin validar: el EAN invalido es justamente el dato de la incidencia.';

create index if not exists import_issues_job_severity_idx
  on public.import_issues (import_job_id, severity);
create index if not exists import_issues_code_idx on public.import_issues (code);
create index if not exists import_issues_ean_idx  on public.import_issues (ean);

-- ---------------------------------------------------------------------------
-- RLS (contrato §7)
-- ---------------------------------------------------------------------------
alter table public.import_jobs   enable row level security;
alter table public.import_issues enable row level security;

revoke all on table public.import_jobs   from anon;
revoke all on table public.import_issues from anon;

-- import_jobs: todos leen; buyer/admin crean; el avance de estado lo hace el
-- servidor con service_role (sin policy de update para authenticated).
drop policy if exists import_jobs_select_authenticated on public.import_jobs;
create policy import_jobs_select_authenticated on public.import_jobs
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists import_jobs_insert_writer on public.import_jobs;
create policy import_jobs_insert_writer on public.import_jobs
  for insert to authenticated
  with check (
    (select public.can_write())
    and created_by = (select auth.uid())
    -- Un job solo puede nacer en 'pending': el pipeline es quien lo avanza.
    and status = 'pending'
  );

-- import_issues: todos leen. El pipeline las escribe con service_role; se deja
-- insert para admin por si hace falta registrar una incidencia manual.
drop policy if exists import_issues_select_authenticated on public.import_issues;
create policy import_issues_select_authenticated on public.import_issues
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists import_issues_insert_admin on public.import_issues;
create policy import_issues_insert_admin on public.import_issues
  for insert to authenticated
  with check ((select public.is_admin()));

-- ---------------------------------------------------------------------------
-- GRANT explicitos (leccion de 0006)
-- ---------------------------------------------------------------------------
-- Primero se REVOCA todo y despues se concede lo justo. El revoke no sobra:
-- una instalacion de Supabase puede traer `alter default privileges` que da
-- ALL sobre las tablas nuevas de `public` a anon/authenticated/service_role
-- (la imagen oficial de Docker lo hace). Sin revocar, `authenticated` tendria
-- update/delete sobre tablas que sus policies no permiten tocar; RLS lo
-- frenaria igual, pero el privilegio efectivo dejaria de coincidir con el
-- contrato §7 y cualquier policy futura mal escrita quedaria sin segunda red.
revoke all on table public.import_jobs   from anon, authenticated, service_role;
revoke all on table public.import_issues from anon, authenticated, service_role;

-- Exactamente las operaciones que las policies de arriba permiten: nada mas.
grant select, insert on table public.import_jobs   to authenticated;
grant select, insert on table public.import_issues to authenticated;

-- service_role omite RLS, pero NO omite los GRANT de tabla. Es el rol que
-- ejecuta el pipeline de importacion: sin esto, el parseo falla con
-- "permission denied" igual que el bug que corrigio 0006.
grant select, insert, update on table public.import_jobs   to service_role;
grant select, insert         on table public.import_issues to service_role;
