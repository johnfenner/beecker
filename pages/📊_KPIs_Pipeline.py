import streamlit as st
import pandas as pd
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import re

st.set_page_config(layout="wide", page_title="Pipeline de Prospección")
st.title("📈 Pipeline de Prospección (Oct 2025)")
st.markdown("Métricas de conversión y seguimiento del embudo de prospección.")

PIPELINE_SHEET_URL_KEY = "pipeline_october_2025"
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/1Qd0ekzNwfHuUEGoqkCYCv6i6TM0X3jmK/edit?gid=971436223#gid=971436223"
PIPELINE_SHEET_NAME = "Prospects"

COL_PRIMARY_DATE = "Lead Generated (Date)"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_CONTACTED = "Contacted?"
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"
COL_MEETING_DATE = "Meeting Date"

SES_START_DATE_KEY = "pipeline_page_start_date_v1"
SES_END_DATE_KEY = "pipeline_page_end_date_v1"
SES_INDUSTRY_KEY = "pipeline_page_industry_v1"
SES_MANAGEMENT_KEY = "pipeline_page_management_v1"
SES_MEETING_KEY = "pipeline_page_meeting_v1"

def parse_date_robustly(date_val):
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
    return pd.to_datetime(date_str, errors='coerce')

def clean_yes_no(val):
    cleaned = str(val).strip().lower()
    if cleaned in ['yes', 'sí', 'si', '1', 'true']:
        return "Si"
    if cleaned in ['no', '0', 'false', '']:
        return "No"
    return "No" 

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

@st.cache_data(ttl=300)
def load_pipeline_data():
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    
    try:
        file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', sheet_url)
        if not file_id_match:
            st.error(f"No se pudo extraer el FILE_ID de la URL: {sheet_url}")
            st.stop()
        
        file_id = file_id_match.group(1)
        
        # --- NUEVA URL DE DESCARGA ---
        download_url = f"https://drive.google.com/u/0/uc?id={file_id}&export=download&format=xlsx"
        
        df = pd.read_excel(
            download_url, 
            sheet_name=PIPELINE_SHEET_NAME,
            engine="openpyxl" 
        )
        
    except Exception as e:
        st.error(f"Error al leer el archivo Excel desde Google Drive: {e}")
        st.info(f"Asegúrate de que el archivo (ID: {file_id}) tenga permisos de 'Cualquier persona con el enlace puede ver'.")
        st.info(f"También verifica que la pestaña se llame exactamente: '{PIPELINE_SHEET_NAME}'")
        st.stop()

    kpi_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in kpi_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no)
        else:
            df[col] = "No"

    if COL_PRIMARY_DATE in df.columns:
        df['Fecha_Principal'] = df[COL_PRIMARY_DATE].apply(parse_date_robustly)
    else:
        st.error(f"Columna de fecha principal '{COL_PRIMARY_DATE}' no encontrada.")
        st.stop()
        
    if COL_MEETING_DATE in df.columns:
        df[COL_MEETING_DATE] = df[COL_MEETING_DATE].apply(parse_date_robustly)

    df.dropna(subset=['Fecha_Principal'], inplace=True)
    
    if not df.empty:
        df['Año'] = df['Fecha_Principal'].dt.year
        df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype(int)
        df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
    else:
        df['Año'] = pd.Series(dtype='int')
        df['NumSemana'] = pd.Series(dtype='int')
        df['AñoMes'] = pd.Series(dtype='str')

    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('N/D')
            df[col] = df[col].astype(str).str.strip().replace('', 'N/D')
        else:
            df[col] = "N/D"
            
    return df

def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")
    
    default_filters = {
        SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
        SES_INDUSTRY_KEY: ["– Todos –"], SES_MANAGEMENT_KEY: ["– Todos –"],
        SES_MEETING_KEY: "– Todos –"
    }
    for key, val in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = val

    st.sidebar.subheader("🗓️ Por Fecha de Lead Generado")
    min_date, max_date = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        min_date = df_options["Fecha_Principal"].min().date()
        max_date = df_options["Fecha_Principal"].max().date()
    
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

    st.sidebar.subheader("👥 Por Atributo de Lead")
    
    def create_multiselect(col_name, label, key):
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            unique_vals = sorted(df_options[col_name].astype(str).unique())
            options.extend([val for val in unique_vals if val != "N/D"])
            if "N/D" in df_options[col_name].astype(str).unique():
                options.append("N/D")
        st.sidebar.multiselect(label, options, key=key)

    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)

    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)

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

def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    df_f = df.copy()

    if "Fecha_Principal" in df_f.columns:
        start_dt_date = pd.to_datetime(start_dt).date() if start_dt else None
        end_dt_date = pd.to_datetime(end_dt).date() if end_dt else None
        
        fecha_series_valid = df_f["Fecha_Principal"].dropna().dt.date

        if start_dt_date and end_dt_date:
            df_f = df_f[fecha_series_valid.between(start_dt_date, end_dt_date, inclusive="both")]
        elif start_dt_date:
            df_f = df_f[fecha_series_valid >= start_dt_date]
        elif end_dt_date:
             df_f = df_f[fecha_series_valid <= end_dt_date]
    
    if industries and "– Todos –" not in industries:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
        
    if managements and "– Todos –" not in managements:
        df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]

    if meeting_status != "– Todos –":
        df_f = df_f[df_f[COL_MEETING] == meeting_status]
        
    return df_f

def display_pipeline_kpis(df_filtered):
    st.markdown("### 🧮 Resumen del Embudo (Periodo Filtrado)")

    total_leads = len(df_filtered)
    total_contacted = len(df_filtered[df_filtered[COL_CONTACTED] == "Si"])
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Leads (Filtrados)", f"{total_leads:,}")
    c2.metric("Contactados", f"{total_contacted:,}")
    c3.metric("Respondieron", f"{total_responded:,}")
    c4.metric("Reuniones Agendadas", f"{total_meetings:,}")

    st.markdown("---")
    st.markdown("#### Tasas de Conversión")
    
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

df_pipeline_base = load_pipeline_data()

if df_pipeline_base.empty:
    st.error("El DataFrame del Pipeline está vacío. No se puede continuar.")
    st.stop()

start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base)

df_pipeline_filtered = apply_pipeline_filters(
    df_pipeline_base, start_date, end_date, industries, managements, meeting_status
)

if not df_pipeline_filtered.empty:
    display_pipeline_kpis(df_pipeline_filtered)
    
    display_pipeline_funnel(df_pipeline_filtered)
    
    display_breakdown_charts(df_pipeline_filtered)

    display_time_evolution(df_pipeline_filtered)

    with st.expander("Ver tabla de datos detallados del pipeline (filtrada)"):
        cols_to_show = [
            "Full Name", "Company", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT,
            COL_PRIMARY_DATE, COL_CONTACTED, COL_RESPONDED, COL_MEETING, COL_MEETING_DATE,
            "Response Channel", "LinkedIn URL"
        ]
        cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
        
        df_display = df_pipeline_filtered[cols_exist].copy()
        
        if 'Fecha_Principal' in df_display.columns: # Usar la columna parseada
            df_display['Fecha_Principal'] = df_display['Fecha_Principal'].dt.strftime('%Y-%m-%d')
            # Renombrar para mostrar con el nombre original si es necesario
            if COL_PRIMARY_DATE not in cols_exist:
                 df_display.rename(columns={'Fecha_Principal': COL_PRIMARY_DATE}, inplace=True)
            
        if COL_MEETING_DATE in df_display.columns:
             df_display[COL_MEETING_DATE] = df_display[COL_MEETING_DATE].dt.strftime('%Y-%m-%d')

        # Asegurarse que la columna renombrada (si aplica) esté en la lista final
        cols_exist_final = []
        for col in cols_to_show:
             if col in df_display.columns:
                 cols_exist_final.append(col)
             elif col == COL_PRIMARY_DATE and 'Fecha_Principal' in df_display.columns: # Caso especial si renombró
                 cols_exist_final.append(COL_PRIMARY_DATE)

        st.dataframe(df_display[cols_exist_final], hide_index=True)
else:
    st.info("No se encontraron datos que coincidan con los filtros seleccionados.")

