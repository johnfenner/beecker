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
        
        if not values or len(values) < 2:
            st.warning("La hoja de cálculo parece estar vacía o no tiene datos con encabezados.")
            return pd.DataFrame(), []
        
        headers = values[0]
        original_column_names = headers[:]
        df = pd.DataFrame(values[1:], columns=headers)

    except Exception as e:
        st.error(f"No se pudo cargar la hoja de Google Sheets. Error: {e}")
        return pd.DataFrame(), []

    cols_a_ignorar_del_sheet = ['% Cumplimiento empresas', 'Acceptance Rate', '% Cumplimiento sesiones', 'Response Rate']
    for col in cols_a_ignorar_del_sheet:
        if col in df.columns:
            df = df.drop(columns=[col])

    if 'Semana' not in df.columns or df['Semana'].eq('').all():
        st.error("Error crítico: La columna 'Semana' no se encontró o está completamente vacía.")
        return pd.DataFrame(), []

    df['FechaSemana'] = pd.to_datetime(df['Semana'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['FechaSemana'], inplace=True)
    if df.empty:
        st.error("No se encontraron fechas válidas en la columna 'Semana'. Verifica el formato (dd/mm/yyyy).")
        return pd.DataFrame(), []
        
    df['SemanaLabel'] = df['FechaSemana'].dt.strftime("Semana del %d/%b/%Y")
    df = df.sort_values(by='FechaSemana', ascending=False)

    numeric_cols = [
        'Empresas agregadas', 'Meta empresas', 'Contactos agregados', 'Conexiones enviadas', 
        'Conexiones aceptadas', 'Mensajes de seguimiento enviados', 'Números telefónicos encontrados', 
        'Whatsapps Enviados', 'Whatsapps Respondidos', 'Llamadas realizadas', 'Sesiones logradas', 'Meta sesiones'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
        else:
            df[col] = 0

    return df, original_column_names

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

    # Cálculos
    total_conexiones_enviadas = int(df['Conexiones enviadas'].sum())
    total_conexiones_aceptadas = int(df['Conexiones aceptadas'].sum())
    total_sesiones = int(df['Sesiones logradas'].sum())
    
    tasa_aceptacion_global = (total_conexiones_aceptadas / total_conexiones_enviadas * 100) if total_conexiones_enviadas > 0 else 0
    conexiones_por_sesion = total_conexiones_enviadas / total_sesiones if total_sesiones > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏢 Empresas Agregadas", f"{int(df['Empresas agregadas'].sum()):,}", help="Suma total de empresas nuevas agregadas.")
    col2.metric("🔗 Conexiones Enviadas", f"{total_conexiones_enviadas:,}", help="Suma total de invitaciones a conectar enviadas.")
    col3.metric("✅ Conexiones Aceptadas", f"{total_conexiones_aceptadas:,}", delta=f"{tasa_aceptacion_global:.1f}% Tasa", help="Total de conexiones aceptadas y su porcentaje sobre las enviadas.")
    col4.metric("🗓️ Sesiones Logradas", f"{total_sesiones:,}", delta=f"{conexiones_por_sesion:.1f} Conex./Sesión", help="Total de sesiones y cuántas conexiones se necesitaron en promedio para lograr cada una (menor es mejor).")

def display_goal_tracking(df):
    st.header("🎯 Seguimiento de Metas")
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
        st.metric(label=f"Logro vs Meta ({meta_empresas})", value=f"{total_empresas}", delta=f"{total_empresas - meta_empresas}")
        st.progress(min(int(cumplimiento_empresas), 100))
        st.caption(f"Cumplimiento: {cumplimiento_empresas:.1f}%")

    with col2:
        st.markdown("<h5>Meta de Sesiones</h5>", unsafe_allow_html=True)
        st.metric(label=f"Logro vs Meta ({meta_sesiones})", value=f"{total_sesiones}", delta=f"{total_sesiones - meta_sesiones}")
        st.progress(min(int(cumplimiento_sesiones), 100))
        st.caption(f"Cumplimiento: {cumplimiento_sesiones:.1f}%")

def display_weekly_evolution(df):
    st.header("📈 Evolución Semanal")
    if df.empty:
        st.info("No hay datos para mostrar la evolución semanal.")
        return

    numeric_cols = df.select_dtypes(include=np.number).columns.tolist()
    df_chart = df.groupby('SemanaLabel', as_index=False, sort=False)[numeric_cols].sum()
    df_chart_sorted = df_chart.sort_values(by='SemanaLabel', key=lambda col: pd.to_datetime(col.str.replace("Semana del ", ""), format="%d/%b/%Y"))

    tab1, tab2 = st.tabs(["Evolución de Actividades", "Evolución de Resultados"])

    with tab1:
        st.markdown("<h5>Volumen de Actividades por Semana</h5>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Conexiones enviadas', pd.Series(0)), name='Conexiones'))
        fig.add_trace(go.Bar(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Llamadas realizadas', pd.Series(0)), name='Llamadas'))
        fig.add_trace(go.Bar(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Whatsapps Enviados', pd.Series(0)), name='Whatsapps'))
        fig.update_layout(barmode='group', xaxis_title="Semana", yaxis_title="Cantidad", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, key="bar_actividades_v5")

    with tab2:
        st.markdown("<h5>Resultados Clave por Semana</h5>", unsafe_allow_html=True)
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Conexiones aceptadas', pd.Series(0)), mode='lines+markers', name='Conexiones Aceptadas'))
        fig.add_trace(go.Scatter(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Whatsapps Respondidos', pd.Series(0)), mode='lines+markers', name='Whatsapps Respondidos'))
        fig.add_trace(go.Scatter(x=df_chart_sorted['SemanaLabel'], y=df_chart_sorted.get('Sesiones logradas', pd.Series(0)), mode='lines+markers', name='Sesiones Logradas', line=dict(color='#28a745', width=4)))
        fig.update_layout(xaxis_title="Semana", yaxis_title="Cantidad", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True, key="line_resultados_v5")

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
        display_summary_kpis(df_filtered)
        st.markdown("---")
        display_goal_tracking(df_filtered)
        st.markdown("---")
        display_weekly_evolution(df_filtered)
        st.markdown("---")
        
        with st.expander("Ver tabla de datos originales del Google Sheet (Período Seleccionado)"):
            st.caption("Esta tabla muestra los datos tal como se ingresaron en la hoja de cálculo, para referencia.")
            
            # --- CORRECCIÓN DEFINITIVA DEL KEYERROR ---
            # Filtramos la lista de columnas originales para quedarnos solo con las que existen en el DataFrame final.
            cols_a_mostrar = [col for col in original_cols if col in df_filtered.columns]
            
            st.dataframe(df_filtered[cols_a_mostrar], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
