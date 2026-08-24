"""Empaqueta PDFs de órdenes emitidas desde una frontera privada de Vercel."""

from __future__ import annotations

import io
import json
import os
import re
import sys
import zipfile
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import UUID

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

REQUIRED_ENV_VARS = ("SUPABASE_DB_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")
MAX_ORDERS_PER_ZIP = 50
ORDER_NUMBER_PATTERN = re.compile(r"^OC-(?:[0-9]{4}-)?[A-Z0-9]+-[0-9]+$")


def _connection() -> Any:
    import psycopg

    return psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=False, prepare_threshold=None)


def _validate_order_ids(payload: dict[str, Any]) -> tuple[list[str] | None, str | None]:
    order_ids = payload.get("orderIds")
    if not isinstance(order_ids, list) or not order_ids or len(order_ids) > MAX_ORDERS_PER_ZIP:
        return None, f"Selecciona entre 1 y {MAX_ORDERS_PER_ZIP} órdenes emitidas."
    if not all(isinstance(order_id, str) for order_id in order_ids) or len(set(order_ids)) != len(order_ids):
        return None, "La selección de órdenes no es válida."
    try:
        [UUID(order_id) for order_id in order_ids]
    except ValueError:
        return None, "La selección de órdenes no es válida."
    return order_ids, None


def _download_pdf(object_path: str) -> bytes:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    request = Request(
        f"{base_url}/storage/v1/object/purchase-order-pdfs/{quote(object_path, safe='/')}",
        headers={"authorization": f"Bearer {secret}", "apikey": secret},
    )
    try:
        with urlopen(request, timeout=30) as response:
            return response.read()
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"No se pudo leer un PDF de Storage ({exc.code}): {detail}") from exc


def _zip_pdfs(pdfs: list[tuple[str, bytes]]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for order_number, content in pdfs:
            if not ORDER_NUMBER_PATTERN.fullmatch(order_number):
                raise ValueError("Una orden tiene un consecutivo no válido para el archivo ZIP.")
            archive.writestr(f"ordenes-de-compra/{order_number}.pdf", content)
    return output.getvalue()


def _build_zip(
    payload: dict[str, Any],
    *,
    connect: Callable[[], Any] = _connection,
    download: Callable[[str], bytes] = _download_pdf,
) -> tuple[int, bytes | dict[str, str]]:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        return 500, {"error": f"Faltan variables de entorno: {', '.join(missing)}."}

    order_ids, validation_error = _validate_order_ids(payload)
    if validation_error:
        return 400, {"error": validation_error}
    assert order_ids is not None

    conn = connect()
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                select po.id, po.order_number, f.bucket, f.object_path
                from purchase_orders po
                join files f on f.id = po.pdf_file_id
                where po.id = any(%s) and po.status = 'issued'
                order by po.order_number
                """,
                (order_ids,),
            )
            rows = cursor.fetchall() or ()
        if len(rows) != len(order_ids) or any(row[1] is None or row[2] != "purchase-order-pdfs" for row in rows):
            return 422, {"error": "Todas las órdenes seleccionadas deben seguir emitidas y tener un PDF disponible."}
        pdfs = [(row[1], download(row[3])) for row in rows]
        return 200, _zip_pdfs(pdfs)
    except Exception as exc:  # noqa: BLE001 - frontera HTTP: mensaje legible
        return 500, {"error": f"No se pudo preparar el archivo ZIP: {exc}"}
    finally:
        conn.close()


class handler(BaseHTTPRequestHandler):  # noqa: N801 - requerido por Vercel
    def do_POST(self) -> None:  # noqa: N802
        secret = os.environ.get("INTERNAL_API_SECRET")
        if not secret or self.headers.get("x-internal-secret") != secret:
            self._json(401, {"error": "No autorizado."})
            return
        try:
            payload = json.loads(self.rfile.read(int(self.headers.get("content-length", 0) or 0)) or b"{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "Cuerpo inválido."})
            return
        if not isinstance(payload, dict):
            self._json(400, {"error": "Cuerpo inválido."})
            return
        status, body = _build_zip(payload)
        if isinstance(body, bytes):
            self.send_response(status)
            self.send_header("content-type", "application/zip")
            self.send_header("content-disposition", 'attachment; filename="ordenes-de-compra.zip"')
            self.send_header("content-length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self._json(status, body)

    def _json(self, status: int, body: dict[str, str]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
