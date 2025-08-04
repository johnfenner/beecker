# pages/📊_KPIs_SDR.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px

# --- Configuración Inicial de la Página ---
st.set_page_config(layout="wide", page_title="KPIs SDR (Evelyn)")
st.title("📊 Dashboard de KPIs de SDR (Evelyn)")
st.markdown(
    "Análisis de métricas absolutas y tasas de conversión para el SDR."
)

# --- Funciones de Procesamiento de Datos ---

def parse_kpi_value(value_str, column_name=""):
    """
    Parsea un valor de KPI, que puede ser numérico o de texto ('si', 'vc', etc.),
    a un valor numérico flotante.
    """
    cleaned_val = str(value_str).strip().lower()
    if not cleaned_val: return 0.0
    try:
        # Intenta convertir directamente a número
        num_val = pd.to_numeric(cleaned_val, errors='raise')
        return 0.0 if pd.isna(num_val) else float(num_val)
    except ValueError:
        # Si falla, procesa como texto
        pass
    
    # Lógica especial para columnas que pueden tener texto afirmativo
    if column_name == "Sesiones agendadas":
        affirmative_session_texts = ['vc', 'si', 'sí', 'yes', 'true', '1', '1.0']
        if cleaned_val in affirmative_session_texts: return 1.0
        return 0.0
    else:
        # Intenta extraer un número de una cadena (ej. '1 - Realizada')
        first_part = cleaned_val.split('-')[0].strip()
        if not first_part: return 0.0
        try:
            num_val_from_part = pd.to_numeric(first_part, errors='raise')
            return 0.0 if pd.isna(num_val_from_part) else float(num_val_from_part)
        except ValueError:
            return 0.0

@st.cache_data(ttl=300)
def load_sdr_kpi_data():
    """
    Carga los datos de KPIs para el SDR desde la hoja 'KPI's SDR'.
    """
    try:
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account] en los 'Secrets' de Streamlit.")
        st.stop()
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets para KPIs de SDR: {e}")
        st.stop()

    sheet_url_kpis = st.secrets.get(
        "main_prostraction_sheet_url",
        "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0"
    )
    
    try:
        workbook = client.open_by_url(sheet_url_kpis)
        # --- LÍNEA MODIFICADA ---
        # Se cambia el apóstrofo para que coincida con el de tu hoja.
        sheet = workbook.worksheet("KPI´s SDR") # <-- CAMBIO CLAVE
        
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos suficientes de la hoja 'KPI´s SDR'.")
            return pd.DataFrame()
        headers = raw_data[0]
        rows = raw_data[1:]
    except gspread.exceptions.WorksheetNotFound:
        # Este mensaje de error seguirá siendo útil si el nombre vuelve a cambiar.
        st.error(f"Error: No se encontró la hoja de cálculo 'KPI´s SDR' en el Google Sheet.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja 'KPI´s SDR': {e}")
        st.stop()

    # El resto de la función permanece igual...
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
        st.warning("Columna 'Fecha' no encontrada. No se podrán aplicar filtros de fecha.")
        for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
        df['AñoMes'] = pd.Series(dtype='str')

    kpi_columns_ordered = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    for col_name in kpi_columns_ordered:
        if col_name not in df.columns:
            st.warning(f"Columna KPI '{col_name}' no encontrada. Se creará con ceros.")
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
    """Calcula una tasa como porcentaje, manejando la división por cero."""
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- Carga de Datos ---
df_kpis_sdr_raw = load_sdr_kpi_data()

if df_kpis_sdr_raw.empty:
    st.error("El DataFrame de KPIs de SDR está vacío después de la carga. No se puede continuar.")
    st.stop()

# --- Gestión de Estado y Filtros (Sidebar) ---
START_DATE_KEY = "sdr_page_fecha_inicio_v1"
END_DATE_KEY = "sdr_page_fecha_fin_v1"
ANALISTA_FILTER_KEY = "sdr_page_filtro_Analista_v1"
REGION_FILTER_KEY = "sdr_page_filtro_Región_v1"
YEAR_FILTER_KEY = "sdr_page_filtro_Año_v1"
WEEK_FILTER_KEY = "sdr_page_filtro_Semana_v1"

default_filters_sdr = {
    START_DATE_KEY: None, END_DATE_KEY: None,
    ANALISTA_FILTER_KEY: ["– Todos –"], REGION_FILTER_KEY: ["– Todos –"],
    YEAR_FILTER_KEY: "– Todos –", WEEK_FILTER_KEY: ["– Todas –"],
}
for key, default_val in default_filters_sdr.items():
    if key not in st.session_state: st.session_state[key] = default_val

def clear_sdr_filters_callback():
    """Limpia los filtros de esta página."""
    for key, default_val in default_filters_sdr.items():
        st.session_state[key] = default_val
    st.toast("Filtros de KPIs de SDR reiniciados ✅", icon="🧹")

def sidebar_filters_sdr(df_options):
    """Renderiza los filtros en la barra lateral."""
    st.sidebar.header("🔍 Filtros de KPIs de SDR")
    st.sidebar.markdown("---")
    
    # Lógica de filtros (es la misma que en KPIs.py)
    # Por Fecha
    st.sidebar.subheader("🗓️ Por Fecha")
    min_date_data, max_date_data = None, None
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) and not df_options["Fecha"].dropna().empty:
        min_date_data, max_date_data = df_options["Fecha"].dropna().min().date(), df_options["Fecha"].dropna().max().date()
    
    col1_date, col2_date = st.sidebar.columns(2)
    with col1_date:
        st.date_input("Desde", value=st.session_state.get(START_DATE_KEY), min_value=min_date_data, max_value=max_date_data, format='DD/MM/YYYY', key=START_DATE_KEY)
    with col2_date:
        st.date_input("Hasta", value=st.session_state.get(END_DATE_KEY), min_value=min_date_data, max_value=max_date_data, format='DD/MM/YYYY', key=END_DATE_KEY)

    # Por Año y Semana
    st.sidebar.subheader("📅 Por Año y Semana")
    # ... (código idéntico a KPIs.py para filtros de año y semana)
    raw_year_options_int = []
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
        raw_year_options_int = sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True)
    
    year_options_str_list = ["– Todos –"] + [str(y) for y in raw_year_options_int]
    selected_year_str = st.sidebar.selectbox("Año", year_options_str_list, key=YEAR_FILTER_KEY)
    selected_year_int = int(selected_year_str) if selected_year_str != "– Todos –" else None

    # Por Analista y Región
    st.sidebar.subheader("👥 Por Analista y Región")
    
    def get_multiselect_val_sdr(col_name, label, key, df_opt):
        options = ["– Todos –"]
        if col_name in df_opt.columns and not df_opt[col_name].dropna().empty:
            unique_vals = df_opt[col_name].astype(str).str.strip().replace('', 'N/D').unique()
            options.extend(sorted([val for val in unique_vals if val and val != 'N/D']))
        return st.sidebar.multiselect(label, options, key=key)

    get_multiselect_val_sdr("Analista", "Analista", ANALISTA_FILTER_KEY, df_options)
    get_multiselect_val_sdr("Región", "Región", REGION_FILTER_KEY, df_options)
    
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros de SDR", on_click=clear_sdr_filters_callback, use_container_width=True)
    
    return (st.session_state[START_DATE_KEY], st.session_state[END_DATE_KEY], selected_year_int,
            st.session_state[WEEK_FILTER_KEY], st.session_state[ANALISTA_FILTER_KEY], st.session_state[REGION_FILTER_KEY])

def apply_sdr_filters(df, start_dt, end_dt, year_val, week_list, analista_list, region_list):
    """Aplica todos los filtros al DataFrame."""
    df_f = df.copy()
    if "Fecha" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f["Fecha"]):
        start_dt_date = start_dt.date() if isinstance(start_dt, datetime.datetime) else start_dt
        end_dt_date = end_dt.date() if isinstance(end_dt, datetime.datetime) else end_dt
        if start_dt_date and end_dt_date:
            df_f = df_f[(df_f["Fecha"].dt.date >= start_dt_date) & (df_f["Fecha"].dt.date <= end_dt_date)]
    
    if analista_list and "– Todos –" not in analista_list and "Analista" in df_f.columns:
        df_f = df_f[df_f["Analista"].isin(analista_list)]
    if region_list and "– Todos –" not in region_list and "Región" in df_f.columns:
        df_f = df_f[df_f["Región"].isin(region_list)]
        
    return df_f

# --- Componentes de Visualización (Reutilizados de KPIs.py) ---
def display_kpi_summary(df_filtered):
    st.markdown("### 🧮 Resumen de KPIs Totales (Periodo Filtrado)")
    
    kpi_cols_funnel_order = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    icons_funnel_order = ["📧", "📤", "💬", "🤝"]
    
    metrics = {col: df_filtered[col].sum() if col in df_filtered.columns else 0 for col in kpi_cols_funnel_order}

    col_metrics_abs = st.columns(len(kpi_cols_funnel_order))
    for i, col_name in enumerate(kpi_cols_funnel_order):
        col_metrics_abs[i].metric(f"{icons_funnel_order[i]} Total {col_name.title()}", f"{metrics.get(col_name, 0):,}")
    
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
    col_metrics_rates[0].metric(f"{rate_icons[0]} Tasa Mensajes / Invite", f"{tasa_mensajes_vs_invites:.1f}%")
    col_metrics_rates[1].metric(f"{rate_icons[1]} Tasa Respuesta / Mensaje", f"{tasa_respuestas_vs_mensajes:.1f}%")
    col_metrics_rates[2].metric(f"{rate_icons[2]} Tasa Agend. / Respuesta", f"{tasa_sesiones_vs_respuestas:.1f}%")
    col_metrics_rates[3].metric(f"{rate_icons[3]} Tasa Agend. / Invite (Global)", f"{tasa_sesiones_vs_invites_global:.1f}%")

def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    st.markdown(f"### {chart_icon} {title_prefix}")
    if group_by_col not in df_filtered.columns or df_filtered.empty:
        st.warning(f"No hay datos o falta la columna '{group_by_col}'.")
        return
        
    kpi_cols_funnel = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    summary_df = df_filtered.groupby(group_by_col, as_index=False)[kpi_cols_funnel].sum()
    
    if not summary_df.empty:
        st.markdown(f"##### Tabla Resumen por {group_by_col}")
        st.dataframe(summary_df, use_container_width=True)
    else:
        st.info(f"No hay datos para desglosar por {group_by_col}.")

# --- Flujo Principal de la Página ---
start_date_val, end_date_val, year_val, week_val, analista_val, region_val = sidebar_filters_sdr(df_kpis_sdr_raw)

df_kpis_sdr_filtered = apply_sdr_filters(
    df_kpis_sdr_raw, start_date_val, end_date_val, year_val, week_val, analista_val, region_val
)

# --- Presentación del Dashboard ---
if not df_kpis_sdr_filtered.empty:
    display_kpi_summary(df_kpis_sdr_filtered)
    st.markdown("---")
    
    display_grouped_breakdown(df_kpis_sdr_filtered, "Analista", "Desglose por Analista", chart_icon="🧑‍💻")
    st.markdown("---")
    display_grouped_breakdown(df_kpis_sdr_filtered, "Región", "Desglose por Región", chart_icon="🌎")
    st.markdown("---")

    with st.expander("Ver tabla de datos detallados del período filtrado"):
        st.dataframe(df_kpis_sdr_filtered, hide_index=True)
else:
    st.info("No se encontraron datos que coincidan con los filtros seleccionados.")

st.markdown("---")
