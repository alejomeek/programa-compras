"""Pruebas de `engine.imports` — orquestación de las tres importaciones.

Todas las fixtures son sintéticas y viven en memoria (ver ``conftest.py``):
ninguna prueba abre los archivos comerciales del repositorio ni se conecta a
ninguna base de datos.

Cubre los casos que el contrato exige (§3.2, §3.4, §5.3, plan §8): importación
completa, EAN inválido/duplicado excluido pero registrado, ``Σ UNSUC# ≠
UNIVTA``, período ilegible o invertido que bloquea la importación entera,
``TISUC#`` desconocido, comodín que solo advierte, y las reglas propias de
inventario y lista de precios.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import (
    EAN_CON_CERO_INICIAL,
    EAN_CORTO,
    EAN_NORMAL,
    EAN_OTRO,
    INVEPTOS_HEADER_2_SUCURSALES,
    build_inveptos_xls,
    frame_from_rows,
    inveptos_frame,
    inveptos_row,
    sdos_frame,
    sdos_row,
    supplier_frame,
)
from engine.imports import (
    ImportType,
    prepare_inventory_import,
    prepare_price_list_import,
    prepare_sales_import,
)
from engine.readers import read_inveptos
from engine.validation import (
    InvalidPeriodError,
    IssueCode,
    IssueSeverity,
    ValidationError,
)


def lines_by_location(prepared) -> dict[str, int]:
    return {line["location_name"]: line["units_sold"] for line in prepared.lines}


# =========================================================================== #
# INVEPTOS → sales_imports / sales_lines
# =========================================================================== #


def test_importacion_de_ventas_exitosa_produce_una_linea_por_ubicacion():
    frame = inveptos_frame(
        [
            inveptos_row(codean=EAN_NORMAL, unsuc1="10", unsuc2="5", univta="15"),
            inveptos_row(codean=EAN_OTRO, unsuc1="1", unsuc2="2", univta="3"),
        ]
    )

    prepared = prepare_sales_import(frame)

    assert prepared.job_type == ImportType.INVEPTOS_SALES
    assert prepared.rows_total == 2
    assert prepared.rows_valid == 2
    assert prepared.rows_rejected == 0
    assert prepared.issues == []
    assert len(prepared.lines) == 4
    assert prepared.period_start == date(2025, 1, 1)
    assert prepared.period_end == date(2025, 1, 31)
    assert prepared.header == {
        "period_start": date(2025, 1, 1),
        "period_end": date(2025, 1, 31),
        "status": "active",
    }


def test_las_lineas_de_ventas_traen_las_columnas_exactas_de_sales_lines():
    prepared = prepare_sales_import(inveptos_frame([inveptos_row(valcos="20.000")]))

    primera = prepared.lines[0]
    assert set(primera) == {
        "ean",
        "location_name",
        "product_id",
        "units_sold",
        "tbc_cost",
        "source_row_number",
    }
    assert primera["ean"] == EAN_NORMAL
    assert primera["location_name"] == "Av. 19"
    assert primera["units_sold"] == 10
    assert primera["tbc_cost"] == 20000.0
    assert primera["product_id"] is None
    # Fila 2 del archivo: encabezado en la 1, primera fila de datos en la 2.
    assert primera["source_row_number"] == 2


def test_ean_invalido_se_excluye_pero_queda_registrado():
    frame = inveptos_frame(
        [
            inveptos_row(codean=EAN_NORMAL),
            inveptos_row(codean="ABC123", codpro="SKU-MALO"),
        ]
    )

    prepared = prepare_sales_import(frame)

    assert prepared.rows_valid == 1
    assert prepared.rows_rejected == 1
    assert {line["ean"] for line in prepared.lines} == {EAN_NORMAL}
    incidencia = prepared.issues_by_code(IssueCode.EAN_INVALIDO)[0]
    assert incidencia.severity == IssueSeverity.ERROR
    assert incidencia.ean == "ABC123"
    assert incidencia.sku == "SKU-MALO"
    assert incidencia.row_number == 3


def test_ean_con_espacios_es_invalido_y_no_se_limpia():
    frame = inveptos_frame([inveptos_row(codean=f" {EAN_NORMAL} ")])

    prepared = prepare_sales_import(frame)

    assert prepared.lines == []
    assert prepared.issues_by_code(IssueCode.EAN_INVALIDO)[0].ean == f" {EAN_NORMAL} "


def test_ean_duplicado_excluye_todas_las_copias():
    frame = inveptos_frame(
        [
            inveptos_row(codean=EAN_NORMAL),
            inveptos_row(codean=EAN_NORMAL),
            inveptos_row(codean=EAN_OTRO),
        ]
    )

    prepared = prepare_sales_import(frame)

    assert prepared.rows_valid == 1
    assert prepared.rows_rejected == 2
    assert {line["ean"] for line in prepared.lines} == {EAN_OTRO}
    assert len(prepared.issues_by_code(IssueCode.EAN_DUPLICADO)) == 2


def test_ean_con_cero_inicial_llega_intacto_a_la_linea():
    frame = inveptos_frame([inveptos_row(codean=EAN_CON_CERO_INICIAL)])

    prepared = prepare_sales_import(frame)

    assert {line["ean"] for line in prepared.lines} == {EAN_CON_CERO_INICIAL}


def test_suma_de_unsuc_distinta_de_univta_genera_incidencia_sin_excluir():
    frame = inveptos_frame([inveptos_row(unsuc1="10", unsuc2="5", univta="20")])

    prepared = prepare_sales_import(frame)

    incidencia = prepared.issues_by_code(IssueCode.TOTAL_INCONSISTENTE)[0]
    assert incidencia.severity == IssueSeverity.WARNING
    assert "15" in incidencia.detail and "20" in incidencia.detail
    # La fila se conserva: el dato por ubicación sigue siendo utilizable.
    assert prepared.rows_valid == 1
    assert lines_by_location(prepared) == {"Av. 19": 10, "Bulevar": 5}


def test_suma_consistente_no_genera_incidencia():
    prepared = prepare_sales_import(
        inveptos_frame([inveptos_row(unsuc1="10", unsuc2="5", univta="15")])
    )

    assert prepared.issues_by_code(IssueCode.TOTAL_INCONSISTENTE) == []


def test_la_incidencia_de_total_explica_unsucx_cuando_existe():
    header = INVEPTOS_HEADER_2_SUCURSALES + ("UNSUCX",)
    frame = frame_from_rows(
        header, [inveptos_row(unsuc1="10", unsuc2="5", univta="18") + ("3",)]
    )

    prepared = prepare_sales_import(frame)

    detalle = prepared.issues_by_code(IssueCode.TOTAL_INCONSISTENTE)[0].detail
    assert "UNSUCX" in detalle and "3 unidades" in detalle


def test_fecha_ilegible_bloquea_la_importacion_completa():
    frame = inveptos_frame(
        [
            inveptos_row(fdesde="no-es-fecha", fhasta=""),
            inveptos_row(codean=EAN_OTRO, fdesde="", fhasta=""),
        ]
    )

    with pytest.raises(InvalidPeriodError) as error:
        prepare_sales_import(frame)

    assert "FDESDE" in str(error.value)
    # El contrato §3.2 es explícito: nunca degradar a period_days = 1.
    assert "bloquea" in str(error.value)


def test_fecha_invertida_bloquea_la_importacion_completa():
    frame = inveptos_frame([inveptos_row(fdesde="31-ene-25", fhasta="01-ene-25")])

    with pytest.raises(InvalidPeriodError):
        prepare_sales_import(frame)


def test_fila_con_periodo_discordante_solo_advierte():
    frame = inveptos_frame(
        [
            inveptos_row(codean=EAN_NORMAL),
            inveptos_row(codean=EAN_OTRO, fdesde="01-feb-25", fhasta="28-feb-25"),
        ]
    )

    prepared = prepare_sales_import(frame)

    assert prepared.period_start == date(2025, 1, 1)
    assert prepared.rows_valid == 2
    incidencia = prepared.issues_by_code(IssueCode.FECHA_INVALIDA)[0]
    assert incidencia.severity == IssueSeverity.WARNING
    assert incidencia.row_number == 3


def test_periodo_se_toma_de_la_primera_fila_legible():
    frame = inveptos_frame(
        [
            inveptos_row(codean=EAN_NORMAL, fdesde="", fhasta=""),
            inveptos_row(codean=EAN_OTRO, fdesde="05-mar-25", fhasta="10-mar-25"),
        ]
    )

    prepared = prepare_sales_import(frame)

    assert prepared.period_start == date(2025, 3, 5)
    assert prepared.period_end == date(2025, 3, 10)


def test_tisuc_desconocido_genera_incidencia_y_no_produce_linea():
    frame = inveptos_frame([inveptos_row(tisuc2="99999")])

    prepared = prepare_sales_import(frame)

    assert lines_by_location(prepared) == {"Av. 19": 10}
    assert prepared.issues_by_code(IssueCode.TISUC_DESCONOCIDO)[0].severity == (
        IssueSeverity.WARNING
    )


def test_tisuc_vacio_no_es_incidencia():
    prepared = prepare_sales_import(inveptos_frame([inveptos_row(tisuc2="", unsuc2="0")]))

    assert prepared.issues_by_code(IssueCode.TISUC_DESCONOCIDO) == []
    assert lines_by_location(prepared) == {"Av. 19": 10}


def test_dos_tisuc_a_la_misma_ubicacion_se_suman_en_una_sola_linea():
    """`unique (sales_import_id, ean, location_id)` no admite dos líneas."""
    frame = inveptos_frame([inveptos_row(tisuc1="10000", tisuc2="10000", univta="15")])

    prepared = prepare_sales_import(frame)

    assert len(prepared.lines) == 1
    assert lines_by_location(prepared) == {"Av. 19": 15}


def test_comodin_distinto_al_declarado_solo_advierte():
    frame = inveptos_frame([inveptos_row(comodi=".999OTRO")])

    prepared = prepare_sales_import(frame, supplier_tbc_code="745")

    assert prepared.rows_valid == 1  # en INVEPTOS el comodín no bloquea (§5.3)
    incidencia = prepared.issues_by_code(IssueCode.COMODIN_INVALIDO)[0]
    assert incidencia.severity == IssueSeverity.WARNING
    assert "999" in incidencia.detail and "745" in incidencia.detail


def test_comodin_coincidente_no_genera_incidencia():
    prepared = prepare_sales_import(inveptos_frame(), supplier_tbc_code="745")

    assert prepared.issues_by_code(IssueCode.COMODIN_INVALIDO) == []


def test_costo_tbc_negativo_advierte_y_se_guarda_sin_costo():
    prepared = prepare_sales_import(inveptos_frame([inveptos_row(valcos="-500")]))

    assert prepared.lines[0]["tbc_cost"] is None
    assert prepared.issues_by_code(IssueCode.COSTO_INVALIDO)[0].severity == (
        IssueSeverity.WARNING
    )


def test_archivo_de_ventas_sin_filas_es_error_explicito():
    with pytest.raises(ValidationError, match="no tiene filas"):
        prepare_sales_import(inveptos_frame([]))


def test_archivo_sin_pares_tisuc_registra_columna_faltante():
    header = ("CODPRO", "COMODI", "DETALL", "VALCOS", "UNIVTA", "FDESDE", "FHASTA", "CODEAN")
    frame = frame_from_rows(
        header, [("SKU-1", ".745X", "Producto", "100", "0", "01-ene-25", "31-ene-25", EAN_NORMAL)]
    )

    prepared = prepare_sales_import(frame)

    assert prepared.issues_by_code(IssueCode.COLUMNA_FALTANTE)[0].severity == (
        IssueSeverity.ERROR
    )
    assert prepared.lines == []


def test_cadena_completa_desde_un_xls_legado_sintetico():
    """Integración: archivo `.xls` real → `read_inveptos` → preparado."""
    buffer = build_inveptos_xls(
        INVEPTOS_HEADER_2_SUCURSALES,
        [inveptos_row(codean=EAN_CON_CERO_INICIAL), inveptos_row(codean=EAN_OTRO)],
    )

    prepared = prepare_sales_import(read_inveptos(buffer))

    assert prepared.rows_valid == 2
    assert {line["ean"] for line in prepared.lines} == {
        EAN_CON_CERO_INICIAL,
        EAN_OTRO,
    }
    assert prepared.period_start == date(2025, 1, 1)


# =========================================================================== #
# SDOSXSUC → inventory_snapshots / inventory_lines
# =========================================================================== #


def test_importacion_de_inventario_exitosa():
    frame = sdos_frame(
        [
            sdos_row(codean=EAN_NORMAL, us01="4", us02="6"),
            sdos_row(codean=EAN_OTRO, us01="0", us02="1"),
        ]
    )

    prepared = prepare_inventory_import(frame, snapshot_date=date(2025, 2, 1))

    assert prepared.job_type == ImportType.SDOS_INVENTORY
    assert prepared.header == {
        "snapshot_date": date(2025, 2, 1),
        "status": "active",
    }
    assert prepared.rows_total == 2
    assert prepared.rows_valid == 2
    assert len(prepared.lines) == 4
    assert prepared.issues == []


def test_las_lineas_de_inventario_traen_las_columnas_exactas():
    prepared = prepare_inventory_import(sdos_frame())

    primera = prepared.lines[0]
    assert set(primera) == {
        "ean",
        "tbc_sku",
        "location_name",
        "on_hand",
        "pvp",
        "supplier_tbc_code",
    }
    assert primera["location_name"] == "Av. 19"
    assert primera["on_hand"] == 4
    assert primera["tbc_sku"] == "SKU-001"
    assert primera["supplier_tbc_code"] == "745"
    # "$ 45.900,00": el punto agrupa miles, no es decimal.
    assert primera["pvp"] == 45900.0


def test_snapshot_date_por_defecto_es_hoy():
    prepared = prepare_inventory_import(sdos_frame())

    assert prepared.header["snapshot_date"] == date.today()


def test_columna_us09_retirada_no_genera_linea_de_bodega_bqlla():
    """Bodega Bqlla se retiró del modelo (contrato §2): ``us09`` presente en
    el archivo ya no produce ninguna línea, igual que cualquier otra columna
    fuera del mapeo vigente."""
    columns = ("Codpro", "Nompro", "Valuni", "Codean", "Codea2", "us05", "us09")
    rows = [sdos_row(us05="7", us09="9")]

    prepared = prepare_inventory_import(sdos_frame(rows, columns=columns))

    assert {line["location_name"] for line in prepared.lines} == {"Oviedo"}


def test_columna_us_ausente_no_es_error_solo_no_genera_linea():
    columns = ("Codpro", "Nompro", "Valuni", "Codean", "Codea2", "us01")
    prepared = prepare_inventory_import(sdos_frame([sdos_row(us01="3")], columns=columns))

    assert {line["location_name"] for line in prepared.lines} == {"Av. 19"}
    assert prepared.issues == []


def test_archivo_sin_ninguna_columna_us_registra_columna_faltante():
    columns = ("Codpro", "Nompro", "Valuni", "Codean", "Codea2")
    prepared = prepare_inventory_import(sdos_frame([sdos_row()], columns=columns))

    assert prepared.issues_by_code(IssueCode.COLUMNA_FALTANTE)[0].severity == (
        IssueSeverity.ERROR
    )
    assert prepared.lines == []


def test_inventario_negativo_excluye_la_linea_con_incidencia():
    prepared = prepare_inventory_import(sdos_frame([sdos_row(us01="-5", us02="6")]))

    # No se recorta a 0: inventar un dato es peor que no tenerlo.
    assert lines_by_location_inventory(prepared) == {"Bulevar": 6}
    incidencia = prepared.issues_by_code(IssueCode.CANTIDAD_INVALIDA)[0]
    assert incidencia.severity == IssueSeverity.WARNING
    assert "Av. 19" in incidencia.detail


def lines_by_location_inventory(prepared) -> dict[str, int]:
    return {line["location_name"]: line["on_hand"] for line in prepared.lines}


def test_pvp_negativo_advierte_y_guarda_sin_precio():
    prepared = prepare_inventory_import(sdos_frame([sdos_row(valuni="-1.000", us01="2")]))

    assert prepared.lines[0]["pvp"] is None
    assert prepared.issues_by_code(IssueCode.COSTO_INVALIDO)[0].severity == (
        IssueSeverity.WARNING
    )


def test_inventario_con_ean_invalido_o_duplicado_se_excluye():
    frame = sdos_frame(
        [
            sdos_row(codean=EAN_NORMAL, us01="1"),
            sdos_row(codean=EAN_NORMAL, us01="2"),
            sdos_row(codean="", us01="3"),
            sdos_row(codean=EAN_CORTO, us01="4"),
        ]
    )

    prepared = prepare_inventory_import(frame)

    assert prepared.rows_valid == 1
    assert prepared.rows_rejected == 3
    assert {line["ean"] for line in prepared.lines} == {EAN_CORTO}
    assert len(prepared.issues_by_code(IssueCode.EAN_DUPLICADO)) == 2
    assert len(prepared.issues_by_code(IssueCode.EAN_INVALIDO)) == 1


def test_codea2_sin_comodin_deja_el_proveedor_en_nulo():
    prepared = prepare_inventory_import(sdos_frame([sdos_row(codea2="SIN-COMODIN")]))

    assert prepared.lines[0]["supplier_tbc_code"] is None


# =========================================================================== #
# Lista de proveedor → price_lists / price_list_items
# =========================================================================== #


def test_importacion_de_lista_de_precios_exitosa():
    frame = supplier_frame(
        [
            (EAN_NORMAL, "Rompecabezas Sintético", "45.900"),
            (EAN_OTRO, "Bloques Sintéticos", "$ 12.500,50"),
        ]
    )

    prepared = prepare_price_list_import(
        frame, supplier_id="sup-1", effective_date=date(2026, 1, 1)
    )

    assert prepared.job_type == ImportType.SUPPLIER_PRICE_LIST
    assert prepared.header == {"supplier_id": "sup-1", "effective_date": date(2026, 1, 1)}
    assert prepared.rows_valid == 2
    assert [line["supplier_cost"] for line in prepared.lines] == [45900.0, 12500.5]
    assert prepared.issues == []


def test_las_lineas_de_lista_traen_las_columnas_exactas_y_el_raw():
    prepared = prepare_price_list_import(supplier_frame(), supplier_id="sup-1")

    primera = prepared.lines[0]
    assert set(primera) == {
        "ean",
        "supplier_product_id",
        "supplier_cost",
        "source_row_number",
        "raw",
    }
    assert primera["supplier_product_id"] is None
    assert primera["raw"]["Costo proveedor"] == "45.900"


def test_costo_ilegible_excluye_la_fila_con_incidencia_de_error():
    frame = supplier_frame(
        [
            (EAN_NORMAL, "Bueno", "10.000"),
            (EAN_OTRO, "Sin precio", "consultar"),
        ]
    )

    prepared = prepare_price_list_import(frame, supplier_id="sup-1")

    assert prepared.rows_valid == 1
    assert prepared.rows_rejected == 1
    incidencia = prepared.issues_by_code(IssueCode.COSTO_INVALIDO)[0]
    assert incidencia.severity == IssueSeverity.ERROR
    assert incidencia.ean == EAN_OTRO


def test_costo_negativo_excluye_la_fila():
    frame = supplier_frame([(EAN_NORMAL, "Negativo", "-3.000")])

    prepared = prepare_price_list_import(frame, supplier_id="sup-1")

    assert prepared.lines == []
    assert prepared.rows_rejected == 1
    assert "negativo" in prepared.issues_by_code(IssueCode.COSTO_INVALIDO)[0].detail


def test_costo_cero_es_valido():
    prepared = prepare_price_list_import(
        supplier_frame([(EAN_NORMAL, "Promoción", "0")]), supplier_id="sup-1"
    )

    assert prepared.lines[0]["supplier_cost"] == 0.0
    assert prepared.issues == []


def test_lista_con_ean_duplicado_excluye_todas_las_copias():
    frame = supplier_frame(
        [
            (EAN_NORMAL, "Uno", "10.000"),
            (EAN_NORMAL, "Otro precio", "11.000"),
            (EAN_OTRO, "Distinto", "12.000"),
        ]
    )

    prepared = prepare_price_list_import(frame, supplier_id="sup-1")

    assert {line["ean"] for line in prepared.lines} == {EAN_OTRO}
    assert len(prepared.issues_by_code(IssueCode.EAN_DUPLICADO)) == 2


def test_effective_date_por_defecto_es_hoy():
    prepared = prepare_price_list_import(supplier_frame(), supplier_id="sup-1")

    assert prepared.header["effective_date"] == date.today()


# =========================================================================== #
# Contrato con la migración de `import_issues`
# =========================================================================== #


def test_el_motor_emite_exactamente_estos_codigos_de_incidencia():
    """Referencia explícita para `import_issues.code` (migración 0007).

    El contrato §6.3 enumera seis códigos; el motor emite tres más, aparecidos
    al portar (`columna_faltante`, `total_inconsistente`) y al orquestar la
    importación de inventario (`cantidad_invalida`). Si la migración los
    restringe con un `check`/enum, tiene que incluir los nueve.
    """
    definidos = {
        value
        for name, value in vars(IssueCode).items()
        if not name.startswith("_") and isinstance(value, str)
    }

    assert definidos == {
        "ean_invalido",
        "ean_duplicado",
        "costo_invalido",
        "comodin_invalido",
        "fecha_invalida",
        "tisuc_desconocido",
        "columna_faltante",
        "total_inconsistente",
        "cantidad_invalida",
    }
