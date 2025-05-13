# Prospe/pages/📊_KPIs_Semanales.py
import streamlit as st
import pandas as pd
import gspread
# from oauth2client.service_account import ServiceAccountCredentials # No se usa con gspread >= 5.0 y st.secrets
import datetime
import plotly.express as px
import os
import sys

# --- Configuración Inicial del Proyecto y Título de la Página ---
st.set_page_config(layout="wide", page_title="KPIs Semanales")

st.title("📊 Dashboard de KPIs y Tasas de Conversión")
st.markdown(
    "Análisis de métricas absolutas y tasas de conversión por analista, región, y periodo."
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
            # st.warning("No hay datos con fechas válidas después de la conversión (KPIs Semanales).") # Comentado para no saturar
            for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
            df['AñoMes'] = pd.Series(dtype='str')
    else:
        st.warning("Columna 'Fecha' no encontrada (KPIs Semanales). No se podrán aplicar filtros de fecha.")
        for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
        df['AñoMes'] = pd.Series(dtype='str')

    numeric_kpi_columns = ["Mensajes Enviados", "Respuestas", "Invites enviadas", "Sesiones agendadas"]
    for col_name in numeric_kpi_columns:
        if col_name not in df.columns:
            st.warning(f"Columna KPI '{col_name}' no encontrada (KPIs Semanales). Se creará con ceros.")
            df[col_name] = 0
        else:
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
WEEK_FILTER_KEY = "kpis_page_filtro_Semana_v6" # Filtro general de semanas en sidebar
DETAILED_VIEW_WEEKS_KEY = "kpis_page_detailed_view_weeks_v1" # Nueva key para el multiselect de la vista detallada

default_filters_kpis = {
    START_DATE_KEY: None, END_DATE_KEY: None,
    ANALISTA_FILTER_KEY: ["– Todos –"], REGION_FILTER_KEY: ["– Todos –"],
    YEAR_FILTER_KEY: "– Todos –", WEEK_FILTER_KEY: ["– Todas –"],
    DETAILED_VIEW_WEEKS_KEY: [] # Por defecto, ninguna semana seleccionada para la vista detallada
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
    st.sidebar.subheader("📅 Por Año y Semana (Filtro General)") # Aclaración del propósito
    year_options = ["– Todos –"] + (sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True) if "Año" in df_options.columns and not df_options["Año"].dropna().empty else [])
    current_year_selection = st.session_state.get(YEAR_FILTER_KEY, "– Todos –")
    if not isinstance(current_year_selection, str): current_year_selection = str(current_year_selection)
    if current_year_selection not in map(str,year_options):
        st.session_state[YEAR_FILTER_KEY] = "– Todos –"
        current_year_selection = "– Todos –"
    
    selected_year_str = st.sidebar.selectbox("Año", year_options, index=year_options.index(current_year_selection), key=YEAR_FILTER_KEY)
    selected_year_int = int(selected_year_str) if selected_year_str != "– Todos –" else None
    
    week_options_sidebar = ["– Todas –"] # Renombrado para evitar conflicto
    df_for_week_sidebar = df_options[df_options["Año"] == selected_year_int] if selected_year_int is not None and "NumSemana" in df_options.columns and "Año" in df_options.columns else df_options
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
    return (st.session_state[START_DATE_KEY], st.session_state[END_DATE_KEY], selected_year_int, st.session_state[WEEK_FILTER_KEY], analista_filter_val, region_filter_val)

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
    # ... (sin cambios en esta función)
    st.markdown("### 📝 Datos Detallados Filtrados (Vista General)")
    if df_filtered.empty:
        st.info("No se encontraron datos que cumplan los criterios de filtro.")
        return
    st.write(f"Mostrando **{len(df_filtered)}** filas.")
    cols_display = ["Fecha", "Año", "NumSemana", "AñoMes", "Analista", "Región", "Mensajes Enviados", "Respuestas", "Invites enviadas", "Sesiones agendadas"]
    if "Semana" in df_filtered.columns: cols_display.insert(3, "Semana")
    cols_present = [col for col in cols_display if col in df_filtered.columns]
    df_display_table = df_filtered[cols_present].copy()
    if "Fecha" in df_display_table.columns:
        df_display_table["Fecha"] = df_display_table["Fecha"].dt.strftime('%d/%m/%Y')
    st.dataframe(df_display_table, use_container_width=True, height=300)


def display_kpi_summary(df_filtered):
    # ... (sin cambios en esta función)
    st.markdown("### 🧮 Resumen de KPIs Totales y Tasas Globales (Periodo Filtrado)")
    kpi_cols = ["Mensajes Enviados", "Respuestas", "Invites enviadas", "Sesiones agendadas"]
    icons = ["📤", "💬", "📧", "🤝"]
    metrics = {}
    if df_filtered.empty:
        for col_name in kpi_cols: metrics[col_name] = 0
    else:
        for col_name in kpi_cols:
            if col_name in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered[col_name]):
                metrics[col_name] = df_filtered[col_name].sum()
            else:
                metrics[col_name] = 0
    col_metrics_abs = st.columns(len(kpi_cols))
    for i, col_name in enumerate(kpi_cols):
        col_metrics_abs[i].metric(f"{icons[i]} Total {col_name.split(' ')[0]}", f"{metrics.get(col_name, 0):,}")
    
    st.markdown("---")
    total_mensajes = metrics.get("Mensajes Enviados", 0)
    total_respuestas = metrics.get("Respuestas", 0)
    total_sesiones = metrics.get("Sesiones agendadas", 0)
    tasa_resp_global = calculate_rate(total_respuestas, total_mensajes)
    tasa_agen_vs_env_global = calculate_rate(total_sesiones, total_mensajes)
    tasa_agen_vs_resp_global = calculate_rate(total_sesiones, total_respuestas)
    rate_icons = ["📈", "🎯", "✨"]
    col_metrics_rates = st.columns(3)
    col_metrics_rates[0].metric(f"{rate_icons[0]} Tasa Respuesta Global", f"{tasa_resp_global:.1f}%")
    col_metrics_rates[1].metric(f"{rate_icons[1]} Tasa Agend. (vs Env.)", f"{tasa_agen_vs_env_global:.1f}%")
    col_metrics_rates[2].metric(f"{rate_icons[2]} Tasa Agend. (vs Resp.)", f"{tasa_agen_vs_resp_global:.1f}%")

def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    # ... (sin cambios en esta función)
    st.markdown(f"### {chart_icon} {title_prefix} - KPIs Absolutos y Tasas")
    if group_by_col not in df_filtered.columns:
        st.warning(f"Columna '{group_by_col}' no encontrada para el desglose.")
        return
    kpi_cols = ["Mensajes Enviados", "Respuestas", "Invites enviadas", "Sesiones agendadas"]
    rate_col_names = {'tasa_resp': 'Tasa Respuesta (%)', 'tasa_ag_env': 'Tasa Ag. (vs Env.) (%)', 'tasa_ag_resp': 'Tasa Ag. (vs Resp.) (%)'}
    actual_kpi_cols = [col for col in kpi_cols if col in df_filtered.columns and pd.api.types.is_numeric_dtype(df_filtered[col])]
    if not actual_kpi_cols:
        st.warning(f"No hay columnas de KPI numéricas para desglose por {group_by_col}.")
        return
    
    df_to_group = df_filtered.copy()
    df_to_group[group_by_col] = df_to_group[group_by_col].astype(str).str.strip().replace('', 'N/D')
    
    if df_to_group.empty or df_to_group[group_by_col].nunique() == 0:
        st.info(f"No hay datos con '{group_by_col}' definido para el desglose en el periodo filtrado.")
        return
        
    summary_df = df_to_group.groupby(group_by_col, as_index=False)[actual_kpi_cols].sum()
    mensajes_col, respuestas_col, sesiones_col = "Mensajes Enviados", "Respuestas", "Sesiones agendadas"
    
    summary_df[rate_col_names['tasa_resp']] = summary_df.apply(lambda r: calculate_rate(r.get(respuestas_col, 0), r.get(mensajes_col, 0)), axis=1) if mensajes_col in summary_df and respuestas_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_ag_env']] = summary_df.apply(lambda r: calculate_rate(r.get(sesiones_col, 0), r.get(mensajes_col, 0)), axis=1) if mensajes_col in summary_df and sesiones_col in summary_df else 0.0
    summary_df[rate_col_names['tasa_ag_resp']] = summary_df.apply(lambda r: calculate_rate(r.get(sesiones_col, 0), r.get(respuestas_col, 0)), axis=1) if respuestas_col in summary_df and sesiones_col in summary_df else 0.0
    
    if not summary_df.empty:
        cols_for_display_table = [group_by_col] + actual_kpi_cols + list(rate_col_names.values())
        summary_df_display = summary_df[cols_for_display_table].copy()
        for kpi_col_disp in actual_kpi_cols: summary_df_display[kpi_col_disp] = summary_df_display[kpi_col_disp].map('{:,}'.format)
        for rate_col_key_disp in rate_col_names: summary_df_display[rate_col_names[rate_col_key_disp]] = summary_df_display[rate_col_names[rate_col_key_disp]].map('{:.1f}%'.format)
        
        st.markdown("##### Tabla Resumen (Absolutos y Tasas)")
        st.dataframe(summary_df_display.set_index(group_by_col), use_container_width=True) 
        st.markdown("---")
        
        if sesiones_col in summary_df.columns and summary_df[sesiones_col].sum() > 0:
            st.markdown("##### Gráfico: Sesiones Agendadas (Absoluto)")
            fig_abs = px.bar(summary_df.sort_values(by=sesiones_col, ascending=False), x=group_by_col, y=sesiones_col, title=f"Sesiones Agendadas por {group_by_col}", color=sesiones_col, text_auto=True, color_continuous_scale=px.colors.sequential.Teal)
            fig_abs.update_traces(texttemplate='%{y:,}') 
            fig_abs.update_layout(title_x=0.5, xaxis_tickangle=-45, yaxis_title="Total Sesiones Agendadas", xaxis_title=group_by_col, margin=dict(b=150))
            st.plotly_chart(fig_abs, use_container_width=True)
            
        rate_to_plot = rate_col_names['tasa_ag_resp']
        if rate_to_plot in summary_df.columns and summary_df[rate_to_plot].sum() > 0:
            st.markdown(f"##### Gráfico: {rate_to_plot}")
            summary_df_sorted_rate = summary_df.sort_values(by=rate_to_plot, ascending=False)
            fig_rate = px.bar(summary_df_sorted_rate, x=group_by_col, y=rate_to_plot, title=f"{rate_to_plot} por {group_by_col}", color=rate_to_plot, text_auto=True, color_continuous_scale=px.colors.sequential.Mint)
            fig_rate.update_traces(texttemplate='%{y:.1f}%') 
            fig_rate.update_layout(title_x=0.5, xaxis_tickangle=-45, yaxis_title=rate_to_plot, xaxis_title=group_by_col, margin=dict(b=150), yaxis_ticksuffix="%")
            st.plotly_chart(fig_rate, use_container_width=True)

def display_time_evolution(df_filtered, time_col_agg, time_col_label, chart_title, x_axis_label, chart_icon="📈"):
    # ... (sin cambios en esta función)
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
        
    kpi_cols_to_sum_time = ["Mensajes Enviados", "Respuestas", "Invites enviadas", "Sesiones agendadas"]
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
            
    df_display_time_cols = [time_col_label if time_col_label in df_agg_time.columns else time_col_agg] + kpi_cols_present_time
    df_display_time = df_agg_time[df_display_time_cols].copy()

    for kpi_col_time_disp in kpi_cols_present_time: 
        df_display_time[kpi_col_time_disp] = df_display_time[kpi_col_time_disp].map('{:,}'.format)
    
    st.dataframe(df_display_time.set_index(df_display_time_cols[0]), use_container_width=True) 
    
    sesiones_col_time = "Sesiones agendadas"
    x_axis_col_for_plot = time_col_label if time_col_label in df_agg_time.columns else time_col_agg

    if sesiones_col_time in df_agg_time.columns and df_agg_time[sesiones_col_time].sum() > 0:
        fig_time = px.line(df_agg_time, x=x_axis_col_for_plot, y=sesiones_col_time, title=f"Evolución de Sesiones Agendadas por {x_axis_label}", labels={x_axis_col_for_plot: x_axis_label, sesiones_col_time: 'Total Sesiones'}, markers=True, text=sesiones_col_time)
        fig_time.update_traces(textposition='top center', texttemplate='%{text:,}')
        fig_time.update_xaxes(type='category', tickangle=-45) 
        fig_time.update_layout(title_x=0.5, margin=dict(b=120))
        st.plotly_chart(fig_time, use_container_width=True)


# --- MODIFICADA FUNCIÓN PARA LA TABLA ESTILO HOJA DE CÁLCULO ---
def display_detailed_weekly_analyst_view(df_filtered, semanas_seleccionadas_para_vista): # Nuevo parámetro
    st.markdown("### 📋 Vista Detallada Semanal por Analista (Estilo Anterior)")

    if df_filtered.empty:
        st.info("No hay datos filtrados para mostrar esta vista detallada.")
        return
    
    if not semanas_seleccionadas_para_vista: # Si no se seleccionó ninguna semana
        st.info("Selecciona una o más semanas del menú desplegable de arriba para ver el detalle.")
        return

    required_cols = ['Año', 'NumSemana', 'Analista', 'Región',
                     'Invites enviadas', 'Mensajes Enviados',
                     'Respuestas', 'Sesiones agendadas']
    
    missing_cols = [col for col in required_cols if col not in df_filtered.columns]
    if missing_cols:
        st.warning(f"Faltan las siguientes columnas necesarias para la vista detallada: {', '.join(missing_cols)}")
        return

    df_work = df_filtered[required_cols].copy()

    df_analyst_weekly = df_work.groupby(
        ['Año', 'NumSemana', 'Analista', 'Región'], as_index=False
    ).agg(
        invites_totales = ('Invites enviadas', 'sum'),
        mensajes_totales = ('Mensajes Enviados', 'sum'),
        respuestas_totales = ('Respuestas', 'sum'),
        sesiones_totales = ('Sesiones agendadas', 'sum')
    )

    df_analyst_weekly['% Mens/Invite'] = df_analyst_weekly.apply(
        lambda x: calculate_rate(x['mensajes_totales'], x['invites_totales'], round_to=2), axis=1
    )
    df_analyst_weekly['% Resp/Mensaje'] = df_analyst_weekly.apply(
        lambda x: calculate_rate(x['respuestas_totales'], x['mensajes_totales'], round_to=2), axis=1
    )
    df_analyst_weekly['% de aceptación'] = df_analyst_weekly.apply(
        lambda x: calculate_rate(x['sesiones_totales'], x['respuestas_totales'], round_to=2), axis=1
    )

    df_analyst_weekly.rename(columns={
        'invites_totales': '1. Invites enviadas',
        'mensajes_totales': '2. Mensajes Enviados',
        'respuestas_totales': '3. Respuestas',
        'sesiones_totales': '4. Sesiones agendadas'
    }, inplace=True)

    df_analyst_weekly_sorted = df_analyst_weekly.sort_values(
        by=['Año', 'NumSemana', 'Analista'], ascending=[False, False, True]
    )

    # Crear etiquetas 'Año-Semana' para el multiselect y para filtrar
    # Asegurarse que df_analyst_weekly_sorted tenga 'Año' y 'NumSemana' antes de esta operación
    if 'Año' in df_analyst_weekly_sorted.columns and 'NumSemana' in df_analyst_weekly_sorted.columns:
        df_analyst_weekly_sorted['AñoSemanaEtiqueta'] = df_analyst_weekly_sorted['Año'].astype(str) + "-S" + df_analyst_weekly_sorted['NumSemana'].astype(str).str.zfill(2)
    else:
        st.error("Las columnas 'Año' o 'NumSemana' no están disponibles para crear etiquetas para el filtro de semanas.")
        return

    # Filtrar las semanas únicas basadas en la selección del usuario
    # 'semanas_seleccionadas_para_vista' contendrá las etiquetas 'Año-Semana'
    semanas_a_mostrar_df = df_analyst_weekly_sorted[df_analyst_weekly_sorted['AñoSemanaEtiqueta'].isin(semanas_seleccionadas_para_vista)]


    # Iterar sobre las semanas seleccionadas y filtradas
    # Para mantener el orden original del multiselect, iteramos sobre semanas_seleccionadas_para_vista
    # y luego filtramos el df_analyst_weekly_sorted para cada una.
    
    if semanas_a_mostrar_df.empty and semanas_seleccionadas_para_vista:
        st.info("No hay datos para las semanas seleccionadas después de aplicar los filtros generales.")
        return

    # Obtener el orden de las semanas tal como fueron seleccionadas por el usuario
    # y luego agrupar el df para mostrar en ese orden.
    
    # Asegurar que se agrupa por la etiqueta para mantener el orden de selección si es posible
    # o simplemente iterar por las etiquetas seleccionadas.

    for etiqueta_semana_seleccionada in semanas_seleccionadas_para_vista:
        # Extraer Año y NumSemana de la etiqueta para el título si es necesario, o usar la etiqueta directamente
        # Suponiendo que la etiqueta es "YYYY-SWW"
        try:
            ano_actual_str, num_semana_actual_str = etiqueta_semana_seleccionada.split('-S')
            ano_actual = int(ano_actual_str)
            num_semana_actual = int(num_semana_actual_str)
            st.markdown(f"#### Semana {num_semana_actual} (Año: {ano_actual})")
        except ValueError:
            st.markdown(f"#### {etiqueta_semana_seleccionada}") # Fallback si el formato no es el esperado

        df_vista_semana = semanas_a_mostrar_df[semanas_a_mostrar_df['AñoSemanaEtiqueta'] == etiqueta_semana_seleccionada]
        
        if df_vista_semana.empty:
            # Esto podría pasar si una semana seleccionada no tiene datos después de otros filtros, aunque el chequeo anterior debería cubrirlo.
            # st.caption(f"No hay datos detallados para mostrar para la semana {etiqueta_semana_seleccionada} con los filtros actuales.")
            continue


        df_display_analistas = df_vista_semana[[
            'Analista', 'Región', '1. Invites enviadas', '2. Mensajes Enviados',
            '% Mens/Invite', '3. Respuestas', '% Resp/Mensaje',
            '4. Sesiones agendadas', '% de aceptación'
        ]].copy()

        total_invites = df_display_analistas['1. Invites enviadas'].sum()
        total_mensajes = df_display_analistas['2. Mensajes Enviados'].sum()
        total_respuestas = df_display_analistas['3. Respuestas'].sum()
        total_sesiones = df_display_analistas['4. Sesiones agendadas'].sum()

        df_fila_total = pd.DataFrame([{
            'Analista': 'Total', 'Región': '', 
            '1. Invites enviadas': total_invites,
            '2. Mensajes Enviados': total_mensajes,
            '% Mens/Invite': calculate_rate(total_mensajes, total_invites, round_to=2),
            '3. Respuestas': total_respuestas,
            '% Resp/Mensaje': calculate_rate(total_respuestas, total_mensajes, round_to=2),
            '4. Sesiones agendadas': total_sesiones,
            '% de aceptación': calculate_rate(total_sesiones, total_respuestas, round_to=2) 
        }])

        df_final_semana = pd.concat([df_display_analistas, df_fila_total], ignore_index=True)

        for col_porcentaje in ['% Mens/Invite', '% Resp/Mensaje', '% de aceptación']:
            df_final_semana[col_porcentaje] = df_final_semana[col_porcentaje].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "0.00%")
        
        st.dataframe(df_final_semana.set_index('Analista'), use_container_width=True)
        st.markdown("---") 
# --- FIN DE LA FUNCIÓN MODIFICADA ---


# --- Flujo Principal de la Página ---
start_date_val_kpis, end_date_val_kpis, year_val_kpis, week_val_kpis_sidebar, analista_val_kpis, region_val_kpis = sidebar_filters_kpis(df_kpis_semanales_raw) # Renombrado week_val_kpis
df_kpis_filtered_page = apply_kpis_filters(df_kpis_semanales_raw, start_date_val_kpis, end_date_val_kpis, year_val_kpis, week_val_kpis_sidebar, analista_val_kpis, region_val_kpis)

if "Analista" in df_kpis_filtered_page.columns and analista_val_kpis and "– Todos –" not in analista_val_kpis:
    if "N/D" not in analista_val_kpis:
        df_kpis_filtered_page = df_kpis_filtered_page[~df_kpis_filtered_page["Analista"].isin(['N/D', ''])]

# --- Presentación del Dashboard ---
display_kpi_summary(df_kpis_filtered_page)
st.markdown("---")
col_breakdown1, col_breakdown2 = st.columns(2)
with col_breakdown1:
    display_grouped_breakdown(df_kpis_filtered_page, "Analista", "Desglose por Analista", chart_icon="🧑‍💻")
with col_breakdown2:
    display_grouped_breakdown(df_kpis_filtered_page, "Región", "Desglose por Región", chart_icon="🌎")
st.markdown("---")
display_filtered_kpis_table(df_kpis_filtered_page) 
st.markdown("---")

# --- SECCIÓN PARA LA VISTA DETALLADA SEMANAL CON SELECTOR ---
st.markdown("### 🔬 Control de Vista Detallada Semanal por Analista")

# Preparar opciones para el multiselect de semanas (basado en los datos ya filtrados por el sidebar)
available_weeks_for_detail_view = []
if not df_kpis_filtered_page.empty and 'Año' in df_kpis_filtered_page.columns and 'NumSemana' in df_kpis_filtered_page.columns:
    # Crear etiquetas Año-Semana únicas y ordenadas de los datos filtrados
    # Ordenar por Año descendente, luego por NumSemana descendente
    unique_year_week_df = df_kpis_filtered_page[['Año', 'NumSemana']].drop_duplicates().sort_values(
        by=['Año', 'NumSemana'], ascending=[False, False]
    )
    available_weeks_for_detail_view = [
        f"{row['Año']}-S{str(row['NumSemana']).zfill(2)}" for index, row in unique_year_week_df.iterrows()
    ]

# Si no hay semanas disponibles después del filtro general, informar al usuario
if not available_weeks_for_detail_view and not df_kpis_filtered_page.empty :
     st.info("No hay semanas específicas disponibles para la vista detallada con los filtros generales aplicados.")
elif df_kpis_filtered_page.empty:
    st.info("No hay datos disponibles según los filtros generales para seleccionar semanas para la vista detallada.")


# Usar st.multiselect para que el usuario elija las semanas
# Asegurarse que el default sea una lista vacía o las semanas actualmente en session_state
selected_weeks_for_detailed_view = st.multiselect(
    "Selecciona las semanas para ver en detalle (Estilo Anterior):",
    options=available_weeks_for_detail_view,
    default=st.session_state.get(DETAILED_VIEW_WEEKS_KEY, []), # Cargar desde session state
    key=DETAILED_VIEW_WEEKS_KEY # Guardar en session state
)

# Llamar a la función de visualización con las semanas seleccionadas
display_detailed_weekly_analyst_view(df_kpis_filtered_page, selected_weeks_for_detailed_view)
st.markdown("---")
# --- FIN DE LA SECCIÓN DE VISTA DETALLADA ---


display_time_evolution(df_kpis_filtered_page, 'NumSemana', 'Año-Semana', "Evolución Semanal de KPIs", "Semana", chart_icon="🗓️")
st.markdown("---")
display_time_evolution(df_kpis_filtered_page, 'AñoMes', 'AñoMes', "Evolución Mensual de KPIs", "Mes (Año-Mes)", chart_icon="📈")

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
