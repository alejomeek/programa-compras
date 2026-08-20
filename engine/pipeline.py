"""Punto de entrada único de la importación: de `import_jobs.id` a guardado.

Este módulo es la pieza de integración (propiedad del lead, Fase 2) que ata lo
que ya construyó `import-backend` (:mod:`engine.readers`, :mod:`engine.imports`,
:mod:`engine.persistence`) a un `import_job` concreto: baja el archivo de
Storage, calcula su `sha256` en servidor (contrato §8: "no se confía en el
cliente"), lee y prepara según el tipo, y persiste.

No abre conexiones ni credenciales, igual que el resto de `engine/`: recibe
``conn`` (interfaz DB-API 2.0, la misma que espera
:func:`engine.persistence.persist_import`) y ``storage`` (algo con un método
``download(bucket, object_path) -> bytes``) ya construidos por quien llama —
la ruta de servidor real, o una prueba con dobles en memoria.

Quién invoca esto y cómo (función Python en Vercel, otro servicio) es una
decisión de despliegue todavía abierta (contrato §11); esta función es el
contrato estable que cualquiera de esas rutas puede llamar.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from io import BytesIO
from typing import Any, Protocol

from engine.imports import (
    ImportType,
    prepare_inventory_import,
    prepare_price_list_import,
    prepare_sales_import,
)
from engine.persistence import PersistResult, mark_failed, persist_import, readable_error
from engine.readers import read_inveptos, read_sdos, read_supplier_price_list
from engine.validation import ValidationError

__all__ = ["StorageDownloader", "ImportJobContext", "run_import_job"]


class StorageDownloader(Protocol):
    """Lo único que este módulo necesita de Storage: bajar un objeto.

    La implementación real (fuera de `engine/`) firma la petición con
    `service_role` y hace la llamada HTTP a Supabase Storage. Una prueba pasa
    cualquier objeto con este método devolviendo bytes en memoria.
    """

    def download(self, *, bucket: str, object_path: str) -> bytes: ...


@dataclass(frozen=True)
class ImportJobContext:
    """Lo que hace falta saber de un `import_job` antes de procesarlo."""

    job_id: Any
    job_type: str
    status: str
    supplier_id: Any
    file_id: Any
    bucket: str
    object_path: str
    created_by: Any = None


def run_import_job(
    job_id: Any,
    *,
    conn: Any,
    storage: StorageDownloader,
    effective_date: date | None = None,
) -> PersistResult:
    """Procesa un `import_job` de punta a punta: descarga, lee, prepara, guarda.

    ``effective_date`` es un parámetro de la corrida, no del archivo: quien
    llama lo conoce (formulario de carga), `engine/` no lo adivina.

    Cualquier fallo ANTES de que exista un `PreparedImport` (archivo
    inaccesible, columnas faltantes, período inválido) se traduce aquí a
    `import_jobs.status = 'failed'` vía :func:`engine.persistence.mark_failed`,
    con el mismo criterio de mensaje legible que usa `persist_import` para los
    fallos posteriores. Nunca se relanza silenciosamente: el resultado siempre
    es un :class:`PersistResult`, `ok` o no.
    """
    context = _load_context(conn, job_id)

    try:
        raw = storage.download(bucket=context.bucket, object_path=context.object_path)
        _record_file_metadata(conn, context.file_id, raw)
        prepared = _prepare(conn, context, raw, effective_date=effective_date)
    except Exception as exc:  # noqa: BLE001 - se traduce a `failed`, no se traga
        message = readable_error(exc)
        mark_failed(
            conn,
            import_job_id=context.job_id,
            error_message=message,
            file_id=context.file_id,
            original=exc,
        )
        return PersistResult(
            import_job_id=context.job_id,
            status="failed",
            error_message=message,
            error=exc,
        )

    return persist_import(
        conn,
        import_job_id=context.job_id,
        prepared=prepared,
        file_id=context.file_id,
        supplier_id=context.supplier_id,
        created_by=context.created_by,
    )


def _load_context(conn: Any, job_id: Any) -> ImportJobContext:
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT ij.type, ij.status, ij.supplier_id, ij.file_id, ij.created_by, "
            "f.bucket, f.object_path "
            "FROM import_jobs ij JOIN files f ON f.id = ij.file_id "
            "WHERE ij.id = %s",
            (job_id,),
        )
        row = cursor.fetchone()
    finally:
        closer = getattr(cursor, "close", None)
        if callable(closer):
            closer()

    if row is None:
        raise ValidationError(
            f"No existe la importación {job_id} o no tiene un archivo asociado."
        )
    job_type, status, supplier_id, file_id, created_by, bucket, object_path = row
    return ImportJobContext(
        job_id=job_id,
        job_type=job_type,
        status=status,
        supplier_id=supplier_id,
        file_id=file_id,
        bucket=bucket,
        object_path=object_path,
        created_by=created_by,
    )


def _record_file_metadata(conn: Any, file_id: Any, raw: bytes) -> None:
    """Calcula `sha256`/`size_bytes` EN SERVIDOR y los guarda de una vez.

    Va en su propia transacción, separada de `persist_import`: el archivo se
    descargó y se pudo hashear con éxito independientemente de si el contenido
    luego resulta importable. Perder ese dato porque el parseo falló después
    sería peor que tenerlo aunque el `import_job` termine en `failed`.
    """
    digest = hashlib.sha256(raw).hexdigest()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE files SET sha256 = %s, size_bytes = %s WHERE id = %s",
            (digest, len(raw), file_id),
        )
    finally:
        closer = getattr(cursor, "close", None)
        if callable(closer):
            closer()
    conn.commit()


def _prepare(
    conn: Any,
    context: ImportJobContext,
    raw: bytes,
    *,
    effective_date: date | None,
):
    buffer = BytesIO(raw)

    if context.job_type == ImportType.INVEPTOS_SALES:
        frame = read_inveptos(buffer)
        supplier_tbc_code = (
            _lookup_supplier_tbc_code(conn, context.supplier_id)
            if context.supplier_id
            else None
        )
        return prepare_sales_import(frame, supplier_tbc_code=supplier_tbc_code)

    if context.job_type == ImportType.SDOS_INVENTORY:
        frame = read_sdos(buffer)
        return prepare_inventory_import(frame)

    if context.job_type == ImportType.SUPPLIER_PRICE_LIST:
        if context.supplier_id is None:
            raise ValidationError(
                "Una lista de precios de proveedor necesita supplier_id en el "
                "import_job antes de poder procesarse."
            )
        frame = read_supplier_price_list(buffer)
        return prepare_price_list_import(
            frame, supplier_id=context.supplier_id, effective_date=effective_date
        )

    raise ValidationError(f"Tipo de importación no soportado: '{context.job_type}'.")


def _lookup_supplier_tbc_code(conn: Any, supplier_id: Any) -> str | None:
    """``suppliers.tbc_code`` del proveedor, si la importación de ventas viene
    acotada a uno (caso raro: INVEPTOS casi siempre es global, contrato §9)."""
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT tbc_code FROM suppliers WHERE id = %s", (supplier_id,))
        row = cursor.fetchone()
    finally:
        closer = getattr(cursor, "close", None)
        if callable(closer):
            closer()
    return row[0] if row else None
