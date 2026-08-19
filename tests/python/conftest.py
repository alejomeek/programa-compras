"""Constructores de fixtures **sintéticas** para las pruebas del motor.

Regla del plan §16.7, sin excepciones: ninguna prueba lee los archivos
comerciales de la raíz del repositorio (`SDOSXSUC (7).CSV`, `INVEPTOS.XLS`,
`LISTA DE PRECIOS ...xls`). Todo archivo de prueba se construye en memoria
(`BytesIO`) con EAN, nombres y proveedores inventados.
"""

from __future__ import annotations

import sys
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd
import pytest

# Permite `import engine...` ejecutando pytest desde la raíz del repositorio.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# --------------------------------------------------------------------------- #
# EAN sintéticos (inventados; no corresponden a ningún producto real)
# --------------------------------------------------------------------------- #

EAN_CON_CERO_INICIAL = "0012345678905"
EAN_NORMAL = "7701234567890"
EAN_CORTO = "12345"
EAN_OTRO = "7709876543210"


# --------------------------------------------------------------------------- #
# SDOSXSUC (CSV Latin-1, separado por ';')
# --------------------------------------------------------------------------- #


def build_sdos_csv(
    rows: Sequence[dict[str, Any]],
    *,
    columns: Sequence[str] | None = None,
    encoding: str = "latin1",
) -> BytesIO:
    """Arma un CSV tipo SDOSXSUC en memoria.

    ``columns`` permite omitir columnas a propósito (por ejemplo, un archivo
    sin ``us06``) para probar el manejo de columnas faltantes.
    """
    frame = pd.DataFrame(list(rows))
    if columns is not None:
        frame = frame.reindex(columns=list(columns), fill_value="")
    text = frame.to_csv(index=False, sep=";")
    return BytesIO(text.encode(encoding))


def sdos_row(
    *,
    codpro: str = "SKU-001",
    nompro: str = "Rompecabezas Sintético",
    valuni: str = "$ 45.900,00",
    codean: str = EAN_NORMAL,
    codea2: str = ".745SINT",
    **inventory: Any,
) -> dict[str, Any]:
    """Una fila de SDOSXSUC con valores sintéticos por defecto."""
    row: dict[str, Any] = {
        "Codpro": codpro,
        "Nompro": nompro,
        "Valuni": valuni,
        "Codean": codean,
        "Codea2": codea2,
    }
    row.update({key: str(value) for key, value in inventory.items()})
    return row


# --------------------------------------------------------------------------- #
# INVEPTOS (.xls legado BIFF, escrito con xlwt)
# --------------------------------------------------------------------------- #

def _require_xlwt():
    """Devuelve el módulo ``xlwt`` o salta la prueba si no está instalado.

    ``xlwt`` es dependencia **solo de pruebas**: es la única forma de generar
    un ``.xls`` legado real (pandas 2.x ya no escribe ese formato) y así
    ejercitar el mismo camino ``xlrd`` que usa producción.
    """
    return pytest.importorskip(
        "xlwt",
        reason="xlwt es necesario para generar .xls legado sintético",
        exc_type=ImportError,
    )


def build_inveptos_xls(
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    encoding: str = "cp1252",
    sheet_name: str = "INVEPTOS",
) -> BytesIO:
    """Arma un ``.xls`` BIFF en memoria con el encabezado y filas dados."""
    xlwt_mod = _require_xlwt()
    workbook = xlwt_mod.Workbook(encoding=encoding)
    sheet = workbook.add_sheet(sheet_name)
    for col, title in enumerate(header):
        sheet.write(0, col, title)
    for row_index, row in enumerate(rows, start=1):
        for col, value in enumerate(row):
            sheet.write(row_index, col, value)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer


#: Encabezado mínimo de INVEPTOS con dos pares TISUC/UNSUC.
INVEPTOS_HEADER_2_SUCURSALES: tuple[str, ...] = (
    "CODPRO",
    "COMODI",
    "DETALL",
    "VALCOS",
    "TISUC1",
    "UNSUC1",
    "SDSUC1",
    "TISUC2",
    "UNSUC2",
    "SDSUC2",
    "UNIVTA",
    "FDESDE",
    "FHASTA",
    "CODEAN",
)


def inveptos_row(
    *,
    codpro: str = "SKU-001",
    comodi: str = ".745SINT",
    detall: str = "Rompecabezas Sintético",
    valcos: str = "20000",
    tisuc1: str = "10000",
    unsuc1: str = "10",
    sdsuc1: str = "3",
    tisuc2: str = "10010",
    unsuc2: str = "5",
    sdsuc2: str = "1",
    univta: str = "15",
    fdesde: str = "01-ene-25",
    fhasta: str = "31-ene-25",
    codean: str = EAN_NORMAL,
) -> tuple[Any, ...]:
    """Una fila alineada a :data:`INVEPTOS_HEADER_2_SUCURSALES`."""
    return (
        codpro,
        comodi,
        detall,
        valcos,
        tisuc1,
        unsuc1,
        sdsuc1,
        tisuc2,
        unsuc2,
        sdsuc2,
        univta,
        fdesde,
        fhasta,
        codean,
    )


# --------------------------------------------------------------------------- #
# Lista de precios de proveedor (.xlsx, encabezado posiblemente desplazado)
# --------------------------------------------------------------------------- #


def build_supplier_xlsx(
    header: Sequence[str],
    rows: Iterable[Sequence[Any]],
    *,
    header_row: int = 0,
    preamble: Sequence[Sequence[Any]] | None = None,
) -> BytesIO:
    """Arma un ``.xlsx`` de lista de precios con el encabezado desplazado.

    ``header_row`` es el índice 0-based de la fila donde va el encabezado; las
    filas anteriores se llenan con ``preamble`` (o quedan vacías), simulando
    los logos y títulos que traen las listas reales.
    """
    from openpyxl import Workbook

    workbook = Workbook()
    sheet = workbook.active
    filler = list(preamble or [])
    for index in range(header_row):
        values = filler[index] if index < len(filler) else []
        for col, value in enumerate(values, start=1):
            sheet.cell(row=index + 1, column=col, value=value)
    for col, title in enumerate(header, start=1):
        sheet.cell(row=header_row + 1, column=col, value=title)
    for row_index, row in enumerate(rows, start=header_row + 2):
        for col, value in enumerate(row, start=1):
            sheet.cell(row=row_index, column=col, value=value)
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    return buffer
