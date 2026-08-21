"""Función serverless de Vercel: calcula y guarda una corrida de compras sugeridas.

    POST /api/purchase_runs_calculate
    Header requerido: X-Internal-Secret == INTERNAL_API_SECRET

Mirror de `api/imports_process.py` (misma frontera: aquí, y solo aquí, se abre
una conexión Postgres real para este flujo). Sin Storage: a diferencia de una
importación, las fuentes ya están en la base — Fase 2 ya las importó —
`engine.recommendation` lee `sales_lines`/`inventory_lines`/`price_list_items`
directo por SQL, no hay archivo que descargar.

Diferencia de ciclo de vida con `imports_process.py`: un `import_job` YA
EXISTE (`pending`) antes de procesar, así que un fallo necesita "marcarlo
failed" para no dejarlo huérfano (ver ese archivo). Una corrida de compras
nace y se calcula en el MISMO paso — `POST /api/purchase-runs` la crea
llamando aquí síncronamente — así que si algo falla, la fila `purchase_runs`
simplemente nunca se inserta (o su `INSERT` se revierte con el resto de la
transacción, ver `engine.purchase_runs.persist_purchase_run`): no hay fila a
medias que marcar. `purchase_runs.status` ni siquiera tiene un valor
`'failed'` en su enum (`draft`/`calculated`/`locked`/`cancelled`); un fallo de
cálculo vive solo en la respuesta HTTP y en el log, nunca en la base.

Variables de entorno requeridas (`.env.example`): `INTERNAL_API_SECRET`,
`SUPABASE_DB_URL`. A diferencia de `imports_process.py`, no hace falta
`SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`: no se toca Storage aquí.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable

# Vercel empaqueta esta función junto al repo, pero por si el cwd de ejecución
# no lo incluye en sys.path, se agrega explícitamente antes de importar engine.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.purchase_runs import persist_purchase_run  # noqa: E402
from engine.recommendation import prepare_recommendation  # noqa: E402
from engine.validation import ValidationError  # noqa: E402

REQUIRED_ENV_VARS = ("SUPABASE_DB_URL",)

logger = logging.getLogger("purchase_runs_calculate")
logger.setLevel(logging.INFO)
if not logger.handlers:
    _stderr_handler = logging.StreamHandler()  # va a stderr; Vercel lo captura como log de función
    _stderr_handler.setFormatter(
        logging.Formatter("%(levelname)s purchase_runs_calculate: %(message)s")
    )
    logger.addHandler(_stderr_handler)


def _connection() -> Any:
    """Conexión psycopg de servicio. Se abre aquí, nunca dentro de `engine/`.

    `prepare_threshold=None` desactiva los prepared statements automáticos
    del lado del servidor: `SUPABASE_DB_URL` apunta al connection pooler de
    Supabase en modo "Transaction" (puerto 6543), que puede cambiar la
    conexión física de fondo entre consultas — un prepared statement queda
    atado a una conexión física puntual y una consulta posterior enrutada a
    otra puede chocar con un nombre (`_pg3_0`, ...) ya usado por otra sesión.
    Hallazgo real en producción (`engine.recommendation.prepare_recommendation`
    hace varias consultas distintas en una sola conexión, más superficie que
    `engine.pipeline.run_import_job` para disparar el auto-prepare).
    """
    import psycopg  # import diferido: solo esta función lo necesita

    db_url = os.environ["SUPABASE_DB_URL"]
    return psycopg.connect(db_url, autocommit=False, prepare_threshold=None)


def _process(payload: dict, *, connect: Callable[[], Any] = _connection) -> tuple[int, dict]:
    """Lógica de negocio de `do_POST`, separada de la mecánica HTTP.

    Recibe `connect` inyectable (mismo criterio que `imports_process.py`) para
    poder probar cada camino de error sin depender de psycopg instalado ni de
    un Postgres real.
    """
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        message = f"Faltan variables de entorno: {', '.join(missing)}."
        logger.error(message)
        return 500, {"error": message}

    try:
        supplier_id = payload["supplierId"]
        sales_import_id = payload["salesImportId"]
        price_list_id = payload["priceListId"]
    except KeyError as exc:
        return 400, {"error": f"Falta {exc.args[0]}."}
    inventory_snapshot_id = payload.get("inventorySnapshotId")
    target_days = payload.get("targetDays") or {}
    created_by = payload.get("createdBy")

    try:
        conn = connect()
    except Exception as exc:  # noqa: BLE001 - error de infraestructura, no de negocio
        message = f"No se pudo conectar a la base: {exc}"
        logger.error("%s (supplier_id=%s)", message, supplier_id)
        return 500, {"error": message}

    try:
        prepared = prepare_recommendation(
            conn,
            supplier_id=supplier_id,
            sales_import_id=sales_import_id,
            price_list_id=price_list_id,
            inventory_snapshot_id=inventory_snapshot_id,
            target_days=target_days,
        )
    except ValidationError as exc:
        conn.close()
        logger.warning("cálculo rechazado (supplier_id=%s): %s", supplier_id, exc)
        return 422, {"error": str(exc)}
    except Exception as exc:  # noqa: BLE001 - infraestructura durante el cálculo, no se traga
        conn.close()
        logger.exception("fallo no controlado calculando la recomendación (supplier_id=%s)", supplier_id)
        return 500, {"error": f"No se pudo calcular la recomendación: {exc}"}

    result = persist_purchase_run(
        conn,
        prepared=prepared,
        supplier_id=supplier_id,
        sales_import_id=sales_import_id,
        price_list_id=price_list_id,
        inventory_snapshot_id=inventory_snapshot_id,
        created_by=created_by,
    )
    conn.close()

    if not result.ok:
        logger.error(
            "no se pudo guardar la corrida (supplier_id=%s): %s", supplier_id, result.error_message
        )
        return 500, {"error": result.error_message}

    logger.info(
        "purchase_run_id=%s calculado: %s líneas (%s sin precio).",
        result.purchase_run_id,
        result.lines_inserted,
        result.lines_without_price,
    )
    return 201, {
        "purchaseRunId": str(result.purchase_run_id),
        "status": result.status,
        "lineCount": result.lines_inserted,
        "linesWithoutPrice": result.lines_without_price,
        "errorMessage": None,
    }


class handler(BaseHTTPRequestHandler):  # noqa: N801 - nombre exigido por Vercel
    def do_POST(self) -> None:  # noqa: N802 - firma exigida por BaseHTTPRequestHandler
        secret = os.environ.get("INTERNAL_API_SECRET")
        header_value = self.headers.get("x-internal-secret")
        if not secret or header_value != secret:
            # Mismo criterio de logging que imports_process.py: nunca se
            # loguea `secret` ni `header_value`, solo si cada uno existe.
            logger.warning(
                "401 No autorizado: INTERNAL_API_SECRET configurado=%s, "
                "header x-internal-secret presente=%s",
                bool(secret),
                header_value is not None,
            )
            self._json(401, {"error": "No autorizado."})
            return

        length = int(self.headers.get("content-length", 0) or 0)
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Cuerpo inválido."})
            return

        status, body = _process(payload)
        self._json(status, body)

    def _json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
