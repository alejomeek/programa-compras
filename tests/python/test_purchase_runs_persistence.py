"""Pruebas de `engine.purchase_runs.persist_purchase_run` (Fase 3).

Mismo criterio que `test_persistence.py`: cero red, cero Postgres real,
`FakeConnection` en memoria. `prepare_recommendation` y `persist_purchase_run`
comparten la misma conexión falsa, igual que lo harían en
`api/purchase_runs_calculate.py` contra una conexión real.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from conftest import FakeConnection

from engine.purchase_runs import persist_purchase_run
from engine.recommendation import prepare_recommendation

SUPPLIER_ID = "sup-1"
SALES_IMPORT_ID = "sales-1"
PRICE_LIST_ID = "pl-1"
CREATED_BY = "user-1"
EAN = "7700000000011"
CEDI = "loc-0006"


def _conn(**kwargs: Any) -> FakeConnection:
    kwargs.setdefault("rec_sales_import", ("2026-01-01", "2026-01-31", 31))
    kwargs.setdefault("rec_supplier_tbc_code", "801")
    kwargs.setdefault("rec_price_list_supplier_id", SUPPLIER_ID)
    kwargs.setdefault("rec_price_list_items", [(EAN, Decimal("100.00"))])
    kwargs.setdefault("rec_sales_lines", [(EAN, CEDI, 10)])
    return FakeConnection(**kwargs)


def _persist(conn: FakeConnection, *, inventory_snapshot_id: Any = None):
    prepared = prepare_recommendation(
        conn,
        supplier_id=SUPPLIER_ID,
        sales_import_id=SALES_IMPORT_ID,
        price_list_id=PRICE_LIST_ID,
        inventory_snapshot_id=inventory_snapshot_id,
        target_days={"CEDI": 30},
    )
    return persist_purchase_run(
        conn,
        prepared=prepared,
        supplier_id=SUPPLIER_ID,
        sales_import_id=SALES_IMPORT_ID,
        price_list_id=PRICE_LIST_ID,
        inventory_snapshot_id=inventory_snapshot_id,
        created_by=CREATED_BY,
    ), prepared


def test_corrida_se_guarda_completa_y_queda_calculated() -> None:
    conn = _conn()
    result, prepared = _persist(conn)

    assert result.ok
    assert result.status == "calculated"
    assert result.purchase_run_id is not None
    assert result.target_days_inserted == len(prepared.target_days)
    assert result.lines_inserted == len(prepared.lines)
    assert conn.wrote_to("purchase_runs")
    assert conn.wrote_to("purchase_run_target_days")
    assert conn.wrote_to("purchase_run_lines")
    assert any(
        sql.startswith("UPDATE purchase_runs SET status = 'calculated'")
        for sql in conn.committed_sql()
    )


def test_todo_o_nada_si_falla_a_mitad_de_camino() -> None:
    conn = _conn(fail_on="INSERT INTO purchase_run_lines")
    result, _ = _persist(conn)

    assert not result.ok
    assert result.status == "failed"
    assert result.purchase_run_id is None
    assert result.error_message
    # nada quedó confirmado: ni la cabecera que sí se había insertado en la
    # transacción abortada.
    assert not conn.wrote_to("purchase_runs")
    assert not conn.wrote_to("purchase_run_target_days")
    assert not conn.wrote_to("purchase_run_lines")
    assert conn.rollbacks >= 1


def test_inventario_sin_producto_en_lista_persiste_corrida_sin_lineas() -> None:
    # El comodín del inventario no habilita compras: si el proveedor no incluyó
    # el EAN en su lista vigente, no se genera ni persiste una línea.
    conn = _conn(
        rec_price_list_items=[],
        rec_inventory_lines=[(EAN, CEDI, 5, "801")],
    )
    result, prepared = _persist(conn, inventory_snapshot_id="inv-1")

    assert result.ok
    assert prepared.lines == []
    assert prepared.lines_without_price == 0
    assert result.lines_without_price == 0
    assert result.lines_inserted == 0
