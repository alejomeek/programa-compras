"""Pruebas de `api.purchase_runs_calculate._process`/`do_POST` (Fase 3).

Mismo criterio que `test_imports_process.py`: cero red, cero psycopg real,
`FakeConnection` en memoria vía `connect` inyectable. Sirve además como la
verificación manual que pedía el plan antes de tocar Next.js — corriendo acá,
repetible y sin depender de un contenedor levantado a mano.
"""

from __future__ import annotations

import email.message
import io
import logging
from decimal import Decimal
from typing import Any

import pytest

from conftest import FakeConnection

import api.purchase_runs_calculate as calculate

SUPPLIER_ID = "sup-1"
SALES_IMPORT_ID = "sales-1"
PRICE_LIST_ID = "pl-1"
EAN = "7700000000011"
CEDI = "loc-0006"


def _happy_conn() -> FakeConnection:
    return FakeConnection(
        rec_sales_import=("2026-01-01", "2026-01-31", 31),
        rec_supplier_tbc_code="801",
        rec_price_list_supplier_id=SUPPLIER_ID,
        rec_price_list_items=[(EAN, Decimal("100.00"))],
        rec_sales_lines=[(EAN, CEDI, 10)],
    )


def _payload(**overrides: Any) -> dict:
    body = {
        "supplierId": SUPPLIER_ID,
        "salesImportId": SALES_IMPORT_ID,
        "priceListId": PRICE_LIST_ID,
        "targetDays": {"CEDI": 30},
        "createdBy": "user-1",
    }
    body.update(overrides)
    return body


@pytest.fixture(autouse=True)
def _db_url_configurada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPABASE_DB_URL", "postgresql://servicio/db")


def _no_deberia_llamarse() -> Any:
    raise AssertionError("connect() no debería invocarse en este camino")


def test_falta_supabase_db_url_da_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPABASE_DB_URL", raising=False)
    status, body = calculate._process(_payload(), connect=_no_deberia_llamarse)

    assert status == 500
    assert "SUPABASE_DB_URL" in body["error"]


@pytest.mark.parametrize("missing_key", ["supplierId", "salesImportId", "priceListId"])
def test_falta_un_campo_obligatorio_da_400(missing_key: str) -> None:
    payload = _payload()
    del payload[missing_key]

    status, body = calculate._process(payload, connect=_no_deberia_llamarse)

    assert status == 400
    assert body["error"]


def test_fallo_de_conexion_da_500(caplog: pytest.LogCaptureFixture) -> None:
    def connect_roto() -> Any:
        raise RuntimeError("password authentication failed")

    with caplog.at_level(logging.ERROR, logger="purchase_runs_calculate"):
        status, body = calculate._process(_payload(), connect=connect_roto)

    assert status == 500
    assert "No se pudo conectar a la base" in body["error"]
    assert any("password authentication failed" in r.getMessage() for r in caplog.records)


def test_parametros_invalidos_dan_422_sin_dejar_nada_escrito() -> None:
    conn = _happy_conn()
    payload = _payload(priceListId="pl-de-otro-proveedor")
    conn.rec_price_list_supplier_id = "otro-proveedor"

    status, body = calculate._process(payload, connect=lambda: conn)

    assert status == 422
    assert body["error"]
    assert not conn.wrote_to("purchase_runs")


def test_camino_feliz_201_con_conteos_correctos() -> None:
    conn = _happy_conn()

    status, body = calculate._process(_payload(), connect=lambda: conn)

    assert status == 201
    assert body["status"] == "calculated"
    assert body["purchaseRunId"]
    assert body["lineCount"] == 6  # 1 ean elegible x 6 ubicaciones operativas
    assert body["linesWithoutPrice"] == 0
    assert body["errorMessage"] is None
    assert conn.wrote_to("purchase_runs")


def test_fallo_de_persistencia_da_500() -> None:
    conn = _happy_conn()
    conn.fail_on = ("INSERT INTO purchase_run_lines",)

    status, body = calculate._process(_payload(), connect=lambda: conn)

    assert status == 500
    assert body["error"]


# --------------------------------------------------------------------------- #
# handler.do_POST — mismo patrón que test_imports_process.py
# --------------------------------------------------------------------------- #


def _make_handler(*, headers: dict[str, str], body: bytes = b"") -> Any:
    instance = calculate.handler.__new__(calculate.handler)
    message = email.message.Message()
    for name, value in headers.items():
        message[name] = value
    instance.headers = message
    instance.rfile = io.BytesIO(body)
    instance._responses: list[tuple[int, dict]] = []
    instance._json = lambda status, resp_body: instance._responses.append((status, resp_body))
    return instance


def test_do_post_401_sin_secreto_configurado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("INTERNAL_API_SECRET", raising=False)
    instance = _make_handler(headers={"x-internal-secret": "lo-que-sea"})

    instance.do_POST()

    assert instance._responses == [(401, {"error": "No autorizado."})]


def test_do_post_secreto_correcto_llega_a_process(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("INTERNAL_API_SECRET", "el-secreto-real")
    body_bytes = b'{"supplierId":"sup-1"}'
    instance = _make_handler(
        headers={"x-internal-secret": "el-secreto-real", "content-length": str(len(body_bytes))},
        body=body_bytes,
    )
    monkeypatch.setattr(calculate, "_process", lambda payload, **kwargs: (400, {"error": "Falta X."}))

    instance.do_POST()

    assert instance._responses == [(400, {"error": "Falta X."})]
