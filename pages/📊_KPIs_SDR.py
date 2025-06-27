# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
import locale

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="KPIs del SDR", layout="wide")
st.title("🚀 Dashboard de KPIs para SDR - Evelyn")
st.markdown("Análisis de rendimiento basado en actividades de prospección y generación de sesiones.")

# Configurar el locale en español para los nombres de los meses
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    # Esta advertencia es normal en algunos sistemas. No afecta la funcionalidad.
    st.warning("El 'locale' en español no está disponible en el sistema. Los meses podrían aparecer en inglés.")
    pass

# --- FUNCIÓN DE CARGA Y LIMPIEZA DE DATOS ---
@st.cache_data(ttl=600)
def load_sdr_data():
    """
    Carga los datos desde la hoja de KPIs del SDR, los limpia y procesa la columna 'Semana'.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets["new_page_sheet_url"]
        client = gspread.service_account_from_dict(creds_dict)
        sheet = client.open_by_url(sheet_url).sheet1
        data = sheet.get_all_records()
        df = pd.DataFrame(data)
    except KeyError:
        st.error("Error de Configuración: Asegúrate de añadir 'new_page_sheet_url' a tus secretos (secrets.toml).")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"No se pudo cargar la hoja de Google Sheets. Error: {e}")
        return pd.DataFrame()

    if df.empty:
        st.warning("La hoja de cálculo parece estar vacía.")
        return pd.DataFrame()

    if 'Semana' not in df.columns:
        st.error("Error crítico: La columna 'Semana' no se encontró en la hoja de cálculo.")
        return pd.DataFrame()

    df['FechaSemana'] = pd.to_datetime(df['Semana'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['FechaSemana'], inplace=True)
    df['SemanaLabel'] = df['FechaSemana'].dt.strftime("Semana del %d/%b/%Y")
    df = df.sort_values(by='FechaSemana', ascending=False)

    numeric_cols = [
        'Empresas agregadas', 'Meta empresas', 'Contactos agregados', 'Conexiones enviadas', 
        'Conexiones aceptadas', 'Mensajes de seguimiento enviados', 'Números telefónicos encontrados', 
        'Whatsapps Enviados', 'Whatsapps Respondidos', 'Llamadas realizadas', 'Sesiones logradas', 'Meta sesiones'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        else:
            st.warning(f"Advertencia: La columna '{col}' no se encontró. Se asumirá como 0.")
            df[col] = 0

    df['Acceptance Rate'] = (df['Conexiones aceptadas'] / df['Conexiones enviadas'] * 100).where(df['Conexiones enviadas'] > 0, 0)
    df['Response Rate'] = (df['Whatsapps Respondidos'] / df['Whatsapps Enviados'] * 100).where(df['Whatsapps Enviados'] > 0, 0)
    df['% Cumplimiento empresas'] = (df['Empresas agregadas'] / df['Meta empresas'] * 100).where(df['Meta empresas'] > 0, 0)
    df['% Cumplimiento sesiones'] = (df['Sesiones logradas'] / df['Meta sesiones'] * 100).where(df['Meta sesiones'] > 0, 0)

    return df

# --- FILTROS EN LA BARRA LATERAL ---
def display_filters(df):
    st.sidebar.header("🔍 Filtros")
    if df.empty or 'SemanaLabel' not in df.columns:
        st.sidebar.warning("No hay datos de 'Semana' para filtrar.")
        return []
    
    semanas_labels = df['SemanaLabel'].unique().tolist()
    
    selected_semanas = st.sidebar.multiselect(
        "Selecciona la(s) Semana(s)",
        options=semanas_labels,
        default=semanas_labels[0] if semanas_labels else []
    )
    return selected_semanas

# --- COMPONENTES DE VISUALIZACIÓN ---

def display_summary_kpis(df):
    st.subheader("Resumen General del Período Seleccionado")
    
    if df.empty:
        st.info("No hay datos para el período seleccionado.")
        return

    total_empresas = int(df['Empresas agregadas'].sum())
    total_conexiones = int(df['Conexiones enviadas'].sum())
    total_llamadas = int(df['Llamadas realizadas'].sum())
    total_sesiones = int(df['Sesiones logradas'].sum())
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Empresas Agregadas", f"{total_empresas:,}")
    col2.metric("🔗 Conexiones Enviadas", f"{total_conexiones:,}")
    col3.metric("📞 Llamadas Realizadas", f"{total_llamadas:,}")
    col4.metric("🗓️ Sesiones Logradas", f"{total_sesiones:,}")

def display_goal_tracking(df):
    st.subheader("🎯 Seguimiento de Metas")
    
    if df.empty:
        st.info("No hay datos de metas para el período seleccionado.")
        return
        
    total_empresas = int(df['Empresas agregadas'].sum())
    meta_empresas = int(df['Meta empresas'].sum())
    total_sesiones = int(df['Sesiones logradas'].sum())
    meta_sesiones = int(df['Meta sesiones'].sum())
    
    cumplimiento_empresas = (total_empresas / meta_empresas * 100) if meta_empresas > 0 else 0
    cumplimiento_sesiones = (total_sesiones / meta_sesiones * 100) if meta_sesiones > 0 else 0

    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("<h5>Meta de Empresas</h5>", unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = total_empresas,
            title = {'text': f"Logro vs Meta ({meta_empresas})"},
            gauge = {'axis': {'range': [None, meta_empresas * 1.2]}, 'bar': {'color': "#36719F"},
                     'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': meta_empresas}}))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Cumplimiento", f"{cumplimiento_empresas:.1f}%")

    with col2:
        st.markdown("<h5>Meta de Sesiones</h5>", unsafe_allow_html=True)
        fig = go.Figure(go.Indicator(
            mode = "gauge+number", value = total_sesiones,
            title = {'text': f"Logro vs Meta ({meta_sesiones})"},
            gauge = {'axis': {'range': [None, meta_sesiones * 1.2]}, 'bar': {'color': "#36719F"},
                     'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': meta_sesiones}}))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
        st.plotly_chart(fig, use_container_width=True)
        st.metric("Cumplimiento", f"{cumplimiento_sesiones:.1f}%")

def display_activity_analysis(df):
    st.subheader("📈 Análisis de Actividades y Conversión")
    
    if df.empty:
        st.info("No hay datos de actividades para el período seleccionado.")
        return

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("<h6>Embudo de Conexiones</h6>", unsafe_allow_html=True)
        total_enviadas = df['Conexiones enviadas'].sum()
        total_aceptadas = df['Conexiones aceptadas'].sum()
        
        fig = go.Figure(go.Funnel(y=["Enviadas", "Aceptadas"], x=[total_enviadas, total_aceptadas], textinfo="value+percent initial"))
        fig.update_layout(height=300, margin=dict(l=50, r=50, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("<h6>Embudo de WhatsApp</h6>", unsafe_allow_html=True)
        total_wa_enviados = df['Whatsapps Enviados'].sum()
        total_wa_respondidos = df['Whatsapps Respondidos'].sum()
        
        fig = go.Figure(go.Funnel(y=["Enviados", "Respondidos"], x=[total_wa_enviados, total_wa_respondidos], textinfo="value+percent initial", marker={"color": ["#6A8D73", "#8AAF7A"]}))
        fig.update_layout(height=300, margin=dict(l=50, r=50, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        
    st.markdown("---")
    
    st.markdown("<h5>Evolución Semanal de Actividades</h5>", unsafe_allow_html=True)
    
    # --- INICIO DE LA CORRECCIÓN ---
    # Se especifican las columnas numéricas que se deben sumar para evitar el error.
    numeric_cols_to_sum = [
        'Empresas agregadas', 'Contactos agregados', 'Conexiones enviadas', 
        'Llamadas realizadas', 'Conexiones aceptadas', 'Whatsapps Respondidos', 
        'Sesiones logradas'
    ]
    # Se asegura que solo las columnas que existen en el df se usen para la suma
    existing_numeric_cols = [col for col in numeric_cols_to_sum if col in df.columns]
    
    df_chart = df.groupby('SemanaLabel', as_index=False)[existing_numeric_cols].sum()
    # --- FIN DE LA CORRECCIÓN ---

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Empresas agregadas'], name='Empresas Agregadas'))
    fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Contactos agregados'], name='Contactos Agregados'))
    fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Conexiones enviadas'], name='Conexiones Enviadas'))
    fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Llamadas realizadas'], name='Llamadas Realizadas'))
    fig.update_layout(barmode='group', title_text='Volumen de Actividades por Semana', xaxis_title="Semana")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<h5>Evolución Semanal de Resultados Clave</h5>", unsafe_allow_html=True)
    fig_line = go.Figure()
    fig_line.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Conexiones aceptadas'], mode='lines+markers', name='Conexiones Aceptadas'))
    fig_line.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Whatsapps Respondidos'], mode='lines+markers', name='Whatsapps Respondidos'))
    fig_line.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Sesiones logradas'], mode='lines+markers', name='Sesiones Logradas', line=dict(color='green', width=3)))
    fig_line.update_layout(title_text='Resultados Clave por Semana', xaxis_title="Semana")
    st.plotly_chart(fig_line, use_container_width=True)

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_raw = load_sdr_data()

if not df_sdr_raw.empty:
    selected_weeks_labels = display_filters(df_sdr_raw)
    
    if not selected_weeks_labels:
        st.warning("Por favor, selecciona al menos una semana en la barra lateral para ver los datos.")
        st.stop()
    
    df_filtered = df_sdr_raw[df_sdr_raw['SemanaLabel'].isin(selected_weeks_labels)].copy()
    
    display_summary_kpis(df_filtered)
    st.markdown("---")
    display_goal_tracking(df_filtered)
    st.markdown("---")
    display_activity_analysis(df_filtered)
    st.markdown("---")
    
    with st.expander("Ver datos detallados del período seleccionado"):
        # Mostramos las columnas originales, no las calculadas, para mantener la vista limpia
        display_cols = [col for col in df_filtered.columns if col not in ['FechaSemana', 'SemanaLabel']]
        st.dataframe(df_filtered[display_cols])

else:
    st.error("No se pudieron cargar los datos para el dashboard.")
