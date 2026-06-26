from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

import pandas as pd


OPERATIVE_LOCATIONS = ["Av. 19", "Bulevar", "Oviedo", "Bvista", "Calle 74", "CEDI"]
STORE_PRIORITY = {"Av. 19": 0, "Bulevar": 1, "Oviedo": 2, "Bvista": 3, "Calle 74": 4}
TISUC_TO_LOCATION = {
    "10000": "Av. 19",
    "10010": "Bulevar",
    "10500": "Calle 74",
    "10510": "Bvista",
    "10600": "Feria",
    "10800": "Oviedo",
    "20010": "CEDI",
    "20020": "Full MercadoLibre",
    "20030": "Bodega Bqlla",
}
REFERENCE_LOCATIONS = ["Full MercadoLibre", "Feria", "Bodega Bqlla"]
ALL_OUTPUT_LOCATIONS = OPERATIVE_LOCATIONS + REFERENCE_LOCATIONS
SPANISH_MONTHS = {
    "ene": 1,
    "feb": 2,
    "mar": 3,
    "abr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "ago": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dic": 12,
}


@dataclass
class AnalysisConfig:
    supplier_code: str
    supplier_name: str = ""
    fair_mode: bool = False
    target_days: dict[str, int] | None = None
    stockout_minimums: dict[str, int] | None = None


@dataclass
class AnalysisResult:
    summary: pd.DataFrame
    carmen_file: pd.DataFrame
    inventory_objective: pd.DataFrame
    purchase: pd.DataFrame
    purchase_summary: pd.DataFrame
    purchase_order_items: pd.DataFrame
    transfers: pd.DataFrame
    manual_review: pd.DataFrame
    cost_changes: pd.DataFrame
    new_products: pd.DataFrame
    discontinued: pd.DataFrame
    no_tbc_cost: pd.DataFrame
    data_issues: pd.DataFrame
    warnings: list[str]
    period_start: datetime | None
    period_end: datetime | None
    period_days: int


def read_sdos(source: str | Path | BinaryIO) -> pd.DataFrame:
    return pd.read_csv(source, sep=";", encoding="latin1", dtype=str).fillna("")


def read_inveptos(source: str | Path | BinaryIO) -> pd.DataFrame:
    return pd.read_excel(source, engine="xlrd", dtype=str).fillna("")


def read_provider(source: str | Path | BinaryIO) -> pd.DataFrame:
    data = _read_excel_any_header(source, required=["EAN-13"])
    data.columns = [str(c).strip() for c in data.columns]
    cost_col = _find_provider_cost_column(data.columns)
    if cost_col is None:
        raise ValueError("La plantilla proveedor debe tener la columna 'Costo proveedor'.")
    name_col = _find_provider_name_column(data.columns)
    if name_col is None:
        raise ValueError("La plantilla proveedor debe tener la columna 'Nombre'.")
    provider = data[["EAN-13", name_col, cost_col]].copy()
    provider = provider.rename(columns={name_col: "Nombre", cost_col: "Costo proveedor"})
    return provider.fillna("")


def make_provider_template() -> bytes:
    output = BytesIO()
    pd.DataFrame(columns=["EAN-13", "Nombre", "Costo proveedor"]).to_excel(output, index=False, engine="openpyxl")
    return output.getvalue()


def analyze(
    sdos_df: pd.DataFrame,
    inveptos_df: pd.DataFrame,
    provider_df: pd.DataFrame,
    config: AnalysisConfig,
) -> AnalysisResult:
    warnings: list[str] = []
    issues: list[dict] = []
    _require_columns(sdos_df, ["Codpro", "Nompro", "Valuni", "Codean", "Codea2"], "SDOSXSUC")
    _require_columns(provider_df, ["EAN-13", "Nombre", "Costo proveedor"], "Proveedor")

    supplier_code = str(config.supplier_code).strip()
    if not re.fullmatch(r"\d{3}", supplier_code):
        raise ValueError("El comodín proveedor debe tener exactamente 3 dígitos.")

    target_days = {loc: int((config.target_days or {}).get(loc, 45)) for loc in OPERATIVE_LOCATIONS}
    stockout_minimums = {loc: int((config.stockout_minimums or {}).get(loc, 1)) for loc in OPERATIVE_LOCATIONS}

    sdos = _prepare_sdos(sdos_df, config.fair_mode, issues)
    carmen_file = _build_carmen_file(sdos_df, config.fair_mode)
    provider = _prepare_provider(provider_df, issues)

    supplier_all = sdos[sdos["comodin"] == supplier_code].copy()
    if supplier_all.empty:
        raise ValueError(f"No se encontraron productos para el comodín {supplier_code} en SDOSXSUC.")

    for _, row in supplier_all[~supplier_all["ean_valido"]].iterrows():
        issues.append(_issue("SDOSXSUC", "EAN inválido", row.get("Codpro", ""), row.get("Codean", ""), row.get("Nompro", ""), "Producto excluido del cruce por EAN."))
    duplicated_sdos = supplier_all[supplier_all["ean_valido"] & supplier_all.duplicated("ean", keep=False)]
    for _, row in duplicated_sdos.iterrows():
        issues.append(_issue("SDOSXSUC", "EAN duplicado", row.get("Codpro", ""), row.get("Codean", ""), row.get("Nompro", ""), "EAN duplicado en SDOSXSUC para el proveedor analizado."))

    supplier_products = supplier_all[supplier_all["ean_valido"]].copy()
    if supplier_products.empty:
        raise ValueError(f"Los productos del comodín {supplier_code} no tienen EAN válido en SDOSXSUC.")

    if inveptos_df is None or inveptos_df.empty:
        warnings.append("INVEPTOS está vacío; se continuará con ventas en 0 y sin costo TBC.")
        sales_prepared = _empty_sales()
        period_start = period_end = None
        period_days = 1
    else:
        _require_columns(inveptos_df, ["CODPRO", "COMODI", "DETALL", "VALUNI", "VALCOS", "FDESDE", "FHASTA", "CODEAN"], "INVEPTOS")
        sales_prepared, period_start, period_end, period_days = _prepare_sales(inveptos_df, supplier_code, issues)
        if sales_prepared.empty:
            warnings.append(f"No se encontraron ventas para el comodín {supplier_code} en INVEPTOS; se continuará con ventas en 0.")

    all_sdos_eans = set(sdos.loc[sdos["ean_valido"], "ean"])
    provider_valid = provider[provider["ean_valido"] & provider["costo_valido"] & ~provider["ean_duplicado"]].copy()
    supplier_eans = set(supplier_products["ean"])
    provider_eans = set(provider_valid["ean"])

    common_eans = sorted(supplier_eans & provider_eans)
    supplier_not_in_provider = supplier_products[~supplier_products["ean"].isin(provider_eans)].copy()
    provider_not_in_sdos = provider_valid[~provider_valid["ean"].isin(all_sdos_eans)].copy()

    sales_by_ean = sales_prepared.set_index("ean") if not sales_prepared.empty else pd.DataFrame()
    purchase_rows: list[dict] = []
    purchase_summary_rows: list[dict] = []
    purchase_order_rows: list[dict] = []
    inventory_objective_rows: list[dict] = []
    transfer_rows: list[dict] = []
    review_rows: list[dict] = []

    provider_by_ean = provider_valid.drop_duplicates("ean").set_index("ean", drop=False)
    supplier_by_ean = supplier_products.drop_duplicates("ean").set_index("ean", drop=False)

    for ean in common_eans:
        product = supplier_by_ean.loc[ean]
        provider_row = provider_by_ean.loc[ean]
        sales_row = sales_by_ean.loc[ean] if ean in sales_by_ean.index else None
        result = _analyze_product(
            product=product,
            provider_row=provider_row,
            sales_row=sales_row,
            target_days=target_days,
            stockout_minimums=stockout_minimums,
            period_days=period_days,
            product_status="Comprable",
        )
        for transfer in result["transfers"]:
            transfer["Estado producto"] = "Comprable"
        inventory_objective_rows.append(_as_inventory_objective(result["purchase"], "Comprable"))
        purchase_rows.append(result["purchase"])
        purchase_summary_rows.append(result["purchase_summary"])
        purchase_order_rows.extend(_as_purchase_order_rows(result["purchase"], provider_row["costo_proveedor"], "Existente"))
        transfer_rows.extend(result["transfers"])
        review_rows.extend(result["manual_review"])

    discontinued_redistribution_eans = sorted(set(supplier_not_in_provider["ean"]))
    for ean in discontinued_redistribution_eans:
        product = supplier_by_ean.loc[ean]
        sales_row = sales_by_ean.loc[ean] if ean in sales_by_ean.index else None
        result = _analyze_product(
            product=product,
            provider_row=None,
            sales_row=sales_row,
            target_days=target_days,
            stockout_minimums=stockout_minimums,
            period_days=period_days,
            apply_stockout_minimum=True,
            product_status="Descontinuado / no encontrado en lista proveedor",
        )
        inventory_objective_rows.append(
            _as_inventory_objective(result["purchase"], "Descontinuado / no encontrado en lista proveedor")
        )
        review_rows.extend(result["manual_review"])
        for transfer in result["transfers"]:
            transfer["Estado producto"] = "Descontinuado / no encontrado en lista proveedor"
        transfer_rows.extend(result["transfers"])

    purchase = pd.DataFrame(purchase_rows)
    purchase_summary = pd.DataFrame(purchase_summary_rows)
    inventory_objective = pd.DataFrame(inventory_objective_rows)
    transfers = pd.DataFrame(transfer_rows)
    manual_review = pd.DataFrame(review_rows)

    no_tbc_cost = _build_no_tbc_cost(supplier_products, provider_valid, sales_prepared)
    cost_changes = _build_cost_changes(supplier_products, provider_valid, sales_prepared)
    new_products = _build_new_products(provider_not_in_sdos)
    purchase_order_rows.extend(_new_product_purchase_order_rows(new_products))
    purchase_order_items = pd.DataFrame(purchase_order_rows)
    discontinued = _build_discontinued(supplier_not_in_provider)
    data_issues = pd.DataFrame(issues)
    summary = _build_summary(
        config=config,
        supplier_products=supplier_products,
        provider_valid=provider_valid,
        purchase=purchase,
        transfers=transfers,
        manual_review=manual_review,
        cost_changes=cost_changes,
        new_products=new_products,
        discontinued=discontinued,
        no_tbc_cost=no_tbc_cost,
        data_issues=data_issues,
        period_start=period_start,
        period_end=period_end,
        period_days=period_days,
    )

    return AnalysisResult(
        summary=summary,
        carmen_file=_clean_df(carmen_file),
        inventory_objective=_order_inventory_objective_columns(_clean_df(inventory_objective)),
        purchase=_order_purchase_columns(_clean_df(purchase)),
        purchase_summary=_order_purchase_summary_columns(_clean_df(purchase_summary)),
        purchase_order_items=_order_purchase_order_columns(_clean_df(purchase_order_items)),
        transfers=_clean_df(transfers),
        manual_review=_order_manual_review_columns(_clean_df(manual_review)),
        cost_changes=_clean_df(cost_changes),
        new_products=_clean_df(new_products),
        discontinued=_clean_df(discontinued),
        no_tbc_cost=_clean_df(no_tbc_cost),
        data_issues=_clean_df(data_issues),
        warnings=warnings,
        period_start=period_start,
        period_end=period_end,
        period_days=period_days,
    )


def result_to_excel(result: AnalysisResult) -> bytes:
    output = BytesIO()
    sheets = {
        "Resumen": result.summary,
        "Archivo Carmen": result.carmen_file,
        "Inventario objetivo": result.inventory_objective,
        "Compra sugerida": result.purchase,
        "Compra sugerida resumida": result.purchase_summary,
        "Redistribucion sugerida": result.transfers,
        "Revision manual": result.manual_review,
        "Cambios de costo": result.cost_changes,
        "Productos nuevos": result.new_products,
        "Descontinuados no encontrados": result.discontinued,
        "Sin costo TBC": result.no_tbc_cost,
        "Problemas de datos": result.data_issues,
    }
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        workbook = writer.book
        summary_palette = {
            "Av. 19": "#E7F0FF",
            "Bulevar": "#EAF7EA",
            "Oviedo": "#FFF1DA",
            "Bvista": "#F4EAFE",
            "Calle 74": "#E8F7F5",
            "CEDI": "#FFF0F0",
        }
        default_header = workbook.add_format({"bold": True, "bg_color": "#F2F2F2", "border": 1})
        frozen_header = workbook.add_format({"bold": True, "bg_color": "#D9EAF7", "border": 1})
        frozen_body = workbook.add_format({"bg_color": "#F7FBFF", "border": 1})
        location_formats = {
            loc: workbook.add_format({"bg_color": color, "border": 1})
            for loc, color in summary_palette.items()
        }
        location_header_formats = {
            loc: workbook.add_format({"bold": True, "bg_color": color, "border": 1})
            for loc, color in summary_palette.items()
        }
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31]
            df.to_excel(writer, sheet_name=safe_name, index=False)
            worksheet = writer.sheets[safe_name]
            if not df.empty:
                freeze_col = 3 if list(df.columns[:3]) == ["SKU", "EAN", "Producto"] else 0
                worksheet.freeze_panes(1, freeze_col)
                worksheet.autofilter(0, 0, len(df), max(len(df.columns) - 1, 0))
            for idx, col in enumerate(df.columns):
                width = _excel_autofit_width(df, col)
                header_format = default_header
                body_format = None
                if sheet_name == "Compra sugerida resumida":
                    if idx <= 2:
                        body_format = frozen_body
                        header_format = frozen_header
                    else:
                        location = next((loc for loc in OPERATIVE_LOCATIONS if str(col).startswith(f"{loc} |")), None)
                        if location:
                            body_format = location_formats[location]
                            header_format = location_header_formats[location]
                worksheet.set_column(idx, idx, width)
                worksheet.write(0, idx, col, header_format)
                if sheet_name == "Compra sugerida resumida" and body_format is not None:
                    for row_idx, value in enumerate(df[col].tolist(), start=1):
                        if pd.isna(value):
                            worksheet.write_blank(row_idx, idx, None, body_format)
                        else:
                            worksheet.write(row_idx, idx, value, body_format)
    return output.getvalue()


def _excel_autofit_width(df: pd.DataFrame, column: str) -> int:
    values = [str(column)]
    if not df.empty:
        values.extend("" if pd.isna(value) else str(value) for value in df[column].tolist())
    max_len = max((len(value) for value in values), default=10)
    return min(max(max_len + 2, 10), 45)


def _read_excel_any_header(source: str | Path | BinaryIO, required: list[str]) -> pd.DataFrame:
    last_error: Exception | None = None
    for header in range(0, 20):
        try:
            df = pd.read_excel(source, header=header, dtype=str)
            cols = [str(c).strip() for c in df.columns]
            if all(req in cols for req in required):
                df.columns = cols
                return df
        except Exception as exc:
            last_error = exc
        if hasattr(source, "seek"):
            source.seek(0)
    if last_error:
        raise last_error
    raise ValueError(f"No se encontraron las columnas requeridas: {', '.join(required)}")


def _find_provider_cost_column(columns) -> str | None:
    stripped = [str(c).strip() for c in columns]
    if "Costo proveedor" in stripped:
        return "Costo proveedor"
    for col in stripped:
        upper = col.upper()
        if "PVP CON DESCUENTO" in upper and "JUGANDO" in upper and "IVA" in upper:
            return col
    return None


def _find_provider_name_column(columns) -> str | None:
    stripped = [str(c).strip() for c in columns]
    if "Nombre" in stripped:
        return "Nombre"
    for col in stripped:
        upper = col.upper()
        if "DESCRIPCION" in upper and "ARTICULO" in upper:
            return col
    return None


def _require_columns(df: pd.DataFrame, columns: list[str], source: str) -> None:
    missing = [c for c in columns if c not in df.columns]
    if missing:
        raise ValueError(f"Faltan columnas obligatorias en {source}: {', '.join(missing)}")


def _prepare_sdos(df: pd.DataFrame, fair_mode: bool, issues: list[dict]) -> pd.DataFrame:
    sdos = df.copy().fillna("")
    sdos["sku"] = sdos["Codpro"].astype(str).str.strip()
    sdos["producto"] = sdos["Nompro"].astype(str).str.strip()
    sdos["pvp_actual"] = sdos["Valuni"].apply(_to_number)
    sdos["ean"] = sdos["Codean"].astype(str)
    sdos["ean_valido"] = sdos["ean"].apply(_is_valid_ean)
    sdos["comodin"] = sdos["Codea2"].apply(_extract_supplier_code)

    mapping = _sdos_inventory_mapping(fair_mode)
    for loc in ALL_OUTPUT_LOCATIONS:
        col = next((c for c, mapped_loc in mapping.items() if mapped_loc == loc), None)
        sdos[f"inv_{loc}"] = sdos[col].apply(_to_int) if col and col in sdos.columns else 0

    return sdos


def _prepare_provider(df: pd.DataFrame, issues: list[dict]) -> pd.DataFrame:
    provider = df.copy().fillna("")
    provider = provider[
        provider["EAN-13"].astype(str).str.strip().ne("")
        | provider["Nombre"].astype(str).str.strip().ne("")
        | provider["Costo proveedor"].astype(str).str.strip().ne("")
    ].copy()
    provider["ean"] = provider["EAN-13"].astype(str)
    provider["nombre_proveedor"] = provider["Nombre"].astype(str).str.strip()
    provider["ean_valido"] = provider["ean"].apply(_is_valid_ean)
    provider["costo_proveedor"] = provider["Costo proveedor"].apply(_to_number)
    provider["costo_valido"] = provider["costo_proveedor"].notna()
    provider["ean_duplicado"] = provider["ean_valido"] & provider.duplicated("ean", keep=False)
    for _, row in provider[~provider["ean_valido"]].iterrows():
        issues.append(_issue("Proveedor", "EAN inválido", "", row.get("EAN-13", ""), "", "Fila excluida del cruce."))
    for _, row in provider[provider["ean_valido"] & ~provider["costo_valido"]].iterrows():
        issues.append(_issue("Proveedor", "Costo proveedor inválido", "", row.get("EAN-13", ""), "", "Fila excluida del cruce."))
    for _, row in provider[provider["ean_duplicado"]].iterrows():
        issues.append(_issue("Proveedor", "EAN duplicado", "", row.get("EAN-13", ""), "", "Fila excluida del cruce."))
    return provider


def _prepare_sales(df: pd.DataFrame, supplier_code: str, issues: list[dict]) -> tuple[pd.DataFrame, datetime | None, datetime | None, int]:
    sales = df.copy().fillna("")
    sales["ean"] = sales["CODEAN"].astype(str)
    sales["ean_valido"] = sales["ean"].apply(_is_valid_ean)
    sales["comodin"] = sales["COMODI"].apply(_extract_supplier_code)
    supplier_sales = sales[sales["comodin"] == supplier_code].copy()

    for _, row in supplier_sales[~supplier_sales["ean_valido"]].iterrows():
        issues.append(_issue("INVEPTOS", "EAN inválido", row.get("CODPRO", ""), row.get("CODEAN", ""), row.get("DETALL", ""), "Fila excluida del cruce."))

    duplicated = supplier_sales[supplier_sales["ean_valido"] & supplier_sales.duplicated("ean", keep=False)]
    for _, row in duplicated.iterrows():
        issues.append(_issue("INVEPTOS", "EAN duplicado", row.get("CODPRO", ""), row.get("CODEAN", ""), row.get("DETALL", ""), "EAN duplicado en INVEPTOS."))

    valid = supplier_sales[supplier_sales["ean_valido"] & ~supplier_sales.duplicated("ean", keep=False)].copy()
    if valid.empty:
        return _empty_sales(), None, None, 1

    period_start = _parse_tbc_date(valid["FDESDE"].iloc[0])
    period_end = _parse_tbc_date(valid["FHASTA"].iloc[0])
    period_days = max(1, (period_end - period_start).days + 1) if period_start and period_end else 1
    records: list[dict] = []
    for _, row in valid.iterrows():
        rec = {
            "ean": row["ean"],
            "sku_ventas": str(row.get("CODPRO", "")).strip(),
            "producto_ventas": str(row.get("DETALL", "")).strip(),
            "costo_tbc": _to_number(row.get("VALCOS", "")),
        }
        for loc in ALL_OUTPUT_LOCATIONS:
            rec[f"ventas_{loc}"] = 0
            rec[f"inv_ventas_{loc}"] = 0
        for col in [c for c in valid.columns if re.fullmatch(r"TISUC\d+", str(c))]:
            suffix = re.search(r"(\d+)$", col).group(1)
            loc = TISUC_TO_LOCATION.get(str(row.get(col, "")).strip())
            if not loc:
                continue
            rec[f"ventas_{loc}"] += _to_int(row.get(f"UNSUC{suffix}", 0))
            rec[f"inv_ventas_{loc}"] += _to_int(row.get(f"SDSUC{suffix}", 0))
        records.append(rec)
    return pd.DataFrame(records), period_start, period_end, period_days


def _empty_sales() -> pd.DataFrame:
    return pd.DataFrame(columns=["ean", "sku_ventas", "producto_ventas", "costo_tbc"])


def _analyze_product(
    product,
    provider_row,
    sales_row,
    target_days,
    stockout_minimums,
    period_days: int,
    apply_stockout_minimum: bool = True,
    product_status: str = "Comprable",
) -> dict:
    base = {
        "SKU": product["sku"],
        "EAN": product["ean"],
        "Producto": product["producto"],
        "PVP actual": product["pvp_actual"],
    }
    needs: dict[str, int] = {}
    excess: dict[str, int] = {}
    received = {loc: 0 for loc in OPERATIVE_LOCATIONS}
    initial_need: dict[str, int] = {}
    target_units: dict[str, int] = {}
    review_flags: list[str] = []
    manual_review: list[dict] = []

    for loc in OPERATIVE_LOCATIONS:
        inv = int(product[f"inv_{loc}"])
        sold = _sales_units_for_location(sales_row, loc)
        days = int(target_days[loc])
        minimum = int(stockout_minimums[loc])
        if sold > 0:
            objective = math.ceil((sold / period_days) * days)
            need = max(0, objective - inv)
        elif inv > 0:
            objective = 0
            need = 0
        elif apply_stockout_minimum:
            objective = max(0, minimum)
            need = max(0, minimum)
            if need > 0:
                review_flags.append(loc)
                manual_review.append({
                    **base,
                    "Estado producto": product_status,
                    "Ubicación": loc,
                    "Ventas periodo": sold,
                    "Inventario actual": inv,
                    "Mínimo aplicado": need,
                    "Motivo": _manual_review_reason(product_status),
                })
        else:
            objective = 0
            need = 0
        needs[loc] = need
        initial_need[loc] = need
        target_units[loc] = objective
        excess[loc] = max(0, inv - objective)

    excess["Bodega Bqlla"] = int(product["inv_Bodega Bqlla"])
    excess["Full MercadoLibre"] = 0
    excess["Feria"] = 0

    transfers: list[dict] = []
    _cover_with_source_pool(base, needs, excess, received, transfers, ["Bvista", "Calle 74"], ["Bodega Bqlla"], "Bodega Bqlla prioritaria para Barranquilla")
    _cover_with_source_pool(base, needs, excess, received, transfers, ["Av. 19", "Bulevar", "Oviedo", "Bvista", "Calle 74"], ["CEDI"], "CEDI como fuente prioritaria")
    _cover_with_source_pool(base, needs, excess, received, transfers, ["Av. 19", "Bulevar"], ["Av. 19", "Bulevar"], "Redistribución local Bogotá")
    _cover_with_source_pool(base, needs, excess, received, transfers, ["Bvista", "Calle 74"], ["Bvista", "Calle 74"], "Redistribución local Barranquilla")

    purchase = dict(base)
    purchase_summary = {
        "SKU": product["sku"],
        "EAN": product["ean"],
        "Producto": product["producto"],
    }
    total_purchase = 0
    for loc in OPERATIVE_LOCATIONS:
        inv = int(product[f"inv_{loc}"])
        sold = _sales_units_for_location(sales_row, loc)
        final_purchase = int(needs[loc])
        total_purchase += final_purchase
        purchase[f"{loc} | Objetivo unidades"] = target_units[loc]
        purchase[f"{loc} | Inventario actual"] = inv
        purchase[f"{loc} | Redistribución recibida"] = received[loc]
        purchase[f"{loc} | Compra sugerida"] = final_purchase
        purchase_summary[f"{loc} | Stock actual"] = inv
        purchase_summary[f"{loc} | Venta"] = sold
        purchase_summary[f"{loc} | Compra sugerida"] = final_purchase

    purchase["Compra total sugerida"] = total_purchase
    return {
        "purchase": purchase,
        "purchase_summary": purchase_summary,
        "transfers": transfers,
        "manual_review": manual_review,
    }


def _cover_with_source_pool(base, needs, excess, received, transfers, destinations, sources, rule):
    while True:
        eligible_destinations = [d for d in destinations if needs.get(d, 0) > 0]
        eligible_sources = [s for s in sources if excess.get(s, 0) > 0]
        if not eligible_destinations or not eligible_sources:
            return
        dest = sorted(eligible_destinations, key=lambda d: (-needs[d], STORE_PRIORITY.get(d, 99)))[0]
        available_sources = [s for s in eligible_sources if s != dest]
        if not available_sources:
            return
        source = sorted(available_sources, key=lambda s: (-excess[s], STORE_PRIORITY.get(s, 99)))[0]
        qty = min(needs[dest], excess[source])
        if qty <= 0:
            return
        needs[dest] -= qty
        excess[source] -= qty
        received[dest] += qty
        transfers.append({
            **base,
            "Origen": source,
            "Destino": dest,
            "Cantidad": qty,
            "Regla aplicada": rule,
        })


def _sales_units_for_location(sales_row, loc: str) -> int:
    if sales_row is None:
        return 0
    if loc == "CEDI":
        return _sales_value(sales_row, "ventas_CEDI", 0) + _sales_value(sales_row, "ventas_Full MercadoLibre", 0)
    return _sales_value(sales_row, f"ventas_{loc}", 0)


def _manual_review_reason(product_status: str) -> str:
    if product_status == "Comprable":
        return "Comprable sin ventas y sin inventario; posible quiebre y puede afectar compra."
    return "Descontinuado sin ventas y sin inventario; no se compra, pero puede redistribuirse si hay inventario disponible."


def _sales_value(sales_row, key: str, default):
    if sales_row is None:
        return default
    try:
        value = sales_row[key]
    except Exception:
        return default
    if pd.isna(value) or value == "":
        return default
    if isinstance(default, int):
        return int(value)
    return value


def _build_cost_changes(supplier_products, provider_valid, sales_prepared) -> pd.DataFrame:
    if sales_prepared.empty:
        return pd.DataFrame()
    merged = (
        supplier_products[["sku", "ean", "producto", "pvp_actual"]]
        .merge(provider_valid[["ean", "costo_proveedor"]], on="ean", how="inner")
        .merge(sales_prepared[["ean", "costo_tbc"]], on="ean", how="inner")
    )
    merged = merged[merged["costo_tbc"].notna()]
    changed = merged[merged["costo_tbc"] != merged["costo_proveedor"]].copy()
    if changed.empty:
        return pd.DataFrame()
    changed["Diferencia costo"] = changed["costo_proveedor"] - changed["costo_tbc"]
    changed["Diferencia porcentual"] = changed.apply(
        lambda r: f"{(r['Diferencia costo'] / r['costo_tbc']) * 100:.2f}%" if r["costo_tbc"] else "",
        axis=1,
    )
    changed = changed.rename(columns={
        "sku": "SKU",
        "ean": "EAN",
        "producto": "Producto",
        "pvp_actual": "PVP actual",
        "costo_tbc": "Costo TBC",
        "costo_proveedor": "Costo proveedor",
    })
    return changed[
        [
            "SKU",
            "EAN",
            "Producto",
            "PVP actual",
            "Costo proveedor",
            "Costo TBC",
            "Diferencia costo",
            "Diferencia porcentual",
        ]
    ]


def _build_no_tbc_cost(supplier_products, provider_valid, sales_prepared) -> pd.DataFrame:
    provider_eans = set(provider_valid["ean"])
    sales_eans = set(sales_prepared["ean"]) if not sales_prepared.empty else set()
    missing = supplier_products[supplier_products["ean"].isin(provider_eans) & ~supplier_products["ean"].isin(sales_eans)].copy()
    if missing.empty:
        return pd.DataFrame()
    return missing[["sku", "ean", "producto", "pvp_actual"]].rename(columns={
        "sku": "SKU",
        "ean": "EAN",
        "producto": "Producto",
        "pvp_actual": "PVP actual",
    })


def _build_new_products(provider_not_in_sdos) -> pd.DataFrame:
    if provider_not_in_sdos.empty:
        return pd.DataFrame()
    return provider_not_in_sdos[["ean", "nombre_proveedor", "costo_proveedor"]].rename(
        columns={"ean": "EAN", "nombre_proveedor": "Nombre", "costo_proveedor": "Costo proveedor"}
    )


def _build_discontinued(supplier_not_in_provider) -> pd.DataFrame:
    if supplier_not_in_provider.empty:
        return pd.DataFrame()
    cols = ["sku", "ean", "producto", "pvp_actual"] + [f"inv_{loc}" for loc in ALL_OUTPUT_LOCATIONS]
    df = supplier_not_in_provider[cols].copy()
    return df.rename(columns={
        "sku": "SKU",
        "ean": "EAN",
        "producto": "Producto",
        "pvp_actual": "PVP actual",
        **{f"inv_{loc}": f"{loc} | Inventario" for loc in ALL_OUTPUT_LOCATIONS},
    })


def _build_summary(**kwargs) -> pd.DataFrame:
    config = kwargs["config"]
    period_start = kwargs["period_start"]
    period_end = kwargs["period_end"]
    rows = [
        ("Proveedor", config.supplier_name or ""),
        ("Comodín", config.supplier_code),
        ("Modo Feria", "Activado" if config.fair_mode else "Desactivado"),
        ("Fecha inicial ventas", period_start.strftime("%Y-%m-%d") if period_start else ""),
        ("Fecha final ventas", period_end.strftime("%Y-%m-%d") if period_end else ""),
        ("Días periodo", kwargs["period_days"]),
        ("Productos proveedor en TBC", len(kwargs["supplier_products"])),
        ("Productos válidos en lista proveedor", len(kwargs["provider_valid"])),
        ("Productos con compra sugerida", int((kwargs["purchase"].get("Compra total sugerida", pd.Series(dtype=int)) > 0).sum()) if not kwargs["purchase"].empty else 0),
        ("Unidades compra sugerida", int(kwargs["purchase"].get("Compra total sugerida", pd.Series(dtype=int)).sum()) if not kwargs["purchase"].empty else 0),
        ("Movimientos de redistribución", len(kwargs["transfers"])),
        ("Productos / ubicaciones en revisión manual", len(kwargs["manual_review"])),
        ("Cambios de costo", len(kwargs["cost_changes"])),
        ("Productos nuevos", len(kwargs["new_products"])),
        ("Descontinuados / no encontrados", len(kwargs["discontinued"])),
        ("Sin costo TBC", len(kwargs["no_tbc_cost"])),
        ("Problemas de datos", len(kwargs["data_issues"])),
    ]
    return pd.DataFrame(rows, columns=["Métrica", "Valor"])


def _sdos_inventory_mapping(fair_mode: bool) -> dict[str, str]:
    if fair_mode:
        return {
            "us01": "Av. 19",
            "us02": "Bulevar",
            "us03": "Calle 74",
            "us04": "Bvista",
            "us05": "Feria",
            "us06": "Oviedo",
            "us07": "CEDI",
            "us08": "Full MercadoLibre",
            "us09": "Bodega Bqlla",
        }
    return {
        "us01": "Av. 19",
        "us02": "Bulevar",
        "us03": "Calle 74",
        "us04": "Bvista",
        "us05": "Oviedo",
        "us06": "CEDI",
        "us07": "Sin uso",
        "us08": "Full MercadoLibre",
        "us09": "Bodega Bqlla",
    }


def _build_carmen_file(sdos_df: pd.DataFrame, fair_mode: bool) -> pd.DataFrame:
    carmen = sdos_df.copy().fillna("")
    mapping = _sdos_inventory_mapping(fair_mode)
    renamed_columns = {}
    for col in carmen.columns:
        if re.fullmatch(r"us\d{2}", str(col)):
            location = mapping.get(col, "Sin mapeo")
            renamed_columns[col] = f"{col} | {location}"
    return carmen.rename(columns=renamed_columns)


def _extract_supplier_code(value) -> str:
    text = str(value).strip()
    match = re.match(r"^\.(\d{3})", text)
    return match.group(1) if match else ""


def _is_valid_ean(value) -> bool:
    text = str(value)
    return bool(text) and text == text.strip() and re.fullmatch(r"\d+", text) is not None


def _to_number(value):
    text = str(value).strip()
    if text == "":
        return None
    text = text.replace("$", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value) -> int:
    number = _to_number(value)
    if number is None or pd.isna(number):
        return 0
    return int(round(number))


def _parse_tbc_date(value) -> datetime | None:
    text = str(value).strip()
    match = re.match(r"^(\d{1,2})-([A-Za-zÁÉÍÓÚáéíóúñÑ]{3})-(\d{2,4})$", text)
    if not match:
        parsed = pd.to_datetime(text, errors="coerce", dayfirst=True)
        return None if pd.isna(parsed) else parsed.to_pydatetime()
    day = int(match.group(1))
    month = SPANISH_MONTHS.get(match.group(2).lower()[:3])
    year = int(match.group(3))
    if year < 100:
        year += 2000
    return datetime(year, month, day) if month else None


def _issue(source: str, issue_type: str, sku: str, ean: str, product: str, detail: str) -> dict:
    return {
        "Fuente": source,
        "Tipo": issue_type,
        "SKU": sku,
        "EAN": ean,
        "Producto": product,
        "Detalle": detail,
    }


def _clean_df(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df.fillna("")


def _order_manual_review_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    ordered = [
        "SKU",
        "EAN",
        "Producto",
        "PVP actual",
        "Estado producto",
        "Ubicación",
        "Ventas periodo",
        "Inventario actual",
        "Mínimo aplicado",
        "Motivo",
    ]
    existing = [col for col in ordered if col in df.columns]
    rest = [col for col in df.columns if col not in existing]
    return df[existing + rest]


def _order_purchase_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    ordered = ["SKU", "EAN", "Producto", "PVP actual", "Compra total sugerida"]
    for loc in OPERATIVE_LOCATIONS:
        ordered.extend(
            [
                f"{loc} | Objetivo unidades",
                f"{loc} | Inventario actual",
                f"{loc} | Redistribución recibida",
                f"{loc} | Compra sugerida",
            ]
        )
    existing = [col for col in ordered if col in df.columns]
    rest = [col for col in df.columns if col not in existing]
    return df[existing + rest]


def _order_purchase_summary_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    ordered = ["SKU", "EAN", "Producto"]
    for loc in OPERATIVE_LOCATIONS:
        ordered.extend(
            [
                f"{loc} | Stock actual",
                f"{loc} | Venta",
                f"{loc} | Compra sugerida",
            ]
        )
    existing = [col for col in ordered if col in df.columns]
    rest = [col for col in df.columns if col not in existing]
    return df[existing + rest]


def _as_purchase_order_rows(purchase_row: dict, unit_cost, status: str) -> list[dict]:
    rows: list[dict] = []
    for loc in OPERATIVE_LOCATIONS:
        suggested = int(purchase_row.get(f"{loc} | Compra sugerida", 0) or 0)
        rows.append(
            {
                "Estado producto": status,
                "Punto": loc,
                "SKU": purchase_row.get("SKU", ""),
                "EAN": purchase_row.get("EAN", ""),
                "Producto": purchase_row.get("Producto", ""),
                "Compra sugerida": suggested,
                "Compra final": suggested,
                "Costo unitario": unit_cost,
                "Total línea": suggested * (unit_cost or 0),
            }
        )
    return rows


def _new_product_purchase_order_rows(new_products: pd.DataFrame) -> list[dict]:
    rows: list[dict] = []
    if new_products.empty:
        return rows
    for _, product in new_products.iterrows():
        for loc in OPERATIVE_LOCATIONS:
            rows.append(
                {
                    "Estado producto": "Nuevo",
                    "Punto": loc,
                    "SKU": "NUEVO",
                    "EAN": product.get("EAN", ""),
                    "Producto": product.get("Nombre", ""),
                    "Compra sugerida": 0,
                    "Compra final": 0,
                    "Costo unitario": product.get("Costo proveedor", 0),
                    "Total línea": 0,
                }
            )
    return rows


def _order_purchase_order_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    ordered = [
        "Estado producto",
        "Punto",
        "SKU",
        "EAN",
        "Producto",
        "Compra sugerida",
        "Compra final",
        "Costo unitario",
        "Total línea",
    ]
    existing = [col for col in ordered if col in df.columns]
    rest = [col for col in df.columns if col not in existing]
    return df[existing + rest]


def _as_inventory_objective(row: dict, status: str) -> dict:
    detail = {
        "SKU": row.get("SKU", ""),
        "EAN": row.get("EAN", ""),
        "Producto": row.get("Producto", ""),
        "PVP actual": row.get("PVP actual", ""),
        "Estado producto": status,
    }
    for loc in OPERATIVE_LOCATIONS:
        detail[f"{loc} | Objetivo unidades"] = row.get(f"{loc} | Objetivo unidades", 0)
        detail[f"{loc} | Inventario actual"] = row.get(f"{loc} | Inventario actual", 0)
    return detail


def _order_inventory_objective_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    ordered = ["SKU", "EAN", "Producto", "PVP actual", "Estado producto"]
    for loc in OPERATIVE_LOCATIONS:
        ordered.extend([f"{loc} | Objetivo unidades", f"{loc} | Inventario actual"])
    existing = [col for col in ordered if col in df.columns]
    rest = [col for col in df.columns if col not in existing]
    return df[existing + rest]
