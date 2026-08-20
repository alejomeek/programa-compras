"""Pruebas de `engine.persistence` — semántica transaccional del contrato §8/§9.

La conexión es un doble DB-API en memoria (``FakeConnection`` en
``conftest.py``): **ninguna prueba se conecta a Postgres ni al proyecto
Supabase del usuario**. El doble distingue lo confirmado (``committed``) de lo
revertido, que es exactamente lo que hay que poder afirmar para la regla
"ningún dato parcial vigente" (§9.3).

Cuando existan las migraciones 0007–0010, esta misma batería debería repetirse
contra un contenedor Postgres efímero para verificar el SQL literal; aquí se
verifica la **lógica** de la transacción.
"""

from __future__ import annotations

from datetime import date

import pytest

from conftest import (
    EAN_NORMAL,
    EAN_OTRO,
    SYNTHETIC_LOCATION_IDS,
    FakeConnection,
    FakeDatabaseError,
    inveptos_frame,
    inveptos_row,
    sdos_frame,
    sdos_row,
    supplier_frame,
)
from engine.imports import (
    prepare_inventory_import,
    prepare_price_list_import,
    prepare_sales_import,
)
from engine.persistence import PersistResult, mark_failed, persist_import
from engine.validation import ImportIssue, IssueCode, IssueSeverity, ValidationError


# --------------------------------------------------------------------------- #
# Ayudas
# --------------------------------------------------------------------------- #


def sales(**kwargs):
    rows = kwargs.pop("rows", [inveptos_row(codean=EAN_NORMAL), inveptos_row(codean=EAN_OTRO)])
    return prepare_sales_import(inveptos_frame(rows), **kwargs)


def inventory(**kwargs):
    rows = kwargs.pop("rows", [sdos_row(us01="4", us02="6")])
    kwargs.setdefault("snapshot_date", date(2025, 2, 1))
    return prepare_inventory_import(sdos_frame(rows), **kwargs)


def price_list(**kwargs):
    rows = kwargs.pop("rows", [(EAN_NORMAL, "Producto", "10.000")])
    kwargs.setdefault("supplier_id", "sup-1")
    kwargs.setdefault("effective_date", date(2026, 1, 1))
    return prepare_price_list_import(supplier_frame(rows), **kwargs)


def only(statements):
    assert len(statements) == 1, statements
    return statements[0]


def index_of(connection, fragment: str) -> int:
    for position, sql in enumerate(connection.committed_sql()):
        if fragment in sql:
            return position
    raise AssertionError(f"no se ejecutó ninguna sentencia con '{fragment}'")


# =========================================================================== #
# Camino feliz
# =========================================================================== #


def test_importacion_de_ventas_se_guarda_completa_en_una_transaccion():
    conn = FakeConnection()

    result = persist_import(
        conn, import_job_id="job-1", prepared=sales(), file_id="file-1", created_by="user-1"
    )

    assert result.ok and result.status == "completed"
    assert result.header_id == "sales_imports-1"
    assert result.lines_inserted == 4
    # Una sola transacción confirmada para todo el trabajo (contrato §9.3).
    assert conn.commits == 1
    assert conn.rollbacks == 0
    assert conn.wrote_to("sales_imports") and conn.wrote_to("sales_lines")


def test_la_cabecera_de_ventas_lleva_las_columnas_exactas_del_contrato():
    conn = FakeConnection()

    persist_import(
        conn,
        import_job_id="job-1",
        prepared=sales(),
        file_id="file-1",
        supplier_id="sup-9",
        created_by="user-1",
    )

    sql, params = only(conn.committed_matching("INSERT INTO sales_imports"))
    assert "(import_job_id, supplier_id, period_start, period_end, status, created_by)" in sql
    assert params == (
        "job-1",
        "sup-9",
        date(2025, 1, 1),
        date(2025, 1, 31),
        "active",
        "user-1",
    )


def test_las_lineas_de_ventas_resuelven_location_id_contra_el_catalogo():
    conn = FakeConnection()

    persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    sql, rows = only(conn.committed_matching("INSERT INTO sales_lines"))
    assert "(sales_import_id, ean, location_id, product_id, units_sold, tbc_cost, source_row_number)" in sql
    assert rows[0][0] == "sales_imports-1"
    assert rows[0][2] == SYNTHETIC_LOCATION_IDS["Av. 19"]
    assert {row[2] for row in rows} == {
        SYNTHETIC_LOCATION_IDS["Av. 19"],
        SYNTHETIC_LOCATION_IDS["Bulevar"],
    }


def test_el_catalogo_de_ubicaciones_se_consulta_una_sola_vez():
    conn = FakeConnection()

    persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    assert len(conn.committed_matching("SELECT id, name FROM locations")) == 1


def test_el_trabajo_queda_completed_con_los_tres_contadores():
    conn = FakeConnection()
    prepared = sales(rows=[inveptos_row(codean=EAN_NORMAL), inveptos_row(codean="MAL")])

    persist_import(conn, import_job_id="job-1", prepared=prepared, file_id="file-1")

    sql, params = only(conn.committed_matching("SET status = 'completed'"))
    assert "rows_total = %s, rows_valid = %s, rows_rejected = %s" in sql
    assert params[:3] == (2, 1, 1)
    # `period_days` es una columna generada: escribirla haría fallar el INSERT.
    assert "period_days" not in sql


def test_el_trabajo_pasa_por_processing_antes_de_escribir():
    conn = FakeConnection()

    persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    assert index_of(conn, "SET status = 'processing'") < index_of(
        conn, "INSERT INTO sales_imports"
    )


def test_las_incidencias_se_guardan_con_el_trabajo_y_el_archivo():
    conn = FakeConnection()
    prepared = sales(rows=[inveptos_row(codean=EAN_NORMAL), inveptos_row(codean="MAL")])

    result = persist_import(
        conn, import_job_id="job-1", prepared=prepared, file_id="file-1"
    )

    assert result.issues_inserted == 1
    sql, rows = only(conn.committed_matching("INSERT INTO import_issues"))
    assert (
        "(import_job_id, file_id, severity, code, source, row_number, ean, sku, "
        "product_name, detail)" in sql
    )
    assert rows[0][0] == "job-1"
    assert rows[0][1] == "file-1"
    assert rows[0][2] == IssueSeverity.ERROR
    assert rows[0][3] == IssueCode.EAN_INVALIDO


def test_importacion_de_inventario_se_guarda_con_su_cabecera():
    conn = FakeConnection()

    result = persist_import(conn, import_job_id="job-2", prepared=inventory(), file_id="file-2")

    assert result.ok
    sql, params = only(conn.committed_matching("INSERT INTO inventory_snapshots"))
    assert "(import_job_id, snapshot_date, status)" in sql
    assert params == ("job-2", date(2025, 2, 1), "active")
    _, rows = only(conn.committed_matching("INSERT INTO inventory_lines"))
    assert rows[0][0] == "inventory_snapshots-1"


def test_una_importacion_sin_lineas_validas_igual_termina_completed():
    conn = FakeConnection()
    prepared = inventory(rows=[sdos_row(codean="", us01="1")])

    result = persist_import(
        conn, import_job_id="job-2", prepared=prepared, file_id="file-2"
    )

    assert result.ok
    assert result.lines_inserted == 0
    assert not conn.wrote_to("inventory_lines")
    assert result.issues_inserted == 1


# =========================================================================== #
# Historial: superseded y versionado (contrato §9.2)
# =========================================================================== #


def test_la_importacion_anterior_del_mismo_periodo_queda_superseded():
    conn = FakeConnection(superseded_id="sales-old")

    result = persist_import(
        conn,
        import_job_id="job-1",
        prepared=sales(),
        file_id="file-1",
        supplier_id="sup-9",
    )

    sql, params = only(conn.committed_matching("SET status = 'superseded'"))
    assert sql.startswith("UPDATE sales_imports SET status = 'superseded'")
    assert "WHERE status = 'active'" in sql
    assert "supplier_id IS NOT DISTINCT FROM %s" in sql
    assert params == ("sup-9", date(2025, 1, 1), date(2025, 1, 31))
    assert result.superseded_id == "sales-old"
    # Antes de insertar la nueva: el índice único parcial no admite dos activas.
    assert index_of(conn, "'superseded'") < index_of(conn, "INSERT INTO sales_imports")


def test_superseder_es_cambio_de_estado_nunca_borrado():
    conn = FakeConnection(superseded_id="sales-old")

    persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    assert not any("DELETE" in sql for sql in conn.committed_sql())


def test_ventas_sin_proveedor_comparan_supplier_id_nulo():
    conn = FakeConnection()

    persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    sql, params = only(conn.committed_matching("SET status = 'superseded'"))
    assert "supplier_id IS NULL" in sql
    assert params == (date(2025, 1, 1), date(2025, 1, 31))


def test_el_snapshot_anterior_de_la_misma_fecha_queda_superseded():
    conn = FakeConnection()

    persist_import(conn, import_job_id="job-2", prepared=inventory(), file_id="file-2")

    sql, params = only(conn.committed_matching("SET status = 'superseded'"))
    assert sql.startswith("UPDATE inventory_snapshots")
    assert params == (date(2025, 2, 1),)


def test_la_lista_de_precios_nace_draft_y_se_activa_despues_de_sus_items():
    conn = FakeConnection()

    result = persist_import(
        conn,
        import_job_id="job-3",
        prepared=price_list(),
        file_id="file-3",
        supplier_id="sup-1",
    )

    assert result.ok
    _, params = only(conn.committed_matching("INSERT INTO price_lists"))
    assert params[5] == "draft"  # status inicial: una lista no-draft es inmutable
    assert index_of(conn, "INSERT INTO price_list_items") < index_of(
        conn, "UPDATE price_lists SET status = 'active'"
    )


def test_la_version_de_la_lista_es_la_siguiente_del_proveedor():
    conn = FakeConnection(max_version=4, superseded_id="pl-old")

    result = persist_import(
        conn,
        import_job_id="job-3",
        prepared=price_list(),
        file_id="file-3",
        supplier_id="sup-1",
    )

    assert result.version == 5
    sql, params = only(conn.committed_matching("SELECT version FROM price_lists"))
    # `FOR UPDATE` no se puede usar con max(): se bloquea la fila más alta.
    assert "ORDER BY version DESC LIMIT 1 FOR UPDATE" in sql
    assert params == ("sup-1",)
    _, header = only(conn.committed_matching("INSERT INTO price_lists"))
    assert header[3] == 5  # version
    assert header[6] == "pl-old"  # supersedes_id


def test_el_primer_proveedor_sin_listas_arranca_en_la_version_1():
    conn = FakeConnection(max_version=None)

    result = persist_import(
        conn,
        import_job_id="job-3",
        prepared=price_list(),
        file_id="file-3",
        supplier_id="sup-1",
    )

    assert result.version == 1
    _, header = only(conn.committed_matching("INSERT INTO price_lists"))
    assert header[6] is None  # supersedes_id


def test_el_raw_del_item_se_serializa_como_jsonb():
    conn = FakeConnection()

    persist_import(
        conn,
        import_job_id="job-3",
        prepared=price_list(),
        file_id="file-3",
        supplier_id="sup-1",
    )

    sql, rows = only(conn.committed_matching("INSERT INTO price_list_items"))
    assert "%s::jsonb" in sql
    assert '"Costo proveedor": "10.000"' in rows[0][-1]


# =========================================================================== #
# Fallos: nada parcial vigente (contrato §9.3)
# =========================================================================== #


def test_un_fallo_al_insertar_lineas_revierte_todo_y_marca_failed():
    conn = FakeConnection(fail_on="INSERT INTO sales_lines")

    result = persist_import(
        conn, import_job_id="job-1", prepared=sales(), file_id="file-1"
    )

    assert result.status == "failed" and not result.ok
    assert isinstance(result.error, FakeDatabaseError)
    assert conn.rollbacks == 1
    # Lo único confirmado es el marcado del fallo: ni cabecera ni líneas.
    assert not conn.wrote_to("sales_imports")
    assert not conn.wrote_to("sales_lines")
    assert conn.committed_matching("SET status = 'failed'")


def test_el_mensaje_de_error_es_legible_y_dice_que_no_quedo_nada_parcial():
    conn = FakeConnection(fail_on="INSERT INTO sales_lines")

    result = persist_import(
        conn, import_job_id="job-1", prepared=sales(), file_id="file-1"
    )

    assert "no quedó ninguna fila parcial" in result.error_message.lower()
    _, params = only(conn.committed_matching("SET status = 'failed'"))
    assert params[0] == result.error_message
    assert params[1] == "job-1"


def test_el_fallo_conserva_las_incidencias_como_diagnostico():
    conn = FakeConnection(fail_on="INSERT INTO sales_lines")
    prepared = sales(rows=[inveptos_row(codean=EAN_NORMAL), inveptos_row(codean="MAL")])

    persist_import(conn, import_job_id="job-1", prepared=prepared, file_id="file-1")

    _, rows = only(conn.committed_matching("INSERT INTO import_issues"))
    assert rows[0][3] == IssueCode.EAN_INVALIDO


def test_una_ubicacion_fuera_del_catalogo_cancela_la_importacion_completa():
    conn = FakeConnection(locations={"Bulevar": "loc-0002"})

    result = persist_import(
        conn, import_job_id="job-1", prepared=sales(), file_id="file-1"
    )

    assert result.status == "failed"
    assert "Av. 19" in result.error_message
    assert conn.rollbacks == 1
    assert not conn.wrote_to("sales_imports")
    assert not conn.wrote_to("sales_lines")


def test_si_el_marcado_de_failed_tambien_falla_se_relanza_el_error_original():
    conn = FakeConnection(
        fail_on=("INSERT INTO sales_lines", "SET status = 'failed'")
    )

    with pytest.raises(FakeDatabaseError) as error:
        persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    assert "sales_lines" in str(error.value)  # el original, no el del marcado
    assert conn.committed == []


def test_mark_failed_registra_un_fallo_previo_al_parseo():
    conn = FakeConnection()
    incidencia = ImportIssue(
        source="INVEPTOS",
        code=IssueCode.FECHA_INVALIDA,
        detail="No se pudo leer el período de ventas.",
    )

    mark_failed(
        conn,
        import_job_id="job-1",
        error_message="No se pudo leer el período de ventas: FDESDE ('xx').",
        issues=[incidencia],
        file_id="file-1",
    )

    assert conn.commits == 1
    _, params = only(conn.committed_matching("SET status = 'failed'"))
    assert params[0].startswith("No se pudo leer el período")
    assert conn.committed_matching("INSERT INTO import_issues")
    assert not conn.wrote_to("sales_imports")


def test_mark_failed_trunca_un_mensaje_desmedido():
    conn = FakeConnection()

    mark_failed(conn, import_job_id="job-1", error_message="x" * 5000)

    _, params = only(conn.committed_matching("SET status = 'failed'"))
    assert len(params[0]) == 2000


# =========================================================================== #
# Un `import_job` terminal no se reutiliza (contrato §8)
# =========================================================================== #


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_un_trabajo_terminal_se_rechaza_sin_escribir_nada(status):
    conn = FakeConnection(job_status=status)

    with pytest.raises(ValidationError, match="importación nueva"):
        persist_import(conn, import_job_id="job-1", prepared=sales(), file_id="file-1")

    assert conn.commits == 0
    assert conn.committed == []


def test_el_reintento_tras_un_fallo_usa_un_import_job_nuevo():
    fallido = FakeConnection(fail_on="INSERT INTO sales_lines")
    primero = persist_import(
        fallido, import_job_id="job-1", prepared=sales(), file_id="file-1"
    )
    assert primero.status == "failed"

    # El mismo trabajo ya no se reprocesa...
    reusado = FakeConnection(job_status="failed")
    with pytest.raises(ValidationError):
        persist_import(reusado, import_job_id="job-1", prepared=sales(), file_id="file-1")

    # ...pero el mismo archivo sí se puede reprocesar con un trabajo nuevo.
    reintento = FakeConnection(job_status="pending")
    segundo = persist_import(
        reintento, import_job_id="job-2", prepared=sales(), file_id="file-1"
    )

    assert segundo.ok
    assert reintento.wrote_to("sales_imports")


def test_un_trabajo_inexistente_se_rechaza_con_mensaje_explicito():
    conn = FakeConnection(job_status=None)

    with pytest.raises(ValidationError, match="No existe la importación"):
        persist_import(conn, import_job_id="job-x", prepared=sales(), file_id="file-1")

    assert conn.committed == []


# =========================================================================== #
# Validación de argumentos
# =========================================================================== #


def test_un_tipo_de_importacion_desconocido_se_rechaza():
    conn = FakeConnection()
    prepared = sales()
    prepared.job_type = "otra_cosa"

    with pytest.raises(ValidationError, match="no soportado"):
        persist_import(conn, import_job_id="job-1", prepared=prepared, file_id="file-1")

    assert conn.committed == []


def test_una_lista_de_precios_sin_proveedor_se_rechaza():
    conn = FakeConnection()

    with pytest.raises(ValidationError, match="supplier_id"):
        persist_import(
            conn, import_job_id="job-3", prepared=price_list(), file_id="file-3"
        )

    assert conn.committed == []


def test_persist_result_expone_ok_solo_si_completed():
    assert PersistResult(import_job_id="x", status="completed").ok
    assert not PersistResult(import_job_id="x", status="failed").ok
