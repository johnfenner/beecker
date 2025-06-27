# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
import locale
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de KPIs", layout="wide")
st.title("📊 Dashboard de KPIs")
st.markdown("Análisis de métricas y tasas de conversión siguiendo el proceso de prospección.")

# --- CONFIGURACIÓN REGIONAL PARA FECHAS EN ESPAÑOL ---
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
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0

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

# --- INICIO DEL FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_raw, original_cols = load_sdr_data()

if not df_sdr_raw.empty:
    selected_weeks_labels = display_filters(df_sdr_raw)
    
    df_filtered = df_sdr_raw.copy()
    if selected_weeks_labels and "– Todas las Semanas –" not in selected_weeks_labels:
        df_filtered = df_sdr_raw[df_sdr_raw['SemanaLabel'].isin(selected_weeks_labels)]
    
    if df_filtered.empty and selected_weeks_labels != ["– Todas las Semanas –"]:
         st.warning("No hay datos para las semanas específicas seleccionadas.")
    else:
        # --- CÁLCULOS GLOBALES PARA EL PERÍODO SELECCIONADO ---
        total_conex_enviadas = int(df_filtered['Conexiones enviadas'].sum())
        total_conex_aceptadas = int(df_filtered['Conexiones aceptadas'].sum())
        total_wa_respondidos = int(df_filtered['Whatsapps Respondidos'].sum())
        total_sesiones = int(df_filtered['Sesiones logradas'].sum())
        
        # --- CÁLCULO DE TASAS DE CONVERSIÓN DEL EMBUDO ---
        tasa_aceptacion = (total_conex_aceptadas / total_conex_enviadas * 100) if total_conex_enviadas > 0 else 0
        tasa_respuesta = (total_wa_respondidos / total_conex_aceptadas * 100) if total_conex_aceptadas > 0 else 0
        tasa_agendamiento = (total_sesiones / total_wa_respondidos * 100) if total_wa_respondidos > 0 else 0
        tasa_global = (total_sesiones / total_conex_enviadas * 100) if total_conex_enviadas > 0 else 0

        # --- SECCIÓN 1: RESUMEN DE KPIS (DISEÑO SOLICITADO) ---
        st.subheader("📈 Resumen de KPIs Totales (Período Filtrado)")
        
        # Fila 1: Métricas Absolutas
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Conexiones Enviadas", f"{total_conex_enviadas:,}")
        col2.metric("Total Conexiones Aceptadas", f"{total_conex_aceptadas:,}")
        col3.metric("Total Respuestas (WA)", f"{total_wa_respondidos:,}")
        col4.metric("Total Sesiones Logradas", f"{total_sesiones:,}")
        
        st.write("") # Espacio vertical

        # Fila 2: Tasas de Conversión
        st.subheader("Tasas de Conversión")
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("Tasa Aceptación / Envío", f"{tasa_aceptacion:.1f}%", help="Calculado como: (Conexiones Aceptadas / Conexiones Enviadas)")
        kpi2.metric("Tasa Respuesta / Aceptación", f"{tasa_respuesta:.1f}%", help="Calculado como: (Respuestas WA / Conexiones Aceptadas)")
        kpi3.metric("Tasa Sesión / Respuesta", f"{tasa_agendamiento:.1f}%", help="Calculado como: (Sesiones Logradas / Respuestas WA)")
        kpi4.metric("Tasa Sesión / Envío (Global)", f"{tasa_global:.1f}%", help="Calculado como: (Sesiones Logradas / Conexiones Enviadas)")

        st.markdown("---")

        # --- SECCIÓN 2: VISUALIZACIÓN DEL EMBUDO ---
        st.subheader("🚀 Visualización del Embudo de Prospección")
        
        fig_funnel = go.Figure(go.Funnel(
            y = ["Conexiones Enviadas", "Conexiones Aceptadas", "Respuestas de WA", "Sesiones Logradas"],
            x = [total_conex_enviadas, total_conex_aceptadas, total_wa_respondidos, total_sesiones],
            textinfo = "value+percent initial"
        ))
        fig_funnel.update_layout(margin=dict(l=50, r=50, t=30, b=10))
        st.plotly_chart(fig_funnel, use_container_width=True)
        st.markdown("---")
        
        # --- SECCIÓN 3: EVOLUCIÓN SEMANAL ---
        st.subheader("🗓️ Evolución Semanal")
        
        df_chart = df_filtered.groupby('FechaSemana', as_index=False).sum(numeric_only=True)
        df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
        df_chart = df_chart.sort_values('FechaSemana')

        st.markdown("<h6>Volumen de Actividades por Semana</h6>", unsafe_allow_html=True)
        fig_actividades = go.Figure()
        fig_actividades.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Conexiones enviadas'], name='Conexiones Enviadas'))
        fig_actividades.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Llamadas realizadas'], name='Llamadas Realizadas'))
        fig_actividades.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Whatsapps Enviados'], name='Whatsapps Enviados'))
        fig_actividades.update_layout(barmode='group', xaxis_title="Semana", yaxis_title="Cantidad", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_actividades, use_container_width=True)

        st.markdown("<h6>Resultados Clave por Semana</h6>", unsafe_allow_html=True)
        fig_resultados = go.Figure()
        fig_resultados.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Conexiones aceptadas'], mode='lines+markers', name='Conexiones Aceptadas'))
        fig_resultados.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Whatsapps Respondidos'], mode='lines+markers', name='Whatsapps Respondidos'))
        fig_resultados.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Sesiones logradas'], mode='lines+markers', name='Sesiones Logradas', line=dict(color='green', width=4)))
        fig_resultados.update_layout(xaxis_title="Semana", yaxis_title="Cantidad", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_resultados, use_container_width=True)

        # --- TABLA DE DATOS ORIGINALES ---
        st.markdown("---")
        with st.expander("Ver tabla de datos originales del Google Sheet (Período Seleccionado)"):
            st.caption("Esta tabla muestra los datos tal como se ingresaron en la hoja de cálculo, para referencia y auditoría.")
            cols_a_mostrar = [col for col in original_cols if col in df_filtered.columns]
            st.dataframe(df_filtered[cols_a_mostrar], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
