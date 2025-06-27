# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
import locale
import re
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="KPIs del SDR", layout="wide")
st.title("🚀 Dashboard de KPIs para SDR - Evelyn")
st.markdown("Análisis de rendimiento basado en actividades de prospección y generación de sesiones.")

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    pass

# --- FUNCIÓN DE LIMPIEZA NUMÉRICA ---
def clean_numeric(value):
    if value is None: return 0
    s = str(value).strip()
    if not s or s.startswith('#'): return 0
    s = s.replace('%', '').replace(',', '.').strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0

# --- FUNCIÓN DE CARGA DE DATOS ---
@st.cache_data(ttl=300)
def load_sdr_data():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets["new_page_sheet_url"]
        client = gspread.service_account_from_dict(creds_dict)
        sheet = client.open_by_url(sheet_url).sheet1
        values = sheet.get_all_values()
        if not values or len(values) < 2: return pd.DataFrame()
        headers = values[0]
        df = pd.DataFrame(values[1:], columns=headers)
    except Exception as e:
        st.error(f"No se pudo cargar la hoja de Google Sheets. Error: {e}")
        return pd.DataFrame()

    cols_a_ignorar_del_sheet = ['% Cumplimiento empresas', 'Acceptance Rate', '% Cumplimiento sesiones', 'Response Rate']
    for col in cols_a_ignorar_del_sheet:
        if col in df.columns: df = df.drop(columns=[col])

    if 'Semana' not in df.columns or df['Semana'].eq('').all(): return pd.DataFrame()
    df['FechaSemana'] = pd.to_datetime(df['Semana'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['FechaSemana'], inplace=True)
    if df.empty: return pd.DataFrame()
    df['SemanaLabel'] = df['FechaSemana'].dt.strftime("Semana del %d/%b/%Y")
    df = df.sort_values(by='FechaSemana', ascending=False)

    numeric_cols = [
        'Empresas agregadas', 'Meta empresas', 'Contactos agregados', 'Conexiones enviadas', 
        'Conexiones aceptadas', 'Mensajes de seguimiento enviados', 'Números telefónicos encontrados', 
        'Whatsapps Enviados', 'Whatsapps Respondidos', 'Llamadas realizadas', 'Sesiones logradas', 'Meta sesiones'
    ]
    for col in numeric_cols:
        if col in df.columns: df[col] = df[col].apply(clean_numeric)
        else: df[col] = 0
    return df

# --- FILTROS EN LA BARRA LATERAL ---
def display_filters(df):
    st.sidebar.header("🔍 Filtros")
    if df.empty or 'SemanaLabel' not in df.columns:
        st.sidebar.warning("No hay datos de 'Semana' para filtrar.")
        return ["– Todas las Semanas –"]
    
    todas_las_semanas_opcion = "– Todas las Semanas –"
    semanas_labels = df['SemanaLabel'].unique().tolist()
    opciones_filtro = [todas_las_semanas_opcion] + semanas_labels
    
    selected_semanas = st.sidebar.multiselect(
        "Selecciona Semanas", options=opciones_filtro, default=[todas_las_semanas_opcion],
        help="Por defecto se muestran todas las semanas. Para ver semanas específicas, quita la opción 'Todas' y elige las que quieras."
    )
    
    if todas_las_semanas_opcion in selected_semanas and len(selected_semanas) > 1:
        return [s for s in selected_semanas if s != todas_las_semanas_opcion]
    elif not selected_semanas:
        return [todas_las_semanas_opcion]
    else:
        return selected_semanas

# --- COMPONENTES DE VISUALIZACIÓN MEJORADOS ---

def display_summary_kpis(df):
    st.header("📊 Resumen del Período Seleccionado")
    if df.empty:
        st.info("No hay datos para el período seleccionado.")
        return

    # Cálculos de Volumen
    total_conexiones_enviadas = int(df['Conexiones enviadas'].sum())
    total_conexiones_aceptadas = int(df['Conexiones aceptadas'].sum())
    total_sesiones = int(df['Sesiones logradas'].sum())
    total_llamadas = int(df['Llamadas realizadas'].sum())
    
    # Cálculos de Tasas y Eficiencia
    tasa_aceptacion_global = (total_conexiones_aceptadas / total_conexiones_enviadas * 100) if total_conexiones_enviadas > 0 else 0
    conexiones_por_sesion = total_conexiones_enviadas / total_sesiones if total_sesiones > 0 else 0
    llamadas_por_sesion = total_llamadas / total_sesiones if total_sesiones > 0 else 0
    
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🔗 Conexiones Enviadas", f"{total_conexiones_enviadas:,}", help="Suma total de invitaciones a conectar enviadas.")
        # --- MEJORA AQUÍ: Se muestra el número literal de aceptadas en el "delta" ---
        st.metric(
            label="📈 Tasa de Aceptación", 
            value=f"{tasa_aceptacion_global:.1f}%", 
            delta=f"{total_conexiones_aceptadas:,} Aceptadas",
            delta_color="off", # 'off' para que el texto sea neutral
            help="Porcentaje de conexiones que fueron aceptadas. (Total Aceptadas / Total Enviadas)"
        )
        
    with col2:
        st.metric("🗓️ Sesiones Logradas", f"{total_sesiones:,}", help="Suma total de sesiones que se concretaron.")
        st.metric("⚙️ Conexiones / Sesión", f"{conexiones_por_sesion:.1f}", help="Eficiencia: ¿Cuántas conexiones se necesitan para lograr 1 sesión? (Menor es mejor)")

    with col3:
        st.metric("📞 Llamadas Realizadas", f"{total_llamadas:,}", help="Suma de llamadas hechas en el período.")
        st.metric("⚙️ Llamadas / Sesión", f"{llamadas_por_sesion:.1f}", help="Eficiencia: ¿Cuántas llamadas se necesitan para lograr 1 sesión? (Menor es mejor)")

    with col4:
        st.metric("🏢 Empresas Agregadas", f"{int(df['Empresas agregadas'].sum()):,}", help="Suma total de empresas nuevas agregadas.")
        st.metric("💬 Whatsapps Respondidos", f"{int(df['Whatsapps Respondidos'].sum()):,}", help="Total de respuestas recibidas por WhatsApp.")

def display_goal_tracking(df):
    st.header("🎯 Seguimiento de Metas")
    if df.empty: return
        
    total_empresas = int(df['Empresas agregadas'].sum())
    meta_empresas = int(df['Meta empresas'].sum())
    total_sesiones = int(df['Sesiones logradas'].sum())
    meta_sesiones = int(df['Meta sesiones'].sum())
    
    cumplimiento_empresas = (total_empresas / meta_empresas * 100) if meta_empresas > 0 else 0
    cumplimiento_sesiones = (total_sesiones / meta_sesiones * 100) if meta_sesiones > 0 else 0

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("<h5>Meta de Empresas</h5>", unsafe_allow_html=True)
        st.metric(label=f"Logro vs Meta ({meta_empresas})", value=f"{total_empresas}", delta=f"{total_empresas - meta_empresas}")
        st.progress(min(int(cumplimiento_empresas), 100))
        st.caption(f"Cumplimiento: {cumplimiento_empresas:.1f}%")

    with col2:
        st.markdown("<h5>Meta de Sesiones</h5>", unsafe_allow_html=True)
        st.metric(label=f"Logro vs Meta ({meta_sesiones})", value=f"{total_sesiones}", delta=f"{total_sesiones - meta_sesiones}")
        st.progress(min(int(cumplimiento_sesiones), 100))
        st.caption(f"Cumplimiento: {cumplimiento_sesiones:.1f}%")

def display_conversion_analysis(df):
    st.header("🔬 Análisis de Conversión y Actividades")
    if df.empty: return

    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown("<h6>Embudo de Prospección Completo</h6>", unsafe_allow_html=True)
        st.caption("Muestra el viaje completo del prospecto y dónde se pierden oportunidades.")
        
        etapas = ['Conexiones Enviadas', 'Conexiones Aceptadas', 'Whatsapps Enviados', 'Whatsapps Respondidos', 'Sesiones Logradas']
        valores = [
            df['Conexiones enviadas'].sum(), df['Conexiones aceptadas'].sum(),
            df['Whatsapps Enviados'].sum(), df['Whatsapps Respondidos'].sum(), df['Sesiones logradas'].sum()
        ]
        
        fig = go.Figure(go.Funnel(y=etapas, x=valores, textposition="inside", textinfo="value+percent previous"))
        fig.update_layout(margin=dict(l=50, r=50, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True, key="funnel_completo_sdr")
    
    with col2:
        st.markdown("<h6>Volumen de Actividades</h6>", unsafe_allow_html=True)
        st.caption("Cantidad de las principales actividades realizadas.")
        
        actividades_df = pd.DataFrame({
            'Actividad': ['Conexiones', 'Mensajes', 'Whatsapps', 'Llamadas'],
            'Cantidad': [
                df['Conexiones enviadas'].sum(), df['Mensajes de seguimiento enviados'].sum(),
                df['Whatsapps Enviados'].sum(), df['Llamadas realizadas'].sum()
            ]
        })
        fig_bar = go.Figure(go.Bar(x=actividades_df['Cantidad'], y=actividades_df['Actividad'], orientation='h', text=actividades_df['Cantidad'], textposition='auto'))
        fig_bar.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_bar, use_container_width=True, key="bar_actividades_sdr")

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_raw = load_sdr_data()

if not df_sdr_raw.empty:
    selected_weeks_labels = display_filters(df_sdr_raw)
    
    df_filtered = df_sdr_raw.copy()
    if selected_weeks_labels and "– Todas las Semanas –" not in selected_weeks_labels:
        df_filtered = df_sdr_raw[df_sdr_raw['SemanaLabel'].isin(selected_weeks_labels)]
    
    if df_filtered.empty and selected_weeks_labels != ["– Todas las Semanas –"]:
         st.warning("No hay datos para las semanas específicas seleccionadas.")
    else:
        display_summary_kpis(df_filtered)
        st.markdown("---")
        display_goal_tracking(df_filtered)
        st.markdown("---")
        display_conversion_analysis(df_filtered)
        st.markdown("---")
        
        with st.expander("Ver tabla de datos detallados (Período Seleccionado)"):
            st.caption("Esta tabla muestra los datos de entrada junto a las tasas calculadas por la aplicación.")
            
            final_table_cols = [
                'Semana', 'Empresas agregadas', 'Meta empresas', 
                'Conexiones enviadas', 'Conexiones aceptadas', 'Tasa de Aceptación (%)',
                'Whatsapps Enviados', 'Whatsapps Respondidos', 'Tasa de Respuesta WA (%)',
                'Llamadas realizadas', 'Sesiones logradas', 'Meta sesiones'
            ]
            final_table_cols_exist = [col for col in final_table_cols if col in df_filtered.columns]
            df_to_display = df_filtered[final_table_cols_exist].copy()
            
            for col in df_to_display.columns:
                if '%' in col: df_to_display[col] = df_to_display[col].map('{:.1f}%'.format)
            
            st.dataframe(df_to_display, hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
