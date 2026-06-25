from procurement_engine import AnalysisConfig, analyze, read_inveptos, read_provider, read_sdos


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
