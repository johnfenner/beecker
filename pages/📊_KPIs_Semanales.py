# Prospe/pages/📊_KPIs_Semanales.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import os
import sys

# --- Configuración Inicial del Proyecto y Título de la Página ---
st.set_page_config(layout="wide", page_title="KPIs Semanales")

st.title("📊 Dashboard de KPIs y Tasas de Conversión del Funnel") # Título ligeramente ajustado
st.markdown(
    "Análisis de métricas absolutas y tasas de conversión siguiendo el proceso de generación de leads." # Subtítulo ajustado
)

# --- Funciones de Procesamiento de Datos ---
def parse_kpi_value(value_str, column_name=""):
    cleaned_val = str(value_str).strip().lower()
    if not cleaned_val: return 0.0
    try:
        num_val = pd.to_numeric(cleaned_val, errors='raise')
        return 0.0 if pd.isna(num_val) else float(num_val)
    except ValueError:
        pass
    
    if column_name == "Sesiones agendadas": 
        affirmative_session_texts = ['vc', 'si', 'sí', 'yes', 'true', '1', '1.0']
        if cleaned_val in affirmative_session_texts: return 1.0
        return 0.0
    else:
        first_part = cleaned_val.split('-')[0].strip()
        if not first_part: return 0.0
        try:
            num_val_from_part = pd.to_numeric(first_part, errors='raise')
            return 0.0 if pd.isna(num_val_from_part) else float(num_val_from_part)
        except ValueError:
            return 0.0

@st.cache_data(ttl=300)
def load_weekly_kpis_data():
    try:
        creds_from_secrets = st.secrets["gcp_service_account"] 
        client = gspread.service_account_from_dict(creds_from_secrets)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account] o alguna de sus claves en los 'Secrets' de Streamlit (KPIs Semanales).")
        st.stop()
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets para KPIs Semanales vía Secrets: {e}")
        st.stop()

    sheet_url_kpis = st.secrets.get(
        "kpis_sheet_url", 
        "https://docs.google.com/spreadsheets/d/1vaJ2lPK7hbWsuikjmycPePKRrFXiOrlwXMXOdoXRY60/edit?gid=0#gid=0"
    )
    try:
        sheet = client.open_by_url(sheet_url_kpis).sheet1
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos suficientes de Google Sheets para KPIs Semanales (URL: {sheet_url_kpis}).")
            return pd.DataFrame() 
        headers = raw_data[0]
        rows = raw_data[1:]
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de KPIs Semanales en la URL: {sheet_url_kpis}")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja de Google Sheets para KPIs Semanales (URL: {sheet_url_kpis}): {e}")
        st.stop()

    cleaned_headers = [str(h).strip() for h in headers]
    df = pd.DataFrame(rows, columns=cleaned_headers)

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
        st.warning("Columna 'Fecha' no encontrada (KPIs Semanales). No se podrán aplicar filtros de fecha.")
        for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
        df['AñoMes'] = pd.Series(dtype='str')

    # Orden de KPIs deseado para el procesamiento y como referencia
    # (Aunque el orden de parseo no impacta, las columnas deben existir)
    kpi_columns_ordered = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    for col_name in kpi_columns_ordered: # Usar el orden definido para asegurar que se procesan si existen
        if col_name not in df.columns:
            st.warning(f"Columna KPI '{col_name}' no encontrada (KPIs Semanales). Se creará con ceros.")
            df[col_name] = 0
        else:
            # Asegurarse que la columna se procesa correctamente incluso si ya existe
            df[col_name] = df[col_name].apply(lambda x: parse_kpi_value(x, column_name=col_name)).astype(int)


    string_cols_kpis = ["Mes", "Semana", "Analista", "Región"]
    for col_str in string_cols_kpis:
        if col_str not in df.columns:
            df[col_str] = pd.Series(dtype='str')
        else:
            df[col_str] = df[col_str].astype(str).str.strip().fillna("N/D")
    return df

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

df_kpis_semanales_raw = load_weekly_kpis_data()

if df_kpis_semanales_raw.empty:
    st.error("El DataFrame de KPIs Semanales está vacío después de la carga. No se puede continuar.")
    st.stop()

START_DATE_KEY = "kpis_page_fecha_inicio_v6" 
END_DATE_KEY = "kpis_page_fecha_fin_v6"
ANALISTA_FILTER_KEY = "kpis_page_filtro_Analista_v6"
REGION_FILTER_KEY = "kpis_page_filtro_Región_v6"
YEAR_FILTER_KEY = "kpis_page_filtro_Año_v6" 
WEEK_FILTER_KEY = "kpis_page_filtro_Semana_v6" 
DETAILED_VIEW_WEEKS_KEY = "kpis_page_detailed_view_weeks_v1" 

default_filters_kpis = {
    START_DATE_KEY: None, END_DATE_KEY: None,
    ANALISTA_FILTER_KEY: ["– Todos –"], REGION_FILTER_KEY: ["– Todos –"],
    YEAR_FILTER_KEY: "– Todos –", WEEK_FILTER_KEY: ["– Todas –"],
    DETAILED_VIEW_WEEKS_KEY: [] 
}
for key, default_val in default_filters_kpis.items():
    if key not in st.session_state: st.session_state[key] = default_val

def clear_kpis_filters_callback():
    for key, default_val in default_filters_kpis.items():
        st.session_state[key] = default_val
    st.toast("Filtros de KPIs reiniciados ✅", icon="🧹")

def sidebar_filters_kpis(df_options):
    st.sidebar.header("🔍 Filtros de KPIs Semanales")
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗓️ Por Fecha")
    min_date_data, max_date_data = None, None
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) and not df_options["Fecha"].dropna().empty:
        min_date_data, max_date_data = df_options["Fecha"].dropna().min().date(), df_options["Fecha"].dropna().max().date()
    
    col1_date, col2_date = st.sidebar.columns(2)
    with col1_date:
        st.date_input("Desde", value=st.session_state.get(START_DATE_KEY), min_value=min_date_data, max_value=max_date_data, format='DD/MM/YYYY', key=START_DATE_KEY)
    with col2_date:
        st.date_input("Hasta", value=st.session_state.get(END_DATE_KEY), min_value=min_date_data, max_value=max_date_data, format='DD/MM/YYYY', key=END_DATE_KEY)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Por Año y Semana (Filtro General)")

    raw_year_options_int = []
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
        raw_year_options_int = sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True)
    
    year_options_str_list = ["– Todos –"] + [str(y) for y in raw_year_options_int]
    current_year_selection_str = st.session_state.get(YEAR_FILTER_KEY, "– Todos –")
    
    if not isinstance(current_year_selection_str, str):
        current_year_selection_str = str(current_year_selection_str)
    if current_year_selection_str not in year_options_str_list:
        st.session_state[YEAR_FILTER_KEY] = "– Todos –"
        current_year_selection_str = "– Todos –"
    
    try:
        default_index_year = year_options_str_list.index(current_year_selection_str)
    except ValueError:
        st.session_state[YEAR_FILTER_KEY] = "– Todos –"
        current_year_selection_str = "– Todos –"
        default_index_year = year_options_str_list.index("– Todos –")

    selected_year_str_from_selectbox = st.sidebar.selectbox(
        "Año", year_options_str_list, index=default_index_year, key=YEAR_FILTER_KEY 
    )
    selected_year_int_for_filtering = int(selected_year_str_from_selectbox) if selected_year_str_from_selectbox != "– Todos –" else None

    week_options_sidebar = ["– Todas –"] 
    df_for_week_sidebar = df_options[df_options["Año"] == selected_year_int_for_filtering] if selected_year_int_for_filtering is not None and "NumSemana" in df_options.columns and "Año" in df_options.columns else df_options
    if "NumSemana" in df_for_week_sidebar.columns and not df_for_week_sidebar["NumSemana"].dropna().empty:
        week_options_sidebar.extend([str(w) for w in sorted(df_for_week_sidebar["NumSemana"].dropna().astype(int).unique())])
    
    current_week_selection_sidebar = st.session_state.get(WEEK_FILTER_KEY, ["– Todas –"])
    valid_week_selection_sidebar = [s for s in current_week_selection_sidebar if s in week_options_sidebar] or (["– Todas –"] if "– Todas –" in week_options_sidebar else [])
    if valid_week_selection_sidebar != current_week_selection_sidebar: st.session_state[WEEK_FILTER_KEY] = valid_week_selection_sidebar
    st.sidebar.multiselect("Semanas del Año (Filtro General)", week_options_sidebar, key=WEEK_FILTER_KEY, default=valid_week_selection_sidebar)
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analista y Región")

    def get_multiselect_val_kpis(col_name, label, key, df_opt):
        options = ["– Todos –"]
        if col_name in df_opt.columns and not df_opt[col_name].dropna().empty:
            unique_vals = df_opt[col_name].astype(str).str.strip().replace('', 'N/D').unique()
            options.extend(sorted([val for val in unique_vals if val and val != 'N/D']))
            if 'N/D' in unique_vals and 'N/D' not in options: options.append('N/D')
        
        current_selection_ms = st.session_state.get(key, ["– Todos –"])
        if not isinstance(current_selection_ms, list): current_selection_ms = ["– Todos –"]
        valid_selection_ms = [s for s in current_selection_ms if s in options] or (["– Todos –"] if "– Todos –" in options else [])
        if valid_selection_ms != current_selection_ms: st.session_state[key] = valid_selection_ms
        return st.sidebar.multiselect(label, options, key=key, default=valid_selection_ms)

    analista_filter_val = get_multiselect_val_kpis("Analista", "Analista", ANALISTA_FILTER_KEY, df_options)
    region_filter_val = get_multiselect_val_kpis("Región", "Región", REGION_FILTER_KEY, df_options)
    
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros de KPIs", on_click=clear_kpis_filters_callback, use_container_width=True, key="btn_clear_kpis_filters_v2")
    return (st.session_state[START_DATE_KEY], st.session_state[END_DATE_KEY], selected_year_int_for_filtering, st.session_state[WEEK_FILTER_KEY], analista_filter_val, region_filter_val)


def apply_kpis_filters(df, start_dt, end_dt, year_val, week_list, analista_list, region_list):
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

def display_filtered_kpis_table(df_filtered):
    st.markdown("### 📝 Datos Detallados Filtrados (Vista General)")
    if df_filtered.empty:
        st.info("No se encontraron datos que cumplan los criterios de filtro.")
        return
    st.write(f"Mostrando **{len(df_filtered)}** filas.")
    # Orden de columnas deseado para la tabla detallada, siguiendo el funnel
    cols_display_ordered = ["Fecha", "Año", "NumSemana", "AñoMes", "Analista", "Región", 
                           "Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    if "Semana" in df_filtered.columns and "Semana" not in cols_display_ordered: # Asegurar que 'Semana' se inserta si existe y no está ya
        idx = cols_display_ordered.index("NumSemana") + 1 if "NumSemana" in cols_display_ordered else 3
        cols_display_ordered.insert(idx, "Semana")
        
    cols_present = [col for col in cols_display_ordered if col in df_filtered.columns]
    df_display_table = df_filtered[cols_present].copy()
    if "Fecha" in df_display_table.columns:
        df_display_table["Fecha"] = df_display_table["Fecha"].dt.strftime('%d/%m/%Y')
    st.dataframe(df_display_table, use_container_width=True, height=300)

def display_kpi_summary(df_filtered):
    st.markdown("### 🧮 Resumen de KPIs Totales y Tasas del Funnel (Periodo Filtrado)")
    
    # Orden de KPIs según el funnel de generación de leads
    kpi_cols_funnel_order = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    # Iconos correspondientes al orden del funnel
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
                st.warning(f"Advertencia: La columna '{col_name}' para el resumen de KPIs no es numérica o no existe. Se mostrará como 0.")


    col_metrics_abs = st.columns(len(kpi_cols_funnel_order))
    for i, col_name in enumerate(kpi_cols_funnel_order):
        # Usar el nombre completo para 'Invites enviadas' y 'Sesiones agendadas' para mayor claridad
        display_name = col_name # Por defecto usa el nombre de la columna
        if col_name == "Invites enviadas":
            display_name = "Invites Enviadas"
        elif col_name == "Mensajes Enviados":
            display_name = "Mensajes Enviados"
        elif col_name == "Sesiones agendadas":
            display_name = "Sesiones Agendadas"
        
        col_metrics_abs[i].metric(f"{icons_funnel_order[i]} Total {display_name}", f"{metrics.get(col_name, 0):,}")
    
    st.markdown("---")
    st.markdown("#### Tasas de Conversión del Funnel")

    total_invites = metrics.get("Invites enviadas", 0)
    total_mensajes = metrics.get("Mensajes Enviados", 0)
    total_respuestas = metrics.get("Respuestas", 0)
    total_sesiones = metrics.get("Sesiones agendadas", 0)

    # Tasas calculadas siguiendo el funnel
    tasa_mensajes_vs_invites = calculate_rate(total_mensajes, total_invites)
    tasa_respuestas_vs_mensajes = calculate_rate(total_respuestas, total_mensajes)
    tasa_sesiones_vs_respuestas = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesiones_vs_invites_global = calculate_rate(total_sesiones, total_invites) # Tasa de conversión general

    # Iconos para las tasas
    rate_icons = ["📨➡️📤", "📤➡️💬", "💬➡️🤝", "📧➡️🤝"] 
    
    col_metrics_rates = st.columns(4) 
    col_metrics_rates[0].metric(f"{rate_icons[0]} Tasa Mensajes / Invite", f"{tasa_mensajes_vs_invites:.1f}%",
                                help="Porcentaje de invites que resultaron en un mensaje enviado. (Mensajes Enviados / Invites enviadas)")
    col_metrics_rates[1].metric(f"{rate_icons[1]} Tasa Respuesta / Mensaje", f"{tasa_respuestas_vs_mensajes:.1f}%",
                                help="Porcentaje de mensajes enviados que recibieron una respuesta. (Respuestas / Mensajes Enviados)")
    col_metrics_rates[2].metric(f"{rate_icons[2]} Tasa Agend. / Respuesta", f"{tasa_sesiones_vs_respuestas:.1f}%",
                                help="Porcentaje de respuestas que condujeron a una sesión agendada. (Sesiones agendadas / Respuestas)")
    col_metrics_rates[3].metric(f"{rate_icons[3]} Tasa Agend. / Invite (Global)", f"{tasa_sesiones_vs_invites_global:.1f}%",
                                help="Porcentaje de invites iniciales que resultaron en una sesión agendada. (Sesiones agendadas / Invites enviadas)")


def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    st.markdown(f"### {chart_icon} {title_prefix} - KPIs Absolutos y Tasas")
    if group_by_col not in df_filtered.columns:
        st.warning(f"Columna '{group_by_col}' no encontrada para el desglose.")
        return
    
    # Orden de KPIs según el funnel
    kpi_cols_funnel = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    
    # Nombres de las columnas de tasas para claridad, siguiendo el funnel
    rate_col_names = {
        'tasa_mens_inv': 'Tasa Mens. / Invite (%)',      # Mensajes / Invites
        'tasa_resp_mens': 'Tasa Resp. / Mensaje (%)',   # Respuestas / Mensajes
        'tasa_agen_resp': 'Tasa Agend. / Resp. (%)',    # Sesiones / Respuestas
        'tasa_agen_inv': 'Tasa Agend. / Invite (%)'     # Sesiones / Invites (Global)
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
    
    invites_col = "Invites enviadas"
    mensajes_col = "Mensajes Enviados"
    respuestas_col = "Respuestas"
    sesiones_col = "Sesiones agendadas"
    
    # Calcular tasas basadas en el funnel
    summary_df[rate_col_names['tasa_mens_inv']] = summary_df.apply(lambda r: calculate_rate(r.get(mensajes_col, 0), r.get(invites_col, 0)), axis=1) if invites_col in summary_df and mensajes_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_resp_mens']] = summary_df.apply(lambda r: calculate_rate(r.get(respuestas_col, 0), r.get(mensajes_col, 0)), axis=1) if mensajes_col in summary_df and respuestas_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_agen_resp']] = summary_df.apply(lambda r: calculate_rate(r.get(sesiones_col, 0), r.get(respuestas_col, 0)), axis=1) if respuestas_col in summary_df and sesiones_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_agen_inv']] = summary_df.apply(lambda r: calculate_rate(r.get(sesiones_col, 0), r.get(invites_col, 0)), axis=1) if invites_col in summary_df and sesiones_col in summary_df else 0.0
    
    if not summary_df.empty:
        # Ordenar las columnas para la tabla: Agrupador, KPIs en orden de funnel, Tasas en orden de funnel
        cols_for_display_table = [group_by_col] + actual_kpi_cols + list(rate_col_names.values())
        summary_df_display = summary_df[cols_for_display_table].copy()
        
        for kpi_col_disp in actual_kpi_cols: summary_df_display[kpi_col_disp] = summary_df_display[kpi_col_disp].map('{:,}'.format)
        for rate_name_key in rate_col_names: summary_df_display[rate_col_names[rate_name_key]] = summary_df_display[rate_col_names[rate_name_key]].map('{:.1f}%'.format)
        
        st.markdown("##### Tabla Resumen (Absolutos y Tasas)")
        st.dataframe(summary_df_display.set_index(group_by_col), use_container_width=True) 
        st.markdown("---")
        
        if sesiones_col in summary_df.columns and summary_df[sesiones_col].sum() > 0:
            st.markdown("##### Gráfico: Sesiones Agendadas (Absoluto)")
            fig_abs = px.bar(summary_df.sort_values(by=sesiones_col, ascending=False), x=group_by_col, y=sesiones_col, title=f"Sesiones Agendadas por {group_by_col}", color=sesiones_col, text_auto=True, color_continuous_scale=px.colors.sequential.Teal)
            fig_abs.update_traces(texttemplate='%{y:,}') 
            fig_abs.update_layout(title_x=0.5, xaxis_tickangle=-45, yaxis_title="Total Sesiones Agendadas", xaxis_title=group_by_col, margin=dict(b=150))
            st.plotly_chart(fig_abs, use_container_width=True)
            
        # Gráfico para la tasa de agendamiento global (vs Invites)
        rate_to_plot_global = rate_col_names.get('tasa_agen_inv')
        if rate_to_plot_global and rate_to_plot_global in summary_df.columns and summary_df[rate_to_plot_global].sum() > 0:
            st.markdown(f"##### Gráfico: {rate_to_plot_global}")
            summary_df_sorted_rate_global = summary_df.sort_values(by=rate_to_plot_global, ascending=False)
            fig_rate_global = px.bar(summary_df_sorted_rate_global, x=group_by_col, y=rate_to_plot_global, title=f"{rate_to_plot_global} por {group_by_col}", color=rate_to_plot_global, text_auto=True, color_continuous_scale=px.colors.sequential.Mint)
            fig_rate_global.update_traces(texttemplate='%{y:.1f}%')
            fig_rate_global.update_layout(title_x=0.5, xaxis_tickangle=-45, yaxis_title=rate_to_plot_global, xaxis_title=group_by_col, margin=dict(b=150), yaxis_ticksuffix="%")
            st.plotly_chart(fig_rate_global, use_container_width=True)
        
        # Gráfico para la tasa de agendamiento vs respuestas
        rate_to_plot_resp = rate_col_names.get('tasa_agen_resp')
        if rate_to_plot_resp and rate_to_plot_resp in summary_df.columns and summary_df[rate_to_plot_resp].sum() > 0: # Corregido para usar la tasa correcta
            st.markdown(f"##### Gráfico: {rate_to_plot_resp}")
            summary_df_sorted_rate_resp = summary_df.sort_values(by=rate_to_plot_resp, ascending=False)
            fig_rate_resp = px.bar(summary_df_sorted_rate_resp, x=group_by_col, y=rate_to_plot_resp, title=f"{rate_to_plot_resp} por {group_by_col}", color=rate_to_plot_resp, text_auto=True, color_continuous_scale=px.colors.sequential.PuBu) # Cambiado color para diferenciar
            fig_rate_resp.update_traces(texttemplate='%{y:.1f}%') 
            fig_rate_resp.update_layout(title_x=0.5, xaxis_tickangle=-45, yaxis_title=rate_to_plot_resp, xaxis_title=group_by_col, margin=dict(b=150), yaxis_ticksuffix="%")
            st.plotly_chart(fig_rate_resp, use_container_width=True)

def display_time_evolution(df_filtered, time_col_agg, time_col_label, chart_title, x_axis_label, chart_icon="📈"):
    st.markdown(f"### {chart_icon} {chart_title}")
    st.caption(f"KPIs sumados por {x_axis_label.lower()} dentro del período filtrado.")
    required_cols_time = ['Fecha', time_col_agg]
    if 'NumSemana' in time_col_agg: required_cols_time.extend(['Año', 'NumSemana'])
    if 'AñoMes' in time_col_agg: required_cols_time.extend(['Año', 'MesNum', 'AñoMes']) 
    
    cols_missing_time = [col for col in list(set(required_cols_time)) if col not in df_filtered.columns]
    fecha_col_time = df_filtered.get('Fecha', pd.Series(dtype='object'))
    
    if cols_missing_time or not pd.api.types.is_datetime64_any_dtype(fecha_col_time):
        st.info(f"Datos insuficientes (faltan: {', '.join(cols_missing_time)}) o en formato incorrecto para {chart_title.lower()}.")
        return
    if df_filtered.empty:
        st.info(f"No hay datos filtrados para {chart_title.lower()}.")
        return
        
    kpi_cols_to_sum_time = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"] # Orden del funnel
    kpi_cols_present_time = [col for col in kpi_cols_to_sum_time if col in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered[col])]
    if not kpi_cols_present_time:
        st.info(f"No hay columnas de KPI numéricas para la agregación por {x_axis_label.lower()}.")
        return
        
    group_by_cols_time = [time_col_agg]
    sort_by_cols_time = [time_col_agg]

    if time_col_agg == 'NumSemana' and 'Año' in df_filtered.columns:
        group_by_cols_time = ['Año', 'NumSemana']
        sort_by_cols_time = ['Año', 'NumSemana']
    elif time_col_agg == 'AñoMes' and 'Año' in df_filtered.columns and 'MesNum' in df_filtered.columns:
        group_by_cols_time = ['Año', 'MesNum', 'AñoMes'] 
        sort_by_cols_time = ['Año', 'MesNum']
        
    df_agg_time = df_filtered.groupby(group_by_cols_time, as_index=False)[kpi_cols_present_time].sum()
    
    if df_agg_time.empty:
        st.info(f"No hay datos agregados para mostrar la evolución por {x_axis_label.lower()}.")
        return
        
    if time_col_agg == 'NumSemana' and 'Año' in df_agg_time.columns and 'NumSemana' in df_agg_time.columns:
        df_agg_time = df_agg_time.sort_values(by=sort_by_cols_time)
        df_agg_time[time_col_label] = df_agg_time['Año'].astype(str) + '-S' + df_agg_time['NumSemana'].astype(str).str.zfill(2)
    elif time_col_agg == 'AñoMes' and 'AñoMes' in df_agg_time.columns: 
        df_agg_time = df_agg_time.sort_values(by=sort_by_cols_time)
        
    if time_col_label not in df_agg_time.columns and (time_col_agg == 'NumSemana' or time_col_agg == 'AñoMes'):
        if time_col_agg in df_agg_time.columns:
            df_agg_time = df_agg_time.sort_values(by=time_col_agg) 
        else:
            st.error(f"La columna de agregación temporal '{time_col_agg}' no existe después de agrupar.")
            return
            
    # Asegurar que las columnas se muestren en el orden del funnel
    df_display_time_cols_ordered = [time_col_label if time_col_label in df_agg_time.columns else time_col_agg] + \
                                   [col for col in kpi_cols_to_sum_time if col in df_agg_time.columns] # Usa kpi_cols_present_time para asegurar que existen
    
    df_display_time = df_agg_time[df_display_time_cols_ordered].copy()


    for kpi_col_time_disp in kpi_cols_present_time: 
        df_display_time[kpi_col_time_disp] = df_display_time[kpi_col_time_disp].map('{:,}'.format)
    
    st.dataframe(df_display_time.set_index(df_display_time_cols_ordered[0]), use_container_width=True) 
    
    sesiones_col_time = "Sesiones agendadas"
    x_axis_col_for_plot = time_col_label if time_col_label in df_agg_time.columns else time_col_agg

    if sesiones_col_time in df_agg_time.columns and df_agg_time[sesiones_col_time].sum() > 0:
        fig_time = px.line(df_agg_time, x=x_axis_col_for_plot, y=sesiones_col_time, title=f"Evolución de Sesiones Agendadas por {x_axis_label}", labels={x_axis_col_for_plot: x_axis_label, sesiones_col_time: 'Total Sesiones'}, markers=True, text=sesiones_col_time)
        fig_time.update_traces(textposition='top center', texttemplate='%{text:,}')
        fig_time.update_xaxes(type='category', tickangle=-45) 
        fig_time.update_layout(title_x=0.5, margin=dict(b=120))
        st.plotly_chart(fig_time, use_container_width=True)


def display_detailed_weekly_analyst_view(df_filtered, semanas_seleccionadas_para_vista):
    st.markdown("### 📋 Vista Detallada Semanal por Analista (Funnel)") # Título ajustado

    if df_filtered.empty:
        st.info("No hay datos filtrados generales para mostrar esta vista detallada.")
        return
    
    if not semanas_seleccionadas_para_vista: 
        st.info("Selecciona una o más semanas del menú desplegable de arriba para ver el detalle.")
        return

    # Columnas requeridas en orden del funnel
    required_cols = ['Año', 'NumSemana', 'Analista', 'Región',
                     'Invites enviadas', 'Mensajes Enviados',
                     'Respuestas', 'Sesiones agendadas']
    
    missing_cols = [col for col in required_cols if col not in df_filtered.columns]
    if missing_cols:
        st.warning(f"Faltan las siguientes columnas necesarias para la vista detallada: {', '.join(missing_cols)}")
        return

    df_work = df_filtered[required_cols].copy()

    # Agregación manteniendo el orden de los KPIs
    agg_dict = {
        'Invites enviadas': ('Invites enviadas', 'sum'),
        'Mensajes Enviados': ('Mensajes Enviados', 'sum'),
        'Respuestas': ('Respuestas', 'sum'),
        'Sesiones agendadas': ('Sesiones agendadas', 'sum')
    }
    df_analyst_weekly = df_work.groupby(
        ['Año', 'NumSemana', 'Analista', 'Región'], as_index=False
    ).agg(**agg_dict) # Usar ** para desempacar el diccionario de agregación

    # Renombrar columnas agregadas para claridad y mantener referencia al funnel
    df_analyst_weekly.rename(columns={
        'Invites enviadas': '1. Invites enviadas',
        'Mensajes Enviados': '2. Mensajes Enviados',
        'Respuestas': '3. Respuestas',
        'Sesiones agendadas': '4. Sesiones agendadas'
    }, inplace=True)
    
    # Calcular tasas del funnel
    df_analyst_weekly['% Mens. / Invite'] = df_analyst_weekly.apply( # Tasa de Mensajes vs Invites
        lambda x: calculate_rate(x['2. Mensajes Enviados'], x['1. Invites enviadas'], round_to=2), axis=1
    )
    df_analyst_weekly['% Resp. / Mensaje'] = df_analyst_weekly.apply( # Tasa de Respuesta vs Mensajes
        lambda x: calculate_rate(x['3. Respuestas'], x['2. Mensajes Enviados'], round_to=2), axis=1
    )
    df_analyst_weekly['% Agend. / Respuesta'] = df_analyst_weekly.apply( # Tasa de Sesiones vs Respuestas (antes '% de aceptación')
        lambda x: calculate_rate(x['4. Sesiones agendadas'], x['3. Respuestas'], round_to=2), axis=1
    )
    df_analyst_weekly['% Agend. / Invite (Global)'] = df_analyst_weekly.apply( # Tasa Global de Sesiones vs Invites
        lambda x: calculate_rate(x['4. Sesiones agendadas'], x['1. Invites enviadas'], round_to=2), axis=1
    )


    df_analyst_weekly_sorted = df_analyst_weekly.sort_values(
        by=['Año', 'NumSemana', 'Analista'], ascending=[False, False, True]
    )

    if 'Año' in df_analyst_weekly_sorted.columns and 'NumSemana' in df_analyst_weekly_sorted.columns:
        df_analyst_weekly_sorted['AñoSemanaEtiqueta'] = df_analyst_weekly_sorted['Año'].astype(str) + "-S" + df_analyst_weekly_sorted['NumSemana'].astype(str).str.zfill(2)
    else:
        st.error("Las columnas 'Año' o 'NumSemana' no están disponibles para crear etiquetas para el filtro de semanas.")
        return

    semanas_a_mostrar_df = df_analyst_weekly_sorted[df_analyst_weekly_sorted['AñoSemanaEtiqueta'].isin(semanas_seleccionadas_para_vista)]
    
    if semanas_a_mostrar_df.empty and semanas_seleccionadas_para_vista:
        st.info("No hay datos para las semanas seleccionadas después de aplicar los filtros generales.")
        return

    for etiqueta_semana_seleccionada in semanas_seleccionadas_para_vista:
        try:
            ano_actual_str, num_semana_actual_str = etiqueta_semana_seleccionada.split('-S')
            ano_actual = int(ano_actual_str)
            num_semana_actual = int(num_semana_actual_str)
            st.markdown(f"#### Semana {num_semana_actual} (Año: {ano_actual})")
        except ValueError:
            st.markdown(f"#### {etiqueta_semana_seleccionada}") 

        df_vista_semana = semanas_a_mostrar_df[semanas_a_mostrar_df['AñoSemanaEtiqueta'] == etiqueta_semana_seleccionada]
        
        if df_vista_semana.empty:
            continue
        
        # Columnas a mostrar en la tabla, en orden del funnel
        cols_to_display_detailed = [
            'Analista', 'Región', 
            '1. Invites enviadas', 
            '2. Mensajes Enviados', '% Mens. / Invite',
            '3. Respuestas', '% Resp. / Mensaje',
            '4. Sesiones agendadas', '% Agend. / Respuesta', 
            '% Agend. / Invite (Global)'
        ]
        df_display_analistas = df_vista_semana[cols_to_display_detailed].copy()

        # Calcular totales para la fila de resumen
        total_invites = df_display_analistas['1. Invites enviadas'].sum()
        total_mensajes = df_display_analistas['2. Mensajes Enviados'].sum()
        total_respuestas = df_display_analistas['3. Respuestas'].sum()
        total_sesiones = df_display_analistas['4. Sesiones agendadas'].sum()

        df_fila_total = pd.DataFrame([{
            'Analista': 'Total Semana', 'Región': '', 
            '1. Invites enviadas': total_invites,
            '2. Mensajes Enviados': total_mensajes,
            '% Mens. / Invite': calculate_rate(total_mensajes, total_invites, round_to=2),
            '3. Respuestas': total_respuestas,
            '% Resp. / Mensaje': calculate_rate(total_respuestas, total_mensajes, round_to=2),
            '4. Sesiones agendadas': total_sesiones,
            '% Agend. / Respuesta': calculate_rate(total_sesiones, total_respuestas, round_to=2),
            '% Agend. / Invite (Global)': calculate_rate(total_sesiones, total_invites, round_to=2)
        }])

        df_final_semana = pd.concat([df_display_analistas, df_fila_total], ignore_index=True)
        
        # Formatear columnas de porcentaje
        for col_porcentaje in ['% Mens. / Invite', '% Resp. / Mensaje', '% Agend. / Respuesta', '% Agend. / Invite (Global)']:
            df_final_semana[col_porcentaje] = df_final_semana[col_porcentaje].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%")
        
        st.dataframe(df_final_semana.set_index('Analista'), use_container_width=True)
        st.markdown("---") 

# --- Flujo Principal de la Página ---
if "kpis_page_filtro_Semana_v6" in st.session_state: # Eliminar el mensaje de "The widget with key..."
    del st.session_state["kpis_page_filtro_Semana_v6"]

start_date_val_kpis, end_date_val_kpis, year_val_kpis, week_val_kpis_sidebar, analista_val_kpis, region_val_kpis = sidebar_filters_kpis(df_kpis_semanales_raw) 
df_kpis_filtered_page = apply_kpis_filters(df_kpis_semanales_raw, start_date_val_kpis, end_date_val_kpis, year_val_kpis, week_val_kpis_sidebar, analista_val_kpis, region_val_kpis)

if "Analista" in df_kpis_filtered_page.columns and analista_val_kpis and "– Todos –" not in analista_val_kpis:
    if "N/D" not in analista_val_kpis:
        df_kpis_filtered_page = df_kpis_filtered_page[~df_kpis_filtered_page["Analista"].isin(['N/D', ''])]

# --- Presentación del Dashboard ---
display_kpi_summary(df_kpis_filtered_page) # Mostrar el resumen primero, ya ordenado según el funnel
st.markdown("---")

# Desgloses por Analista y Región
col_breakdown1, col_breakdown2 = st.columns(2)
with col_breakdown1:
    display_grouped_breakdown(df_kpis_filtered_page, "Analista", "Desglose por Analista", chart_icon="🧑‍💻")
with col_breakdown2:
    display_grouped_breakdown(df_kpis_filtered_page, "Región", "Desglose por Región", chart_icon="🌎")
st.markdown("---")

# Tabla detallada filtrada
display_filtered_kpis_table(df_kpis_filtered_page) 
st.markdown("---")

# Control y vista detallada semanal por analista
st.markdown("### 🔬 Control de Vista Detallada Semanal por Analista")
available_weeks_for_detail_view = []
if not df_kpis_filtered_page.empty and 'Año' in df_kpis_filtered_page.columns and 'NumSemana' in df_kpis_filtered_page.columns:
    unique_year_week_df = df_kpis_filtered_page[['Año', 'NumSemana']].drop_duplicates().sort_values(
        by=['Año', 'NumSemana'], ascending=[False, False]
    )
    available_weeks_for_detail_view = [
        f"{row['Año']}-S{str(row['NumSemana']).zfill(2)}" for index, row in unique_year_week_df.iterrows()
    ]

if not available_weeks_for_detail_view and not df_kpis_filtered_page.empty :
     st.info("No hay semanas específicas disponibles para la vista detallada con los filtros generales aplicados.")
elif df_kpis_filtered_page.empty:
    st.info("No hay datos disponibles según los filtros generales para seleccionar semanas para la vista detallada.")

selected_weeks_for_detailed_view = st.multiselect(
    "Selecciona las semanas para ver en detalle:", # Texto del multiselect ligeramente ajustado
    options=available_weeks_for_detail_view,
    default=st.session_state.get(DETAILED_VIEW_WEEKS_KEY, []), 
    key=DETAILED_VIEW_WEEKS_KEY,
    help="Elige una o más semanas (Año-Semana) para un análisis detallado por analista."
)
display_detailed_weekly_analyst_view(df_kpis_filtered_page, selected_weeks_for_detailed_view)
st.markdown("---")

# Evoluciones temporales
display_time_evolution(df_kpis_filtered_page, 'NumSemana', 'Año-Semana', "Evolución Semanal de KPIs", "Semana", chart_icon="🗓️")
st.markdown("---")
display_time_evolution(df_kpis_filtered_page, 'AñoMes', 'AñoMes', "Evolución Mensual de KPIs", "Mes (Año-Mes)", chart_icon="📈")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
