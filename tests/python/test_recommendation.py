"""Pruebas de `engine.recommendation.prepare_recommendation` (Fase 3).

Cero red, cero Postgres real: `conn` es el mismo `FakeConnection` de
`conftest.py`, extendido con los kwargs `rec_*` — un escenario por prueba,
igual que `job_status`/`max_version` ya hacen para `engine.persistence`.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import pytest

from conftest import FakeConnection

from engine.recommendation import (
    DEFAULT_TARGET_DAYS,
    ENGINE_VERSION,
    prepare_recommendation,
)
from engine.validation import ValidationError

SUPPLIER_ID = "sup-1"
SALES_IMPORT_ID = "sales-1"
PRICE_LIST_ID = "pl-1"
INVENTORY_SNAPSHOT_ID = "inv-1"
EAN = "7700000000011"
CEDI = "loc-0006"
FULLML = "loc-0008"
AV19 = "loc-0001"


def _conn(**kwargs: Any) -> FakeConnection:
    kwargs.setdefault("rec_sales_import", ("2026-01-01", "2026-01-31", 31))
    kwargs.setdefault("rec_supplier_tbc_code", "801")
    kwargs.setdefault("rec_price_list_supplier_id", SUPPLIER_ID)
    return FakeConnection(**kwargs)


def _run(conn: FakeConnection, **overrides: Any) -> Any:
    params = {
        "supplier_id": SUPPLIER_ID,
        "sales_import_id": SALES_IMPORT_ID,
        "price_list_id": PRICE_LIST_ID,
        "inventory_snapshot_id": INVENTORY_SNAPSHOT_ID,
    }
    params.update(overrides)
    return prepare_recommendation(conn, **params)


def _line_for(prepared: Any, ean: str, location_id: str) -> dict[str, Any]:
    matches = [
        line for line in prepared.lines if line["ean"] == ean and line["location_id"] == location_id
    ]
    assert len(matches) == 1, f"esperaba exactamente una línea para {ean}/{location_id}"
    return matches[0]


# --------------------------------------------------------------------------- #
# Ventas = 0
# --------------------------------------------------------------------------- #


def test_sin_ventas_sugerencia_es_0_con_stock() -> None:
    conn = _conn(
        rec_price_list_items=[(EAN, Decimal("12000.00"))],
        rec_inventory_lines=[(EAN, CEDI, 50, "801")],
        rec_sales_lines=[],
    )
    prepared = _run(conn)

    linea = _line_for(prepared, EAN, CEDI)
    assert linea["sales_units"] == 0
    assert linea["suggested_quantity"] == 0
    assert linea["stock_reference"] == 50  # se muestra, pero no cambió la sugerencia


def test_sin_ventas_sugerencia_es_0_sin_stock() -> None:
    conn = _conn(rec_price_list_items=[(EAN, Decimal("12000.00"))], rec_sales_lines=[])
    prepared = _run(conn, inventory_snapshot_id=None)

    linea = _line_for(prepared, EAN, CEDI)
    assert linea["suggested_quantity"] == 0
    assert linea["stock_reference"] is None


# --------------------------------------------------------------------------- #
# Redondeo
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("sales_units", "period_days", "target_days", "expected"),
    [
        (10, 31, 45, 15),  # 10/31*45 = 14.51... -> 15
        (1, 31, 45, 2),  # 1/31*45 = 1.45 -> 2
        (45, 45, 45, 45),  # exacto, sin redondeo hacia arriba de más
        (1, 100, 1, 1),  # 1/100*1 = 0.01 -> 1 (nunca 0 si hubo ventas)
    ],
)
def test_redondeo_hacia_arriba_estricto(
    sales_units: int, period_days: int, target_days: int, expected: int
) -> None:
    conn = _conn(
        rec_sales_import=("2026-01-01", "2026-12-31", period_days),
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, sales_units)],
    )
    prepared = _run(conn, inventory_snapshot_id=None, target_days={"CEDI": target_days})

    assert _line_for(prepared, EAN, CEDI)["suggested_quantity"] == expected


def test_periodo_de_1_dia_no_distorsiona_la_formula() -> None:
    conn = _conn(
        rec_sales_import=("2026-01-01", "2026-01-01", 1),
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, 1)],
    )
    prepared = _run(conn, inventory_snapshot_id=None, target_days={"CEDI": 45})

    assert _line_for(prepared, EAN, CEDI)["suggested_quantity"] == 45


# --------------------------------------------------------------------------- #
# D1: Full Mercado Libre se suma a CEDI
# --------------------------------------------------------------------------- #


def test_full_ml_se_suma_a_cedi_y_no_genera_fila_propia() -> None:
    conn = _conn(
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, 6), (EAN, FULLML, 4)],
    )
    prepared = _run(conn, inventory_snapshot_id=None, target_days={"CEDI": 31})

    linea = _line_for(prepared, EAN, CEDI)
    assert linea["sales_units"] == 10  # 6 (CEDI) + 4 (Full ML)
    assert linea["suggested_quantity"] == 10  # ceil(10/31*31)
    assert not any(line["location_id"] == FULLML for line in prepared.lines)


# --------------------------------------------------------------------------- #
# D2: días objetivo independientes por ubicación
# --------------------------------------------------------------------------- #


def test_dias_objetivo_independientes_por_ubicacion() -> None:
    conn = _conn(
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, 31), (EAN, AV19, 31)],
    )
    prepared = _run(
        conn, inventory_snapshot_id=None, target_days={"CEDI": 10, "AV19": 20}
    )

    assert _line_for(prepared, EAN, CEDI)["suggested_quantity"] == 10
    assert _line_for(prepared, EAN, AV19)["suggested_quantity"] == 20


def test_ubicacion_operativa_sin_target_days_explicito_usa_el_default() -> None:
    conn = _conn(
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, 31)],
    )
    prepared = _run(conn, inventory_snapshot_id=None, target_days={"AV19": 20})

    assert DEFAULT_TARGET_DAYS == 45
    assert _line_for(prepared, EAN, CEDI)["suggested_quantity"] == 45  # ceil(31/31*45)


# --------------------------------------------------------------------------- #
# Reproducibilidad
# --------------------------------------------------------------------------- #


def test_mismos_parametros_dan_el_mismo_params_hash_y_las_mismas_lineas() -> None:
    def build() -> Any:
        conn = _conn(
            rec_price_list_items=[(EAN, Decimal("100.00"))],
            rec_sales_lines=[(EAN, CEDI, 10)],
        )
        return _run(conn, inventory_snapshot_id=None, target_days={"CEDI": 30})

    first, second = build(), build()

    assert first.params_hash == second.params_hash
    assert first.engine_version == ENGINE_VERSION == second.engine_version
    assert [dict(line) for line in first.lines] == [dict(line) for line in second.lines]


def test_params_hash_cambia_si_cambian_los_dias_objetivo() -> None:
    def build(target_days: int) -> Any:
        conn = _conn(
            rec_price_list_items=[(EAN, Decimal("100.00"))],
            rec_sales_lines=[(EAN, CEDI, 10)],
        )
        return _run(conn, inventory_snapshot_id=None, target_days={"CEDI": target_days})

    assert build(30).params_hash != build(45).params_hash


# --------------------------------------------------------------------------- #
# Elegibilidad y precio
# --------------------------------------------------------------------------- #


def test_elegible_por_inventario_sin_precio_vigente_da_status_no_price() -> None:
    conn = _conn(
        rec_inventory_lines=[(EAN, CEDI, 5, "801")],
        rec_price_list_items=[],  # sin precio en la lista elegida
        rec_sales_lines=[(EAN, CEDI, 10)],
    )
    prepared = _run(conn)

    linea = _line_for(prepared, EAN, CEDI)
    assert linea["status"] == "no_price"
    assert linea["suggested_quantity"] == 0  # forzada a 0 aunque hubo ventas
    assert prepared.lines_without_price == len(
        [loc for loc in conn.rec_locations if loc[3]]
    )  # una línea sin precio por cada ubicación operativa


def test_producto_nuevo_solo_en_lista_de_precios_es_elegible() -> None:
    """Sin historia TBC (no aparece en inventory_lines): elegible igual, por
    estar en la lista de precios del proveedor (contrato: agregable a mano)."""
    conn = _conn(
        rec_inventory_lines=[],  # nada de comodín para este EAN
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[],
    )
    prepared = _run(conn)

    assert prepared.eligible_product_count == 1
    assert _line_for(prepared, EAN, CEDI)["status"] == "ok"


def test_inventory_snapshot_none_igual_calcula() -> None:
    conn = _conn(rec_price_list_items=[(EAN, Decimal("100.00"))], rec_sales_lines=[(EAN, CEDI, 5)])
    prepared = _run(conn, inventory_snapshot_id=None, target_days={"CEDI": 10})

    linea = _line_for(prepared, EAN, CEDI)
    assert linea["status"] == "ok"
    assert linea["stock_reference"] is None
    assert linea["suggested_quantity"] == 2  # ceil(5/31*10)


# --------------------------------------------------------------------------- #
# Validaciones
# --------------------------------------------------------------------------- #


def test_ubicacion_desconocida_en_target_days_lanza_error() -> None:
    conn = _conn(rec_price_list_items=[(EAN, Decimal("100.00"))])
    with pytest.raises(ValidationError, match="FERIA"):
        _run(conn, inventory_snapshot_id=None, target_days={"FERIA": 30})


def test_target_days_no_positivo_lanza_error() -> None:
    conn = _conn(rec_price_list_items=[(EAN, Decimal("100.00"))])
    with pytest.raises(ValidationError):
        _run(conn, inventory_snapshot_id=None, target_days={"CEDI": 0})


def test_proveedor_inexistente_lanza_error() -> None:
    conn = _conn(rec_supplier_exists=False)
    with pytest.raises(ValidationError):
        _run(conn)


def test_sales_import_inexistente_lanza_error() -> None:
    conn = _conn(rec_sales_import=None)
    with pytest.raises(ValidationError):
        _run(conn)


def test_price_list_de_otro_proveedor_lanza_error() -> None:
    conn = _conn(rec_price_list_supplier_id="otro-proveedor")
    with pytest.raises(ValidationError):
        _run(conn)


def test_inventory_snapshot_inexistente_lanza_error() -> None:
    conn = _conn(rec_inventory_snapshot_exists=False)
    with pytest.raises(ValidationError):
        _run(conn)


# --------------------------------------------------------------------------- #
# Estructural anti-regresión (contrato §1: nada de redistribución/objetivo de
# inventario/mínimos por quiebre/transferencias en el dominio nuevo). La
# prueba autoritativa (columnas reales de Postgres) vive en
# supabase/tests/sql/80_purchase_runs.sql; esta es el equivalente en memoria.
# --------------------------------------------------------------------------- #

_FORBIDDEN_KEYS = {
    "stockout_minimum",
    "inventory_target",
    "transfer_quantity",
    "redistribution_flag",
    "minimum_quantity",
}

_ALLOWED_LINE_KEYS = {
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
}

_ALLOWED_TARGET_DAYS_KEYS = {"location_id", "target_days"}


def test_no_existen_campos_de_redistribucion() -> None:
    conn = _conn(
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, 10)],
    )
    prepared = _run(conn)

    for line in prepared.lines:
        assert set(line) == _ALLOWED_LINE_KEYS
        assert not (set(line) & _FORBIDDEN_KEYS)
    for row in prepared.target_days:
        assert set(row) == _ALLOWED_TARGET_DAYS_KEYS
