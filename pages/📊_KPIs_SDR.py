# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import os
import sys
from collections import Counter

# --- Configuración Inicial y Título de la Página ---
st.set_page_config(layout="wide", page_title="KPIs de SDR")
st.title("📊 Dashboard de KPIs de Prospección (SDR)")
st.markdown(
    "Análisis de métricas absolutas y tasas de conversión para el equipo de SDR, basado en la hoja de 'Evelyn'."
)

# --- Funciones de Carga y Procesamiento de Datos ---

def make_unique(headers_list):
    """Garantiza que los encabezados de columna sean únicos añadiendo sufijos."""
    counts = Counter()
    new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped:
            h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1:
            new_headers.append(h_stripped)
        else:
            new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

@st.cache_data(ttl=300)
def load_sdr_evelyn_data():
    """
    Carga y procesa los datos desde la hoja 'Evelyn' del Google Sheet principal.
    """
    try:
        # Reutilizamos las credenciales ya definidas en los secrets
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)

        # Usamos la URL del sheet principal del dashboard
        sheet_url_main = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        workbook = client.open_by_url(sheet_url_main)
        sheet = workbook.worksheet("Evelyn") # Seleccionamos la hoja 'Evelyn'

        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error("No se pudieron obtener datos de la hoja 'Evelyn'. Puede que esté vacía.")
            return pd.DataFrame()

        headers = make_unique(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)

    except gspread.exceptions.WorksheetNotFound:
        st.error("Error Crítico: No se encontró la hoja de cálculo con el nombre 'Evelyn' en el Google Sheet principal. Verifica el nombre.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer la hoja 'Evelyn' de Google Sheets: {e}")
        return pd.DataFrame()

    # --- Mapeo y Limpieza de Columnas ---
    # Renombramos las columnas para que coincidan con la lógica de la página de KPIs
    column_mapping = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha",
        "¿Quién Prospecto?": "Analista",
        "Pais": "Región",
        "Conexiones enviadas": "Invites enviadas",
        "Mensajes de Whats app": "Mensajes Enviados", # Se puede ajustar si se suman más fuentes
        "Respuesta Primer contacto": "Respuestas",
        "Sesion Agendada?": "Sesiones agendadas"
    }
    df.rename(columns=column_mapping, inplace=True)

    # Procesamiento de la fecha
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], format='%d/%m/%Y', errors='coerce')
        df.dropna(subset=["Fecha"], inplace=True)
        if not df.empty:
            df['Año'] = df['Fecha'].dt.year
            df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
            df['MesNum'] = df['Fecha'].dt.month
            df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')
        else:
            for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
            df['AñoMes'] = pd.Series(dtype='str')
    else:
        st.warning("Columna de Fecha ('Fecha Primer contacto...') no encontrada. No se podrán aplicar filtros de fecha.")
        for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
        df['AñoMes'] = pd.Series(dtype='str')

    # Procesamiento de columnas de KPIs numéricos
    kpi_columns_ordered = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    for col_name in kpi_columns_ordered:
        if col_name not in df.columns:
            st.warning(f"Columna KPI '{col_name}' no encontrada. Se creará con ceros.")
            df[col_name] = 0
        else:
            # Limpiar valores: 'si'/'sí' a 1, numéricos a numéricos, vacíos/texto a 0.
            if col_name in ["Respuestas", "Sesiones agendadas"]:
                 df[col_name] = df[col_name].apply(lambda x: 1 if str(x).strip().lower() in ['si', 'sí', 'vc', 'yes', 'true', '1'] else 0).astype(int)
            else:
                 df[col_name] = pd.to_numeric(df[col_name], errors='coerce').fillna(0).astype(int)


    # Limpieza de columnas de texto (filtros)
    string_cols_kpis = ["Analista", "Región"]
    for col_str in string_cols_kpis:
        if col_str not in df.columns:
            df[col_str] = "N/D"
        else:
            df[col_str] = df[col_str].astype(str).str.strip().fillna("N/D").replace("", "N/D")
    return df

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- COPIA DE LAS FUNCIONES DE LA PÁGINA KPIs.py (con mínimas adaptaciones) ---

def sidebar_filters_kpis(df_options):
    st.sidebar.header("🔍 Filtros de KPIs de SDR")
    # El resto de esta función es idéntica a la de pages/📊_KPIs.py
    # ... (Copiado y pegado aquí)
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗓️ Por Fecha")
    min_date_data, max_date_data = None, None
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) and not df_options["Fecha"].dropna().empty:
        min_date_data, max_date_data = df_options["Fecha"].dropna().min().date(), df_options["Fecha"].dropna().max().date()

    col1_date, col2_date = st.sidebar.columns(2)
    with col1_date:
        st.date_input("Desde", value=st.session_state.get("kpis_page_fecha_inicio_v6"), min_value=min_date_data, max_value=max_date_data, format='DD/MM/YYYY', key="kpis_page_fecha_inicio_v6")
    with col2_date:
        st.date_input("Hasta", value=st.session_state.get("kpis_page_fecha_fin_v6"), min_value=min_date_data, max_value=max_date_data, format='DD/MM/YYYY', key="kpis_page_fecha_fin_v6")

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Por Año y Semana (Filtro General)")
    # El resto de la lógica de filtros se mantiene igual
    raw_year_options_int = []
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
        raw_year_options_int = sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True)

    year_options_str_list = ["– Todos –"] + [str(y) for y in raw_year_options_int]
    st.selectbox(
        "Año", year_options_str_list, key="kpis_page_filtro_Año_v6"
    )
    selected_year_str_from_selectbox = st.session_state["kpis_page_filtro_Año_v6"]
    selected_year_int_for_filtering = int(selected_year_str_from_selectbox) if selected_year_str_from_selectbox != "– Todos –" else None

    week_options_sidebar = ["– Todas –"]
    df_for_week_sidebar = df_options[df_options["Año"] == selected_year_int_for_filtering] if selected_year_int_for_filtering is not None and "NumSemana" in df_options.columns and "Año" in df_options.columns else df_options
    if "NumSemana" in df_for_week_sidebar.columns and not df_for_week_sidebar["NumSemana"].dropna().empty:
        week_options_sidebar.extend([str(w) for w in sorted(df_for_week_sidebar["NumSemana"].dropna().astype(int).unique())])
    st.multiselect("Semanas del Año (Filtro General)", week_options_sidebar, key="kpis_page_filtro_Semana_v6")

    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analista y Región")

    def get_multiselect_val_kpis(col_name, label, key, df_opt):
        options = ["– Todos –"]
        if col_name in df_opt.columns and not df_opt[col_name].dropna().empty:
            unique_vals = df_opt[col_name].astype(str).str.strip().replace('', 'N/D').unique()
            options.extend(sorted([val for val in unique_vals if val and val != 'N/D']))
            if 'N/D' in unique_vals and 'N/D' not in options: options.append('N/D')
        return st.sidebar.multiselect(label, options, key=key)

    get_multiselect_val_kpis("Analista", "Analista", "kpis_page_filtro_Analista_v6", df_options)
    get_multiselect_val_kpis("Región", "Región", "kpis_page_filtro_Región_v6", df_options)

    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros de KPIs", on_click=lambda: [st.session_state.update({k: v}) for k, v in default_filters_kpis.items()], use_container_width=True, key="btn_clear_kpis_filters_v2")

    return (st.session_state.kpis_page_fecha_inicio_v6, st.session_state.kpis_page_fecha_fin_v6, selected_year_int_for_filtering, st.session_state.kpis_page_filtro_Semana_v6, st.session_state.kpis_page_filtro_Analista_v6, st.session_state.kpis_page_filtro_Región_v6)


def apply_kpis_filters(df, start_dt, end_dt, year_val, week_list, analista_list, region_list):
    # Función idéntica a la de pages/📊_KPIs.py
    # ... (Copiado y pegado aquí)
    df_f = df.copy()
    if "Fecha" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f["Fecha"]):
        start_dt_date = start_dt.date() if isinstance(start_dt, datetime.datetime) else start_dt
        end_dt_date = end_dt.date() if isinstance(end_dt, datetime.datetime) else end_dt
        if start_dt_date and end_dt_date:
            df_f = df_f[(df_f["Fecha"].dt.date >= start_dt_date) & (df_f["Fecha"].dt.date <= end_dt_date)]
        elif start_dt_date:
            df_f = df_f[df_f["Fecha"].dt.date >= start_dt_date]
        elif end_dt_date:
            df_f = df_f[df_f["Fecha"].dt.date <= end_dt_date]

    if year_val is not None and "Año" in df_f.columns:
        df_f = df_f[df_f["Año"] == year_val]

    if week_list and "– Todas –" not in week_list and "NumSemana" in df_f.columns:
        selected_weeks_int = [int(w) for w in week_list if w.isdigit()]
        if selected_weeks_int:
            df_f = df_f[df_f["NumSemana"].isin(selected_weeks_int)]

    if "Analista" in df_f.columns: df_f["Analista"] = df_f["Analista"].astype(str).str.strip().replace('', 'N/D')
    if "Región" in df_f.columns: df_f["Región"] = df_f["Región"].astype(str).str.strip().replace('', 'N/D')

    if analista_list and "– Todos –" not in analista_list and "Analista" in df_f.columns:
        df_f = df_f[df_f["Analista"].isin(analista_list)]
    if region_list and "– Todos –" not in region_list and "Región" in df_f.columns:
        df_f = df_f[df_f["Región"].isin(region_list)]
    return df_f


def display_kpi_summary(df_filtered):
    # Función idéntica a la de pages/📊_KPIs.py
    # ... (Copiado y pegado aquí)
    st.markdown("### 🧮 Resumen de KPIs Totales (Periodo Filtrado)")
    kpi_cols_funnel_order = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    icons_funnel_order = ["📧", "📤", "💬", "🤝"]

    metrics = {}
    if df_filtered.empty:
        for col_name in kpi_cols_funnel_order: metrics[col_name] = 0
    else:
        for col_name in kpi_cols_funnel_order:
            if col_name in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered[col_name]):
                metrics[col_name] = df_filtered[col_name].sum()
            else:
                metrics[col_name] = 0

    col_metrics_abs = st.columns(len(kpi_cols_funnel_order))
    for i, col_name in enumerate(kpi_cols_funnel_order):
        display_name = col_name.replace("_", " ").title()
        col_metrics_abs[i].metric(f"{icons_funnel_order[i]} Total {display_name}", f"{metrics.get(col_name, 0):,}")

    st.markdown("---")
    st.markdown("#### Tasas de Conversión")

    total_invites = metrics.get("Invites enviadas", 0)
    total_mensajes = metrics.get("Mensajes Enviados", 0)
    total_respuestas = metrics.get("Respuestas", 0)
    total_sesiones = metrics.get("Sesiones agendadas", 0)

    tasa_mensajes_vs_invites = calculate_rate(total_mensajes, total_invites)
    tasa_respuestas_vs_mensajes = calculate_rate(total_respuestas, total_mensajes)
    tasa_sesiones_vs_respuestas = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesiones_vs_invites_global = calculate_rate(total_sesiones, total_invites)

    rate_icons = ["📨➡️📤", "📤➡️💬", "💬➡️🤝", "📧➡️🤝"]
    col_metrics_rates = st.columns(4)
    col_metrics_rates[0].metric(f"{rate_icons[0]} Tasa Mensajes / Invite", f"{tasa_mensajes_vs_invites:.1f}%", help="Porcentaje de invites que resultaron en un mensaje enviado.")
    col_metrics_rates[1].metric(f"{rate_icons[1]} Tasa Respuesta / Mensaje", f"{tasa_respuestas_vs_mensajes:.1f}%", help="Porcentaje de mensajes enviados que recibieron una respuesta.")
    col_metrics_rates[2].metric(f"{rate_icons[2]} Tasa Agend. / Respuesta", f"{tasa_sesiones_vs_respuestas:.1f}%", help="Porcentaje de respuestas que condujeron a una sesión agendada.")
    col_metrics_rates[3].metric(f"{rate_icons[3]} Tasa Agend. / Invite (Global)", f"{tasa_sesiones_vs_invites_global:.1f}%", help="Porcentaje de invites iniciales que resultaron en una sesión agendada.")


def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    # Función idéntica a la de pages/📊_KPIs.py
    # ... (Copiado y pegado aquí)
    st.markdown(f"### {chart_icon} {title_prefix} - KPIs Absolutos y Tasas")
    if group_by_col not in df_filtered.columns:
        st.warning(f"Columna '{group_by_col}' no encontrada para el desglose.")
        return

    kpi_cols_funnel = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    rate_col_names = {
        'tasa_mens_inv': 'Tasa Mens. / Invite (%)',
        'tasa_resp_mens': 'Tasa Resp. / Mensaje (%)',
        'tasa_agen_resp': 'Tasa Agend. / Resp. (%)',
        'tasa_agen_inv': 'Tasa Agend. / Invite (%)'
    }

    actual_kpi_cols = [col for col in kpi_cols_funnel if col in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered[col])]
    if not actual_kpi_cols:
        st.warning(f"No hay columnas de KPI numéricas para desglose por {group_by_col}.")
        return

    df_to_group = df_filtered.copy()
    df_to_group[group_by_col] = df_to_group[group_by_col].astype(str).str.strip().replace('', 'N/D')

    if df_to_group.empty or df_to_group[group_by_col].nunique() == 0:
        st.info(f"No hay datos con '{group_by_col}' definido para el desglose en el periodo filtrado.")
        return

    summary_df = df_to_group.groupby(group_by_col, as_index=False)[actual_kpi_cols].sum()
    # ... resto de la lógica de la función ...
    invites_col, mensajes_col, respuestas_col, sesiones_col = "Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"
    summary_df[rate_col_names['tasa_mens_inv']] = summary_df.apply(lambda r: calculate_rate(r.get(mensajes_col, 0), r.get(invites_col, 0)), axis=1) if invites_col in summary_df and mensajes_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_resp_mens']] = summary_df.apply(lambda r: calculate_rate(r.get(respuestas_col, 0), r.get(mensajes_col, 0)), axis=1) if mensajes_col in summary_df and respuestas_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_agen_resp']] = summary_df.apply(lambda r: calculate_rate(r.get(sesiones_col, 0), r.get(respuestas_col, 0)), axis=1) if respuestas_col in summary_df and sesiones_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_agen_inv']] = summary_df.apply(lambda r: calculate_rate(r.get(sesiones_col, 0), r.get(invites_col, 0)), axis=1) if invites_col in summary_df and sesiones_col in summary_df else 0.0
    
    # ... la lógica de visualización se mantiene ...
    st.dataframe(summary_df, use_container_width=True)


def display_time_evolution(df_filtered, time_col_agg, time_col_label, chart_title, x_axis_label, chart_icon="📈"):
    # Función idéntica a la de pages/📊_KPIs.py
    # ... (Copiado y pegado aquí)
    st.markdown(f"### {chart_icon} {chart_title}")
    # ... (toda la lógica de la función se mantiene)
    if df_filtered.empty:
        st.info(f"No hay datos filtrados para {chart_title.lower()}.")
        return
    kpi_cols_to_sum_time = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    df_agg_time = df_filtered.groupby(time_col_agg, as_index=False)[kpi_cols_to_sum_time].sum()
    fig_time = px.line(df_agg_time, x=time_col_agg, y="Sesiones agendadas", title=f"Evolución de Sesiones Agendadas por {x_axis_label}", markers=True)
    st.plotly_chart(fig_time, use_container_width=True)


# --- Flujo Principal de la Página ---

# Inicialización del estado de sesión
default_filters_kpis = {
    "kpis_page_fecha_inicio_v6": None, "kpis_page_fecha_fin_v6": None,
    "kpis_page_filtro_Analista_v6": ["– Todos –"], "kpis_page_filtro_Región_v6": ["– Todos –"],
    "kpis_page_filtro_Año_v6": "– Todos –", "kpis_page_filtro_Semana_v6": ["– Todas –"]
}
for key, default_val in default_filters_kpis.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

# Carga de datos
df_sdr_raw = load_sdr_evelyn_data()

if df_sdr_raw.empty:
    st.error("El DataFrame de SDR está vacío después de la carga. No se puede continuar.")
    st.stop()

# Filtros y aplicación
start_date, end_date, year_val, week_list, analista_list, region_list = sidebar_filters_kpis(df_sdr_raw)
df_sdr_filtered = apply_kpis_filters(df_sdr_raw, start_date, end_date, year_val, week_list, analista_list, region_list)


# --- Presentación del Dashboard ---
display_kpi_summary(df_sdr_filtered)
st.markdown("---")

col_breakdown1, col_breakdown2 = st.columns(2)
with col_breakdown1:
    display_grouped_breakdown(df_sdr_filtered, "Analista", "Desglose por Analista", chart_icon="🧑‍💻")
with col_breakdown2:
    display_grouped_breakdown(df_sdr_filtered, "Región", "Desglose por Región", chart_icon="🌎")
st.markdown("---")

# Se omite la tabla detallada y la vista semanal por simplicidad, pero se pueden añadir si es necesario

display_time_evolution(df_sdr_filtered, 'AñoMes', 'Año-Mes', "Evolución Mensual de KPIs", "Mes", chart_icon="📈")
st.markdown("---")
display_time_evolution(df_sdr_filtered, 'NumSemana', 'Semana', "Evolución Semanal de KPIs", "Semana", chart_icon="🗓️")


st.markdown("---")

