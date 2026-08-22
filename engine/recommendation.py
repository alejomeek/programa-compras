"""Cálculo de compra sugerida (contrato §1, §5, §6.3, §9, Fase 3).

A diferencia de `engine.imports` (que prepara un resultado a partir de un
`DataFrame` ya leído de un archivo), aquí el "archivo" de origen ES Postgres:
`sales_lines`/`inventory_lines`/`price_list_items` ya están en la base porque
Fase 2 ya los importó. `prepare_recommendation` recibe una conexión inyectada
(misma interfaz DB-API que `engine.persistence`, sin abrir credenciales) y
hace sus propias consultas `SELECT` — es el primer módulo de `engine/` que lee
de Postgres en vez de un archivo.

Fórmula (cerrada, contrato §1, no admite reinterpretación):

    compra_sugerida = ceil((ventas_históricas / días_del_período) × días_objetivo)

Reglas invariantes:
    - Ventas = 0 en un punto ⇒ sugerencia = 0, sin excepción por inventario.
    - La lista de precios vigente define por sí sola qué EAN son comprables.
      El inventario (`stock_reference`) es solo referencia para esos EAN:
      nunca agrega candidatos, nunca resta, nunca es mínimo y nunca cambia el
      resultado.
    - No existen campos de redistribución, mínimos por quiebre, transferencias
      ni "objetivo de inventario" en este dominio.
    - D1 (Full Mercado Libre): sus ventas se suman a la demanda de CEDI en el
      cálculo, sin reasignar el dato de origen en `sales_lines`.
    - D2 (días objetivo): global por ubicación, editable por corrida; lo que
      se usa realmente se guarda como fotografía (ver `PreparedRecommendation.
      target_days`, destino `purchase_run_target_days`).
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping

from engine.validation import ValidationError

__all__ = [
    "ENGINE_VERSION",
    "DEFAULT_TARGET_DAYS",
    "PreparedRecommendation",
    "prepare_recommendation",
]

#: `purchase_runs.engine_version`, para reproducibilidad (contrato §6.3).
#: 3.0.1 distingue las corridas cuya elegibilidad depende solo de la lista.
ENGINE_VERSION = "3.0.1"

#: D2: default de días objetivo por ubicación operativa cuando la corrida no
#: especifica uno explícito. Heredado de `AnalysisConfig` del MVP viejo.
DEFAULT_TARGET_DAYS = 45


@dataclass
class PreparedRecommendation:
    """Resultado puro del cálculo, listo para que `engine.purchase_runs` lo
    persista. Nada aquí toca la base: son solo estructuras en memoria."""

    engine_version: str
    params_hash: str
    #: `period_start`/`period_end` de `sales_imports`, para la cabecera de
    #: `purchase_runs` (`period_days` es columna generada, no se incluye).
    header: dict[str, Any]
    #: Filas listas para `purchase_run_target_days`: una por ubicación operativa.
    target_days: list[dict[str, Any]]
    #: Filas listas para `purchase_run_lines`: una por EAN elegible x ubicación operativa.
    lines: list[dict[str, Any]]
    eligible_product_count: int
    lines_without_price: int
    warnings: list[str] = field(default_factory=list)


def prepare_recommendation(
    conn: Any,
    *,
    supplier_id: Any,
    sales_import_id: Any,
    price_list_id: Any,
    inventory_snapshot_id: Any | None = None,
    target_days: Mapping[str, int] | None = None,
) -> PreparedRecommendation:
    """Calcula la compra sugerida para un proveedor a partir de fuentes ya
    importadas. Lanza `ValidationError` si alguna fuente no existe, no
    corresponde al proveedor pedido, o `target_days` trae una ubicación
    desconocida o un valor <= 0 — antes de calcular nada.

    `target_days` es `código de ubicación -> días`; una ubicación operativa
    sin entrada explícita usa `DEFAULT_TARGET_DAYS` (D2).
    """
    locations = _load_locations(conn)
    period_start, period_end, period_days = _load_sales_import(conn, sales_import_id)
    # Conserva la validación de existencia del proveedor, aunque su código TBC
    # ya no determina los productos comprables.
    _load_supplier_tbc_code(conn, supplier_id)
    _validate_price_list_supplier(conn, price_list_id, supplier_id)
    if inventory_snapshot_id is not None:
        _require_inventory_snapshot(conn, inventory_snapshot_id)

    operative = [loc for loc in locations.values() if loc["is_purchase_target"]]
    resolved_target_days = _resolve_target_days(operative, target_days)

    price_by_ean = _load_price_list_items(conn, price_list_id)
    # La lista que entregó el proveedor es la fuente de verdad sobre
    # disponibilidad. El comodín TBC del inventario sirve para reconciliación,
    # nunca para agregar productos que el proveedor no incluyó en su lista
    # vigente.
    eligible_eans = set(price_by_ean)

    stock_by_ean_location: dict[tuple[str, Any], int] = {}
    if inventory_snapshot_id is not None:
        stock_by_ean_location = _load_inventory(conn, inventory_snapshot_id)

    location_id_by_code = {loc["code"]: loc["id"] for loc in locations.values()}
    cedi_id = location_id_by_code.get("CEDI")
    fullml_id = location_id_by_code.get("FULLML")
    sales_by_ean_location = _load_and_merge_sales(
        conn, sales_import_id, cedi_id=cedi_id, fullml_id=fullml_id
    )

    product_id_by_ean = _load_product_ids(conn, eligible_eans)

    lines: list[dict[str, Any]] = []
    lines_without_price = 0
    for ean in sorted(eligible_eans):
        unit_cost = price_by_ean.get(ean)
        for loc in operative:
            location_id = loc["id"]
            sales_units = sales_by_ean_location.get((ean, location_id), 0)
            target = resolved_target_days[location_id]
            suggested_quantity = (
                0 if sales_units == 0 else _ceil_div(sales_units * target, period_days)
            )
            daily_sales = (Decimal(sales_units) / Decimal(period_days)).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
            lines.append(
                {
                    "product_id": product_id_by_ean.get(ean),
                    "ean": ean,
                    "location_id": location_id,
                    "sales_units": sales_units,
                    "period_days": period_days,
                    "daily_sales": daily_sales,
                    "suggested_quantity": suggested_quantity,
                    "final_quantity": suggested_quantity,
                    "stock_reference": stock_by_ean_location.get((ean, location_id)),
                    "unit_cost": unit_cost,
                    "status": "ok",
                }
            )

    target_days_rows = [
        {"location_id": loc["id"], "target_days": resolved_target_days[loc["id"]]}
        for loc in operative
    ]

    params_hash = _compute_params_hash(
        supplier_id=supplier_id,
        sales_import_id=sales_import_id,
        price_list_id=price_list_id,
        inventory_snapshot_id=inventory_snapshot_id,
        target_days_by_code={loc["code"]: resolved_target_days[loc["id"]] for loc in operative},
    )

    return PreparedRecommendation(
        engine_version=ENGINE_VERSION,
        params_hash=params_hash,
        header={"period_start": period_start, "period_end": period_end},
        target_days=target_days_rows,
        lines=lines,
        eligible_product_count=len(eligible_eans),
        lines_without_price=lines_without_price,
    )


def _ceil_div(numerator: int, denominator: int) -> int:
    """`ceil(numerator / denominator)` en aritmética entera exacta, sin
    floats: matemáticamente idéntico a `ceil(ventas/período × días)` pero
    reproducible bit a bit."""
    return -(-numerator // denominator)


def _resolve_target_days(
    operative: list[Mapping[str, Any]], target_days: Mapping[str, int] | None
) -> dict[Any, int]:
    provided = dict(target_days or {})
    operative_codes = {loc["code"] for loc in operative}
    unknown = set(provided) - operative_codes
    if unknown:
        raise ValidationError(
            "target_days trae ubicaciones que no son operativas o no existen: "
            f"{', '.join(sorted(unknown))}."
        )
    for code, days in provided.items():
        if days is None or days <= 0:
            raise ValidationError(f"target_days de '{code}' debe ser mayor que 0.")

    resolved: dict[Any, int] = {}
    for loc in operative:
        resolved[loc["id"]] = provided.get(loc["code"], DEFAULT_TARGET_DAYS)
    return resolved


def _compute_params_hash(
    *,
    supplier_id: Any,
    sales_import_id: Any,
    price_list_id: Any,
    inventory_snapshot_id: Any | None,
    target_days_by_code: Mapping[str, int],
) -> str:
    payload = {
        "engine_version": ENGINE_VERSION,
        "supplier_id": str(supplier_id),
        "sales_import_id": str(sales_import_id),
        "price_list_id": str(price_list_id),
        "inventory_snapshot_id": None if inventory_snapshot_id is None else str(inventory_snapshot_id),
        "target_days": sorted(target_days_by_code.items()),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Consultas (todas bulk, sin N+1)
# --------------------------------------------------------------------------- #


def _load_locations(conn: Any) -> dict[Any, dict[str, Any]]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, code, name, is_purchase_target FROM locations WHERE active", ()
        )
        rows = cursor.fetchall() or ()
    finally:
        _close(cursor)
    return {
        row[0]: {"id": row[0], "code": row[1], "name": row[2], "is_purchase_target": bool(row[3])}
        for row in rows
    }


def _load_sales_import(conn: Any, sales_import_id: Any) -> tuple[Any, Any, int]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT period_start, period_end, period_days FROM sales_imports WHERE id = %s",
            (sales_import_id,),
        )
        row = cursor.fetchone()
    finally:
        _close(cursor)
    if row is None:
        raise ValidationError(f"No existe la importación de ventas {sales_import_id}.")
    return row[0], row[1], int(row[2])


def _load_supplier_tbc_code(conn: Any, supplier_id: Any) -> str | None:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tbc_code FROM suppliers WHERE id = %s", (supplier_id,))
        row = cursor.fetchone()
    finally:
        _close(cursor)
    if row is None:
        raise ValidationError(f"No existe el proveedor {supplier_id}.")
    return row[0]


def _validate_price_list_supplier(conn: Any, price_list_id: Any, supplier_id: Any) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT supplier_id FROM price_lists WHERE id = %s", (price_list_id,))
        row = cursor.fetchone()
    finally:
        _close(cursor)
    if row is None:
        raise ValidationError(f"No existe la lista de precios {price_list_id}.")
    # str(...) en ambos lados: psycopg devuelve columnas `uuid` como
    # `uuid.UUID`, pero `supplier_id` llega como texto plano desde el JSON de
    # la petición HTTP (api/purchase_runs_calculate.py) — `UUID(...) != "..."`
    # es SIEMPRE `True` en Python aunque representen el mismo valor
    # (`UUID.__eq__` no sabe comparar contra `str`), así que esta validación
    # rechazaba toda corrida real sin importar que la lista sí perteneciera
    # al proveedor. Bug invisible en `tests/python` porque `FakeConnection`
    # nunca simulaba ese tipo de dato (los fixtures usan `str` de punta a
    # punta) — encontrado en producción, con psycopg real.
    if str(row[0]) != str(supplier_id):
        raise ValidationError(
            f"La lista de precios {price_list_id} no pertenece al proveedor {supplier_id}."
        )


def _require_inventory_snapshot(conn: Any, inventory_snapshot_id: Any) -> None:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT 1 FROM inventory_snapshots WHERE id = %s", (inventory_snapshot_id,)
        )
        row = cursor.fetchone()
    finally:
        _close(cursor)
    if row is None:
        raise ValidationError(f"No existe el inventario de referencia {inventory_snapshot_id}.")


def _load_price_list_items(conn: Any, price_list_id: Any) -> dict[str, Decimal]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ean, supplier_cost FROM price_list_items WHERE price_list_id = %s",
            (price_list_id,),
        )
        rows = cursor.fetchall() or ()
    finally:
        _close(cursor)
    return {row[0]: row[1] for row in rows}


def _load_inventory(conn: Any, inventory_snapshot_id: Any) -> dict[tuple[str, Any], int]:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ean, location_id, on_hand, supplier_tbc_code FROM inventory_lines "
            "WHERE snapshot_id = %s",
            (inventory_snapshot_id,),
        )
        rows = cursor.fetchall() or ()
    finally:
        _close(cursor)

    stock: dict[tuple[str, Any], int] = {}
    for ean, location_id, on_hand, _row_supplier_code in rows:
        stock[(ean, location_id)] = on_hand
    return stock


def _load_and_merge_sales(
    conn: Any, sales_import_id: Any, *, cedi_id: Any, fullml_id: Any
) -> dict[tuple[str, Any], int]:
    """`sales_units` por (ean, ubicación), con Full ML sumado a CEDI (D1) sin
    reasignar el dato crudo en `sales_lines`. Una ubicación que ya no está
    `active` (ej. Feria/Bodega Bqlla, retiradas en Fase 2) no está en el
    catálogo de `_load_locations` y se ignora aquí: son ventas históricas de
    una ubicación que ya no participa en ninguna corrida nueva."""
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ean, location_id, units_sold FROM sales_lines WHERE sales_import_id = %s",
            (sales_import_id,),
        )
        rows = cursor.fetchall() or ()
    finally:
        _close(cursor)

    merged: dict[tuple[str, Any], int] = defaultdict(int)
    for ean, location_id, units_sold in rows:
        target_location_id = cedi_id if location_id == fullml_id else location_id
        merged[(ean, target_location_id)] += units_sold
    return dict(merged)


def _load_product_ids(conn: Any, eans: set[str]) -> dict[str, Any]:
    if not eans:
        return {}
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, ean FROM products WHERE ean = ANY(%s)", (list(eans),)
        )
        rows = cursor.fetchall() or ()
    finally:
        _close(cursor)
    return {ean: product_id for product_id, ean in rows}


def _close(cursor: Any) -> None:
    closer = getattr(cursor, "close", None)
    if callable(closer):
        closer()
