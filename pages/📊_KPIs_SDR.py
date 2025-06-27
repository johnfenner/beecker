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
st.markdown("Métricas de rendimiento para el proceso de Sales Development Representative.")

try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    pass

# --- FUNCIÓN DE LIMPIEZA Y CARGA DE DATOS (Sin cambios) ---
def clean_numeric(value):
    if value is None: return 0
    s = str(value).strip()
    if not s or s.startswith('#'): return 0
    s = s.replace('%', '').replace(',', '.').strip()
    try: return float(s)
    except (ValueError, TypeError): return 0

@st.cache_data(ttl=300)
def load_sdr_data():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets["new_page_sheet_url"]
        client = gspread.service_account_from_dict(creds_dict)
        sheet = client.open_by_url(sheet_url).sheet1
        values = sheet.get_all_values()
        if not values or len(values) < 2: return pd.DataFrame(), []
        headers = values[0]
        original_column_names = headers[:]
        df = pd.DataFrame(values[1:], columns=headers)
    except Exception as e:
        st.error(f"No se pudo cargar la hoja de Google Sheets. Error: {e}")
        return pd.DataFrame(), []

    cols_a_ignorar_del_sheet = ['% Cumplimiento empresas', 'Acceptance Rate', '% Cumplimiento sesiones', 'Response Rate']
    for col in cols_a_ignorar_del_sheet:
        if col in df.columns: df = df.drop(columns=[col])

    if 'Semana' not in df.columns or df['Semana'].eq('').all(): return pd.DataFrame(), []
    df['FechaSemana'] = pd.to_datetime(df['Semana'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['FechaSemana'], inplace=True)
    if df.empty: return pd.DataFrame(), []
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
    return df, original_column_names

# --- FILTROS EN LA BARRA LATERAL (Sin cambios) ---
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

# --- NUEVA ESTRUCTURA DE COMPONENTES VISUALES ---

def display_prospecting_activities(df):
    st.header("1. Actividades de Prospección (Volumen)")
    st.caption("Resume el volumen total de trabajo inicial realizado en el período seleccionado.")
    if df.empty:
        st.info("No hay datos de actividades para mostrar.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Empresas Agregadas", f"{int(df['Empresas agregadas'].sum()):,}", help="Total de nuevas empresas añadidas a la lista de prospección.")
    col2.metric("🔗 Conexiones Enviadas", f"{int(df['Conexiones enviadas'].sum()):,}", help="Total de invitaciones a conectar enviadas (ej. LinkedIn).")
    col3.metric("📞 Llamadas Realizadas", f"{int(df['Llamadas realizadas'].sum()):,}", help="Total de llamadas en frío o de seguimiento ejecutadas.")
    col4.metric("💬 Whatsapps Enviados", f"{int(df['Whatsapps Enviados'].sum()):,}", help="Total de mensajes de WhatsApp enviados.")

def display_conversion_rates(df):
    st.header("2. Efectividad y Tasas de Respuesta")
    st.caption("Mide qué tan bien funcionaron las actividades de prospección iniciales.")
    if df.empty:
        st.info("No hay datos de conversión para mostrar.")
        return

    # Cálculos
    total_enviadas = df['Conexiones enviadas'].sum()
    total_aceptadas = df['Conexiones aceptadas'].sum()
    total_wa_enviados = df['Whatsapps Enviados'].sum()
    total_wa_respondidos = df['Whatsapps Respondidos'].sum()

    tasa_aceptacion = (total_aceptadas / total_enviadas * 100) if total_enviadas > 0 else 0
    tasa_respuesta_wa = (total_wa_respondidos / total_wa_enviados * 100) if total_wa_enviados > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("✅ Conexiones Aceptadas", f"{int(total_aceptadas):,}", help="Número de personas que aceptaron la invitación a conectar.")
    col2.metric("📈 Tasa de Aceptación", f"{tasa_aceptacion:.1f}%", help="Porcentaje de conexiones que fueron aceptadas. (Aceptadas / Enviadas)")
    col3.metric("🗣️ Whatsapps Respondidos", f"{int(total_wa_respondidos):,}", help="Número de respuestas obtenidas por WhatsApp.")
    col4.metric("📈 Tasa de Respuesta WA", f"{tasa_respuesta_wa:.1f}%", help="Porcentaje de Whatsapps que recibieron respuesta. (Respondidos / Enviados)")
    
def display_final_results(df):
    st.header("3. Resultados Finales y Eficiencia")
    st.caption("Muestra el objetivo principal (sesiones logradas) y cuánto esfuerzo costó alcanzarlas.")
    if df.empty:
        st.info("No hay datos de resultados para mostrar.")
        return
        
    # Cálculos
    total_sesiones = int(df['Sesiones logradas'].sum())
    meta_sesiones = int(df['Meta sesiones'].sum())
    total_conexiones = int(df['Conexiones enviadas'].sum())
    
    cumplimiento_sesiones = (total_sesiones / meta_sesiones * 100) if meta_sesiones > 0 else 0
    esfuerzo_por_sesion = total_conexiones / total_sesiones if total_sesiones > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("🗓️ Sesiones Logradas", f"{int(total_sesiones):,}", help="El número final de reuniones o sesiones conseguidas.")
    col2.metric(f"🎯 Meta de Sesiones ({meta_sesiones})", f"{cumplimiento_sesiones:.1f}%", help="Porcentaje de la meta de sesiones que se ha cumplido.")
    col3.metric("⚙️ Esfuerzo por Sesión", f"{esfuerzo_por_sesion:.1f} Conexiones", help="Indica cuántas conexiones se necesitaron en promedio para lograr una sesión. (Menor es mejor)")

def display_weekly_evolution(df):
    st.header("📉 Análisis Visual de la Evolución Semanal")
    if df.empty:
        st.info("No hay datos para mostrar la evolución semanal.")
        return

    # Preparar datos para gráficos
    numeric_cols_to_sum = df.select_dtypes(include=np.number).columns.tolist()
    df_chart = df.groupby('SemanaLabel', as_index=False, sort=False)[numeric_cols_to_sum].sum()
    df_chart_sorted = df_chart.sort_values(by='SemanaLabel', key=lambda col: pd.to_datetime(col.str.replace("Semana del ", ""), format="%d/%b/%Y"))

    # Crear pestañas para organizar los gráficos
    tab1, tab2 = st.tabs(["Evolución de Actividades", "Evolución de Resultados"])

    with tab1:
        st.markdown("<h5>Volumen de Actividades por Semana</h5>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Conexiones enviadas', pd.Series(0)), name='Conexiones'))
        fig.add_trace(go.Bar(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Llamadas realizadas', pd.Series(0)), name='Llamadas'))
        fig.add_trace(go.Bar(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Whatsapps Enviados', pd.Series(0)), name='Whatsapps'))
        fig.update_layout(barmode='group', xaxis_title="Semana", yaxis_title="Cantidad", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, key="bar_actividades_v3")

    with tab2:
        st.markdown("<h5>Resultados Clave por Semana</h5>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Conexiones aceptadas', pd.Series(0)), mode='lines+markers', name='Conexiones Aceptadas'))
        fig.add_trace(go.Scatter(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Whatsapps Respondidos', pd.Series(0)), mode='lines+markers', name='Whatsapps Respondidos'))
        fig.add_trace(go.Scatter(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Sesiones logradas', pd.Series(0)), mode='lines+markers', name='Sesiones Logradas', line=dict(color='#28a745', width=4)))
        fig.update_layout(xaxis_title="Semana", yaxis_title="Cantidad", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, key="line_resultados_v3")

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_raw, original_cols = load_sdr_data()

if not df_sdr_raw.empty:
    selected_weeks_labels = display_filters(df_sdr_raw)
    
    df_filtered = df_sdr_raw.copy()
    if selected_weeks_labels and "– Todas las Semanas –" not in selected_weeks_labels:
        df_filtered = df_sdr_raw[df_sdr_raw['SemanaLabel'].isin(selected_weeks_labels)]
    
    if df_filtered.empty and selected_weeks_labels != ["– Todas las Semanas –"]:
         st.warning("No hay datos para las semanas específicas seleccionadas.")
    else:
        # Llamar a los nuevos componentes en el orden lógico
        display_prospecting_activities(df_filtered)
        st.markdown("---")
        display_conversion_rates(df_filtered)
        st.markdown("---")
        display_final_results(df_filtered)
        st.markdown("---")
        display_weekly_evolution(df_filtered)
        st.markdown("---")
        
        with st.expander("Ver tabla de datos originales (Período Seleccionado)"):
            st.caption("Esta tabla muestra los datos tal como se ingresaron en la hoja de cálculo.")
            st.dataframe(df_filtered[original_cols], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
