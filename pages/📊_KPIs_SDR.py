# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
from collections import Counter

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Desempeño SDR", layout="wide")
st.title("📊 Dashboard de Desempeño SDR")

# --- SELECTOR DE PERSPECTIVA ---
st.markdown("---")
analysis_mode = st.radio(
    "Selecciona la perspectiva del análisis:",
    options=["Desempeño del Mes (Fecha del Evento)", "Análisis de Cohorte (Fecha de Primer Contacto)"],
    horizontal=True,
    key="analysis_mode_selector",
    help=(
        "**Desempeño del Mes:** Muestra los totales de eventos que ocurrieron en el período seleccionado (ej: sesiones agendadas en Julio). "
        "**Análisis de Cohorte:** Filtra un grupo de prospectos por su fecha de primer contacto y analiza todo su recorrido."
    )
)
st.markdown("---")

# --- FUNCIONES DE CARGA Y LÓGICA DE NEGOCIO ---

@st.cache_data(ttl=300)
def load_and_process_sdr_data():
    """
    Carga y procesa todos los datos y fechas necesarios desde la hoja 'Evelyn'.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        client = gspread.service_account_from_dict(creds_dict)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet("Evelyn")
        values = sheet.get_all_values()
        if len(values) < 2: return pd.DataFrame()
        
        # Función interna para asegurar encabezados únicos
        counts = Counter()
        headers = []
        for h in values[0]:
            h_stripped = str(h).strip()
            counts[h_stripped] += 1
            if counts[h_stripped] == 1:
                headers.append(h_stripped)
            else:
                headers.append(f"{h_stripped}_{counts[h_stripped]-1}")

        df = pd.DataFrame(values[1:], columns=headers)
    except Exception as e:
        st.error(f"No se pudo cargar la hoja 'Evelyn'. Error: {e}")
        return pd.DataFrame()

    date_columns = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha_Primer_Contacto",
        "Fecha de Primer Acercamiento": "Fecha_Primer_Acercamiento",
        "Fecha de Primer Respuesta": "Fecha_Primera_Respuesta",
        "Fecha De Recontacto": "Fecha_Recontacto",
        "Fecha Agendamiento": "Fecha_Agendamiento"
    }
    
    for original, new in date_columns.items():
        if original in df.columns:
            df[new] = pd.to_datetime(df[original], format='%d/%m/%Y', errors='coerce')
        else:
            df[new] = pd.NaT

    df['AñoMes_Contacto'] = df['Fecha_Primer_Contacto'].dt.strftime('%Y-%m')
    
    for col in ["Fuente de la Lista", "Campaña", "Proceso", "Industria", "Pais", "Puesto"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"
    return df

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- COMPONENTES VISUALES Y DE FILTRADO ---

def sidebar_filters(df):
    """
    Gestiona los filtros de la barra lateral. Devuelve un rango de fechas y filtros de categorías.
    La interfaz es la original, con el selector de modo de fecha.
    """
    st.sidebar.header("🔍 Filtros de Análisis")
    if df.empty:
        return None, None, {}

    st.sidebar.subheader("📅 Filtrar por Fecha")
    filter_mode = st.sidebar.radio(
        "Elige cómo filtrar por fecha:",
        ("Rango de Fechas", "Mes(es) Específico(s)"),
        key="date_filter_mode",
        horizontal=True
    )
    
    start_date, end_date = None, None

    if filter_mode == "Rango de Fechas":
        min_date = df['Fecha_Primer_Contacto'].dropna().min().date()
        max_date = df['Fecha_Primer_Contacto'].dropna().max().date()
        col1, col2 = st.sidebar.columns(2)
        start_date = col1.date_input("Fecha Inicial", value=min_date, min_value=min_date, max_value=max_date, key="start_date")
        end_date = col2.date_input("Fecha Final", value=max_date, min_value=start_date, max_value=max_date, key="end_date")
    else: # Mes(es) Específico(s)
        meses_disponibles = sorted(df['AñoMes_Contacto'].dropna().unique(), reverse=True)
        selected_months = st.sidebar.multiselect("Selecciona el/los mes(es):", meses_disponibles, key="month_select")
        if selected_months:
            start_date = pd.to_datetime(min(selected_months) + "-01").date()
            last_month = pd.to_datetime(max(selected_months) + "-01")
            end_date = (last_month + pd.offsets.MonthEnd(1)).date()

    other_filters = {}
    st.sidebar.subheader("🔎 Filtros Adicionales")
    for dim_col in ["Fuente de la Lista", "Campaña"]:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            other_filters[dim_col] = st.sidebar.multiselect(f"Filtrar por {dim_col}", opciones, default=["– Todos –"])
    
    return start_date, end_date, other_filters


def display_kpi_summary(df, start_date, end_date, other_filters, mode):
    """
    Calcula y muestra los KPIs según la perspectiva de análisis seleccionada.
    """
    st.header(f"🧮 Resumen de KPIs: {mode.split('(')[0].strip()}")

    # Aplica filtros de categorías (Fuente, Campaña, etc.) primero
    df_filtered_by_cats = df.copy()
    for col, values in other_filters.items():
        if values and "– Todos –" not in values:
            df_filtered_by_cats = df_filtered_by_cats[df_filtered_by_cats[col].isin(values)]
    
    start_date_ts = pd.to_datetime(start_date)
    end_date_ts = pd.to_datetime(end_date)

    if mode == "Análisis de Cohorte (Fecha de Primer Contacto)":
        # 1. Se filtra el grupo de prospectos por fecha de primer contacto
        mask = (df_filtered_by_cats['Fecha_Primer_Contacto'] >= start_date_ts) & (df_filtered_by_cats['Fecha_Primer_Contacto'] <= end_date_ts)
        df_cohort = df_filtered_by_cats[mask]
        
        # 2. Todos los KPIs se calculan sobre ese grupo fijo
        total_acercamientos = len(df_cohort)
        total_mensajes = df_cohort['Fecha_Primer_Acercamiento'].notna().sum()
        total_respuestas = df_cohort['Fecha_Primera_Respuesta'].notna().sum()
        total_sesiones = df_cohort['Fecha_Agendamiento'].notna().sum()
        
    else: # "Desempeño del Mes (Fecha del Evento)"
        # Cada KPI se calcula de forma independiente filtrando por su propia fecha
        total_acercamientos = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Primer_Contacto'] >= start_date_ts) & (df_filtered_by_cats['Fecha_Primer_Contacto'] <= end_date_ts)])
        total_mensajes = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Primer_Acercamiento'] >= start_date_ts) & (df_filtered_by_cats['Fecha_Primer_Acercamiento'] <= end_date_ts)])
        total_respuestas = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Primera_Respuesta'] >= start_date_ts) & (df_filtered_by_cats['Fecha_Primera_Respuesta'] <= end_date_ts)])
        total_sesiones = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Agendamiento'] >= start_date_ts) & (df_filtered_by_cats['Fecha_Agendamiento'] <= end_date_ts)])

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("🚀 Total Acercamientos", f"{int(total_acercamientos):,}")
    kpi_cols[1].metric("📤 Total Mensajes Enviados", f"{int(total_mensajes):,}")
    kpi_cols[2].metric("💬 Total Respuestas Iniciales", f"{int(total_respuestas):,}")
    kpi_cols[3].metric("🗓️ Total Sesiones Agendadas", f"{int(total_sesiones):,}")

    # Las tasas de conversión solo tienen sentido en el Análisis de Cohorte
    if mode == "Análisis de Cohorte (Fecha de Primer Contacto)":
        st.markdown("---")
        st.markdown("#### 📊 Tasas de Conversión de la Cohorte")
        tasa_mens_vs_acerc = calculate_rate(total_mensajes, total_acercamientos)
        tasa_resp_vs_msj = calculate_rate(total_respuestas, total_mensajes)
        tasa_sesion_vs_resp = calculate_rate(total_sesiones, total_respuestas)
        tasa_sesion_global = calculate_rate(total_sesiones, total_acercamientos)

        rate_cols = st.columns(4)
        rate_cols[0].metric("📨 Tasa Mensajes / Acercamiento", f"{tasa_mens_vs_acerc:.1f}%")
        rate_cols[1].metric("🗣️ Tasa Respuesta / Mensaje", f"{tasa_resp_vs_msj:.1f}%")
        rate_cols[2].metric("🤝 Tasa Sesión / Respuesta", f"{tasa_sesion_vs_resp:.1f}%")
        rate_cols[3].metric("🏆 Tasa Sesión / Acercamiento (Global)", f"{tasa_sesion_global:.1f}%")


# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_data = load_and_process_sdr_data()

if not df_sdr_data.empty:
    start_date, end_date, other_filters = sidebar_filters(df_sdr_data)
    
    if start_date and end_date:
        display_kpi_summary(df_sdr_data, start_date, end_date, other_filters, analysis_mode)
        # Aquí se podrían añadir más visualizaciones que respeten el modo de análisis
    else:
        st.info("Por favor, selecciona un rango de fechas o uno o más meses en la barra lateral para comenzar el análisis.")

    st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
    with st.expander("Ver tabla de datos completos (sin filtrar)"):
        st.dataframe(df_sdr_data, hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")
