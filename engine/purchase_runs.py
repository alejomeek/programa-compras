"""Persistencia de una corrida de compras calculada (contrato §6.3, §9).

No reutiliza `engine.persistence.ImportTarget`/`persist_import`: esa
maquinaria asume un `import_jobs` preexistente (una corrida no viene de un
archivo subido, no tiene `import_job_id`) y supersesión por período/proveedor
— nada de eso aplica a una corrida calculada, cuyo ciclo de vida posterior
(edición de `final_quantity` vía el RPC `update_final_quantity`) es ajeno al
modelo "importar una sola vez". Sí reutiliza los helpers DB-API genéricos de
`engine.persistence` (mismo criterio "no abrir conexiones ni leer
credenciales" que el resto de `engine/`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from engine.persistence import _close, _placeholders, _rollback, readable_error
from engine.recommendation import PreparedRecommendation

__all__ = ["PurchaseRunPersistResult", "persist_purchase_run"]

_HEADER_COLUMNS: tuple[str, ...] = (
    "supplier_id",
    "sales_import_id",
    "price_list_id",
    "inventory_snapshot_id",
    "period_start",
    "period_end",
    "status",
    "engine_version",
    "params_hash",
    "created_by",
)
_TARGET_DAYS_COLUMNS: tuple[str, ...] = ("purchase_run_id", "location_id", "target_days")
_LINE_COLUMNS: tuple[str, ...] = (
    "purchase_run_id",
    "product_id",
    "ean",
    "location_id",
    "sales_units",
    "period_days",
    "daily_sales",
    "suggested_quantity",
    "final_quantity",
    "stock_reference",
    "unit_cost",
    "status",
)


@dataclass
class PurchaseRunPersistResult:
    """Qué pasó al guardar una corrida calculada. Mismo criterio que
    `engine.persistence.PersistResult`: un fallo previsto no se relanza, se
    refleja en `status='failed'` con `error_message` legible."""

    purchase_run_id: Any
    status: str  # 'calculated' | 'failed'
    lines_inserted: int = 0
    lines_without_price: int = 0
    target_days_inserted: int = 0
    error_message: str | None = None
    error: BaseException | None = field(default=None, repr=False)

    @property
    def ok(self) -> bool:
        return self.status == "calculated"


def persist_purchase_run(
    conn: Any,
    *,
    prepared: PreparedRecommendation,
    supplier_id: Any,
    sales_import_id: Any,
    price_list_id: Any,
    inventory_snapshot_id: Any | None,
    created_by: Any,
) -> PurchaseRunPersistResult:
    """Guarda una corrida completa o no guarda nada.

    Inserta `purchase_runs` (nace `draft`) + `purchase_run_target_days` +
    `purchase_run_lines`, y sube el estado a `calculated` — todo en una sola
    transacción. Cualquier excepción hace `rollback` y el resultado vuelve
    `status='failed'` con un mensaje legible (nunca se relanza silenciosamente,
    el llamador de HTTP decide qué responder, igual que `persist_import`).
    """
    result = PurchaseRunPersistResult(purchase_run_id=None, status="draft")
    try:
        cursor = conn.cursor()
        try:
            header = {
                "supplier_id": supplier_id,
                "sales_import_id": sales_import_id,
                "price_list_id": price_list_id,
                "inventory_snapshot_id": inventory_snapshot_id,
                "period_start": prepared.header["period_start"],
                "period_end": prepared.header["period_end"],
                "status": "draft",
                "engine_version": prepared.engine_version,
                "params_hash": prepared.params_hash,
                "created_by": created_by,
            }
            cursor.execute(
                f"INSERT INTO purchase_runs ({', '.join(_HEADER_COLUMNS)}) "
                f"VALUES ({_placeholders(_HEADER_COLUMNS)}) RETURNING id",
                tuple(header[column] for column in _HEADER_COLUMNS),
            )
            row = cursor.fetchone()
            if row is None:
                raise RuntimeError("La base no devolvió el id de la corrida insertada.")
            result.purchase_run_id = row[0]

            target_days_rows = [
                (result.purchase_run_id, entry["location_id"], entry["target_days"])
                for entry in prepared.target_days
            ]
            if target_days_rows:
                cursor.executemany(
                    f"INSERT INTO purchase_run_target_days "
                    f"({', '.join(_TARGET_DAYS_COLUMNS)}) "
                    f"VALUES ({_placeholders(_TARGET_DAYS_COLUMNS)})",
                    target_days_rows,
                )
            result.target_days_inserted = len(target_days_rows)

            line_rows = [
                tuple(
                    result.purchase_run_id if column == "purchase_run_id" else line.get(column)
                    for column in _LINE_COLUMNS
                )
                for line in prepared.lines
            ]
            if line_rows:
                cursor.executemany(
                    f"INSERT INTO purchase_run_lines ({', '.join(_LINE_COLUMNS)}) "
                    f"VALUES ({_placeholders(_LINE_COLUMNS)})",
                    line_rows,
                )
            result.lines_inserted = len(line_rows)
            result.lines_without_price = prepared.lines_without_price

            cursor.execute(
                "UPDATE purchase_runs SET status = 'calculated', calculated_at = now() "
                "WHERE id = %s",
                (result.purchase_run_id,),
            )
        finally:
            _close(cursor)
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - se traduce a 'failed', no se traga
        _rollback(conn)
        return PurchaseRunPersistResult(
            purchase_run_id=None,
            status="failed",
            error_message=readable_error(exc),
            error=exc,
        )

    result.status = "calculated"
    return result
