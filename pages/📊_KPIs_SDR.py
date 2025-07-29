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
st.markdown("Análisis de efectividad y conversión basado en la hoja de trabajo 'Evelyn'.")

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

        if len(values) < 2:
            st.warning("La hoja 'Evelyn' está vacía o solo tiene encabezados.")
            return pd.DataFrame()

        headers = make_unique(values[0])
        df = pd.DataFrame(values[1:], columns=headers)

    except gspread.exceptions.WorksheetNotFound:
        st.error("Error Crítico: No se encontró la hoja 'Evelyn' en el Google Sheet principal.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"No se pudo cargar la hoja 'Evelyn'. Error: {e}")
        return pd.DataFrame()

    # --- LÓGICA CORRECTA ---
    # 1. Se procesan todas las fechas relevantes
    date_columns_to_process = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha",
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

    # 2. La fecha principal para FILTRAR es 'Fecha Primer contacto'
    if "Fecha" not in df.columns or df["Fecha"].isnull().all():
        st.error("Columna 'Fecha Primer contacto (...)' no encontrada o vacía. Es esencial para el análisis.")
        return pd.DataFrame()
    
    df.dropna(subset=['Fecha'], inplace=True)

    # 3. Se crean las columnas de métricas (banderas 0 o 1) para CADA prospecto
    df['Acercamientos'] = df['Fecha'].notna().astype(int)
    df['Mensajes_Enviados'] = df['Fecha_Primer_Acercamiento'].notna().astype(int)
    df['Respuestas_Iniciales'] = df['Fecha_Primera_Respuesta'].notna().astype(int)
    df['Sesiones_Agendadas'] = df['Fecha_Agendamiento'].notna().astype(int)
    df['Necesita_Recontacto'] = df['Fecha_Recontacto'].notna().astype(int)
    
    # 4. Se crea la columna para el widget de filtro de mes, basada en la fecha principal
    df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')

    for col in ["Fuente de la Lista", "Campaña", "Proceso", "Industria", "Pais", "Puesto"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"

    return df.sort_values(by='Fecha', ascending=False)

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

def clear_all_filters():
    st.session_state.date_filter_mode = "Rango de Fechas"
    st.session_state.month_select = []
    
    prospecting_cols = ["Fuente de la Lista"]
    for col in prospecting_cols:
        key = f"filter_{col.lower().replace(' ', '_')}"
        if key in st.session_state:
            st.session_state[key] = ["– Todos –"]

    if "start_date" in st.session_state: del st.session_state.start_date
    if "end_date" in st.session_state: del st.session_state.end_date

# --- COMPONENTES VISUALES ---

def sidebar_filters(df):
    st.sidebar.header("🔍 Filtros de Análisis")
    if df.empty:
        st.sidebar.warning("No hay datos para filtrar.")
        return None, None, None, None, {}

    st.sidebar.subheader("📅 Filtrar por Fecha")
    filter_mode = st.sidebar.radio(
        "Elige cómo filtrar por fecha:",
        ("Rango de Fechas", "Mes(es) Específico(s)"),
        key="date_filter_mode",
        horizontal=True
    )
    start_date, end_date, selected_months = None, None, None

    if filter_mode == "Rango de Fechas":
        min_date, max_date = df['Fecha'].min().date(), df['Fecha'].max().date()
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Fecha Inicial", value=min_date, min_value=min_date, max_value=max_date, key="start_date")
        with col2:
            end_date = st.date_input("Fecha Final", value=max_date, min_value=start_date, max_value=max_date, key="end_date")
    else:
        if 'AñoMes' in df.columns:
            meses_disponibles = sorted(df['AñoMes'].unique(), reverse=True)
            selected_months = st.sidebar.multiselect("Selecciona el/los mes(es):", meses_disponibles, key="month_select")

    other_filters = {}
    st.sidebar.subheader("🔎 Filtrar por Fuente")
    
    prospecting_cols = ["Fuente de la Lista"]
    for dim_col in prospecting_cols:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtro_key = f"filter_{dim_col.lower().replace(' ', '_')}"
            other_filters[dim_col] = st.sidebar.multiselect(dim_col, opciones, default=["– Todos –"], key=filtro_key)

    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_all_filters, use_container_width=True)

    return filter_mode, start_date, end_date, selected_months, other_filters

def apply_filters(df, filter_mode, start_date, end_date, selected_months, other_filters):
    df_f = df.copy()
    
    if filter_mode == "Rango de Fechas":
        if start_date and end_date:
            df_f = df_f[(df_f['Fecha'].dt.date >= start_date) & (df_f['Fecha'].dt.date <= end_date)]
    elif filter_mode == "Mes(es) Específico(s)":
        if selected_months:
            df_f = df_f[df_f['AñoMes'].isin(selected_months)]

    for col, values in other_filters.items():
        if values and "– Todos –" not in values:
            df_f = df_f[df_f[col].isin(values)]
    return df_f

def display_kpi_summary(df_filtered):
    st.markdown("### 🧮 Resumen de KPIs SDR Totales (Periodo Filtrado)")

    total_acercamientos = int(df_filtered['Acercamientos'].sum())
    total_mensajes = int(df_filtered['Mensajes_Enviados'].sum())
    total_respuestas = int(df_filtered['Respuestas_Iniciales'].sum())
    total_sesiones = int(df_filtered['Sesiones_Agendadas'].sum())

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("🚀 Total Acercamientos", f"{total_acercamientos:,}")
    kpi_cols[1].metric("📤 Total Mensajes Enviados", f"{total_mensajes:,}")
    kpi_cols[2].metric("💬 Total Respuestas Iniciales", f"{total_respuestas:,}")
    kpi_cols[3].metric("🗓️ Total Sesiones Agendadas", f"{total_sesiones:,}")

    st.markdown("---")
    st.markdown("#### 📊 Tasas de Conversión")

    tasa_mens_vs_acerc = calculate_rate(total_mensajes, total_acercamientos)
    tasa_resp_vs_msj = calculate_rate(total_respuestas, total_mensajes)
    tasa_sesion_vs_resp = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesion_global = calculate_rate(total_sesiones, total_acercamientos)

    rate_cols = st.columns(4)
    rate_cols[0].metric("📨 Tasa Mensajes / Acercamiento", f"{tasa_mens_vs_acerc:.1f}%", help="Porcentaje de acercamientos que resultaron en un mensaje enviado.")
    rate_cols[1].metric("🗣️ Tasa Respuesta / Mensaje", f"{tasa_resp_vs_msj:.1f}%", help="Porcentaje de mensajes enviados que recibieron una respuesta.")
    rate_cols[2].metric("🤝 Tasa Sesión / Respuesta", f"{tasa_sesion_vs_resp:.1f}%", help="Porcentaje de respuestas que condujeron a una sesión agendada.")
    rate_cols[3].metric("🏆 Tasa Sesión / Acercamiento (Global)", f"{tasa_sesion_global:.1f}%", help="Eficiencia total del proceso: (Sesiones Agendadas / Acercamientos)")

def display_follow_up_metrics(df_filtered):
    st.markdown("### 📈 Análisis de Seguimiento y Recontacto")
    
    total_acercamientos = int(df_filtered['Acercamientos'].sum())
    total_recontactos = int(df_filtered['Necesita_Recontacto'].sum())
    tasa_recontacto = calculate_rate(total_recontactos, total_acercamientos)

    col1, col2 = st.columns(2)
    col1.metric("🔄 Total Prospectos en Seguimiento", f"{total_recontactos:,}", help="Número de prospectos que tienen una fecha de recontacto futura.")
    col2.metric("📊 Tasa de Seguimiento", f"{tasa_recontacto:.1f}%", help="Porcentaje de todos los acercamientos que necesitaron un seguimiento planificado.")

def display_new_grouped_breakdown(df_filtered, group_by_col):
    st.markdown(f"#### Análisis por `{group_by_col}`")
    
    if group_by_col not in df_filtered.columns or df_filtered[group_by_col].nunique() < 2:
        st.info(f"No hay suficientes datos o diversidad para analizar por '{group_by_col}'.")
        return

    summary_df = df_filtered.groupby(group_by_col).agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    summary_df = summary_df[summary_df['Acercamientos'] > 0]
    summary_df['Tasa_Conversion'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Acercamientos), axis=1)
    
    col1, col2 = st.columns([0.5, 0.5])

    with col1:
        st.markdown("##### Top 10 por Volumen de Sesiones")
        top_10_volumen = summary_df.nlargest(10, 'Sesiones_Agendadas')
        st.dataframe(
            top_10_volumen.style.format({
                'Tasa_Conversion': '{:.1f}%'
            }),
            hide_index=True,
            use_container_width=True
        )

    with col2:
        st.markdown("##### Top 10 por Eficiencia (Tasa de Conversión)")
        top_10_eficiencia = summary_df[summary_df['Sesiones_Agendadas'] > 0].nlargest(10, 'Tasa_Conversion')

        fig = px.bar(
            top_10_eficiencia.sort_values('Tasa_Conversion', ascending=True),
            x='Tasa_Conversion',
            y=group_by_col,
            orientation='h',
            text='Tasa_Conversion',
            title=f"Tasa de Sesión Agendada / Acercamiento"
        )
        fig.update_traces(
            texttemplate='%{x:.1f}%', 
            textposition='outside',
            marker_color='#30B88A'
        )
        fig.update_layout(
            yaxis_title=None,
            xaxis_title="Tasa de Conversión (%)",
            showlegend=False,
            margin=dict(t=30, b=10, l=10, r=10),
            height=400
        )
        st.plotly_chart(fig, use_container_width=True)

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_data = load_and_process_sdr_data()

if not df_sdr_data.empty:
    filter_mode, start_date, end_date, selected_months, other_filters = sidebar_filters(df_sdr_data)
    df_sdr_filtered = apply_filters(df_sdr_data, filter_mode, start_date, end_date, selected_months, other_filters)

    if df_sdr_filtered.empty:
        st.warning("No se encontraron datos que coincidan con los filtros seleccionados.")
    else:
        display_kpi_summary(df_sdr_filtered)
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        
        display_follow_up_metrics(df_sdr_filtered)
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        
        st.markdown("## 🔬 Desglose de Rendimiento por Dimensiones")
        
        tabs_list = ["Campaña", "Proceso", "Industria", "Pais", "Puesto"]
        tabs = st.tabs([f"📊 Por {t}" for t in tabs_list])
        
        for i, dimension in enumerate(tabs_list):
            with tabs[i]:
                display_new_grouped_breakdown(df_sdr_filtered, dimension)

        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        with st.expander("Ver tabla de datos detallados del período filtrado"):
            st.dataframe(df_sdr_filtered, hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")

st.markdown("---")
