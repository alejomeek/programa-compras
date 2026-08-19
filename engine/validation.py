"""Reglas transversales de validación del dominio de compras.

Portadas desde el motor MVP (`procurement_engine.py`) según el contrato de
implementación §5.2, con **un cambio deliberado de comportamiento**:

    El cálculo de días de período ahora **bloquea** (lanza `InvalidPeriodError`)
    si las fechas no parsean o están invertidas. El motor viejo caía en silencio
    a ``period_days = 1``, lo que multiplicaba la sugerencia de compra hasta
    ×174 en datos reales (riesgo de corrección #1 del informe de auditoría).

Invariante que atraviesa todo el módulo: **el EAN es texto exacto**. Ninguna
función de este módulo convierte un EAN a número, ni le aplica ``strip``,
ni lo normaliza silenciosamente.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Iterable, Sequence

__all__ = [
    "SPANISH_MONTHS",
    "ValidationError",
    "InvalidPeriodError",
    "IssueSeverity",
    "IssueCode",
    "ImportIssue",
    "IssueCollector",
    "is_valid_ean",
    "describe_ean_problem",
    "find_duplicate_eans",
    "extract_supplier_code",
    "is_valid_supplier_code",
    "require_supplier_code",
    "parse_tbc_date",
    "period_days",
    "to_number",
    "to_int",
]


# --------------------------------------------------------------------------- #
# Errores
# --------------------------------------------------------------------------- #


class ValidationError(ValueError):
    """Error de validación de una fuente de datos, con mensaje para el usuario.

    Hereda de ``ValueError`` para no romper llamadores que ya capturaban el
    comportamiento del motor viejo.
    """


class InvalidPeriodError(ValidationError):
    """El período de ventas (``FDESDE``/``FHASTA``) no es utilizable.

    Se lanza cuando alguna de las fechas no parsea o cuando ``FDESDE`` es
    posterior a ``FHASTA``. Nunca se degrada a ``period_days = 1``: una
    importación con período ilegible se bloquea completa (plan §6.4).
    """


# --------------------------------------------------------------------------- #
# Incidencias estructuradas (alimentan `import_issues`)
# --------------------------------------------------------------------------- #


class IssueSeverity:
    """Severidad de una incidencia de importación."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueCode:
    """Códigos estables de incidencia (espejo de `import_issues.code`, §6.3)."""

    EAN_INVALIDO = "ean_invalido"
    EAN_DUPLICADO = "ean_duplicado"
    COSTO_INVALIDO = "costo_invalido"
    COMODIN_INVALIDO = "comodin_invalido"
    FECHA_INVALIDA = "fecha_invalida"
    TISUC_DESCONOCIDO = "tisuc_desconocido"
    COLUMNA_FALTANTE = "columna_faltante"
    TOTAL_INCONSISTENTE = "total_inconsistente"
    #: Cantidad no utilizable (inventario negativo). El contrato §6.3 no lo
    #: enumera porque el caso apareció al orquestar la importación de
    #: SDOSXSUC: `inventory_lines.on_hand` tiene `check (>= 0)`, así que una
    #: existencia negativa no se puede guardar y tampoco se recorta a 0
    #: (sería inventar un dato). Se excluye esa existencia y se registra aquí.
    CANTIDAD_INVALIDA = "cantidad_invalida"


#: Fuentes válidas para el campo `source` de una incidencia.
SOURCE_SDOS = "SDOSXSUC"
SOURCE_INVEPTOS = "INVEPTOS"
SOURCE_SUPPLIER = "Proveedor"


@dataclass(frozen=True)
class ImportIssue:
    """Una incidencia de importación, lista para persistirse en `import_issues`.

    Los nombres de campo coinciden con las columnas de la tabla para que la
    capa de persistencia no tenga que traducir. ``ean`` y ``sku`` se guardan
    tal cual vinieron del archivo (sin limpiar), porque el valor crudo es
    justamente la evidencia de la incidencia.
    """

    source: str
    code: str
    detail: str
    severity: str = IssueSeverity.ERROR
    row_number: int | None = None
    sku: str = ""
    ean: str = ""
    product_name: str = ""

    def as_dict(self) -> dict[str, Any]:
        """Representación serializable (una fila de `import_issues`)."""
        return {
            "source": self.source,
            "code": self.code,
            "severity": self.severity,
            "row_number": self.row_number,
            "sku": self.sku,
            "ean": self.ean,
            "product_name": self.product_name,
            "detail": self.detail,
        }


@dataclass
class IssueCollector:
    """Acumulador de incidencias de una importación.

    Reemplaza la lista de dicts sueltos (`_issue`) del motor viejo. Se pasa a
    los lectores y validadores para que registren en vez de descartar en
    silencio (contrato §3.2: un `TISUC#` desconocido debe generar incidencia).
    """

    issues: list[ImportIssue] = field(default_factory=list)

    def add(
        self,
        source: str,
        code: str,
        detail: str,
        *,
        severity: str = IssueSeverity.ERROR,
        row_number: int | None = None,
        sku: Any = "",
        ean: Any = "",
        product_name: Any = "",
    ) -> ImportIssue:
        """Registra una incidencia y la devuelve."""
        issue = ImportIssue(
            source=source,
            code=code,
            detail=detail,
            severity=severity,
            row_number=row_number,
            sku="" if sku is None else str(sku),
            ean="" if ean is None else str(ean),
            product_name="" if product_name is None else str(product_name),
        )
        self.issues.append(issue)
        return issue

    def extend(self, issues: Iterable[ImportIssue]) -> None:
        self.issues.extend(issues)

    @property
    def errors(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.ERROR]

    @property
    def warnings(self) -> list[ImportIssue]:
        return [i for i in self.issues if i.severity == IssueSeverity.WARNING]

    def has_errors(self) -> bool:
        return any(i.severity == IssueSeverity.ERROR for i in self.issues)

    def by_code(self, code: str) -> list[ImportIssue]:
        return [i for i in self.issues if i.code == code]

    def as_records(self) -> list[dict[str, Any]]:
        """Todas las incidencias como filas listas para insertar."""
        return [i.as_dict() for i in self.issues]

    def __len__(self) -> int:  # pragma: no cover - trivial
        return len(self.issues)

    def __iter__(self):  # pragma: no cover - trivial
        return iter(self.issues)


# --------------------------------------------------------------------------- #
# EAN
# --------------------------------------------------------------------------- #

_EAN_RE = re.compile(r"\d+")


def is_valid_ean(value: Any) -> bool:
    """¿Es un EAN válido según la regla exacta del negocio?

    Reglas (contrato §3.4, portadas literalmente):

    - No vacío.
    - **Sin espacios al inicio o al final**: un EAN con espacio es *inválido*,
      no se limpia. No se hace ``strip`` en ningún caso.
    - Solo dígitos.
    - **Cualquier longitud** — no se exige 13.
    - Nunca se convierte a número (un EAN con ceros iniciales debe sobrevivir).
    """
    text = _as_text(value)
    return bool(text) and text == text.strip() and _EAN_RE.fullmatch(text) is not None


def describe_ean_problem(value: Any) -> str:
    """Motivo legible por el que un EAN es inválido (``""`` si es válido).

    Sirve para el campo ``detail`` de la incidencia, en vez del genérico
    "Fila excluida del cruce" del motor viejo.
    """
    text = _as_text(value)
    if not text:
        return "EAN vacío."
    if text != text.strip():
        return "EAN con espacios al inicio o al final (no se limpian: la fila se excluye)."
    if _EAN_RE.fullmatch(text) is None:
        return "EAN con caracteres no numéricos."
    return ""


def find_duplicate_eans(values: Iterable[Any]) -> set[str]:
    """EAN que aparecen más de una vez en la secuencia.

    **Regla unificada** (contrato §3.4): un EAN duplicado excluye *todas* sus
    copias del cruce automático, en las tres fuentes. El motor viejo se quedaba
    con la primera copia en SDOSXSUC; ese comportamiento no se porta.

    Solo se consideran EAN válidos: un EAN inválido ya está excluido por otra
    razón y no debe contar como duplicado dos veces.
    """
    seen: set[str] = set()
    duplicated: set[str] = set()
    for value in values:
        text = _as_text(value)
        if not is_valid_ean(text):
            continue
        if text in seen:
            duplicated.add(text)
        else:
            seen.add(text)
    return duplicated


# --------------------------------------------------------------------------- #
# Comodín de proveedor
# --------------------------------------------------------------------------- #

#: Comodín tal como viene en el archivo: punto + al menos 3 dígitos.
#: El regex **no ancla el final** a propósito (comportamiento portado): un
#: valor como ``.7451LAS`` extrae ``745``. Documentado en el contrato §3.4.
_SUPPLIER_CODE_IN_FILE_RE = re.compile(r"^\.(\d{3})")

#: Comodín ingresado por el usuario: exactamente 3 dígitos, sin punto.
_SUPPLIER_CODE_INPUT_RE = re.compile(r"\d{3}")


def extract_supplier_code(value: Any) -> str:
    """Extrae el comodín de proveedor de ``Codea2`` (SDOSXSUC) o ``COMODI``.

    Formato ``.NNNxxxx``: se exige que empiece por punto y traiga al menos tres
    dígitos; el resto se ignora (``.7451LAS`` → ``"745"``). Devuelve ``""`` si
    el valor no tiene comodín reconocible.
    """
    text = _as_text(value).strip()
    match = _SUPPLIER_CODE_IN_FILE_RE.match(text)
    return match.group(1) if match else ""


def is_valid_supplier_code(value: Any) -> bool:
    """¿El comodín ingresado por el usuario tiene exactamente 3 dígitos?"""
    return _SUPPLIER_CODE_INPUT_RE.fullmatch(_as_text(value).strip()) is not None


def require_supplier_code(value: Any) -> str:
    """Valida y normaliza el comodín ingresado por el usuario.

    Lanza ``ValidationError`` con mensaje en español si no son 3 dígitos
    exactos.
    """
    text = _as_text(value).strip()
    if not is_valid_supplier_code(text):
        raise ValidationError("El comodín proveedor debe tener exactamente 3 dígitos.")
    return text


# --------------------------------------------------------------------------- #
# Fechas TBC y período
# --------------------------------------------------------------------------- #

#: Abreviaturas de mes en español usadas por TBC en ``FDESDE``/``FHASTA``.
SPANISH_MONTHS: dict[str, int] = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "set": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}

_TBC_DATE_RE = re.compile(r"^(\d{1,2})-([A-Za-zÁÉÍÓÚáéíóúñÑ]{3})-(\d{2,4})$")
_ISO_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def parse_tbc_date(value: Any) -> date | None:
    """Parsea una fecha TBC (``dd-Mmm-aa``, mes en español) a ``date``.

    - Año de 2 dígitos ⇒ ``+2000`` (``25`` → 2025).
    - Acepta también ``date``/``datetime`` ya tipados y el formato ISO
      ``YYYY-MM-DD`` (algunas exportaciones lo traen así).
    - Devuelve ``None`` si no se puede interpretar. **El bloqueo no ocurre
      aquí**, ocurre en :func:`period_days`, para que el llamador pueda
      distinguir "fecha ausente" de "período inválido" al registrar la
      incidencia.

    Devuelve ``date`` y no ``datetime`` a propósito: los períodos de negocio se
    guardan en columnas ``date`` (contrato §6.1) para que un cambio de zona
    horaria no mueva un período.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = _as_text(value).strip()
    if not text:
        return None

    match = _TBC_DATE_RE.match(text)
    if match:
        day = int(match.group(1))
        month = SPANISH_MONTHS.get(_strip_accents(match.group(2).lower())[:3])
        year = int(match.group(3))
        if year < 100:
            year += 2000
        if month is None:
            return None
        try:
            return date(year, month, day)
        except ValueError:
            # Día fuera de rango para ese mes (31-feb-25).
            return None

    iso = _ISO_DATE_RE.match(text)
    if iso:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    return None


def period_days(start: Any, end: Any) -> int:
    """Días del período de ventas, **inclusivo** y **bloqueante**.

    ``FHASTA - FDESDE + 1``. Un período de un solo día da 1 (y multiplica la
    sugerencia por los días objetivo — es matemáticamente correcto pero
    explosivo; queda documentado, no corregido aquí).

    Lanza :class:`InvalidPeriodError` si:

    - ``FDESDE`` o ``FHASTA`` no parsean (o vienen vacías), o
    - ``FDESDE > FHASTA`` (fechas invertidas).

    **Este es el cambio deliberado frente al motor viejo**, que ante cualquiera
    de esos casos devolvía ``1`` en silencio e inflaba toda la corrida. No hay
    parámetro para restaurar el comportamiento antiguo: es una regla, no una
    opción.
    """
    parsed_start = parse_tbc_date(start)
    parsed_end = parse_tbc_date(end)

    invalid: list[str] = []
    if parsed_start is None:
        invalid.append(f"FDESDE ({_describe_raw(start)})")
    if parsed_end is None:
        invalid.append(f"FHASTA ({_describe_raw(end)})")
    if invalid:
        raise InvalidPeriodError(
            "No se pudo leer el período de ventas: "
            + " y ".join(invalid)
            + ". Se esperaba el formato dd-Mmm-aa (por ejemplo 01-ene-25). "
            "La importación se bloquea: un período ilegible multiplicaría la compra sugerida."
        )

    assert parsed_start is not None and parsed_end is not None  # para type checkers
    if parsed_start > parsed_end:
        raise InvalidPeriodError(
            f"El período de ventas está invertido: FDESDE ({parsed_start.isoformat()}) "
            f"es posterior a FHASTA ({parsed_end.isoformat()}). La importación se bloquea."
        )

    return (parsed_end - parsed_start).days + 1


# --------------------------------------------------------------------------- #
# Números en formato es-CO
# --------------------------------------------------------------------------- #


#: Un punto que agrupa miles: ``1.234``, ``45.900``, ``1.234.567``.
_THOUSANDS_ONLY_RE = re.compile(r"^\d{1,3}(?:\.\d{3})+$")


def to_number(value: Any) -> float | None:
    """Parsea un número en formato colombiano.

    Acepta ``$``, separador de miles ``.`` y decimal ``,``
    (``"$ 1.234,50"`` → ``1234.5``). Devuelve ``None`` si está vacío o no es
    numérico — **nunca 0**, para poder distinguir "sin costo" de "costo cero".

    Resolución de la ambigüedad del punto solitario (**corrección frente al
    motor viejo**): si el texto trae solo puntos y su patrón es de agrupación
    de miles (``^\\d{1,3}(\\.\\d{3})+$``), los puntos se descartan y
    ``"45.900"`` vale 45900. El motor viejo lo interpretaba como decimal y
    devolvía 45.9 — un PVP mil veces menor, que luego se comparaba contra el
    costo del proveedor. Un punto que no forma grupos de tres
    (``"1.5"``, ``"1234.56"``) se sigue tratando como decimal.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return None if _is_nan(value) else float(value)

    text = _as_text(value).strip()
    if text == "":
        return None
    text = text.replace("$", "").replace(" ", "").replace("\u00a0", "")

    sign = ""
    if text[:1] in ("+", "-"):
        sign, text = text[0], text[1:]
    if text == "":
        return None

    if "," in text and "." in text:
        # Formato canónico es-CO: miles con punto, decimal con coma.
        text = text.replace(".", "").replace(",", ".")
    elif text.count(",") > 1:
        # Varias comas solo pueden ser agrupación de miles.
        text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")
    elif _THOUSANDS_ONLY_RE.fullmatch(text):
        text = text.replace(".", "")

    try:
        number = float(sign + text)
    except ValueError:
        return None
    return None if _is_nan(number) else number


def to_int(value: Any) -> int:
    """Parsea un entero en formato colombiano; ``0`` si no es interpretable.

    Se usa para unidades vendidas e inventario, donde "ausente" y "cero" son
    equivalentes para el negocio (columna faltante ⇒ 0, no error).
    """
    number = to_number(value)
    if number is None:
        return 0
    return int(round(number))


# --------------------------------------------------------------------------- #
# Helpers internos
# --------------------------------------------------------------------------- #

_ACCENTS = str.maketrans("áéíóúÁÉÍÓÚ", "aeiouAEIOU")


def _as_text(value: Any) -> str:
    """Convierte a texto sin perder ceros iniciales ni introducir ``'nan'``."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if _is_nan(value):
        return ""
    return str(value)


def _is_nan(value: Any) -> bool:
    return isinstance(value, float) and value != value


def _strip_accents(text: str) -> str:
    return text.translate(_ACCENTS)


def _describe_raw(value: Any) -> str:
    text = _as_text(value).strip()
    return f"'{text}'" if text else "vacío"


def missing_columns(available: Sequence[Any], required: Sequence[str]) -> list[str]:
    """Columnas requeridas que faltan, en el orden en que fueron pedidas."""
    present = {str(c).strip() for c in available}
    return [c for c in required if c not in present]
