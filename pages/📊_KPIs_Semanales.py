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
# La gestión de sys.path usualmente se hace en el script principal (🏠_Dashboard_Principal.py)
# o es manejada por Streamlit en el entorno de la nube.

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
    
    # Asegúrate que 'Sesiones agendadas' coincida exactamente con el nombre de tu columna en la hoja de KPIs
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
        # CORRECCIÓN: Usar la sección [gcp_service_account] de tus secretos
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account] o alguna de sus claves en los 'Secrets' de Streamlit (KPIs Semanales).")
        st.error("Asegúrate de haber configurado correctamente tus secretos en Streamlit Cloud.")
        st.stop()
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets para KPIs Semanales vía Secrets: {e}")
        st.stop()

    # Usar la clave específica para la URL de esta hoja desde tus secretos
    sheet_url_kpis = st.secrets.get(
        "kpis_sheet_url", # Clave que definiste en tu secrets.toml
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
            st.warning("No hay datos con fechas válidas después de la conversión (KPIs Semanales).")
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

# --- Función para calcular tasas de forma segura ---
def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- Carga de Datos ---
df_kpis_semanales_raw = load_weekly_kpis_data()

if df_kpis_semanales_raw.empty:
    st.error("El DataFrame de KPIs Semanales está vacío después de la carga. No se puede continuar.")
    st.stop()

# --- Estado de Sesión para Filtros ---
START_DATE_KEY = "kpis_page_fecha_inicio_v6"
END_DATE_KEY = "kpis_page_fecha_fin_v6"
ANALISTA_FILTER_KEY = "kpis_page_filtro_Analista_v6"
REGION_FILTER_KEY = "kpis_page_filtro_Región_v6"
YEAR_FILTER_KEY = "kpis_page_filtro_Año_v6"
WEEK_FILTER_KEY = "kpis_page_filtro_Semana_v6"

default_filters_kpis = {
    START_DATE_KEY: None, END_DATE_KEY: None,
    ANALISTA_FILTER_KEY: ["– Todos –"], REGION_FILTER_KEY: ["– Todos –"],
    YEAR_FILTER_KEY: "– Todos –", WEEK_FILTER_KEY: ["– Todas –"]
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
    st.sidebar.subheader("📅 Por Año y Semana")
    
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
        unique_years_int = sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True)
        year_options = ["– Todos –"] + [str(year) for year in unique_years_int]
    else:
        year_options = ["– Todos –"]

    current_year_selection = st.session_state.get(YEAR_FILTER_KEY, "– Todos –")

    if not isinstance(current_year_selection, str):
        current_year_selection = str(current_year_selection)

    if current_year_selection not in year_options:
        st.session_state[YEAR_FILTER_KEY] = "– Todos –"
        current_year_selection = "– Todos –"
    
    selected_index = 0
    try:
        selected_index = year_options.index(current_year_selection)
    except ValueError:
        st.sidebar.warning(f"'{current_year_selection}' no se encontró en las opciones de año. Usando la primera opción.") # <--- CAMBIO: st.sidebar.warning
        if year_options:
            selected_index = 0
            current_year_selection = year_options[selected_index]
            st.session_state[YEAR_FILTER_KEY] = current_year_selection
        else:
            year_options = ["(No hay años)"]
            current_year_selection = year_options[0]
            st.session_state[YEAR_FILTER_KEY] = current_year_selection
            selected_index = 0
    
    selected_year_str = st.sidebar.selectbox(
        "Año",
        year_options,
        index=selected_index,
        key=YEAR_FILTER_KEY
    )
    selected_year_int = int(selected_year_str) if selected_year_str != "– Todos –" and selected_year_str.isdigit() else None
    
    # --- INICIO DE CAMBIOS CON DEBUG ---
    st.sidebar.write(f"Año seleccionado (str): {selected_year_str}") # DEBUG
    st.sidebar.write(f"Año seleccionado (int): {selected_year_int}") # DEBUG

    week_options = ["– Todas –"]
    # Filtrar df_options por el año seleccionado para obtener las semanas correspondientes
    if selected_year_int is not None:
        df_for_week = df_options[df_options["Año"] == selected_year_int]
    else: # Si el año es "– Todos –", usar todas las opciones
        df_for_week = df_options
    
    st.sidebar.write(f"Filas en df_for_week (para semanas): {len(df_for_week)}") # DEBUG

    if "NumSemana" in df_for_week.columns and not df_for_week["NumSemana"].dropna().empty:
        unique_weeks_for_year = sorted(df_for_week["NumSemana"].dropna().astype(int).unique())
        week_options.extend([str(w) for w in unique_weeks_for_year])
        st.sidebar.write(f"Semanas únicas para el año '{selected_year_str}': {unique_weeks_for_year}") # DEBUG
    
    st.sidebar.write(f"Opciones finales de semana: {week_options}") # DEBUG
    # --- FIN DE CAMBIOS CON DEBUG ---
    
    current_week_selection = st.session_state.get(WEEK_FILTER_KEY, ["– Todas –"])
    # Asegurar que la selección actual de semanas sea válida con las nuevas opciones de semana
    valid_week_selection = [s for s in current_week_selection if s in week_options]
    if not valid_week_selection: # Si ninguna de las selecciones anteriores es válida
        if "– Todas –" in week_options:
            valid_week_selection = ["– Todas –"]
        elif week_options: # Si hay opciones pero ninguna es "– Todas –" y la selección previa no es válida
             valid_week_selection = [] # Dejar vacío o seleccionar la primera opción disponible si se prefiere
                                     # valid_week_selection = [week_options[0]] # (si week_options[0] no es '– Todas –')
    
    # Si la selección válida es diferente de lo que estaba en el estado de sesión, actualizar el estado.
    # Esto es importante para resetear la selección de semanas si el año cambia y las semanas previas ya no aplican.
    if set(valid_week_selection) != set(st.session_state.get(WEEK_FILTER_KEY, ["– Todas –"])):
        st.session_state[WEEK_FILTER_KEY] = valid_week_selection
    
    st.sidebar.multiselect("Semanas del Año", week_options, key=WEEK_FILTER_KEY, default=valid_week_selection)
    
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
        
        valid_selection_ms = [s for s in current_selection_ms if s in options]
        if not valid_selection_ms:
            if "– Todos –" in options:
                valid_selection_ms = ["– Todos –"]
            elif options: # Si hay opciones pero ninguna es "– Todos –"
                valid_selection_ms = [] # O [options[0]] si se prefiere seleccionar la primera por defecto

        if set(valid_selection_ms) != set(st.session_state.get(key, ["– Todos –"])):
             st.session_state[key] = valid_selection_ms

        return st.sidebar.multiselect(label, options, key=key, default=valid_selection_ms)

    analista_val_kpis = get_multiselect_val_kpis("Analista", "Analista", ANALISTA_FILTER_KEY, df_options)
    region_val_kpis = get_multiselect_val_kpis("Región", "Región", REGION_FILTER_KEY, df_options)
    
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros de KPIs", on_click=clear_kpis_filters_callback, use_container_width=True, key="btn_clear_kpis_filters_v2")
    return (st.session_state[START_DATE_KEY], st.session_state[END_DATE_KEY], selected_year_int, st.session_state[WEEK_FILTER_KEY], analista_val_kpis, region_val_kpis)

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
    st.markdown("### 📝 Datos Detallados Filtrados")
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
    # Asegurar que la columna de agrupación sea string para evitar errores con .str y .replace
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

# --- Flujo Principal de la Página ---
start_date_val_kpis, end_date_val_kpis, year_val_kpis, week_val_kpis, analista_val_kpis, region_val_kpis = sidebar_filters_kpis(df_kpis_semanales_raw)
df_kpis_filtered_page = apply_kpis_filters(df_kpis_semanales_raw, start_date_val_kpis, end_date_val_kpis, year_val_kpis, week_val_kpis, analista_val_kpis, region_val_kpis)

if "Analista" in df_kpis_filtered_page.columns and analista_val_kpis and "– Todos –" not in analista_val_kpis:
    if "N/D" not in analista_val_kpis: # Solo filtrar 'N/D' si 'N/D' no fue explícitamente seleccionado
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
display_time_evolution(df_kpis_filtered_page, 'NumSemana', 'Año-Semana', "Evolución Semanal de KPIs", "Semana", chart_icon="🗓️")
st.markdown("---")
display_time_evolution(df_kpis_filtered_page, 'AñoMes', 'AñoMes', "Evolución Mensual de KPIs", "Mes (Año-Mes)", chart_icon="📈")

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
