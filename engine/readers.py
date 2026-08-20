"""Lectura de las tres fuentes de datos del programa de compras.

Portado desde el motor MVP (`procurement_engine.py`) según el contrato §5.2,
con tres cambios deliberados:

1. ``read_inveptos`` fija el **encoding explícitamente** (``cp1252`` por
   defecto) en vez de depender del fallback silencioso de ``xlrd`` a
   ``iso-8859-1`` cuando el ``.xls`` no trae registro ``CODEPAGE``.
2. La detección de columnas de la lista de proveedor deja de ser una
   heurística de texto cableada a un proveedor concreto y pasa a ser un
   **mapeo de alias configurable** (:class:`SupplierColumnMapping`), pensado
   para persistirse por proveedor en base de datos.
3. Un ``TISUC#`` fuera del catálogo de ubicaciones **genera incidencia** en vez
   de descartarse en silencio.

Todas las funciones de lectura aceptan ``str | Path | BinaryIO``, igual que el
motor viejo, y devuelven ``DataFrame`` con **todo el contenido como texto**:
el EAN nunca pasa por un tipo numérico en ningún punto de la cadena.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any, BinaryIO, Iterable, Sequence

import pandas as pd

from engine.validation import (
    IssueCode,
    IssueCollector,
    IssueSeverity,
    ValidationError,
    missing_columns,
)

__all__ = [
    "TISUC_TO_LOCATION",
    "SDOS_INVENTORY_MAPPING",
    "OPERATIVE_LOCATIONS",
    "REFERENCE_LOCATIONS",
    "ALL_LOCATIONS",
    "SOURCE_SDOS",
    "SOURCE_INVEPTOS",
    "SOURCE_SUPPLIER",
    "AliasSpec",
    "SupplierColumnMapping",
    "DEFAULT_SUPPLIER_COLUMNS",
    "NORMALIZED_TEMPLATE_COLUMNS",
    "SDOS_REQUIRED_COLUMNS",
    "INVEPTOS_REQUIRED_COLUMNS",
    "read_sdos",
    "read_inveptos",
    "read_supplier_price_list",
    "read_excel_any_header",
    "require_columns",
    "sdos_inventory_mapping",
    "sdos_inventory_columns",
    "discover_tisuc_suffixes",
    "location_for_tisuc",
]

SOURCE_SDOS = "SDOSXSUC"
SOURCE_INVEPTOS = "INVEPTOS"
SOURCE_SUPPLIER = "Proveedor"


# --------------------------------------------------------------------------- #
# Catálogo de ubicaciones
# --------------------------------------------------------------------------- #

#: Código ``TISUC#`` de TBC → nombre de ubicación (espejo de `locations`, §6.3).
#:
#: ``Feria`` (10600) y ``Bodega Bqlla`` (20030) se retiraron del modelo:
#: decisión de negocio (contrato §2) tras confirmar que, sin redistribución,
#: no tenían ningún efecto operativo. Sus filas en `locations` quedan
#: `active = false` (nunca se borran, ver 0003_locations.sql), y un
#: `TISUC#` 10600/20030 en un archivo real ahora es un código desconocido
#: como cualquier otro: genera incidencia `tisuc_desconocido`
#: (`location_for_tisuc`), no se descarta en silencio.
TISUC_TO_LOCATION: dict[str, str] = {
    "10000": "Av. 19",
    "10010": "Bulevar",
    "10500": "Calle 74",
    "10510": "Bvista",
    "10800": "Oviedo",
    "20010": "CEDI",
    "20020": "Full MercadoLibre",
}

#: Ubicaciones que pueden recibir una compra (`is_purchase_target`).
OPERATIVE_LOCATIONS: tuple[str, ...] = (
    "Av. 19",
    "Bulevar",
    "Calle 74",
    "Bvista",
    "Oviedo",
    "CEDI",
)

#: Ubicaciones que existen en los archivos pero no son destino de compra.
REFERENCE_LOCATIONS: tuple[str, ...] = ("Full MercadoLibre",)

ALL_LOCATIONS: tuple[str, ...] = OPERATIVE_LOCATIONS + REFERENCE_LOCATIONS

#: ``us01..us09`` → ubicación. ``us07`` y ``us09`` no se usan: ``us09`` era
#: Bodega Bqlla, retirada del modelo (ver `TISUC_TO_LOCATION`); ``us07``
#: nunca estuvo mapeada. ``us10..us30`` existen en el archivo real y **no**
#: están mapeadas (comportamiento heredado; su descarte es intencional hasta
#: que negocio diga lo contrario — contrato §3.1).
#:
#: Ya no depende de Modo Feria: el mapeo `us05 → Feria` (variante "Modo
#: Feria" del archivo) se retiró junto con la ubicación — un archivo
#: exportado en Modo Feria hoy simplemente no aporta ninguna cifra a esa
#: columna, igual que cualquier otra columna sin ubicación vigente.
SDOS_INVENTORY_MAPPING: dict[str, str] = {
    "us01": "Av. 19",
    "us02": "Bulevar",
    "us03": "Calle 74",
    "us04": "Bvista",
    "us05": "Oviedo",
    "us06": "CEDI",
    "us08": "Full MercadoLibre",
}

#: Columnas sin las que SDOSXSUC no es utilizable.
SDOS_REQUIRED_COLUMNS: tuple[str, ...] = ("Codpro", "Nompro", "Valuni", "Codean", "Codea2")

#: Columnas sin las que INVEPTOS no es utilizable. Los pares
#: ``TISUC#``/``UNSUC#`` se descubren dinámicamente y **no** se exigen aquí:
#: su cantidad varía entre exportaciones (contrato §3.2).
INVEPTOS_REQUIRED_COLUMNS: tuple[str, ...] = (
    "CODPRO",
    "COMODI",
    "DETALL",
    "VALCOS",
    "FDESDE",
    "FHASTA",
    "CODEAN",
)

_TISUC_RE = re.compile(r"^TISUC(\d+)$", re.IGNORECASE)


def sdos_inventory_mapping() -> dict[str, str]:
    """Mapeo ``us##`` → ubicación para SDOSXSUC."""
    return dict(SDOS_INVENTORY_MAPPING)


def sdos_inventory_columns(columns: Sequence[Any]) -> dict[str, str]:
    """Columnas ``us##`` **presentes** en el archivo → ubicación.

    Una columna ausente simplemente no aparece en el resultado: el llamador
    debe tratarla como inventario 0, no como error (contrato §3.1). La
    comparación es insensible a mayúsculas porque las exportaciones alternan
    entre ``us01`` y ``US01``.
    """
    present = {str(c).strip().lower(): str(c).strip() for c in columns}
    mapping = sdos_inventory_mapping()
    return {
        present[key]: location
        for key, location in mapping.items()
        if key in present
    }


def discover_tisuc_suffixes(columns: Sequence[Any]) -> list[str]:
    """Sufijos numéricos de los pares ``TISUC#``/``UNSUC#`` presentes.

    Se descubren **dinámicamente por regex**: el número de pares varía entre
    exportaciones (la muestra real trae 6, sin Full ML / Bodega Bqlla / Feria)
    y asumir un conteo fijo rompería el parser (contrato §3.2).
    """
    suffixes: list[str] = []
    for column in columns:
        match = _TISUC_RE.match(str(column).strip())
        if match:
            suffixes.append(match.group(1))
    return sorted(set(suffixes), key=lambda s: (len(s), s))


def location_for_tisuc(
    code: Any,
    issues: IssueCollector | None = None,
    *,
    row_number: int | None = None,
    sku: Any = "",
    ean: Any = "",
    product_name: Any = "",
) -> str | None:
    """Ubicación para un código ``TISUC#``; ``None`` si no está en el catálogo.

    Un código desconocido **genera incidencia** (`tisuc_desconocido`) en vez de
    descartarse en silencio como hacía el motor viejo. Un código vacío no es
    incidencia: significa que esa columna no aplica a esa fila.
    """
    text = "" if code is None else str(code).strip()
    if not text:
        return None
    location = TISUC_TO_LOCATION.get(text)
    if location is None and issues is not None:
        issues.add(
            SOURCE_INVEPTOS,
            IssueCode.TISUC_DESCONOCIDO,
            f"El código de sucursal '{text}' no está en el catálogo de ubicaciones. "
            "Sus unidades no se asignaron a ninguna ubicación.",
            severity=IssueSeverity.WARNING,
            row_number=row_number,
            sku=sku,
            ean=ean,
            product_name=product_name,
        )
    return location


# --------------------------------------------------------------------------- #
# Validación de columnas
# --------------------------------------------------------------------------- #


def require_columns(
    frame: pd.DataFrame,
    columns: Sequence[str],
    source: str,
) -> None:
    """Verifica columnas obligatorias; lanza con la lista **completa** de faltantes."""
    missing = missing_columns(frame.columns, columns)
    if missing:
        raise ValidationError(
            f"Faltan columnas obligatorias en {source}: {', '.join(missing)}."
        )


# --------------------------------------------------------------------------- #
# SDOSXSUC (CSV)
# --------------------------------------------------------------------------- #


def read_sdos(
    source: str | Path | BinaryIO,
    *,
    encoding: str = "latin1",
    validate: bool = True,
) -> pd.DataFrame:
    """Lee ``SDOSXSUC.CSV``: separador ``;``, Latin-1, todo como texto.

    ``dtype=str`` es obligatorio, no una preferencia: cerca del 9% de los EAN
    reales tienen ceros iniciales y leerlos como número corrompe el catálogo.
    Los vacíos se normalizan a cadena vacía (nunca ``NaN``) para que el resto
    del motor no tenga que distinguir ambos.
    """
    frame = pd.read_csv(source, sep=";", encoding=encoding, dtype=str).fillna("")
    frame.columns = [str(c).strip() for c in frame.columns]
    if validate:
        require_columns(frame, SDOS_REQUIRED_COLUMNS, SOURCE_SDOS)
    return frame


# --------------------------------------------------------------------------- #
# INVEPTOS (.xls legado)
# --------------------------------------------------------------------------- #

#: Encoding con el que se interpretan los ``.xls`` de TBC. Se fija de forma
#: **explícita**: el archivo real no trae registro ``CODEPAGE`` y ``xlrd``
#: cae en silencio a ``iso-8859-1``, lo que rompe tildes y ``ñ`` en los
#: nombres de producto (contrato §3.2).
DEFAULT_XLS_ENCODING = "cp1252"


def read_inveptos(
    source: str | Path | BinaryIO,
    *,
    encoding: str = DEFAULT_XLS_ENCODING,
    sheet: int | str = 0,
    validate: bool = True,
) -> pd.DataFrame:
    """Lee ``INVEPTOS.XLS`` (BIFF legado) con ``xlrd`` y encoding explícito.

    No se usa ``pandas.read_excel`` porque no expone ``encoding_override`` de
    ``xlrd``; se abre el libro directamente para poder fijarlo. Todas las
    celdas se devuelven como texto:

    - Un número entero se formatea sin ``.0`` (``123``, no ``123.0``) — si el
      EAN quedó guardado como número en el ``.xls``, esta es la única forma de
      no corromperlo.
    - Una fecha se devuelve en ISO ``YYYY-MM-DD``, que
      :func:`engine.validation.parse_tbc_date` sabe leer.
    """
    import xlrd  # import diferido: solo hace falta para el formato legado

    workbook = xlrd.open_workbook(
        **_xlrd_open_args(source),
        encoding_override=encoding,
        formatting_info=False,
    )
    try:
        book_sheet = (
            workbook.sheet_by_index(sheet)
            if isinstance(sheet, int)
            else workbook.sheet_by_name(sheet)
        )
        if book_sheet.nrows == 0:
            raise ValidationError(f"El archivo {SOURCE_INVEPTOS} está vacío.")

        header = [str(value).strip() for value in book_sheet.row_values(0)]
        rows = [
            [
                _xls_cell_to_text(book_sheet.cell(r, c), workbook.datemode)
                for c in range(book_sheet.ncols)
            ]
            for r in range(1, book_sheet.nrows)
        ]
    finally:
        workbook.release_resources()

    frame = pd.DataFrame(rows, columns=header).fillna("")
    if validate:
        require_columns(frame, INVEPTOS_REQUIRED_COLUMNS, SOURCE_INVEPTOS)
    return frame


def _xlrd_open_args(source: str | Path | BinaryIO) -> dict[str, Any]:
    if isinstance(source, (str, Path)):
        return {"filename": str(source)}
    if hasattr(source, "seek"):
        source.seek(0)
    return {"file_contents": source.read()}


def _xls_cell_to_text(cell: Any, datemode: int) -> str:
    """Convierte una celda ``xlrd`` a texto sin perder precisión del dato."""
    import xlrd

    if cell.ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return ""
    if cell.ctype == xlrd.XL_CELL_TEXT:
        return str(cell.value)
    if cell.ctype == xlrd.XL_CELL_NUMBER:
        number = float(cell.value)
        # Sin ".0": un EAN guardado como número debe volver como dígitos exactos.
        return str(int(number)) if number.is_integer() else repr(number)
    if cell.ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate_as_datetime(cell.value, datemode).date().isoformat()
    if cell.ctype == xlrd.XL_CELL_BOOLEAN:
        return "1" if cell.value else "0"
    return ""


# --------------------------------------------------------------------------- #
# Lista de precios de proveedor
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class AliasSpec:
    """Cómo se identifica **una** columna lógica dentro de un archivo real.

    Dos mecanismos, en orden de prioridad:

    - ``aliases``: nombres exactos (comparados sin distinguir mayúsculas ni
      espacios sobrantes). Es el mecanismo preferido y el que debería
      persistirse por proveedor en base de datos.
    - ``contains_all``: grupos de palabras que deben aparecer *todas* en el
      nombre de la columna. Es el escape para encabezados largos e
      irrepetibles (``PVP CON DESCUENTO ... ANTES DE IVA``). Va vacío por
      defecto: existe para que una configuración guardada pueda expresarlo,
      no para adivinar.
    """

    aliases: tuple[str, ...] = ()
    contains_all: tuple[tuple[str, ...], ...] = ()

    def find(self, columns: Sequence[str]) -> str | None:
        """Primera columna que satisface el alias; ``None`` si ninguna."""
        stripped = [str(c).strip() for c in columns]
        lowered = {c.casefold(): c for c in reversed(stripped)}
        for alias in self.aliases:
            match = lowered.get(str(alias).strip().casefold())
            if match is not None:
                return match
        for tokens in self.contains_all:
            needles = [t.casefold() for t in tokens]
            for column in stripped:
                haystack = column.casefold()
                if all(n in haystack for n in needles):
                    return column
        return None

    @property
    def describe(self) -> str:
        parts = list(self.aliases)
        parts += ["+".join(tokens) for tokens in self.contains_all]
        return " / ".join(parts) if parts else "(sin alias configurado)"


@dataclass(frozen=True)
class SupplierColumnMapping:
    """Mapeo de columnas de una lista de precios de proveedor.

    Sustituye la heurística cableada al formato de un proveedor concreto que
    tenía el motor viejo (contrato §3.3). Cada proveedor puede traer el suyo
    desde base de datos vía :meth:`from_config`.
    """

    ean: AliasSpec
    name: AliasSpec
    cost: AliasSpec

    @classmethod
    def from_config(cls, config: dict[str, Any]) -> "SupplierColumnMapping":
        """Construye el mapeo desde una configuración persistida.

        Formato aceptado por campo (``ean``/``name``/``cost``):

        - ``"EAN-13"`` — un nombre exacto.
        - ``["EAN-13", "EAN"]`` — varios nombres exactos.
        - ``{"aliases": [...], "contains_all": [["pvp", "descuento"]]}``.
        """
        missing = [k for k in ("ean", "name", "cost") if k not in config]
        if missing:
            raise ValidationError(
                "La configuración de columnas del proveedor debe definir: "
                + ", ".join(missing)
                + "."
            )
        return cls(**{key: _alias_spec(config[key]) for key in ("ean", "name", "cost")})

    def resolve(self, columns: Sequence[str]) -> dict[str, str]:
        """Columna real para cada campo lógico; lanza si falta alguna."""
        resolved: dict[str, str] = {}
        unresolved: list[str] = []
        for field_name, spec, label in (
            ("ean", self.ean, "EAN"),
            ("name", self.name, "Nombre"),
            ("cost", self.cost, "Costo proveedor"),
        ):
            column = spec.find(columns)
            if column is None:
                unresolved.append(f"{label} (se buscó: {spec.describe})")
            else:
                resolved[field_name] = column
        if unresolved:
            raise ValidationError(
                "No se encontraron estas columnas en la lista del proveedor: "
                + "; ".join(unresolved)
                + ". Columnas disponibles: "
                + ", ".join(str(c).strip() for c in columns)
                + "."
            )
        return resolved


def _alias_spec(value: Any) -> AliasSpec:
    if isinstance(value, AliasSpec):
        return value
    if isinstance(value, str):
        return AliasSpec(aliases=(value,))
    if isinstance(value, dict):
        return AliasSpec(
            aliases=tuple(value.get("aliases", ()) or ()),
            contains_all=tuple(
                tuple(group) for group in (value.get("contains_all", ()) or ())
            ),
        )
    if isinstance(value, Iterable):
        return AliasSpec(aliases=tuple(str(v) for v in value))
    raise ValidationError(f"Alias de columna no reconocido: {value!r}.")


#: Plantilla normalizada que publica la aplicación.
NORMALIZED_TEMPLATE_COLUMNS: tuple[str, ...] = ("EAN-13", "Nombre", "Costo proveedor")

#: Mapeo por defecto: la plantilla normalizada más los sinónimos genéricos más
#: comunes. **No incluye** los encabezados propios de ningún proveedor: esos
#: van en la configuración de ese proveedor.
DEFAULT_SUPPLIER_COLUMNS = SupplierColumnMapping(
    ean=AliasSpec(aliases=("EAN-13", "EAN13", "EAN", "Código EAN", "Codigo EAN")),
    name=AliasSpec(aliases=("Nombre", "Producto", "Descripción", "Descripcion")),
    cost=AliasSpec(aliases=("Costo proveedor", "Costo", "Costo unitario")),
)


def read_supplier_price_list(
    source: str | Path | BinaryIO,
    mapping: SupplierColumnMapping = DEFAULT_SUPPLIER_COLUMNS,
    *,
    max_header_row: int = 19,
    sheet: int | str = 0,
) -> pd.DataFrame:
    """Lee una lista de precios de proveedor y la normaliza.

    Soporta las dos variantes del contrato §3.3: la plantilla normalizada
    (encabezado en la primera fila) y las listas reales con el **encabezado
    desplazado** varias filas hacia abajo. Los nombres de columna se
    ``strip``ean siempre — varios encabezados reales traen espacios finales.

    Devuelve un ``DataFrame`` con exactamente tres columnas de texto:
    ``EAN-13``, ``Nombre``, ``Costo proveedor``. El EAN se conserva tal cual
    vino (con ceros iniciales, y sin limpiar espacios: un EAN con espacios es
    inválido, no se corrige). La validación de EAN/costo no ocurre aquí, sino
    en la etapa de preparación, que es la que registra incidencias.
    """
    frame = read_excel_any_header(
        source,
        matches=lambda columns: _mapping_resolves(mapping, columns),
        max_header_row=max_header_row,
        sheet=sheet,
    )
    resolved = mapping.resolve(frame.columns)
    normalized = frame[[resolved["ean"], resolved["name"], resolved["cost"]]].copy()
    normalized.columns = list(NORMALIZED_TEMPLATE_COLUMNS)
    normalized = normalized.fillna("").astype(str)
    # Se descartan solo las filas completamente vacías (relleno del archivo).
    keep = normalized.apply(lambda row: any(v.strip() for v in row), axis=1)
    return normalized[keep].reset_index(drop=True) if len(normalized) else normalized


def _mapping_resolves(mapping: SupplierColumnMapping, columns: Sequence[str]) -> bool:
    try:
        mapping.resolve(columns)
    except ValidationError:
        return False
    return True


def read_excel_any_header(
    source: str | Path | BinaryIO,
    *,
    matches,
    max_header_row: int = 19,
    sheet: int | str = 0,
) -> pd.DataFrame:
    """Lee un Excel probando la fila de encabezado de 0 a ``max_header_row``.

    Devuelve el primer intento cuyas columnas satisfacen ``matches``. Si
    ninguno lo hace, lanza ``ValidationError`` describiendo lo que sí se
    encontró, en vez de propagar un error de pandas ilegible.
    """
    data = _as_seekable(source)
    last_columns: list[str] = []
    last_error: Exception | None = None

    for header in range(0, max_header_row + 1):
        data.seek(0)
        try:
            frame = pd.read_excel(data, header=header, dtype=str, sheet_name=sheet)
        except Exception as exc:  # hoja más corta que el encabezado probado, etc.
            last_error = exc
            continue
        columns = [str(c).strip() for c in frame.columns]
        if columns:
            last_columns = columns
        if matches(columns):
            frame.columns = columns
            return frame.dropna(how="all").reset_index(drop=True)

    detail = (
        f" En el último intento se leyeron estas columnas: {', '.join(last_columns)}."
        if last_columns
        else f" No se pudo leer ninguna fila de encabezado ({last_error})."
    )
    raise ValidationError(
        "No se encontró la fila de encabezado del archivo del proveedor en las "
        f"primeras {max_header_row + 1} filas.{detail}"
    )


def _as_seekable(source: str | Path | BinaryIO) -> BinaryIO:
    """Devuelve un buffer reposicionable para poder reintentar la lectura."""
    if isinstance(source, (str, Path)):
        return BytesIO(Path(source).read_bytes())
    if hasattr(source, "seek"):
        source.seek(0)
        return source  # type: ignore[return-value]
    return BytesIO(source.read())
