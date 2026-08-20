"""Orquestación de las tres importaciones: leído → validado → listo para persistir.

Este módulo es la capa que va **entre** :mod:`engine.readers` (que solo lee y
normaliza la forma del archivo) y :mod:`engine.persistence` (que solo escribe en
base de datos). Aquí no se abre ningún archivo ni ninguna conexión: se recibe un
``DataFrame`` ya leído y se devuelve un :class:`PreparedImport` con las filas
mapeadas a las **columnas exactas** de las tablas del contrato §6.3 y la lista
de incidencias (`import_issues`).

Reglas de exclusión (contrato §3.4, §5.3, plan §8), unificadas para las tres
fuentes:

- EAN inválido ⇒ incidencia ``ean_invalido`` (ERROR) y la fila se excluye.
- EAN duplicado ⇒ incidencia ``ean_duplicado`` (ERROR) y se excluyen **todas**
  sus copias, no solo la segunda.
- Un problema que no invalida la fila (comodín que no coincide, ``TISUC#``
  desconocido, ``Σ UNSUC# ≠ UNIVTA``) genera incidencia WARNING y **no** excluye.

Lo único que bloquea la importación completa es el período ilegible o invertido
de INVEPTOS: :func:`engine.validation.period_days` lanza ``InvalidPeriodError``
y aquí se deja propagar a propósito (contrato §3.2: nunca degradar a
``period_days = 1``). Una fila suelta con período distinto del de la
importación **no** bloquea: es incidencia ``fecha_invalida`` (WARNING) y se usa
el período de la primera fila legible.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Sequence

import pandas as pd

from engine.readers import (
    SOURCE_INVEPTOS,
    SOURCE_SDOS,
    SOURCE_SUPPLIER,
    discover_tisuc_suffixes,
    location_for_tisuc,
    sdos_inventory_columns,
)
from engine.validation import (
    ImportIssue,
    InvalidPeriodError,
    IssueCode,
    IssueCollector,
    IssueSeverity,
    ValidationError,
    describe_ean_problem,
    extract_supplier_code,
    find_duplicate_eans,
    parse_tbc_date,
    period_days,
    to_int,
    to_number,
)

__all__ = [
    "ImportType",
    "PreparedImport",
    "prepare_sales_import",
    "prepare_inventory_import",
    "prepare_price_list_import",
]


class ImportType:
    """Valores exactos de ``import_jobs.type`` (contrato §6.3)."""

    SDOS_INVENTORY = "sdos_inventory"
    INVEPTOS_SALES = "inveptos_sales"
    SUPPLIER_PRICE_LIST = "supplier_price_list"


#: Primera fila de datos de un archivo con encabezado en la fila 1. Se usa para
#: que ``source_row_number`` coincida con lo que el usuario ve en Excel.
FIRST_DATA_ROW = 2


@dataclass
class PreparedImport:
    """Resultado de preparar una importación: cabecera + líneas + incidencias.

    Es una estructura **pura**: no toca base de datos y no conoce ids. Las
    claves de ``header`` y de cada elemento de ``lines`` son los nombres de
    columna del contrato §6.3, salvo dos excepciones deliberadas que resuelve
    :mod:`engine.persistence` porque requieren consultar la base:

    - ``location_name`` en las líneas → ``location_id`` (uuid de `locations`).
    - los ids de cabecera (``sales_import_id`` / ``snapshot_id`` /
      ``price_list_id``), que solo existen después del ``INSERT``.

    Los contadores son de **filas de origen**, no de líneas generadas: una fila
    de INVEPTOS válida produce tantas líneas como ubicaciones reporte, y sigue
    contando como una sola fila válida (es lo que espera
    ``import_jobs.rows_total/rows_valid/rows_rejected``, §6.3).
    """

    job_type: str
    source: str
    header: dict[str, Any]
    lines: list[dict[str, Any]] = field(default_factory=list)
    issues: list[ImportIssue] = field(default_factory=list)
    rows_total: int = 0
    rows_valid: int = 0
    rows_rejected: int = 0
    period_start: date | None = None
    period_end: date | None = None

    @property
    def counters(self) -> dict[str, int]:
        """Los tres contadores tal como van a `import_jobs`."""
        return {
            "rows_total": self.rows_total,
            "rows_valid": self.rows_valid,
            "rows_rejected": self.rows_rejected,
        }

    @property
    def issue_records(self) -> list[dict[str, Any]]:
        """Incidencias como filas listas para `import_issues`."""
        return [issue.as_dict() for issue in self.issues]

    def issues_by_code(self, code: str) -> list[ImportIssue]:
        return [issue for issue in self.issues if issue.code == code]


# --------------------------------------------------------------------------- #
# Acceso posicional a las filas
# --------------------------------------------------------------------------- #


class _Columns:
    """Índice de columnas insensible a mayúsculas, con acceso posicional.

    Se usa acceso por posición (y no ``DataFrame.to_dict``) para no perder
    columnas cuando un archivo trae encabezados repetidos, y para no pagar el
    costo de construir un dict por fila en archivos de decenas de miles de
    filas.
    """

    def __init__(self, frame: pd.DataFrame) -> None:
        self._by_name: dict[str, int] = {}
        self.names: list[str] = []
        for position, column in enumerate(frame.columns):
            name = str(column).strip()
            self.names.append(name)
            self._by_name.setdefault(name.casefold(), position)

    def position(self, name: str) -> int | None:
        return self._by_name.get(str(name).strip().casefold())

    def has(self, name: str) -> bool:
        return self.position(name) is not None

    def value(self, row: Sequence[Any], name: str) -> Any:
        position = self.position(name)
        return "" if position is None else row[position]


def _text(value: Any) -> str:
    """Texto crudo de una celda, **sin** ``strip``: el EAN no se limpia."""
    if value is None:
        return ""
    if isinstance(value, float) and value != value:  # NaN
        return ""
    return str(value)


def _rows(frame: pd.DataFrame) -> list[tuple[Any, ...]]:
    return list(frame.itertuples(index=False, name=None))


def _reject_ean(
    issues: IssueCollector,
    source: str,
    ean: str,
    duplicates: set[str],
    *,
    row_number: int,
    sku: Any,
    product_name: Any,
) -> bool:
    """Registra la incidencia de EAN si corresponde; ``True`` si hay que excluir."""
    problem = describe_ean_problem(ean)
    if problem:
        issues.add(
            source,
            IssueCode.EAN_INVALIDO,
            f"{problem} La fila se excluyó de la importación.",
            severity=IssueSeverity.ERROR,
            row_number=row_number,
            sku=sku,
            ean=ean,
            product_name=product_name,
        )
        return True
    if ean in duplicates:
        issues.add(
            source,
            IssueCode.EAN_DUPLICADO,
            f"El EAN {ean} aparece más de una vez en el archivo. "
            "Todas sus copias se excluyeron (regla unificada: no se conserva la primera).",
            severity=IssueSeverity.ERROR,
            row_number=row_number,
            sku=sku,
            ean=ean,
            product_name=product_name,
        )
        return True
    return False


# --------------------------------------------------------------------------- #
# INVEPTOS → sales_imports / sales_lines
# --------------------------------------------------------------------------- #


def prepare_sales_import(
    frame: pd.DataFrame,
    *,
    supplier_tbc_code: str | None = None,
    issues: IssueCollector | None = None,
) -> PreparedImport:
    """Prepara una importación de ventas a partir de ``read_inveptos``.

    ``supplier_tbc_code`` es el comodín de tres dígitos que el usuario declaró
    al subir el archivo. Si se pasa, cada fila cuyo ``COMODI`` no lo contenga
    genera **advertencia** (`comodin_invalido`), nunca bloqueo: en INVEPTOS el
    comodín solo advierte (contrato §5.3); el bloqueo por comodín es de
    SDOSXSUC y lo decide la corrida, no la importación.

    Lanza ``InvalidPeriodError`` si ninguna fila trae un período legible o si
    el período está invertido — la importación completa se bloquea y no se
    devuelve ninguna fila.
    """
    collector = issues or IssueCollector()
    columns = _Columns(frame)
    rows = _rows(frame)

    if not rows:
        raise ValidationError(
            f"El archivo {SOURCE_INVEPTOS} no tiene filas de datos: no hay ventas que importar."
        )

    start, end = _resolve_period(columns, rows)
    suffixes = discover_tisuc_suffixes(columns.names)
    if not suffixes:
        collector.add(
            SOURCE_INVEPTOS,
            IssueCode.COLUMNA_FALTANTE,
            "El archivo no trae ningún par TISUC#/UNSUC#: no se pudo asignar ninguna "
            "venta a una ubicación.",
            severity=IssueSeverity.ERROR,
        )

    duplicates = find_duplicate_eans(columns.value(row, "CODEAN") for row in rows)

    prepared = PreparedImport(
        job_type=ImportType.INVEPTOS_SALES,
        source=SOURCE_INVEPTOS,
        header={
            "period_start": start,
            "period_end": end,
            "status": "active",
        },
        period_start=start,
        period_end=end,
        rows_total=len(rows),
    )

    for offset, row in enumerate(rows):
        row_number = FIRST_DATA_ROW + offset
        ean = _text(columns.value(row, "CODEAN"))
        sku = _text(columns.value(row, "CODPRO")).strip()
        product_name = _text(columns.value(row, "DETALL")).strip()

        if _reject_ean(
            collector,
            SOURCE_INVEPTOS,
            ean,
            duplicates,
            row_number=row_number,
            sku=sku,
            product_name=product_name,
        ):
            prepared.rows_rejected += 1
            continue

        _check_row_period(collector, columns, row, start, end, row_number, sku, ean, product_name)
        _check_supplier_code(
            collector, columns, row, supplier_tbc_code, row_number, sku, ean, product_name
        )

        tbc_cost = to_number(columns.value(row, "VALCOS"))
        if tbc_cost is not None and tbc_cost < 0:
            collector.add(
                SOURCE_INVEPTOS,
                IssueCode.COSTO_INVALIDO,
                f"El costo TBC (VALCOS) es negativo: {tbc_cost}. Se guardó sin costo.",
                severity=IssueSeverity.WARNING,
                row_number=row_number,
                sku=sku,
                ean=ean,
                product_name=product_name,
            )
            tbc_cost = None

        units_by_location: dict[str, int] = {}
        total_in_pairs = 0
        for suffix in suffixes:
            units = to_int(columns.value(row, f"UNSUC{suffix}"))
            total_in_pairs += units
            location = location_for_tisuc(
                columns.value(row, f"TISUC{suffix}"),
                collector,
                row_number=row_number,
                sku=sku,
                ean=ean,
                product_name=product_name,
            )
            if location is None:
                # Código vacío (la columna no aplica a esta fila) o desconocido
                # (ya quedó registrado como incidencia por `location_for_tisuc`).
                continue
            # Suma en vez de asignar: dos TISUC# distintos podrían mapear a la
            # misma ubicación y `unique (sales_import_id, ean, location_id)`
            # no admite dos líneas.
            units_by_location[location] = units_by_location.get(location, 0) + units

        _check_total_consistency(
            collector,
            columns,
            row,
            total_in_pairs,
            row_number=row_number,
            sku=sku,
            ean=ean,
            product_name=product_name,
        )

        for location, units in units_by_location.items():
            prepared.lines.append(
                {
                    "ean": ean,
                    "location_name": location,
                    "product_id": None,
                    "units_sold": units,
                    "tbc_cost": tbc_cost,
                    "source_row_number": row_number,
                }
            )
        prepared.rows_valid += 1

    prepared.issues = list(collector.issues)
    return prepared


def _resolve_period(columns: _Columns, rows: list[tuple[Any, ...]]) -> tuple[date, date]:
    """Período de la importación: el de la **primera fila legible**.

    Si ninguna fila trae fechas legibles se deja que ``period_days`` lance con
    su mensaje (que nombra la columna concreta y explica por qué se bloquea),
    en vez de inventar un mensaje distinto aquí.
    """
    for row in rows:
        raw_start = columns.value(row, "FDESDE")
        raw_end = columns.value(row, "FHASTA")
        start = parse_tbc_date(raw_start)
        end = parse_tbc_date(raw_end)
        if start is not None and end is not None:
            # Valida el orden; lanza InvalidPeriodError si está invertido.
            period_days(start, end)
            return start, end

    first = rows[0]
    period_days(columns.value(first, "FDESDE"), columns.value(first, "FHASTA"))
    raise InvalidPeriodError(  # pragma: no cover - period_days ya lanzó
        "No se pudo determinar el período de ventas del archivo."
    )


def _check_row_period(
    collector: IssueCollector,
    columns: _Columns,
    row: Sequence[Any],
    start: date,
    end: date,
    row_number: int,
    sku: str,
    ean: str,
    product_name: str,
) -> None:
    """Advierte si la fila declara un período distinto al de la importación."""
    row_start = parse_tbc_date(columns.value(row, "FDESDE"))
    row_end = parse_tbc_date(columns.value(row, "FHASTA"))
    if row_start == start and row_end == end:
        return
    if row_start is None or row_end is None:
        detail = (
            "La fila no trae un período legible en FDESDE/FHASTA. Se usó el período "
            f"de la importación ({start.isoformat()} a {end.isoformat()})."
        )
    else:
        detail = (
            f"La fila declara el período {row_start.isoformat()} a {row_end.isoformat()}, "
            f"distinto al de la importación ({start.isoformat()} a {end.isoformat()}). "
            "Se usó el de la importación."
        )
    collector.add(
        SOURCE_INVEPTOS,
        IssueCode.FECHA_INVALIDA,
        detail,
        severity=IssueSeverity.WARNING,
        row_number=row_number,
        sku=sku,
        ean=ean,
        product_name=product_name,
    )


def _check_supplier_code(
    collector: IssueCollector,
    columns: _Columns,
    row: Sequence[Any],
    expected: str | None,
    row_number: int,
    sku: str,
    ean: str,
    product_name: str,
) -> None:
    if not expected:
        return
    found = extract_supplier_code(columns.value(row, "COMODI"))
    if found == expected:
        return
    detail = (
        f"El comodín de la fila ({found or 'ausente'}) no coincide con el declarado "
        f"({expected}). La fila se importó igual: en INVEPTOS el comodín solo advierte."
    )
    collector.add(
        SOURCE_INVEPTOS,
        IssueCode.COMODIN_INVALIDO,
        detail,
        severity=IssueSeverity.WARNING,
        row_number=row_number,
        sku=sku,
        ean=ean,
        product_name=product_name,
    )


def _check_total_consistency(
    collector: IssueCollector,
    columns: _Columns,
    row: Sequence[Any],
    total_in_pairs: int,
    *,
    row_number: int,
    sku: str,
    ean: str,
    product_name: str,
) -> None:
    """Valida ``Σ UNSUC# == UNIVTA`` (contrato §3.2, pendiente desde Fase 1).

    El motor viejo ignoraba ``UNSUCX`` sin verificar que estuviera en cero, así
    que una diferencia entre la suma por sucursal y el total pasaba inadvertida.
    Aquí se compara y se registra como **advertencia**: la diferencia casi
    siempre es ``UNSUCX`` (ventas de una ubicación fuera de los pares
    ``TISUC#``), el dato por ubicación sigue siendo utilizable y excluir la fila
    perdería ventas reales. Por eso la fila no se excluye.
    """
    if not columns.has("UNIVTA"):
        return
    declared = to_int(columns.value(row, "UNIVTA"))
    if declared == total_in_pairs:
        return

    difference = declared - total_in_pairs
    detail = (
        f"La suma de unidades por sucursal (Σ UNSUC# = {total_in_pairs}) no coincide con "
        f"el total declarado (UNIVTA = {declared}); diferencia de {difference}."
    )
    if columns.has("UNSUCX"):
        unsucx = to_int(columns.value(row, "UNSUCX"))
        if unsucx:
            detail += (
                f" UNSUCX trae {unsucx} unidades, que no pertenecen a ninguna sucursal "
                "de los pares TISUC#/UNSUC# y explican total o parcialmente la diferencia."
            )
    detail += " La fila se importó igual; revisar el archivo de origen."

    collector.add(
        SOURCE_INVEPTOS,
        IssueCode.TOTAL_INCONSISTENTE,
        detail,
        severity=IssueSeverity.WARNING,
        row_number=row_number,
        sku=sku,
        ean=ean,
        product_name=product_name,
    )


# --------------------------------------------------------------------------- #
# SDOSXSUC → inventory_snapshots / inventory_lines
# --------------------------------------------------------------------------- #


def prepare_inventory_import(
    frame: pd.DataFrame,
    *,
    snapshot_date: date | None = None,
    issues: IssueCollector | None = None,
) -> PreparedImport:
    """Prepara un snapshot de inventario a partir de ``read_sdos``.

    Una columna ``us##`` ausente no es error: simplemente no genera líneas para
    esa ubicación (contrato §3.1, "columna ausente ⇒ inventario 0").
    """
    collector = issues or IssueCollector()
    columns = _Columns(frame)
    rows = _rows(frame)
    inventory_columns = sdos_inventory_columns(columns.names)

    if not inventory_columns:
        collector.add(
            SOURCE_SDOS,
            IssueCode.COLUMNA_FALTANTE,
            "El archivo no trae ninguna columna de inventario us01..us09: "
            "no se pudo asignar existencias a ninguna ubicación.",
            severity=IssueSeverity.ERROR,
        )

    duplicates = find_duplicate_eans(columns.value(row, "Codean") for row in rows)

    prepared = PreparedImport(
        job_type=ImportType.SDOS_INVENTORY,
        source=SOURCE_SDOS,
        header={
            "snapshot_date": snapshot_date or date.today(),
            "status": "active",
        },
        rows_total=len(rows),
    )

    for offset, row in enumerate(rows):
        row_number = FIRST_DATA_ROW + offset
        ean = _text(columns.value(row, "Codean"))
        sku = _text(columns.value(row, "Codpro")).strip()
        product_name = _text(columns.value(row, "Nompro")).strip()

        if _reject_ean(
            collector,
            SOURCE_SDOS,
            ean,
            duplicates,
            row_number=row_number,
            sku=sku,
            product_name=product_name,
        ):
            prepared.rows_rejected += 1
            continue

        pvp = to_number(columns.value(row, "Valuni"))
        if pvp is not None and pvp < 0:
            collector.add(
                SOURCE_SDOS,
                IssueCode.COSTO_INVALIDO,
                f"El precio de venta (Valuni) es negativo: {pvp}. Se guardó sin precio.",
                severity=IssueSeverity.WARNING,
                row_number=row_number,
                sku=sku,
                ean=ean,
                product_name=product_name,
            )
            pvp = None

        supplier_code = extract_supplier_code(columns.value(row, "Codea2")) or None

        for column_name, location in inventory_columns.items():
            on_hand = to_int(columns.value(row, column_name))
            if on_hand < 0:
                # No se recorta a 0: inventar un dato es peor que no tenerlo.
                collector.add(
                    SOURCE_SDOS,
                    IssueCode.CANTIDAD_INVALIDA,
                    f"El inventario de {location} ({column_name}) es negativo: {on_hand}. "
                    "Esa existencia no se guardó.",
                    severity=IssueSeverity.WARNING,
                    row_number=row_number,
                    sku=sku,
                    ean=ean,
                    product_name=product_name,
                )
                continue
            prepared.lines.append(
                {
                    "ean": ean,
                    "tbc_sku": sku or None,
                    "location_name": location,
                    "on_hand": on_hand,
                    "pvp": pvp,
                    "supplier_tbc_code": supplier_code,
                }
            )
        prepared.rows_valid += 1

    prepared.issues = list(collector.issues)
    return prepared


# --------------------------------------------------------------------------- #
# Lista de proveedor → price_lists / price_list_items
# --------------------------------------------------------------------------- #


def prepare_price_list_import(
    frame: pd.DataFrame,
    *,
    supplier_id: Any,
    effective_date: date | None = None,
    issues: IssueCollector | None = None,
) -> PreparedImport:
    """Prepara una lista de precios a partir de ``read_supplier_price_list``.

    El ``DataFrame`` de entrada ya viene normalizado a ``EAN-13`` / ``Nombre`` /
    ``Costo proveedor``; aquí solo se valida el contenido. Un costo ilegible o
    negativo **excluye la fila** con incidencia ``costo_invalido``: una lista de
    precios sin precio no sirve, y suponer 0 haría que la comparación de costos
    contra TBC diera un ahorro inventado.

    ``version`` y ``status`` no se fijan aquí: la versión es ``max+1`` por
    proveedor y solo puede calcularse dentro de la transacción de escritura
    (:mod:`engine.persistence`), y el estado inicial es ``draft`` porque una
    `price_lists` no-draft es inmutable por trigger (contrato §9.1) y no
    admitiría que se le inserten sus propios ítems.
    """
    collector = issues or IssueCollector()
    columns = _Columns(frame)
    rows = _rows(frame)
    duplicates = find_duplicate_eans(columns.value(row, "EAN-13") for row in rows)

    prepared = PreparedImport(
        job_type=ImportType.SUPPLIER_PRICE_LIST,
        source=SOURCE_SUPPLIER,
        header={
            "supplier_id": supplier_id,
            "effective_date": effective_date or date.today(),
        },
        rows_total=len(rows),
    )

    for offset, row in enumerate(rows):
        row_number = FIRST_DATA_ROW + offset
        ean = _text(columns.value(row, "EAN-13"))
        product_name = _text(columns.value(row, "Nombre")).strip()
        raw_cost = columns.value(row, "Costo proveedor")

        if _reject_ean(
            collector,
            SOURCE_SUPPLIER,
            ean,
            duplicates,
            row_number=row_number,
            sku="",
            product_name=product_name,
        ):
            prepared.rows_rejected += 1
            continue

        cost = to_number(raw_cost)
        if cost is None or cost < 0:
            reason = (
                "no es un número interpretable"
                if cost is None
                else f"es negativo ({cost})"
            )
            collector.add(
                SOURCE_SUPPLIER,
                IssueCode.COSTO_INVALIDO,
                f"El costo del proveedor {reason}: '{_text(raw_cost).strip()}'. "
                "La fila se excluyó de la lista de precios.",
                severity=IssueSeverity.ERROR,
                row_number=row_number,
                ean=ean,
                product_name=product_name,
            )
            prepared.rows_rejected += 1
            continue

        prepared.lines.append(
            {
                "ean": ean,
                "supplier_product_id": None,
                "supplier_cost": cost,
                "source_row_number": row_number,
                "raw": {
                    "EAN-13": ean,
                    "Nombre": product_name,
                    "Costo proveedor": _text(raw_cost),
                },
            }
        )
        prepared.rows_valid += 1

    prepared.issues = list(collector.issues)
    return prepared
