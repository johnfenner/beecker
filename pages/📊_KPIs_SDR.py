# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de Desempeño SDR", layout="wide")
st.title("📊 Dashboard de Desempeño SDR")

# --- SELECTOR DE PERSPECTIVA (LA SOLUCIÓN AL "PROBLEMOTA") ---
st.markdown("---")
analysis_mode = st.radio(
    "Selecciona la perspectiva del análisis:",
    options=["Desempeño del Mes (Fecha del Evento)", "Análisis de Cohorte (Fecha de Primer Contacto)"],
    horizontal=True,
    help=(
        "**Desempeño del Mes:** Muestra los totales de eventos que ocurrieron en el período seleccionado (ej: sesiones agendadas en Julio). "
        "**Análisis de Cohorte:** Filtra un grupo de prospectos por su fecha de primer contacto y analiza todo su recorrido."
    )
)
st.markdown("---")


# --- FUNCIONES DE CARGA Y LÓGICA DE NEGOCIO ---

def make_unique(headers_list):
    """Garantiza que los encabezados de columna sean únicos."""
    counts = Counter()
    new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped: h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1:
            new_headers.append(h_stripped)
        else:
            new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

@st.cache_data(ttl=300)
def load_and_process_sdr_data():
    """
    Carga y procesa datos desde la hoja 'Evelyn'.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        client = gspread.service_account_from_dict(creds_dict)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet("Evelyn")
        values = sheet.get_all_values()
        if len(values) < 2: return pd.DataFrame()
        headers = make_unique(values[0])
        df = pd.DataFrame(values[1:], columns=headers)
    except Exception as e:
        st.error(f"No se pudo cargar la hoja 'Evelyn'. Error: {e}")
        return pd.DataFrame()

    date_columns_to_process = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha_Primer_Contacto",
        "Fecha de Primer Acercamiento": "Fecha_Primer_Acercamiento",
        "Fecha de Primer Respuesta": "Fecha_Primera_Respuesta",
        "Fecha De Recontacto": "Fecha_Recontacto",
        "Fecha Agendamiento": "Fecha_Agendamiento"
    }
    
    for original_col, new_col in date_columns_to_process.items():
        if original_col in df.columns:
            df[new_col] = pd.to_datetime(df[original_col], format='%d/%m/%Y', errors='coerce')
        else:
            df[new_col] = pd.NaT

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

def sidebar_filters(df, mode):
    st.sidebar.header("🔍 Filtros de Análisis")
    if df.empty:
        st.sidebar.warning("No hay datos para filtrar.")
        return None, None, {}
    
    date_col = 'Fecha_Primer_Contacto'
    st.sidebar.subheader(f"📅 Filtrar por Fecha")
    
    min_date = df[date_col].dropna().min().date()
    max_date = df[date_col].dropna().max().date()

    # Usamos un rango de fechas unificado para ambos modos
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Fecha Inicial", value=min_date, min_value=min_date, max_value=max_date, key="start_date")
    end_date = col2.date_input("Fecha Final", value=max_date, min_value=start_date, max_value=max_date, key="end_date")

    other_filters = {}
    st.sidebar.subheader("🔎 Filtros Adicionales")
    prospecting_cols = ["Fuente de la Lista", "Campaña"]
    for dim_col in prospecting_cols:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtro_key = f"filter_{dim_col.lower().replace(' ', '_')}"
            other_filters[dim_col] = st.sidebar.multiselect(f"Filtrar por {dim_col}", opciones, default=["– Todos –"], key=filtro_key)
    
    return start_date, end_date, other_filters

def display_kpi_summary(df, start_date, end_date, other_filters, mode):
    st.header(f"🧮 Resumen de KPIs: {mode}")

    df_filtered_by_cats = df.copy()
    for col, values in other_filters.items():
        if values and "– Todos –" not in values:
            df_filtered_by_cats = df_filtered_by_cats[df_filtered_by_cats[col].isin(values)]
    
    start_date = pd.to_datetime(start_date)
    end_date = pd.to_datetime(end_date)

    if mode == "Análisis de Cohorte (Fecha de Primer Contacto)":
        mask = (df_filtered_by_cats['Fecha_Primer_Contacto'] >= start_date) & (df_filtered_by_cats['Fecha_Primer_Contacto'] <= end_date)
        df_final_cohort = df_filtered_by_cats[mask]
        
        total_acercamientos = len(df_final_cohort)
        total_mensajes = df_final_cohort['Fecha_Primer_Acercamiento'].notna().sum()
        total_respuestas = df_final_cohort['Fecha_Primera_Respuesta'].notna().sum()
        total_sesiones = df_final_cohort['Fecha_Agendamiento'].notna().sum()
        
    else: # Desempeño del Mes (Fecha del Evento)
        total_acercamientos = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Primer_Contacto'] >= start_date) & (df_filtered_by_cats['Fecha_Primer_Contacto'] <= end_date)])
        total_mensajes = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Primer_Acercamiento'] >= start_date) & (df_filtered_by_cats['Fecha_Primer_Acercamiento'] <= end_date)])
        total_respuestas = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Primera_Respuesta'] >= start_date) & (df_filtered_by_cats['Fecha_Primera_Respuesta'] <= end_date)])
        total_sesiones = len(df_filtered_by_cats[(df_filtered_by_cats['Fecha_Agendamiento'] >= start_date) & (df_filtered_by_cats['Fecha_Agendamiento'] <= end_date)])

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("🚀 Total Acercamientos", f"{total_acercamientos:,}")
    kpi_cols[1].metric("📤 Total Mensajes Enviados", f"{total_mensajes:,}")
    kpi_cols[2].metric("💬 Total Respuestas Iniciales", f"{total_respuestas:,}")
    kpi_cols[3].metric("🗓️ Total Sesiones Agendadas", f"{total_sesiones:,}")

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
    start_date, end_date, other_filters = sidebar_filters(df_sdr_data, analysis_mode)
    
    if start_date and end_date:
        display_kpi_summary(df_sdr_data, start_date, end_date, other_filters, analysis_mode)
    else:
        st.warning("Por favor, selecciona un rango de fechas válido en la barra lateral.")

    # El resto de los desgloses se pueden adaptar o mostrar condicionalmente si se desea
    st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
    with st.expander("Ver tabla de datos completos (sin filtrar por fecha)"):
        st.dataframe(df_sdr_data, hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")
