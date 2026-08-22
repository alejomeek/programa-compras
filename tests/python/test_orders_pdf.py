from __future__ import annotations

import pytest

from engine.orders_pdf import build_purchase_order_pdf


def test_pdf_de_orden_tiene_cabecera_pdf_y_contenido() -> None:
    pdf = build_purchase_order_pdf(
        order_number="OC-2026-CEDI-0001",
        supplier_name="Proveedor de prueba",
        destination_name="CEDI",
        issued_at="2026-08-22",
        items=[
            {"ean": "7700000000011", "product_name": "Producto de prueba", "quantity": 3, "unit_cost": 12000},
        ],
    )

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1_000


@pytest.mark.parametrize(
    "item",
    [
        {"ean": "7700000000011", "product_name": "Producto", "quantity": 0, "unit_cost": 12000},
        {"ean": "7700000000011", "product_name": "", "quantity": 1, "unit_cost": 12000},
        {"ean": "7700000000011", "product_name": "Producto", "quantity": 1, "unit_cost": -1},
    ],
)
def test_pdf_rechaza_linea_invalida(item: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        build_purchase_order_pdf(
            order_number="OC-2026-CEDI-0001",
            supplier_name="Proveedor",
            destination_name="CEDI",
            issued_at="2026-08-22",
            items=[item],
        )
