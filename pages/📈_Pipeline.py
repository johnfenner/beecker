# pages/📈_Pipeline.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import re # Para limpiar GID

# --- Configuración de Página ---
st.set_page_config(layout="wide", page_title="Pipeline de Prospección")
st.title("📈 Pipeline de Prospección (Oct 2025)")
st.markdown("Métricas de conversión y seguimiento del embudo de prospección.")

# --- Constantes y Claves de Sesión ---
PIPELINE_SHEET_URL_KEY = "pipeline_october_2025"
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/1Qd0ekzNwfHuUEGoqkCYCv6i6TM0X3jmK/edit?gid=971436223#gid=971436223"
SHEET_GID = "971436223" # Extraído de tu URL

# Columnas Clave del Pipeline
COL_PRIMARY_DATE = "Lead Generated (Date)" # Usaremos esta como la fecha principal
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_CONTACTED = "Contacted?"
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"
COL_MEETING_DATE = "Meeting Date"

# Claves de Sesión para Filtros (¡Únicas para esta página!)
SES_START_DATE_KEY = "pipeline_page_start_date_v1"
SES_END_DATE_KEY = "pipeline_page_end_date_v1"
SES_INDUSTRY_KEY = "pipeline_page_industry_v1"
SES_MANAGEMENT_KEY = "pipeline_page_management_v1"
SES_MEETING_KEY = "pipeline_page_meeting_v1"

# --- Funciones de Utilidad ---

def get_worksheet_by_gid(workbook, gid):
    """
    Encuentra una hoja de trabajo por su GID en un workbook de gspread.
    """
    gid = str(gid)
    try:
        worksheets = workbook.worksheets()
        for worksheet in worksheets:
            if str(worksheet.id) == gid:
                return worksheet
    except Exception as e:
        st.error(f"Error buscando GID {gid}: {e}")
    
    # Fallback si no se encuentra por GID (intenta con la primera)
    st.warning(f"No se encontró la hoja con GID {gid}. Usando la primera hoja por defecto.")
    try:
        return workbook.sheet1
    except Exception:
        return None

def parse_date_robustly(date_val):
    """Parsea fechas en varios formatos comunes."""
    if pd.isna(date_val) or str(date_val).strip() == "":
        return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)):
        return pd.to_datetime(date_val)
    
    date_str = str(date_val).strip()
    common_formats = (
        "%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d",
        "%d-%m-%Y", "%m-%d-%Y",
        "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S"
    )
    for fmt in common_formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except (ValueError, TypeError):
            continue
    # Intento final genérico
    return pd.to_datetime(date_str, errors='coerce')

def clean_yes_no(val):
    """Limpia valores 'Yes', 'Sí', 'No' a 'Si' o 'No'."""
    cleaned = str(val).strip().lower()
    if cleaned in ['yes', 'sí', 'si', '1', 'true']:
        return "Si"
    if cleaned in ['no', '0', 'false', '']:
        return "No"
    return "No" # Asumir 'No' por defecto si no es un 'Si' claro

def make_unique_headers(headers_list):
    """Garantiza que los nombres de las columnas sean únicos."""
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

def calculate_rate(numerator, denominator, round_to=1):
    """Calcula una tasa como porcentaje, manejando la división por cero."""
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- Carga y Procesamiento de Datos ---

@st.cache_data(ttl=300)
def load_pipeline_data():
    """Carga y procesa los datos de la hoja del Pipeline."""
    try:
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
    except Exception as e:
        st.error(f"Error de credenciales [gcp_service_account]: {e}")
        st.stop()

    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    
    try:
        workbook = client.open_by_url(sheet_url)
        # Extraer GID de la URL para asegurar que abrimos la hoja correcta
        gid_match = re.search(r'gid=(\d+)', sheet_url)
        gid_to_use = gid_match.group(1) if gid_match else SHEET_GID
        
        sheet = get_worksheet_by_gid(workbook, gid_to_use)
        if sheet is None:
            st.error(f"No se pudo encontrar la hoja con GID {gid_to_use}.")
            st.stop()
            
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error("La hoja del Pipeline está vacía o no se pudo leer.")
            return pd.DataFrame()
        
        headers = make_unique_headers(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)
        
    except Exception as e:
        st.error(f"Error al leer la hoja de Google Sheets (Pipeline): {e}")
        st.stop()

    # --- Procesamiento Específico del Pipeline ---
    
    # 1. Limpiar columnas de KPI (Sí/No)
    kpi_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in kpi_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no)
        else:
            st.warning(f"Columna KPI '{col}' no encontrada. Se rellenará con 'No'.")
            df[col] = "No"

    # 2. Parsear Fechas
    # Usamos la fecha principal para filtros y análisis de tiempo
    if COL_PRIMARY_DATE in df.columns:
        df['Fecha_Principal'] = df[COL_PRIMARY_DATE].apply(parse_date_robustly)
    else:
        st.error(f"Columna de fecha principal '{COL_PRIMARY_DATE}' no encontrada. No se puede continuar.")
        st.stop()
        
    # Parsear otras fechas relevantes
    if COL_MEETING_DATE in df.columns:
        df[COL_MEETING_DATE] = df[COL_MEETING_DATE].apply(parse_date_robustly)

    df.dropna(subset=['Fecha_Principal'], inplace=True)
    
    # 3. Crear columnas de tiempo para agrupar
    if not df.empty:
        df['Año'] = df['Fecha_Principal'].dt.year
        df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype(int)
        df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
    else:
        df['Año'] = pd.Series(dtype='int')
        df['NumSemana'] = pd.Series(dtype='int')
        df['AñoMes'] = pd.Series(dtype='str')

    # 4. Limpiar columnas categóricas (para filtros)
    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('', 'N/D')
        else:
            st.warning(f"Columna de filtro '{col}' no encontrada. Se rellenará con 'N/D'.")
            df[col] = "N/D"
            
    return df

# --- Filtros de Barra Lateral ---

def sidebar_filters_pipeline(df_options):
    """Renderiza los filtros en la barra lateral para la página del pipeline."""
    st.sidebar.header("🔍 Filtros del Pipeline")
    
    # Inicializar estado de sesión
    default_filters = {
        SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
        SES_INDUSTRY_KEY: ["– Todos –"], SES_MANAGEMENT_KEY: ["– Todos –"],
        SES_MEETING_KEY: "– Todos –"
    }
    for key, val in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = val

    # 1. Filtro de Fecha (basado en Fecha_Principal)
    st.sidebar.subheader("🗓️ Por Fecha de Lead Generado")
    min_date, max_date = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        min_date = df_options["Fecha_Principal"].min().date()
        max_date = df_options["Fecha_Principal"].max().date()
    
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

    # 2. Filtros Categóricos
    st.sidebar.subheader("👥 Por Atributo de Lead")
    
    def create_multiselect(col_name, label, key):
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            unique_vals = sorted(df_options[col_name].unique())
            options.extend([val for val in unique_vals if val != "N/D"])
            if "N/D" in df_options[col_name].unique():
                options.append("N/D")
        st.sidebar.multiselect(label, options, key=key)

    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)

    # 3. Filtro de Estado (Meeting)
    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)

    # 4. Botón de Limpiar
    def clear_pipeline_filters():
        for key, val in default_filters.items():
            st.session_state[key] = val
        st.toast("Filtros del Pipeline reiniciados ✅", icon="🧹")
        
    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_pipeline_filters, use_container_width=True)

    return (
        st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY],
        st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY],
        st.session_state[SES_MEETING_KEY]
    )

# --- Aplicación de Filtros ---

def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    """Aplica los filtros seleccionados al DataFrame del pipeline."""
    df_f = df.copy()

    # 1. Filtro de Fecha
    if "Fecha_Principal" in df_f.columns:
        start_dt_date = start_dt.date() if isinstance(start_dt, datetime.datetime) else start_dt
        end_dt_date = end_dt.date() if isinstance(end_dt, datetime.datetime) else end_dt
        if start_dt_date and end_dt_date:
            df_f = df_f[(df_f["Fecha_Principal"].dt.date >= start_dt_date) & (df_f["Fecha_Principal"].dt.date <= end_dt_date)]
    
    # 2. Filtros Categóricos
    if industries and "– Todos –" not in industries:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
        
    if managements and "– Todos –" not in managements:
        df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]

    # 3. Filtro de Estado
    if meeting_status != "– Todos –":
        df_f = df_f[df_f[COL_MEETING] == meeting_status]
        
    return df_f

# --- Componentes de Visualización ---

def display_pipeline_kpis(df_filtered):
    """Muestra las métricas KPI y las tasas de conversión."""
    st.markdown("### 🧮 Resumen del Embudo (Periodo Filtrado)")

    total_leads = len(df_filtered)
    total_contacted = len(df_filtered[df_filtered[COL_CONTACTED] == "Si"])
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])

    # Métricas Absolutas
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads (Filtrados)", f"{total_leads:,}")
    c2.metric("Contactados", f"{total_contacted:,}")
    c3.metric("Respondieron", f"{total_responded:,}")
    c4.metric("Reuniones Agendadas", f"{total_meetings:,}")

    st.markdown("---")
    st.markdown("#### Tasas de Conversión")
    
    # Tasas
    rate_contact = calculate_rate(total_contacted, total_leads)
    rate_response = calculate_rate(total_responded, total_contacted)
    rate_meeting = calculate_rate(total_meetings, total_responded)
    rate_global = calculate_rate(total_meetings, total_leads)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Tasa de Contacto", f"{rate_contact:.1f}%", help="Contactados / Total Leads")
    r2.metric("Tasa de Respuesta", f"{rate_response:.1f}%", help="Respondieron / Contactados")
    r3.metric("Tasa de Reunión", f"{rate_meeting:.1f}%", help="Reuniones / Respondieron")
    r4.metric("Tasa de Conversión Global", f"{rate_global:.1f}%", help="Reuniones / Total Leads")

def display_pipeline_funnel(df_filtered):
    """Muestra un gráfico de embudo de conversión."""
    
    total_leads = len(df_filtered)
    total_contacted = len(df_filtered[df_filtered[COL_CONTACTED] == "Si"])
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])
    
    funnel_data = pd.DataFrame({
        "Etapa": ["Total Leads", "Contactados", "Respondieron", "Reuniones"],
        "Cantidad": [total_leads, total_contacted, total_responded, total_meetings]
    })
    
    fig = go.Figure(go.Funnel(
        y=funnel_data["Etapa"],
        x=funnel_data["Cantidad"],
        textposition="inside",
        textinfo="value+percent previous"
    ))
    fig.update_layout(title="Embudo de Conversión del Pipeline")
    st.plotly_chart(fig, use_container_width=True)

def display_breakdown_charts(df_filtered):
    """Muestra gráficos de barras por Industria y Nivel de Management."""
    st.markdown("---")
    st.markdown("### 📊 Desglose por Atributo")

    if df_filtered.empty:
        st.info("No hay datos para mostrar en los desgloses.")
        return

    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown(f"#### Reuniones por {COL_INDUSTRY}")
        if COL_INDUSTRY in df_filtered.columns:
            industry_summary = df_filtered[df_filtered[COL_MEETING] == "Si"][COL_INDUSTRY].value_counts().reset_index()
            industry_summary.columns = [COL_INDUSTRY, 'Reuniones']
            if not industry_summary.empty:
                fig = px.bar(industry_summary.head(10), x=COL_INDUSTRY, y='Reuniones', title="Top 10 Industrias por Reuniones", text_auto=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No hay reuniones agendadas para este desglose.")
        
    with c2:
        st.markdown(f"#### Reuniones por {COL_MANAGEMENT}")
        if COL_MANAGEMENT in df_filtered.columns:
            management_summary = df_filtered[df_filtered[COL_MEETING] == "Si"][COL_MANAGEMENT].value_counts().reset_index()
            management_summary.columns = [COL_MANAGEMENT, 'Reuniones']
            if not management_summary.empty:
                fig = px.bar(management_summary.head(10), x=COL_MANAGEMENT, y='Reuniones', title="Top 10 Nivel de Management por Reuniones", text_auto=True)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No hay reuniones agendadas para este desglose.")

def display_time_evolution(df_filtered):
    """Muestra la evolución de leads y reuniones a lo largo del tiempo."""
    st.markdown("---")
    st.markdown("### 📈 Evolución Temporal (por 'Lead Generated Date')")
    
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns:
        st.info("No hay suficientes datos para mostrar la evolución temporal.")
        return

    time_summary = df_filtered.groupby('AñoMes').agg(
        Total_Leads=('AñoMes', 'count'),
        Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index().sort_values('AñoMes')
    
    if not time_summary.empty:
        fig = px.line(time_summary, x='AñoMes', y=['Total_Leads', 'Total_Reuniones'],
                      title="Evolución de Leads Generados vs. Reuniones Agendadas",
                      markers=True, labels={"value": "Cantidad", "variable": "Métrica"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.caption("No hay datos de evolución temporal.")


# --- Flujo Principal de la Página ---
df_pipeline_base = load_pipeline_data()

if df_pipeline_base.empty:
    st.error("El DataFrame del Pipeline está vacío. No se puede continuar.")
    st.stop()

# Obtener valores de los filtros de la barra lateral
start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base)

# Aplicar filtros
df_pipeline_filtered = apply_pipeline_filters(
    df_pipeline_base, start_date, end_date, industries, managements, meeting_status
)

# --- Presentación del Dashboard ---
if not df_pipeline_filtered.empty:
    display_pipeline_kpis(df_pipeline_filtered)
    
    display_pipeline_funnel(df_pipeline_filtered)
    
    display_breakdown_charts(df_pipeline_filtered)

    display_time_evolution(df_pipeline_filtered)

    with st.expander("Ver tabla de datos detallados del pipeline (filtrada)"):
        # Seleccionar un subconjunto de columnas para no saturar
        cols_to_show = [
            "Full Name", "Company", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT,
            COL_PRIMARY_DATE, COL_CONTACTED, COL_RESPONDED, COL_MEETING, COL_MEETING_DATE,
            "Response Channel", "LinkedIn URL"
        ]
        cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
        st.dataframe(df_pipeline_filtered[cols_exist], hide_index=True)
else:
    st.info("No se encontraron datos que coincidan con los filtros seleccionados.")

st.markdown("---")
st.info("Esta página ha sido generada siguiendo el patrón de KPIs SDR.")
