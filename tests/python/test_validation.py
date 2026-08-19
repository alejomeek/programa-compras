"""Pruebas de `engine.validation` (contrato §5.4).

Cubre: validez de EAN en sus formatos límite, duplicados con la regla
unificada, extracción/validez del comodín, parseo de fecha en español,
período inclusivo, **bloqueo ante fecha inválida o invertida**, y parseo
numérico es-CO.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

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
    is_valid_ean,
    is_valid_supplier_code,
    missing_columns,
    parse_tbc_date,
    period_days,
    require_supplier_code,
    to_int,
    to_number,
)


# --------------------------------------------------------------------------- #
# EAN
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "value",
    [
        "7701234567890",  # EAN-13 típico
        "0012345678905",  # ceros iniciales: válido y se conserva
        "12345",          # cualquier longitud: no se exige 13
        "0",              # un solo dígito
    ],
)
def test_ean_valido_en_formatos_limite(value):
    assert is_valid_ean(value) is True
    assert describe_ean_problem(value) == ""


@pytest.mark.parametrize(
    "value",
    [
        "",                 # vacío
        "   ",              # solo espacios
        " 7701234567890",   # espacio inicial: inválido, NO se limpia
        "7701234567890 ",   # espacio final: inválido, NO se limpia
        "770 1234 567890",  # espacios internos
        "770123456789X",    # carácter no numérico
        "77.0123456789",    # separador
        "-7701234567890",   # signo
        None,
    ],
)
def test_ean_invalido_en_sus_variantes(value):
    assert is_valid_ean(value) is False
    assert describe_ean_problem(value) != ""


def test_ean_con_espacios_no_se_limpia_silenciosamente():
    """Un EAN con espacios es una incidencia, no un dato a corregir."""
    problema = describe_ean_problem(" 7701234567890")
    assert "espacios" in problema.lower()
    assert is_valid_ean(" 7701234567890".strip()) is True  # el limpio sí valdría


def test_ean_nunca_se_convierte_a_numero():
    """El cero inicial sobrevive: la función opera sobre texto, no sobre número."""
    ean = "0012345678905"
    assert is_valid_ean(ean)
    assert ean.startswith("00")
    # Un float traído por error de una hoja de cálculo no pasa como EAN válido.
    assert is_valid_ean(12345678905.0) is False


def test_ean_duplicado_excluye_todas_las_copias():
    """Regla unificada del contrato §3.4: se excluyen todas, no solo las extra."""
    duplicados = find_duplicate_eans(
        ["7701234567890", "0012345678905", "7701234567890", "7709876543210"]
    )
    assert duplicados == {"7701234567890"}


def test_ean_duplicado_ignora_los_invalidos():
    """Dos filas con EAN vacío no son 'un duplicado': ya están excluidas."""
    assert find_duplicate_eans(["", "", "  ", None]) == set()


def test_ean_duplicado_distingue_cero_inicial():
    """`0012345678905` y `12345678905` son EAN distintos, no duplicados."""
    assert find_duplicate_eans(["0012345678905", "12345678905"]) == set()


# --------------------------------------------------------------------------- #
# Comodín de proveedor
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (".745", "745"),
        (".745SINT", "745"),
        (".7451LAS", "745"),  # el regex no ancla el final: comportamiento portado
        ("  .745  ", "745"),
        (".0745", "074"),     # documentado: toma los 3 primeros dígitos
        ("745", ""),          # sin punto: no es comodín de archivo
        (".74", ""),          # menos de 3 dígitos
        ("", ""),
        (None, ""),
        ("X.745", ""),        # debe empezar por punto
    ],
)
def test_extraccion_de_comodin(value, expected):
    assert extract_supplier_code(value) == expected


@pytest.mark.parametrize("value", ["745", "007", " 745 "])
def test_comodin_de_usuario_valido(value):
    assert is_valid_supplier_code(value) is True
    assert require_supplier_code(value) == value.strip()


@pytest.mark.parametrize("value", ["74", "7451", ".745", "abc", "", None])
def test_comodin_de_usuario_invalido_bloquea(value):
    assert is_valid_supplier_code(value) is False
    with pytest.raises(ValidationError, match="exactamente 3 dígitos"):
        require_supplier_code(value)


# --------------------------------------------------------------------------- #
# Fechas TBC
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("01-ene-25", date(2025, 1, 1)),
        ("31-dic-24", date(2024, 12, 31)),
        ("5-mar-26", date(2026, 3, 5)),
        ("15-AGO-25", date(2025, 8, 15)),   # mayúsculas
        ("15-Ago-2025", date(2025, 8, 15)),  # año de 4 dígitos
        ("2025-08-15", date(2025, 8, 15)),   # variante ISO
    ],
)
def test_parseo_de_fecha_en_espanol(value, expected):
    assert parse_tbc_date(value) == expected


def test_ano_de_dos_digitos_suma_2000():
    assert parse_tbc_date("01-ene-25").year == 2025
    assert parse_tbc_date("01-ene-99").year == 2099


def test_parse_acepta_date_y_datetime_ya_tipados():
    assert parse_tbc_date(date(2025, 1, 1)) == date(2025, 1, 1)
    assert parse_tbc_date(datetime(2025, 1, 1, 13, 45)) == date(2025, 1, 1)


@pytest.mark.parametrize(
    "value",
    ["", "   ", None, "sin fecha", "01-xxx-25", "31-feb-25", "99-ene-25", "0"],
)
def test_fecha_ilegible_devuelve_none(value):
    assert parse_tbc_date(value) is None


# --------------------------------------------------------------------------- #
# Período — el cambio deliberado frente al motor viejo
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        ("01-ene-25", "31-ene-25", 31),   # mes completo, inclusivo
        ("01-ene-25", "01-ene-25", 1),    # un solo día
        ("01-ene-25", "02-ene-25", 2),
        ("01-ene-24", "31-dic-24", 366),  # año bisiesto
    ],
)
def test_periodo_es_inclusivo(start, end, expected):
    assert period_days(start, end) == expected


def test_periodo_de_un_dia_es_valido_aunque_explosivo():
    """Un período de 1 día es legítimo; su efecto multiplicador es del negocio.

    Con 10 unidades vendidas en 1 día y 45 días objetivo, la fórmula de la
    Fase 3 pediría 450 unidades. El motor no lo corrige: solo garantiza que
    ese 1 sea real y no el fallback silencioso que se eliminó.
    """
    assert period_days("15-mar-25", "15-mar-25") == 1


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("", "31-ene-25"),
        ("01-ene-25", ""),
        ("", ""),
        (None, None),
        ("basura", "31-ene-25"),
        ("01-ene-25", "31-xxx-25"),
    ],
)
def test_fecha_invalida_bloquea_no_cae_a_un_dia(start, end):
    """Riesgo de corrección #1: jamás degradar a `period_days = 1` en silencio."""
    with pytest.raises(InvalidPeriodError) as excinfo:
        period_days(start, end)
    assert "bloquea" in str(excinfo.value).lower()


def test_fecha_invertida_bloquea():
    with pytest.raises(InvalidPeriodError, match="invertido"):
        period_days("31-ene-25", "01-ene-25")


def test_error_de_periodo_nombra_la_columna_problematica():
    """El mensaje debe decirle al usuario cuál de las dos fechas falló."""
    with pytest.raises(InvalidPeriodError) as excinfo:
        period_days("basura", "31-ene-25")
    mensaje = str(excinfo.value)
    assert "FDESDE" in mensaje and "basura" in mensaje
    assert "FHASTA" not in mensaje


def test_invalid_period_error_es_capturable_como_validation_error():
    """La capa de importación puede capturar un solo tipo para marcar `failed`."""
    assert issubclass(InvalidPeriodError, ValidationError)
    assert issubclass(ValidationError, ValueError)


# --------------------------------------------------------------------------- #
# Números es-CO
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1234", 1234.0),
        ("1.234", 1234.0),          # separador de miles
        ("1.234.567", 1234567.0),   # dos grupos de miles
        ("1.234,50", 1234.5),       # miles + decimal
        ("1234,5", 1234.5),         # solo decimal
        ("$ 45.900,00", 45900.0),   # con símbolo y espacio
        ("$45.900", 45900.0),
        ("0", 0.0),
        ("-1.500", -1500.0),
        (1234, 1234.0),
        (1234.5, 1234.5),
    ],
)
def test_parseo_numerico_es_co(value, expected):
    assert to_number(value) == pytest.approx(expected)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("45.900", 45900.0),   # patrón de miles ⇒ 45.900 pesos
        ("1.5", 1.5),          # no forma grupos de tres ⇒ decimal
        ("1234.56", 1234.56),  # decimal con más de 3 enteros
        ("0.5", 0.5),
    ],
)
def test_punto_solitario_se_resuelve_por_patron_de_agrupacion(value, expected):
    """Corrección frente al motor viejo, que leía `45.900` como 45.9.

    El contrato §3.4 define el punto como separador de miles en es-CO. Se
    aplica solo cuando el texto tiene forma de agrupación (`\\d{1,3}(\\.\\d{3})+`);
    un punto decimal legítimo se respeta.
    """
    assert to_number(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["", "   ", None, "abc", "$", float("nan")])
def test_numero_no_interpretable_es_none_no_cero(value):
    """`None` y `0` no son lo mismo: 'sin costo' ≠ 'costo cero'."""
    assert to_number(value) is None


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("10", 10),
        ("10,4", 10),
        ("10,5", 10),      # round() de Python: mitad al par
        ("11,5", 12),
        ("1.234", 1234),
        ("", 0),           # columna ausente/vacía ⇒ 0 unidades, no error
        (None, 0),
        ("abc", 0),
    ],
)
def test_parseo_entero_es_co(value, expected):
    assert to_int(value) == expected


# --------------------------------------------------------------------------- #
# Registro estructurado de incidencias
# --------------------------------------------------------------------------- #


def test_incidencia_se_registra_con_todos_los_campos():
    issues = IssueCollector()
    issues.add(
        "INVEPTOS",
        IssueCode.EAN_INVALIDO,
        "Fila excluida del cruce.",
        row_number=12,
        sku="SKU-001",
        ean=" 7701234567890",
        product_name="Rompecabezas Sintético",
    )
    registro = issues.as_records()[0]
    assert registro == {
        "source": "INVEPTOS",
        "code": "ean_invalido",
        "severity": "error",
        "row_number": 12,
        "sku": "SKU-001",
        "ean": " 7701234567890",  # se guarda crudo: es la evidencia
        "product_name": "Rompecabezas Sintético",
        "detail": "Fila excluida del cruce.",
    }


def test_incidencias_se_separan_por_severidad():
    issues = IssueCollector()
    issues.add("Proveedor", IssueCode.COSTO_INVALIDO, "Costo ilegible.")
    issues.add(
        "INVEPTOS",
        IssueCode.TISUC_DESCONOCIDO,
        "Sucursal fuera del catálogo.",
        severity=IssueSeverity.WARNING,
    )
    assert issues.has_errors() is True
    assert len(issues.errors) == 1
    assert len(issues.warnings) == 1
    assert len(issues) == 2
    assert [i.code for i in issues.by_code(IssueCode.COSTO_INVALIDO)] == ["costo_invalido"]


def test_codigos_de_incidencia_coinciden_con_el_esquema():
    """Los códigos son contrato con `import_issues.code` (§6.3), no texto libre."""
    esperados = {
        "ean_invalido",
        "ean_duplicado",
        "costo_invalido",
        "comodin_invalido",
        "fecha_invalida",
        "tisuc_desconocido",
    }
    definidos = {
        value
        for name, value in vars(IssueCode).items()
        if not name.startswith("_") and isinstance(value, str)
    }
    assert esperados <= definidos


def test_import_issue_es_inmutable():
    issue = ImportIssue("SDOSXSUC", IssueCode.EAN_DUPLICADO, "detalle")
    with pytest.raises(Exception):
        issue.detail = "otro"  # type: ignore[misc]


# --------------------------------------------------------------------------- #
# Columnas faltantes
# --------------------------------------------------------------------------- #


def test_missing_columns_devuelve_todas_las_faltantes_en_orden():
    faltantes = missing_columns(["Codpro", "Codean "], ["Codpro", "Nompro", "Codean", "Codea2"])
    assert faltantes == ["Nompro", "Codea2"]
