"""Función serverless de Vercel: procesa un `import_job` de punta a punta.

    POST /api/imports_process   { "jobId": "..." }
    Header requerido: X-Internal-Secret == INTERNAL_API_SECRET

Es el ÚNICO lugar del repositorio donde `engine.pipeline.run_import_job` se
conecta a un Postgres y un Storage reales. Todo lo demás en `engine/` recibe
una conexión y un `storage` ya inyectados y no lee credenciales — esa regla
se mantiene aquí también: este archivo es la frontera, no una excepción.

Convención de Vercel para funciones Python (`api/*.py`): una clase llamada
`handler` que extiende `BaseHTTPRequestHandler`.

Variables de entorno requeridas (`.env.example`, docs/IMPLEMENTATION_CONTRACT.md
§14 punto 3):
    INTERNAL_API_SECRET        secreto compartido con `src/app/api/imports/route.ts`.
    SUPABASE_URL                misma URL que NEXT_PUBLIC_SUPABASE_URL.
    SUPABASE_SERVICE_ROLE_KEY   clave de servicio (omite RLS). NUNCA al navegador.
    SUPABASE_DB_URL             cadena de conexión Postgres de servicio, para psycopg.

Hotfix de producción (post primer smoke test real, ver contrato §15): un 500
"antes de llamadas externas" resultó ser `psycopg` sin instalar (Vercel
instala dependencias Python solo desde el requirements.txt de la raíz, ver
ese archivo) combinado con `SUPABASE_URL` sin documentar. Esta versión además
registra en logs (stdout/stderr, visibles en Vercel) todo camino de error y
evita que un fallo deje un `import_job` en `pending` para siempre sin rastro:
ante cualquier excepción no controlada, intenta — best-effort, solo si hay
una conexión válida a la base — marcarlo `failed` con `engine.persistence.
mark_failed`. Nunca se promete ese marcado si no hay conexión (sin
`SUPABASE_DB_URL`, o si el propio `connect()` falla): ahí no hay nada que
actualizar, y el error solo puede quedar en el log + en la respuesta HTTP.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable, Protocol

# Vercel empaqueta esta función junto al repo, pero por si el cwd de ejecución
# no lo incluye en sys.path, se agrega explícitamente antes de importar engine.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.persistence import mark_failed, readable_error  # noqa: E402
from engine.pipeline import run_import_job  # noqa: E402

REQUIRED_ENV_VARS = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_DB_URL")

logger = logging.getLogger("imports_process")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _stderr_handler = logging.StreamHandler()  # va a stderr; Vercel lo captura como log de función
    _stderr_handler.setFormatter(logging.Formatter("%(levelname)s imports_process: %(message)s"))
    logger.addHandler(_stderr_handler)


class StorageDownloader(Protocol):
    def download(self, *, bucket: str, object_path: str) -> bytes: ...


class HttpStorage:
    """Descarga un objeto de Supabase Storage vía REST, con `service_role`.

    Implementa el protocolo ``StorageDownloader`` de :mod:`engine.pipeline`
    sin depender del paquete ``supabase``: una sola llamada HTTP con
    ``urllib`` (librería estándar), para no sumarle dependencias a la función.
    """

    def __init__(self, *, base_url: str, service_role_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._key = service_role_key

    def download(self, *, bucket: str, object_path: str) -> bytes:
        url = f"{self._base_url}/storage/v1/object/{bucket}/{object_path}"
        request = urllib.request.Request(
            url,
            headers={"Authorization": f"Bearer {self._key}", "apikey": self._key},
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(
                f"Storage devolvió {exc.code} al leer {bucket}/{object_path}."
            ) from exc


def _connection() -> Any:
    """Conexión psycopg de servicio. Se abre aquí, nunca dentro de `engine/`."""
    import psycopg  # import diferido: solo esta función lo necesita

    db_url = os.environ["SUPABASE_DB_URL"]
    return psycopg.connect(db_url, autocommit=False)


def _default_storage_factory(base_url: str, service_role_key: str) -> StorageDownloader:
    return HttpStorage(base_url=base_url, service_role_key=service_role_key)


def _mark_failed_with_connection(conn: Any, job_id: Any, message: str) -> None:
    """Best-effort: marca `failed` reusando una conexión YA abierta y válida.

    `conn` puede quedar en una transacción abortada si el fallo vino de un
    `execute` a mitad de camino (por ejemplo, `_load_context` de
    `engine.pipeline`); por eso se hace `rollback()` antes de intentar el
    `UPDATE`. Si el marcado también falla, se loguea y se sigue: nunca se deja
    que un fallo secundario tape el error original que ya se está devolviendo
    en la respuesta HTTP.
    """
    try:
        conn.rollback()
    except Exception:  # noqa: BLE001 - best-effort, la conexión puede ya estar rota
        pass
    try:
        mark_failed(conn, import_job_id=job_id, error_message=message)
        logger.info("job_id=%s marcado como failed (best-effort).", job_id)
    except Exception as exc:  # noqa: BLE001 - no se relanza: es una salvaguarda adicional
        logger.error("no se pudo marcar failed el job_id=%s: %s", job_id, exc)


def _mark_failed_with_new_connection(
    connect: Callable[[], Any], job_id: Any, message: str
) -> None:
    """Best-effort: abre una conexión nueva solo para marcar `failed`.

    Se usa cuando el fallo ocurrió ANTES de intentar procesar (por ejemplo,
    faltan `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY` pero sí está
    `SUPABASE_DB_URL`): no hay conexión abierta todavía, pero sí es posible
    abrir una. Si ni eso se puede (falta `SUPABASE_DB_URL`, o `connect()`
    falla), no se promete nada: se loguea y no queda nada por marcar.
    """
    try:
        conn = connect()
    except Exception as exc:  # noqa: BLE001 - sin conexión no hay nada que marcar
        logger.error(
            "no se pudo abrir una conexión para marcar failed el job_id=%s: %s", job_id, exc
        )
        return
    try:
        _mark_failed_with_connection(conn, job_id, message)
    finally:
        conn.close()


def _process(
    job_id: Any,
    *,
    connect: Callable[[], Any] = _connection,
    storage_factory: Callable[[str, str], StorageDownloader] = _default_storage_factory,
) -> tuple[int, dict]:
    """Lógica de negocio de `do_POST`, separada de la mecánica HTTP.

    Recibe `connect`/`storage_factory` inyectables (mismo criterio que
    `engine/`: nada de credenciales ni red reales en las pruebas) para poder
    probar cada camino de error sin depender de psycopg instalado ni de un
    Postgres real.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        message = f"Faltan variables de entorno: {', '.join(missing)}."
        logger.error("%s (job_id=%s)", message, job_id)
        if "SUPABASE_DB_URL" not in missing:
            _mark_failed_with_new_connection(connect, job_id, message)
        return 500, {"error": message}

    try:
        conn = connect()
    except Exception as exc:  # noqa: BLE001 - error de infraestructura, no de negocio
        message = f"No se pudo conectar a la base: {exc}"
        logger.error("%s (job_id=%s)", message, job_id)
        return 500, {"error": message}

    storage = storage_factory(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

    try:
        result = run_import_job(job_id, conn=conn, storage=storage)
    except Exception as exc:  # noqa: BLE001 - se traduce a 500 + failed, nunca se traga
        message = readable_error(exc)
        logger.exception("fallo no controlado procesando job_id=%s", job_id)
        _mark_failed_with_connection(conn, job_id, message)
        conn.close()
        return 500, {"error": message}

    conn.close()

    if result.ok:
        logger.info(
            "job_id=%s completado: %s líneas, %s incidencias.",
            job_id,
            result.lines_inserted,
            result.issues_inserted,
        )
    else:
        logger.warning(
            "job_id=%s terminó en %s: %s", job_id, result.status, result.error_message
        )

    return (
        200 if result.ok else 422,
        {
            "importJobId": str(result.import_job_id),
            "status": result.status,
            "linesInserted": result.lines_inserted,
            "issuesInserted": result.issues_inserted,
            "errorMessage": result.error_message,
        },
    )


class handler(BaseHTTPRequestHandler):  # noqa: N801 - nombre exigido por Vercel
    def do_POST(self) -> None:  # noqa: N802 - firma exigida por BaseHTTPRequestHandler
        secret = os.environ.get("INTERNAL_API_SECRET")
        if not secret or self.headers.get("x-internal-secret") != secret:
            self._json(401, {"error": "No autorizado."})
            return

        length = int(self.headers.get("content-length", 0) or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Cuerpo inválido."})
            return

        job_id = payload.get("jobId")
        if not job_id:
            self._json(400, {"error": "Falta jobId."})
            return

        status, body = _process(job_id)
        self._json(status, body)

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
