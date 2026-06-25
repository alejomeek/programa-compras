from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from procurement_engine import (
    AnalysisConfig,
    OPERATIVE_LOCATIONS,
    analyze,
    make_provider_template,
    read_inveptos,
    read_provider,
    read_sdos,
    result_to_excel,
)


st.set_page_config(page_title="Compras Jugando y Educando", layout="wide")

LOCAL_SDOS = Path("SDOSXSUC (7).CSV")
LOCAL_INVEPTOS = Path("INVEPTOS.XLS")
LOCAL_PROVIDER = Path("LISTA DE PRECIOS JUGANDO Y EDUCANDO.xls")


def main() -> None:
    st.title("Compras Jugando y Educando")
    st.caption("MVP para cruzar inventario TBC, ventas históricas y lista de precios del proveedor.")

    with st.sidebar:
        st.header("Archivos")
        use_local = st.checkbox(
            "Usar archivos locales de ejemplo",
            value=LOCAL_SDOS.exists() and LOCAL_INVEPTOS.exists() and LOCAL_PROVIDER.exists(),
            help="Útil para trabajar desde esta carpeta. En Streamlit Cloud normalmente se suben los archivos.",
        )

        sdos_file = st.file_uploader("SDOSXSUC.CSV", type=["csv"])
        inveptos_file = st.file_uploader("INVEPTOS.XLS", type=["xls"])
        provider_file = st.file_uploader("Plantilla proveedor", type=["xlsx", "xls"])

        st.download_button(
            "Descargar plantilla proveedor",
            data=make_provider_template(),
            file_name="plantilla_proveedor_jugando_y_educando.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )

        st.header("Proveedor")
        supplier_code = st.text_input("Comodín proveedor", value="745", max_chars=3)
        supplier_name = st.text_input("Nombre proveedor", value="SPEKTRA")
        fair_mode = st.toggle("Modo Feria", value=False)

        st.header("Reposición")
        global_days = st.number_input("Días objetivo global", min_value=1, max_value=365, value=45, step=1)
        global_minimum = st.number_input("Mínimo quiebre global", min_value=0, max_value=999, value=1, step=1)

    if not _inputs_ready(use_local, sdos_file, inveptos_file, provider_file):
        st.info("Carga los archivos o activa los archivos locales de ejemplo para iniciar el análisis.")
        return

    st.subheader("Parámetros por ubicación")
    default_config = pd.DataFrame(
        {
            "Ubicación": OPERATIVE_LOCATIONS,
            "Días objetivo": [int(global_days)] * len(OPERATIVE_LOCATIONS),
            "Mínimo quiebre": [int(global_minimum)] * len(OPERATIVE_LOCATIONS),
        }
    )
    config_table = st.data_editor(
        default_config,
        hide_index=True,
        use_container_width=True,
        column_config={
            "Días objetivo": st.column_config.NumberColumn(min_value=1, max_value=365, step=1),
            "Mínimo quiebre": st.column_config.NumberColumn(min_value=0, max_value=999, step=1),
        },
    )

    run = st.button("Ejecutar análisis", type="primary", use_container_width=True)
    if not run and "analysis_result" not in st.session_state:
        return

    if run:
        try:
            with st.spinner("Leyendo archivos y calculando recomendaciones..."):
                sdos_df = read_sdos(LOCAL_SDOS if use_local and sdos_file is None else sdos_file)
                inveptos_df = read_inveptos(LOCAL_INVEPTOS if use_local and inveptos_file is None else inveptos_file)
                provider_df = read_provider(LOCAL_PROVIDER if use_local and provider_file is None else provider_file)

                target_days = dict(zip(config_table["Ubicación"], config_table["Días objetivo"]))
                stockout_minimums = dict(zip(config_table["Ubicación"], config_table["Mínimo quiebre"]))
                result = analyze(
                    sdos_df=sdos_df,
                    inveptos_df=inveptos_df,
                    provider_df=provider_df,
                    config=AnalysisConfig(
                        supplier_code=supplier_code,
                        supplier_name=supplier_name,
                        fair_mode=fair_mode,
                        target_days=target_days,
                        stockout_minimums=stockout_minimums,
                    ),
                )
            st.session_state.analysis_result = result
        except Exception as exc:
            st.error(str(exc))
            return

    result = st.session_state.analysis_result
    for warning in result.warnings:
        st.warning(warning)

    excel_bytes = result_to_excel(result)
    st.download_button(
        "Descargar Excel del análisis",
        data=excel_bytes,
        file_name=f"analisis_compras_{supplier_code or 'proveedor'}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

    render_tabs(result)


def render_tabs(result) -> None:
    tabs = st.tabs(
        [
            "Resumen",
            "Inventario objetivo",
            "Compra sugerida",
            "Compra sugerida resumida",
            "Redistribución sugerida",
            "Revisión manual",
            "Cambios de costo",
            "Productos nuevos",
            "Descontinuados / no encontrados",
            "Sin costo TBC",
            "Problemas de datos",
        ]
    )

    with tabs[0]:
        st.dataframe(result.summary, use_container_width=True, hide_index=True)

    with tabs[1]:
        st.dataframe(general_search(result.inventory_objective, "inventario objetivo"), use_container_width=True, hide_index=True)

    with tabs[2]:
        df = purchase_filters(result.purchase)
        st.dataframe(df, use_container_width=True, hide_index=True)

    with tabs[3]:
        st.dataframe(general_search(result.purchase_summary, "compra sugerida resumida"), use_container_width=True, hide_index=True)

    with tabs[4]:
        st.dataframe(general_search(result.transfers, "redistribución"), use_container_width=True, hide_index=True)

    with tabs[5]:
        st.dataframe(general_search(result.manual_review, "revisión manual"), use_container_width=True, hide_index=True)

    with tabs[6]:
        st.dataframe(general_search(result.cost_changes, "cambios de costo"), use_container_width=True, hide_index=True)

    with tabs[7]:
        st.dataframe(general_search(result.new_products, "productos nuevos"), use_container_width=True, hide_index=True)

    with tabs[8]:
        st.dataframe(general_search(result.discontinued, "descontinuados"), use_container_width=True, hide_index=True)

    with tabs[9]:
        st.dataframe(general_search(result.no_tbc_cost, "sin costo TBC"), use_container_width=True, hide_index=True)

    with tabs[10]:
        st.dataframe(general_search(result.data_issues, "problemas de datos"), use_container_width=True, hide_index=True)


def purchase_filters(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        st.info("No hay registros para mostrar.")
        return df

    c1, c2 = st.columns([2, 1])
    query = c1.text_input("Buscar por SKU, EAN o producto", key="purchase_search")
    only_purchase = c2.checkbox("Solo compra > 0", value=True)
    location = st.selectbox("Tienda con compra sugerida", ["Todas"] + OPERATIVE_LOCATIONS)

    filtered = _filter_query(df, query)
    if only_purchase and "Compra total sugerida" in filtered:
        filtered = filtered[filtered["Compra total sugerida"] > 0]
    if location != "Todas":
        col = f"{location} | Compra sugerida"
        if col in filtered:
            filtered = filtered[filtered[col] > 0]
    return filtered


def general_search(df: pd.DataFrame, key_prefix: str) -> pd.DataFrame:
    if df.empty:
        st.info("No hay registros para mostrar.")
        return df
    query = st.text_input("Buscar por SKU, EAN o producto", key=f"search_{key_prefix}")
    return _filter_query(df, query)


def _filter_query(df: pd.DataFrame, query: str) -> pd.DataFrame:
    if not query:
        return df
    query = query.strip().lower()
    candidate_cols = [c for c in ["SKU", "EAN", "Producto"] if c in df.columns]
    if not candidate_cols:
        return df
    mask = pd.Series(False, index=df.index)
    for col in candidate_cols:
        mask = mask | df[col].astype(str).str.lower().str.contains(query, na=False)
    return df[mask]


def _inputs_ready(use_local: bool, sdos_file, inveptos_file, provider_file) -> bool:
    if use_local and LOCAL_SDOS.exists() and LOCAL_INVEPTOS.exists() and LOCAL_PROVIDER.exists():
        return True
    return sdos_file is not None and inveptos_file is not None and provider_file is not None


if __name__ == "__main__":
    main()
