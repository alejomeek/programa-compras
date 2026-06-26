from io import BytesIO

import pandas as pd

from procurement_engine import (
    AnalysisConfig,
    OPERATIVE_LOCATIONS,
    analyze,
    read_inveptos,
    read_provider,
    read_purchase_orders,
    read_sdos,
    result_to_excel,
)


def test_analysis_with_local_sample_files():
    sdos = read_sdos("SDOSXSUC (7).CSV")
    inveptos = read_inveptos("INVEPTOS.XLS")
    provider = read_provider("LISTA DE PRECIOS JUGANDO Y EDUCANDO.xls")

    result = analyze(
        sdos,
        inveptos,
        provider,
        AnalysisConfig(
            supplier_code="745",
            supplier_name="SPEKTRA",
            fair_mode=False,
            target_days={loc: 45 for loc in ["Av. 19", "Bulevar", "Oviedo", "Bvista", "Calle 74", "CEDI"]},
            stockout_minimums={loc: 1 for loc in ["Av. 19", "Bulevar", "Oviedo", "Bvista", "Calle 74", "CEDI"]},
        ),
    )

    assert not result.summary.empty
    assert "Compra total sugerida" in result.purchase.columns
    assert result.period_days > 0


def test_purchase_order_workbook_round_trip():
    sdos = read_sdos("SDOSXSUC (7).CSV")
    inveptos = read_inveptos("INVEPTOS.XLS")
    provider = read_provider("LISTA DE PRECIOS JUGANDO Y EDUCANDO.xls")
    result = analyze(
        sdos,
        inveptos,
        provider,
        AnalysisConfig(supplier_code="745"),
    )

    assert list(result.purchase_orders.columns) == ["SKU", "EAN", "Producto", *OPERATIVE_LOCATIONS]
    assert (result.purchase_orders[OPERATIVE_LOCATIONS] == "NUEVO").any().any()

    workbook = BytesIO(result_to_excel(result))
    order_sheet = pd.read_excel(workbook, sheet_name="Ordenes de Compra", dtype=str)
    order_sheet.loc[:, OPERATIVE_LOCATIONS] = "0"
    first_new = order_sheet.index[order_sheet["SKU"].fillna("").eq("")][0]
    order_sheet.loc[first_new, "Av. 19"] = "3"

    updated = BytesIO()
    with pd.ExcelWriter(updated, engine="openpyxl") as writer:
        order_sheet.to_excel(writer, sheet_name="Ordenes de Compra", index=False)
        pd.read_excel(workbook, sheet_name="_Datos OC", dtype=str).to_excel(writer, sheet_name="_Datos OC", index=False)

    parsed = read_purchase_orders(BytesIO(updated.getvalue()))
    assert len(parsed) == 1
    assert parsed.iloc[0]["Punto"] == "Av. 19"
    assert parsed.iloc[0]["Cantidad"] == 3
