"""Pruebas de `engine.pipeline.run_import_job` con dobles en memoria.

Cero conexiones reales, cero credenciales, cero archivos comerciales — mismo
criterio que el resto de `tests/python/` (plan §16.7).
"""

from __future__ import annotations

from typing import Any

import pytest

from conftest import (
    EAN_NORMAL,
    FakeConnection,
    FakeDatabaseError,
    INVEPTOS_HEADER_2_SUCURSALES,
    build_inveptos_xls,
    build_sdos_csv,
    build_supplier_xlsx,
    inveptos_row,
    sdos_row,
)
from engine.imports import ImportType
from engine.pipeline import run_import_job
from engine.validation import ValidationError

FILE_ID = "file-1"
JOB_ID = "job-1"
SUPPLIER_ID = "supplier-1"


class FakeStorage:
    """Doble de Storage: bytes en memoria, sin red ni credenciales."""

    def __init__(self, payload: bytes, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail
        self.calls: list[tuple[str, str]] = []

    def download(self, *, bucket: str, object_path: str) -> bytes:
        self.calls.append((bucket, object_path))
        if self.fail:
            raise FakeDatabaseError(f"objeto no encontrado: {bucket}/{object_path}")
        return self.payload


class PipelineFakeConnection(FakeConnection):
    """Extiende el doble de `import-backend` con las consultas de `pipeline`.

    Solo añade lo que `run_import_job` necesita antes de llegar a
    `persist_import` (que ya sabe manejar todo lo demás); todo lo que no
    reconoce se delega al padre sin duplicar su lógica.
    """

    def __init__(
        self,
        *,
        job_type: str,
        supplier_id: Any = None,
        bucket: str = "source-files",
        object_path: str = "2026/08/uploader/archivo.csv",
        supplier_tbc_code: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(**kwargs)
        self.job_type = job_type
        self.supplier_id = supplier_id
        self.bucket = bucket
        self.object_path = object_path
        self.supplier_tbc_code = supplier_tbc_code

    def _result_for(self, statement: str) -> list[tuple[Any, ...]]:
        if statement.startswith("SELECT ij.type"):
            if self.job_status is None:
                return []
            return [
                (
                    self.job_type,
                    self.job_status,
                    self.supplier_id,
                    FILE_ID,
                    None,
                    self.bucket,
                    self.object_path,
                )
            ]
        if statement.startswith("SELECT tbc_code FROM suppliers"):
            return [] if self.supplier_tbc_code is None else [(self.supplier_tbc_code,)]
        return super()._result_for(statement)


# --------------------------------------------------------------------------- #
# Camino feliz, uno por tipo
# --------------------------------------------------------------------------- #


def test_run_import_job_ventas_completo() -> None:
    payload = build_inveptos_xls(
        INVEPTOS_HEADER_2_SUCURSALES, [inveptos_row()]
    ).getvalue()
    conn = PipelineFakeConnection(job_type=ImportType.INVEPTOS_SALES)
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.ok, result.error_message
    assert storage.calls == [("source-files", "2026/08/uploader/archivo.csv")]
    assert conn.wrote_to("sales_lines")
    assert conn.wrote_to("files")  # backfill de sha256/size_bytes


def test_run_import_job_inventario_completo() -> None:
    payload = build_sdos_csv([sdos_row(us01="4", us02="6")]).getvalue()
    conn = PipelineFakeConnection(job_type=ImportType.SDOS_INVENTORY)
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.ok, result.error_message
    assert conn.wrote_to("inventory_lines")


def test_run_import_job_lista_precios_completo() -> None:
    payload = build_supplier_xlsx(
        ["EAN-13", "Nombre", "Costo proveedor"],
        [(EAN_NORMAL, "Producto Demo", "45900")],
    ).getvalue()
    conn = PipelineFakeConnection(
        job_type=ImportType.SUPPLIER_PRICE_LIST, supplier_id=SUPPLIER_ID
    )
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.ok, result.error_message
    assert conn.wrote_to("price_list_items")


# --------------------------------------------------------------------------- #
# sha256 / size_bytes se calculan en SERVIDOR, siempre, incluso si falla luego
# --------------------------------------------------------------------------- #


def test_sha256_se_calcula_en_servidor_y_no_confia_en_el_cliente() -> None:
    import hashlib

    payload = build_sdos_csv([sdos_row(us01="1")]).getvalue()
    conn = PipelineFakeConnection(job_type=ImportType.SDOS_INVENTORY)
    storage = FakeStorage(payload)

    run_import_job(JOB_ID, conn=conn, storage=storage)

    update = next(
        params for sql, params in conn.committed if sql.startswith("UPDATE files SET sha256")
    )
    assert update[0] == hashlib.sha256(payload).hexdigest()
    assert update[1] == len(payload)


def test_sha256_queda_guardado_aunque_el_parseo_falle_despues() -> None:
    # CSV sin las columnas obligatorias: read_sdos revienta, pero el archivo sí
    # se descargó y se pudo hashear.
    payload = b"columna_random;otra\nvalor;valor\n"
    conn = PipelineFakeConnection(job_type=ImportType.SDOS_INVENTORY)
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.status == "failed"
    assert conn.wrote_to("files")
    assert not conn.wrote_to("inventory_lines")


# --------------------------------------------------------------------------- #
# Fallos antes de que exista un PreparedImport: mark_failed, nunca se traga
# --------------------------------------------------------------------------- #


def test_descarga_fallida_marca_failed_sin_escribir_nada_de_negocio() -> None:
    conn = PipelineFakeConnection(job_type=ImportType.SDOS_INVENTORY)
    storage = FakeStorage(b"", fail=True)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.status == "failed"
    assert "no encontrado" in result.error_message or result.error_message
    assert not conn.wrote_to("files")
    assert not conn.wrote_to("inventory_lines")


def test_lista_de_precios_sin_supplier_id_marca_failed() -> None:
    payload = build_supplier_xlsx(
        ["EAN-13", "Nombre", "Costo proveedor"], [(EAN_NORMAL, "X", "100")]
    ).getvalue()
    conn = PipelineFakeConnection(job_type=ImportType.SUPPLIER_PRICE_LIST, supplier_id=None)
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.status == "failed"
    assert "supplier_id" in result.error_message or "proveedor" in result.error_message


def test_tipo_no_soportado_marca_failed() -> None:
    payload = b"contenido irrelevante"
    conn = PipelineFakeConnection(job_type="tipo_inventado")
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.status == "failed"
    assert "no soportado" in result.error_message


def test_import_job_inexistente_lanza_antes_de_tocar_storage() -> None:
    conn = PipelineFakeConnection(job_type=ImportType.SDOS_INVENTORY, job_status=None)
    storage = FakeStorage(b"no deberia leerse")

    with pytest.raises(ValidationError):
        run_import_job(JOB_ID, conn=conn, storage=storage)

    assert storage.calls == []


# --------------------------------------------------------------------------- #
# Ventas acotadas a un proveedor (caso raro, contrato §9): resuelve tbc_code
# --------------------------------------------------------------------------- #


def test_ventas_con_supplier_id_resuelve_tbc_code_y_no_bloquea() -> None:
    payload = build_inveptos_xls(
        INVEPTOS_HEADER_2_SUCURSALES, [inveptos_row(comodi=".745SINT")]
    ).getvalue()
    conn = PipelineFakeConnection(
        job_type=ImportType.INVEPTOS_SALES,
        supplier_id=SUPPLIER_ID,
        supplier_tbc_code="745",
    )
    storage = FakeStorage(payload)

    result = run_import_job(JOB_ID, conn=conn, storage=storage)

    assert result.ok, result.error_message
