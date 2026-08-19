"""Función serverless de Vercel: procesa un `import_job` de punta a punta.

    POST /api/imports_process   { "jobId": "..." }
    Header requerido: X-Internal-Secret == INTERNAL_API_SECRET

Es el ÚNICO lugar del repositorio donde `engine.pipeline.run_import_job` se
conecta a un Postgres y un Storage reales. Todo lo demás en `engine/` recibe
una conexión y un `storage` ya inyectados y no lee credenciales — esa regla
se mantiene aquí también: este archivo es la frontera, no una excepción.

Convención de Vercel para funciones Python (`api/*.py`): una clase llamada
`handler` que extiende `BaseHTTPRequestHandler`. NO VERIFICADO contra un
despliegue real (Vercel no está confirmado como conectado a este repo,
docs/IMPLEMENTATION_CONTRACT.md §14) — es la interfaz documentada de Vercel,
pero su primera ejecución real conviene tratarla como un smoke test, no como
algo ya probado.

Variables de entorno requeridas, ninguna con valor todavía en este repo
(acción manual pendiente, §14):
    INTERNAL_API_SECRET        secreto compartido con `src/app/api/imports/route.ts`.
    SUPABASE_URL                misma URL que NEXT_PUBLIC_SUPABASE_URL.
    SUPABASE_SERVICE_ROLE_KEY   clave de servicio (omite RLS). NUNCA al navegador.
    SUPABASE_DB_URL             cadena de conexión Postgres de servicio, para psycopg.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler
from pathlib import Path

# Vercel empaqueta esta función junto al repo, pero por si el cwd de ejecución
# no lo incluye en sys.path, se agrega explícitamente antes de importar engine.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.pipeline import run_import_job  # noqa: E402


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


def _connection():
    """Conexión psycopg de servicio. Se abre aquí, nunca dentro de `engine/`."""
    import psycopg  # import diferido: solo esta función lo necesita

    db_url = os.environ["SUPABASE_DB_URL"]
    return psycopg.connect(db_url, autocommit=False)


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

        try:
            base_url = os.environ["SUPABASE_URL"]
            service_key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        except KeyError as exc:
            self._json(500, {"error": f"Falta configurar la variable {exc.args[0]}."})
            return

        storage = HttpStorage(base_url=base_url, service_role_key=service_key)

        try:
            conn = _connection()
        except Exception as exc:  # noqa: BLE001 - error de infraestructura, no de negocio
            self._json(500, {"error": f"No se pudo conectar a la base: {exc}"})
            return

        try:
            result = run_import_job(job_id, conn=conn, storage=storage)
        finally:
            conn.close()

        self._json(
            200 if result.ok else 422,
            {
                "importJobId": str(result.import_job_id),
                "status": result.status,
                "linesInserted": result.lines_inserted,
                "issuesInserted": result.issues_inserted,
                "errorMessage": result.error_message,
            },
        )

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
