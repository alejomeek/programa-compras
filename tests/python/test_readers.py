"""Pruebas de `engine.readers` (contrato §5.4).

Cubre: preservación de ceros iniciales en el EAN, manejo de Latin-1, columnas
``us##``/``TISUC#`` dinámicas y faltantes, detección de encabezado desplazado,
alias de columna configurable, y mensajes de error con la lista completa de
columnas faltantes.

Todas las fixtures son sintéticas y se construyen en memoria (ver
``conftest.py``): ninguna prueba abre los archivos comerciales del repositorio.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from conftest import (
    EAN_CON_CERO_INICIAL,
    EAN_CORTO,
    EAN_NORMAL,
    EAN_OTRO,
    INVEPTOS_HEADER_2_SUCURSALES,
    build_inveptos_xls,
    build_sdos_csv,
    build_supplier_xlsx,
    inveptos_row,
    sdos_row,
)
from engine.readers import (
    DEFAULT_SUPPLIER_COLUMNS,
    NORMALIZED_TEMPLATE_COLUMNS,
    SDOS_INVENTORY_MAPPING,
    SDOS_INVENTORY_MAPPING_FAIR,
    AliasSpec,
    SupplierColumnMapping,
    discover_tisuc_suffixes,
    location_for_tisuc,
    read_inveptos,
    read_sdos,
    read_supplier_price_list,
    require_columns,
    sdos_inventory_columns,
)
from engine.validation import (
    IssueCode,
    IssueCollector,
    IssueSeverity,
    ValidationError,
    find_duplicate_eans,
    is_valid_ean,
    to_int,
)


# =========================================================================== #
# SDOSXSUC (CSV)
# =========================================================================== #


def test_sdos_conserva_ceros_iniciales_del_ean():
    """El caso que corrompe el catálogo si el CSV se lee como número."""
    csv = build_sdos_csv([sdos_row(codean=EAN_CON_CERO_INICIAL)])
    frame = read_sdos(csv)
    assert frame["Codean"].iloc[0] == EAN_CON_CERO_INICIAL
    assert frame["Codean"].dtype == object
    assert is_valid_ean(frame["Codean"].iloc[0])


def test_sdos_lee_todo_como_texto():
    """Ninguna columna se infiere como numérica, ni siquiera el PVP."""
    csv = build_sdos_csv([sdos_row(codpro="000123", valuni="45900")])
    frame = read_sdos(csv)
    assert frame["Codpro"].iloc[0] == "000123"
    assert isinstance(frame["Valuni"].iloc[0], str)


def test_sdos_decodifica_latin1():
    """Tildes y ñ sobreviven la decodificación Latin-1."""
    csv = build_sdos_csv([sdos_row(nompro="Camión Ñandú Sintético")])
    frame = read_sdos(csv)
    assert frame["Nompro"].iloc[0] == "Camión Ñandú Sintético"


def test_sdos_normaliza_vacios_a_cadena_vacia():
    """Nunca ``NaN``: el resto del motor solo trata con texto."""
    csv = build_sdos_csv([sdos_row(codean="")])
    frame = read_sdos(csv)
    assert frame["Codean"].iloc[0] == ""
    assert not frame.isna().any().any()


def test_sdos_acepta_ruta_y_buffer(tmp_path: Path):
    """Igual que el motor viejo: ``str | Path | BinaryIO``."""
    csv = build_sdos_csv([sdos_row()])
    destino = tmp_path / "sdos.csv"
    destino.write_bytes(csv.getvalue())

    desde_ruta = read_sdos(destino)
    desde_texto = read_sdos(str(destino))
    csv.seek(0)
    desde_buffer = read_sdos(csv)

    assert desde_ruta["Codean"].iloc[0] == EAN_NORMAL
    assert desde_texto["Codean"].iloc[0] == EAN_NORMAL
    assert desde_buffer["Codean"].iloc[0] == EAN_NORMAL


def test_sdos_reporta_todas_las_columnas_faltantes():
    """El mensaje lista **todas** las faltantes, no solo la primera."""
    csv = build_sdos_csv(
        [sdos_row()], columns=["Codpro", "Codean"]
    )
    with pytest.raises(ValidationError) as excinfo:
        read_sdos(csv)
    mensaje = str(excinfo.value)
    assert "Nompro" in mensaje and "Valuni" in mensaje and "Codea2" in mensaje
    assert "SDOSXSUC" in mensaje


# --------------------------------------------------------------------------- #
# Columnas us## dinámicas
# --------------------------------------------------------------------------- #


def test_columnas_us_presentes_se_mapean_a_ubicacion():
    columnas = ["Codpro", "Codean", "us01", "us02", "us06"]
    mapeo = sdos_inventory_columns(columnas)
    assert mapeo == {"us01": "Av. 19", "us02": "Bulevar", "us06": "CEDI"}


def test_columna_us_ausente_significa_inventario_cero_no_error():
    """Contrato §3.1: columna ausente ⇒ 0, nunca excepción."""
    csv = build_sdos_csv(
        [sdos_row(us01="5", us02="7")],
        columns=["Codpro", "Nompro", "Valuni", "Codean", "Codea2", "us01", "us02"],
    )
    frame = read_sdos(csv)
    mapeo = sdos_inventory_columns(frame.columns)
    inventario = {
        location: to_int(frame[column].iloc[0]) for column, location in mapeo.items()
    }
    for location in SDOS_INVENTORY_MAPPING.values():
        assert inventario.get(location, 0) >= 0
    assert inventario["Av. 19"] == 5
    assert inventario.get("CEDI", 0) == 0  # us06 no existe en este archivo


def test_columnas_us_no_mapeadas_se_ignoran():
    """``us07`` (sin uso) y ``us10..us30`` no producen ubicación."""
    mapeo = sdos_inventory_columns(["us01", "us07", "us10", "us30"])
    assert mapeo == {"us01": "Av. 19"}


def test_columnas_us_se_detectan_sin_distinguir_mayusculas():
    assert sdos_inventory_columns(["US01", "Us02"]) == {"US01": "Av. 19", "Us02": "Bulevar"}


def test_modo_feria_solo_cambia_el_mapeo_de_columnas():
    """Modo Feria es metadato de la importación, no un parámetro de cálculo.

    Lo único que cambia es a qué ubicación apunta cada columna del archivo;
    ninguna de las dos variantes altera un cálculo, porque el inventario nunca
    entra a la fórmula (contrato §5.1).
    """
    columnas = [f"us0{n}" for n in range(1, 10)]
    normal = sdos_inventory_columns(columnas, fair_mode=False)
    feria = sdos_inventory_columns(columnas, fair_mode=True)

    assert normal["us05"] == "Oviedo"
    assert feria["us05"] == "Feria"
    assert feria["us07"] == "CEDI"
    assert "us07" not in normal  # sin uso en operación normal
    assert set(normal.values()) <= set(SDOS_INVENTORY_MAPPING.values())
    assert set(feria.values()) <= set(SDOS_INVENTORY_MAPPING_FAIR.values())


# =========================================================================== #
# INVEPTOS (.xls legado)
# =========================================================================== #


def test_inveptos_conserva_ceros_iniciales_del_ean():
    xls = build_inveptos_xls(
        INVEPTOS_HEADER_2_SUCURSALES,
        [inveptos_row(codean=EAN_CON_CERO_INICIAL)],
    )
    frame = read_inveptos(xls)
    assert frame["CODEAN"].iloc[0] == EAN_CON_CERO_INICIAL


def test_inveptos_ean_guardado_como_numero_no_gana_decimales():
    """Si la hoja guardó el EAN como número, vuelve como dígitos, no ``...0``."""
    xls = build_inveptos_xls(
        INVEPTOS_HEADER_2_SUCURSALES,
        [inveptos_row(codean=7701234567890)],
    )
    frame = read_inveptos(xls)
    assert frame["CODEAN"].iloc[0] == "7701234567890"
    assert is_valid_ean(frame["CODEAN"].iloc[0])


def test_inveptos_usa_encoding_explicito():
    """No se depende del fallback silencioso de xlrd a iso-8859-1."""
    xls = build_inveptos_xls(
        INVEPTOS_HEADER_2_SUCURSALES,
        [inveptos_row(detall="Camión Ñandú")],
        encoding="cp1252",
    )
    frame = read_inveptos(xls, encoding="cp1252")
    assert frame["DETALL"].iloc[0] == "Camión Ñandú"


def test_inveptos_acepta_ruta_y_buffer(tmp_path: Path):
    xls = build_inveptos_xls(INVEPTOS_HEADER_2_SUCURSALES, [inveptos_row()])
    destino = tmp_path / "inveptos.xls"
    destino.write_bytes(xls.getvalue())

    assert read_inveptos(destino)["CODEAN"].iloc[0] == EAN_NORMAL
    assert read_inveptos(str(destino))["CODEAN"].iloc[0] == EAN_NORMAL
    xls.seek(0)
    assert read_inveptos(xls)["CODEAN"].iloc[0] == EAN_NORMAL


def test_inveptos_reporta_todas_las_columnas_faltantes():
    xls = build_inveptos_xls(("CODPRO", "CODEAN"), [("SKU-1", EAN_NORMAL)])
    with pytest.raises(ValidationError) as excinfo:
        read_inveptos(xls)
    mensaje = str(excinfo.value)
    for columna in ("COMODI", "DETALL", "VALCOS", "FDESDE", "FHASTA"):
        assert columna in mensaje


# --------------------------------------------------------------------------- #
# Pares TISUC#/UNSUC# dinámicos
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("cantidad", [1, 2, 6, 9])
def test_pares_tisuc_se_descubren_dinamicamente(cantidad):
    """El número de sucursales varía entre exportaciones: nunca asumir uno fijo."""
    columnas = ["CODPRO", "CODEAN"]
    for n in range(1, cantidad + 1):
        columnas += [f"TISUC{n}", f"UNSUC{n}", f"SDSUC{n}"]
    assert discover_tisuc_suffixes(columnas) == [str(n) for n in range(1, cantidad + 1)]


def test_sin_columnas_tisuc_no_falla():
    assert discover_tisuc_suffixes(["CODPRO", "CODEAN", "UNIVTA"]) == []


def test_tisuc_no_confunde_columnas_parecidas():
    assert discover_tisuc_suffixes(["TISUCX", "SDSUC1", "UNSUC1", "TISUC1"]) == ["1"]


def test_tisuc_se_lee_del_archivo_real_generado():
    """El descubrimiento opera sobre las columnas que trae el archivo leído."""
    xls = build_inveptos_xls(INVEPTOS_HEADER_2_SUCURSALES, [inveptos_row()])
    frame = read_inveptos(xls)
    assert discover_tisuc_suffixes(frame.columns) == ["1", "2"]
    assert frame["TISUC1"].iloc[0] == "10000"
    assert to_int(frame["UNSUC1"].iloc[0]) == 10


@pytest.mark.parametrize(
    ("codigo", "ubicacion"),
    [
        ("10000", "Av. 19"),
        ("10010", "Bulevar"),
        ("10500", "Calle 74"),
        ("10510", "Bvista"),
        ("10600", "Feria"),
        ("10800", "Oviedo"),
        ("20010", "CEDI"),
        ("20020", "Full MercadoLibre"),
        ("20030", "Bodega Bqlla"),
    ],
)
def test_catalogo_completo_de_tisuc(codigo, ubicacion):
    issues = IssueCollector()
    assert location_for_tisuc(codigo, issues) == ubicacion
    assert len(issues) == 0


def test_tisuc_desconocido_genera_incidencia_no_descarte_silencioso():
    """Contrato §3.2: hoy se descarta en silencio; en el motor nuevo se reporta."""
    issues = IssueCollector()
    assert location_for_tisuc("99999", issues, row_number=4, sku="SKU-9", ean=EAN_NORMAL) is None

    registradas = issues.by_code(IssueCode.TISUC_DESCONOCIDO)
    assert len(registradas) == 1
    incidencia = registradas[0]
    assert incidencia.severity == IssueSeverity.WARNING
    assert incidencia.source == "INVEPTOS"
    assert incidencia.row_number == 4
    assert "99999" in incidencia.detail


def test_tisuc_vacio_no_es_incidencia():
    """Una columna que no aplica a esa fila no es un problema de datos."""
    issues = IssueCollector()
    assert location_for_tisuc("", issues) is None
    assert location_for_tisuc("   ", issues) is None
    assert location_for_tisuc(None, issues) is None
    assert len(issues) == 0


# =========================================================================== #
# Lista de precios de proveedor
# =========================================================================== #

FILAS_PLANTILLA = [
    (EAN_NORMAL, "Bloques Sintéticos 100 pzs", "$ 32.500,00"),
    (EAN_CON_CERO_INICIAL, "Tren de Madera Sintético", "18.900"),
]


def test_plantilla_normalizada_con_encabezado_en_la_primera_fila():
    xlsx = build_supplier_xlsx(NORMALIZED_TEMPLATE_COLUMNS, FILAS_PLANTILLA)
    lista = read_supplier_price_list(xlsx)
    assert list(lista.columns) == list(NORMALIZED_TEMPLATE_COLUMNS)
    assert lista["EAN-13"].tolist() == [EAN_NORMAL, EAN_CON_CERO_INICIAL]
    assert lista["Costo proveedor"].iloc[0] == "$ 32.500,00"


def test_encabezado_desplazado_se_detecta():
    """Las listas reales traen logos/títulos antes del encabezado."""
    xlsx = build_supplier_xlsx(
        NORMALIZED_TEMPLATE_COLUMNS,
        FILAS_PLANTILLA,
        header_row=7,
        preamble=[["LISTA DE PRECIOS PROVEEDOR SINTÉTICO"], [], ["Vigencia 2026"]],
    )
    lista = read_supplier_price_list(xlsx)
    assert lista["EAN-13"].tolist() == [EAN_NORMAL, EAN_CON_CERO_INICIAL]


def test_encabezado_mas_alla_del_limite_falla_con_mensaje_util():
    xlsx = build_supplier_xlsx(NORMALIZED_TEMPLATE_COLUMNS, FILAS_PLANTILLA, header_row=25)
    with pytest.raises(ValidationError) as excinfo:
        read_supplier_price_list(xlsx, max_header_row=19)
    assert "encabezado" in str(excinfo.value).lower()


def test_espacios_finales_en_encabezados_se_recortan():
    """Obligatorio: varios encabezados reales traen espacios sobrantes."""
    xlsx = build_supplier_xlsx(
        ("EAN-13 ", " Nombre", "Costo proveedor  "), FILAS_PLANTILLA
    )
    lista = read_supplier_price_list(xlsx)
    assert list(lista.columns) == list(NORMALIZED_TEMPLATE_COLUMNS)


def test_ean_del_proveedor_conserva_ceros_iniciales():
    xlsx = build_supplier_xlsx(
        NORMALIZED_TEMPLATE_COLUMNS, [(EAN_CON_CERO_INICIAL, "Producto", "1000")]
    )
    lista = read_supplier_price_list(xlsx)
    assert lista["EAN-13"].iloc[0] == EAN_CON_CERO_INICIAL


def test_ean_corto_del_proveedor_se_conserva():
    xlsx = build_supplier_xlsx(
        NORMALIZED_TEMPLATE_COLUMNS, [(EAN_CORTO, "Producto corto", "500")]
    )
    lista = read_supplier_price_list(xlsx)
    assert lista["EAN-13"].iloc[0] == EAN_CORTO


def test_filas_completamente_vacias_se_descartan():
    xlsx = build_supplier_xlsx(
        NORMALIZED_TEMPLATE_COLUMNS,
        [FILAS_PLANTILLA[0], (None, None, None), FILAS_PLANTILLA[1]],
    )
    lista = read_supplier_price_list(xlsx)
    assert len(lista) == 2


def test_lectura_conserva_las_copias_de_un_ean_duplicado():
    """La lectura no filtra: la exclusión por duplicado es de la etapa siguiente.

    El lector entrega el archivo tal cual (para poder reportar *todas* las
    filas afectadas como incidencia); quien decide excluir es la preparación,
    con :func:`engine.validation.find_duplicate_eans`, que excluye **todas**
    las copias, no solo las repetidas.
    """
    xlsx = build_supplier_xlsx(
        NORMALIZED_TEMPLATE_COLUMNS,
        [
            (EAN_NORMAL, "Producto A", "1.000"),
            (EAN_OTRO, "Producto B", "2.000"),
            (EAN_NORMAL, "Producto A (repetido)", "1.100"),
        ],
    )
    lista = read_supplier_price_list(xlsx)
    assert len(lista) == 3
    assert find_duplicate_eans(lista["EAN-13"]) == {EAN_NORMAL}


def test_columnas_faltantes_en_lista_de_proveedor_dan_error_explicito():
    xlsx = build_supplier_xlsx(("EAN-13", "Nombre"), [(EAN_NORMAL, "Producto")])
    with pytest.raises(ValidationError) as excinfo:
        read_supplier_price_list(xlsx)
    mensaje = str(excinfo.value)
    assert "encabezado" in mensaje.lower() or "Costo proveedor" in mensaje


# --------------------------------------------------------------------------- #
# Alias de columna configurable (ya no cableado a un proveedor)
# --------------------------------------------------------------------------- #


def test_alias_por_defecto_acepta_sinonimos_genericos():
    xlsx = build_supplier_xlsx(
        ("EAN", "Descripción", "Costo"), [(EAN_NORMAL, "Producto", "1000")]
    )
    lista = read_supplier_price_list(xlsx)
    assert list(lista.columns) == list(NORMALIZED_TEMPLATE_COLUMNS)
    assert lista["Nombre"].iloc[0] == "Producto"


def test_mapeo_configurado_por_proveedor_lee_encabezados_propios():
    """El caso 'lista real': se resuelve con configuración, no con heurística.

    Los encabezados largos de un proveedor concreto son **configuración**
    (persistida por proveedor en base de datos), no reglas del motor.
    """
    encabezados = (
        "ITEM",
        "LINEA",
        "CODIGO",
        "EAN-13",
        "DESCRIPCION DEL ARTICULO",
        "P.V.P UNITARIO SIN I.V.A 2026",
        "PVP CON DESCUENTO PARA DISTRIBUIDOR ANTES DE IVA",
        "UNIDAD DE EMPAQUE",
    )
    fila = (
        "1",
        "JUGUETERIA",
        "COD-001",
        EAN_NORMAL,
        "Set de bloques sintético",
        "$ 40.000,00",
        "$ 28.000,00",
        "6",
    )
    mapping = SupplierColumnMapping.from_config(
        {
            "ean": "EAN-13",
            "name": "DESCRIPCION DEL ARTICULO",
            "cost": "PVP CON DESCUENTO PARA DISTRIBUIDOR ANTES DE IVA",
        }
    )
    xlsx = build_supplier_xlsx(encabezados, [fila], header_row=7)
    lista = read_supplier_price_list(xlsx, mapping)

    assert lista["EAN-13"].iloc[0] == EAN_NORMAL
    assert lista["Nombre"].iloc[0] == "Set de bloques sintético"
    assert lista["Costo proveedor"].iloc[0] == "$ 28.000,00"


def test_mapeo_admite_alias_por_tokens_para_encabezados_variables():
    """``contains_all`` cubre encabezados que cambian de año en año."""
    mapping = SupplierColumnMapping.from_config(
        {
            "ean": ["EAN-13"],
            "name": {"contains_all": [["descripcion", "articulo"]]},
            "cost": {"contains_all": [["pvp", "descuento", "iva"]]},
        }
    )
    xlsx = build_supplier_xlsx(
        (
            "EAN-13",
            "DESCRIPCION DEL ARTICULO",
            "PVP CON DESCUENTO DISTRIBUIDOR ANTES DE IVA 2027",
        ),
        [(EAN_NORMAL, "Producto", "$ 1.000,00")],
    )
    lista = read_supplier_price_list(xlsx, mapping)
    assert lista["Costo proveedor"].iloc[0] == "$ 1.000,00"


def test_alias_no_distingue_mayusculas_ni_espacios():
    spec = AliasSpec(aliases=("Costo proveedor",))
    assert spec.find(["  COSTO PROVEEDOR "]) == "COSTO PROVEEDOR"
    assert spec.find(["Otra columna"]) is None


def test_alias_prioriza_el_nombre_exacto_sobre_el_token():
    """Si existe la columna canónica, gana sobre cualquier coincidencia parcial."""
    spec = AliasSpec(
        aliases=("Costo proveedor",),
        contains_all=(("pvp", "descuento"),),
    )
    assert spec.find(["PVP CON DESCUENTO", "Costo proveedor"]) == "Costo proveedor"


def test_mapeo_incompleto_es_error_de_configuracion():
    with pytest.raises(ValidationError) as excinfo:
        SupplierColumnMapping.from_config({"ean": "EAN-13"})
    assert "name" in str(excinfo.value) and "cost" in str(excinfo.value)


def test_error_de_resolucion_lista_las_columnas_disponibles():
    """El comprador debe poder ver qué trae su archivo para configurar el alias."""
    with pytest.raises(ValidationError) as excinfo:
        DEFAULT_SUPPLIER_COLUMNS.resolve(["Columna A", "Columna B"])
    mensaje = str(excinfo.value)
    assert "Columna A" in mensaje and "Columna B" in mensaje
    assert "Costo proveedor" in mensaje


# =========================================================================== #
# require_columns
# =========================================================================== #


def test_require_columns_pasa_cuando_estan_todas():
    frame = pd.DataFrame(columns=["A", "B"])
    require_columns(frame, ["A", "B"], "Fuente")


def test_require_columns_enumera_todas_las_faltantes():
    frame = pd.DataFrame(columns=["A"])
    with pytest.raises(ValidationError) as excinfo:
        require_columns(frame, ["A", "B", "C"], "Fuente")
    assert "B, C" in str(excinfo.value)
    assert "Fuente" in str(excinfo.value)


# =========================================================================== #
# Higiene: ninguna prueba toca datos comerciales
# =========================================================================== #


def test_ningun_modulo_referencia_archivos_comerciales_del_repositorio():
    """Prueba estructural (plan §16.7): fixtures sintéticas, nunca datos reales.

    Los nombres prohibidos se descubren en tiempo de ejecución a partir de los
    archivos de datos que estén en la raíz del repositorio, para no tener que
    escribirlos como literal en esta misma prueba.
    """
    repo_root = Path(__file__).resolve().parents[2]
    extensiones = {".csv", ".xls", ".xlsx"}
    comerciales = [
        f.name
        for f in repo_root.glob("*")
        if f.is_file() and f.suffix.lower() in extensiones
    ]

    revisados = list((repo_root / "engine").glob("*.py"))
    revisados += list(Path(__file__).parent.glob("*.py"))
    assert revisados, "no se encontraron módulos que revisar"

    for modulo in revisados:
        arbol = ast.parse(modulo.read_text(encoding="utf-8"))
        literales = [
            nodo.value
            for nodo in ast.walk(arbol)
            if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str)
        ]
        for literal in literales:
            texto = literal.strip()
            for nombre in comerciales:
                # Se compara el literal completo: mencionar ``INVEPTOS.XLS`` como
                # nombre de formato en un docstring es legítimo; usarlo como
                # ruta de archivo no lo es.
                assert texto != nombre and not texto.endswith(f"/{nombre}"), (
                    f"{modulo.name} abre el archivo comercial '{nombre}'"
                )
