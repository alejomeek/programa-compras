"""Emite una orden de compra y almacena su PDF desde una frontera privada.

La ruta Next.js autentica al usuario y llama esta función con
``X-Internal-Secret``. Aquí se reserva el consecutivo dentro de la misma
transacción que marca la orden emitida; el PDF se construye con el snapshot de
ítems y se sube al bucket privado con la clave de servicio, que nunca sale del
servidor.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import date
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.orders_pdf import build_purchase_order_pdf  # noqa: E402

REQUIRED_ENV_VARS = ("SUPABASE_DB_URL", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY")


def _connection() -> Any:
    import psycopg

    return psycopg.connect(os.environ["SUPABASE_DB_URL"], autocommit=False, prepare_threshold=None)


def _process(payload: dict[str, Any], *, connect: Callable[[], Any] = _connection) -> tuple[int, dict[str, Any]]:
    missing = [name for name in REQUIRED_ENV_VARS if not os.environ.get(name)]
    if missing:
        return 500, {"error": f"Faltan variables de entorno: {', '.join(missing)}."}

    order_id = payload.get("orderId")
    issued_by = payload.get("issuedBy")
    if not order_id or not issued_by:
        return 400, {"error": "Faltan orderId o issuedBy."}

    conn = connect()
    object_path: str | None = None
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                select po.id, po.status, po.supplier_id, po.location_id, po.notes,
                       s.name, l.code, l.name
                from purchase_orders po
                join suppliers s on s.id = po.supplier_id
                join locations l on l.id = po.location_id
                where po.id = %s
                for update
                """,
                (order_id,),
            )
            order = cursor.fetchone()
            if order is None or order[1] != "draft":
                conn.rollback()
                return 422, {"error": "La orden no existe o ya no es un borrador."}

            cursor.execute("select role, active from profiles where id = %s", (issued_by,))
            actor = cursor.fetchone()
            if actor is None or not actor[1] or actor[0] not in ("admin", "buyer"):
                conn.rollback()
                return 403, {"error": "Tu rol no tiene permiso para emitir órdenes."}

            cursor.execute(
                """
                select ean, product_name, quantity, unit_cost
                from purchase_order_items
                where purchase_order_id = %s
                order by created_at, id
                """,
                (order_id,),
            )
            item_rows = cursor.fetchall() or ()
            if not item_rows:
                conn.rollback()
                return 422, {"error": "La orden debe tener al menos una línea antes de emitirse."}

            year = date.today().year
            cursor.execute(
                """
                insert into purchase_order_counters (order_year, last_value)
                values (%s, 1)
                on conflict (order_year) do update
                  set last_value = purchase_order_counters.last_value + 1
                returning last_value
                """,
                (year,),
            )
            serial = cursor.fetchone()[0]
            order_number = f"OC-{year}-{order[6]}-{serial:04d}"
            items = [
                {"ean": row[0], "product_name": row[1], "quantity": row[2], "unit_cost": row[3]}
                for row in item_rows
            ]
            pdf = build_purchase_order_pdf(
                order_number=order_number,
                supplier_name=order[5],
                destination_name=order[7],
                issued_at=date.today(),
                items=items,
                notes=order[4],
            )

            file_id = str(uuid4())
            object_path = f"{order[2]}/{order_id}/{order_number}.pdf"
            _upload_pdf(object_path, pdf)
            cursor.execute(
                """
                insert into files (id, bucket, object_path, original_name, mime_type, size_bytes, sha256, uploaded_by)
                values (%s, 'purchase-order-pdfs', %s, %s, 'application/pdf', %s, %s, %s)
                """,
                (file_id, object_path, f"{order_number}.pdf", len(pdf), hashlib.sha256(pdf).hexdigest(), issued_by),
            )
            # El trigger de auditoría utiliza auth.uid(); se fija dentro de la
            # transacción para que el evento conserve al usuario real, no al
            # rol técnico de la función Python.
            cursor.execute("select set_config('request.jwt.claim.sub', %s, true)", (str(issued_by),))
            cursor.execute(
                """
                update purchase_orders
                set status = 'issued', order_number = %s, issued_at = now(),
                    issued_by = %s, pdf_file_id = %s
                where id = %s and status = 'draft'
                returning order_number, status
                """,
                (order_number, issued_by, file_id, order_id),
            )
            emitted = cursor.fetchone()
            if emitted is None:
                raise RuntimeError("La orden cambió mientras se emitía; no se confirmó la emisión.")
        conn.commit()
        return 201, {"orderNumber": emitted[0], "status": emitted[1]}
    except Exception as exc:  # noqa: BLE001 - respuesta HTTP legible; rollback obligatorio
        conn.rollback()
        if object_path:
            _delete_pdf(object_path)
        return 500, {"error": f"No se pudo emitir la orden: {exc}"}
    finally:
        conn.close()


def _upload_pdf(object_path: str, pdf: bytes) -> None:
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    request = Request(
        f"{base_url}/storage/v1/object/purchase-order-pdfs/{quote(object_path, safe='/')}",
        data=pdf,
        method="POST",
        headers={
            "authorization": f"Bearer {secret}",
            "apikey": secret,
            "content-type": "application/pdf",
            "x-upsert": "false",
        },
    )
    try:
        with urlopen(request, timeout=30):
            pass
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Storage rechazó el PDF ({exc.code}): {detail}") from exc


def _delete_pdf(object_path: str) -> None:
    """Mejor esfuerzo: un error de DB no debe dejar un PDF huérfano."""
    base_url = os.environ["SUPABASE_URL"].rstrip("/")
    secret = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    request = Request(
        f"{base_url}/storage/v1/object/purchase-order-pdfs/{quote(object_path, safe='/')}",
        method="DELETE",
        headers={"authorization": f"Bearer {secret}", "apikey": secret},
    )
    try:
        with urlopen(request, timeout=15):
            pass
    except Exception:  # noqa: BLE001 - el error original es más relevante
        pass


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
        status, body = _process(payload)
        self._json(status, body)

    def _json(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("content-type", "application/json")
        self.send_header("content-length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)
