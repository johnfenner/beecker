# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import locale
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de KPIs", layout="wide")
st.title("🚀 Dashboard de Prospección de Evelyn")
st.markdown("Análisis de rendimiento, trazabilidad del embudo y eficacia por canal.")

# --- CONFIGURACIÓN REGIONAL ---
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    pass

# --- FUNCIÓN DE CARGA Y LIMPIEZA DE DATOS (Optimizada) ---
def clean_numeric(value):
    if value is None: return 0
    s = str(value).strip().replace('%', '').replace(',', '.')
    if not s or s.startswith('#'): return 0
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
        
        if len(values) < 2:
            st.warning("La hoja de cálculo está vacía o solo tiene encabezados.")
            return pd.DataFrame(), []
        
        headers = values[0]
        df = pd.DataFrame(values[1:], columns=headers)

    except Exception as e:
        st.error(f"No se pudo cargar la hoja de Google Sheets. Error: {e}")
        return pd.DataFrame(), []

    if 'Semana' not in df.columns or df['Semana'].eq('').all():
        st.error("Error crítico: La columna 'Semana' es indispensable y no se encontró o está vacía.")
        return pd.DataFrame(), []

    df['FechaSemana'] = pd.to_datetime(df['Semana'], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['FechaSemana'], inplace=True)
    
    numeric_cols = [
        'Empresas agregadas', 'Meta empresas', 'Contactos agregados', 'Conexiones enviadas', 
        'Conexiones aceptadas', 'Mensajes de seguimiento enviados', 'Números telefónicos encontrados', 
        'Whatsapps Enviados', 'Whatsapps Respondidos', 'Llamadas realizadas', 'Sesiones logradas', 'Meta sesiones'
    ]
    for col in numeric_cols:
        df[col] = df[col].apply(clean_numeric) if col in df.columns else 0

    return df.sort_values(by='FechaSemana', ascending=False), headers

# --- FILTROS EN LA BARRA LATERAL ---
def display_filters(df):
    st.sidebar.header("🔍 Filtros")
    if df.empty or 'FechaSemana' not in df.columns:
        st.sidebar.warning("No hay datos para filtrar.")
        return ["– Todas las Semanas –"]
    
    df['SemanaLabel'] = df['FechaSemana'].dt.strftime("Semana del %d/%b/%Y")
    opciones_filtro = ["– Todas las Semanas –"] + df['SemanaLabel'].unique().tolist()
    
    selected_semanas = st.sidebar.multiselect(
        "Selecciona Semanas", options=opciones_filtro, default=["– Todas las Semanas –"]
    )
    
    if "– Todas las Semanas –" in selected_semanas and len(selected_semanas) > 1:
        return [s for s in selected_semanas if s != "– Todas las Semanas –"]
    return selected_semanas

# --- INICIO DEL FLUJO PRINCIPAL ---
df_sdr_raw, original_cols = load_sdr_data()

if not df_sdr_raw.empty:
    selected_weeks_labels = display_filters(df_sdr_raw)
    
    df_filtered = df_sdr_raw.copy()
    if selected_weeks_labels and "– Todas las Semanas –" not in selected_weeks_labels:
        df_filtered = df_sdr_raw[df_sdr_raw['SemanaLabel'].isin(selected_weeks_labels)]
    
    if df_filtered.empty and selected_weeks_labels != ["– Todas las Semanas –"]:
        st.warning("No hay datos para las semanas específicas seleccionadas.")
    else:
        # --- CÁLCULOS GLOBALES ---
        total_conex_enviadas = int(df_filtered['Conexiones enviadas'].sum())
        total_conex_aceptadas = int(df_filtered['Conexiones aceptadas'].sum())
        total_wa_enviados = int(df_filtered['Whatsapps Enviados'].sum())
        total_wa_respondidos = int(df_filtered['Whatsapps Respondidos'].sum())
        total_llamadas = int(df_filtered['Llamadas realizadas'].sum())
        total_sesiones = int(df_filtered['Sesiones logradas'].sum())

        # --- RESUMEN DE KPIS ---
        st.subheader("Resumen de KPIs (Período Filtrado)")
        
        with st.container(border=True):
            st.markdown("##### Actividades Cuantificadas (Tu Esfuerzo)")
            act1, act2, act3 = st.columns(3)
            act1.metric("🔗 Conexiones Enviadas (LI)", f"{total_conex_enviadas:,}")
            act2.metric("💬 Whatsapps Enviados", f"{total_wa_enviados:,}")
            act3.metric("📞 Llamadas Realizadas", f"{total_llamadas:,}")
            
            st.markdown("##### Resultados Obtenidos")
            res1, res2, res3 = st.columns(3)
            res1.metric("✅ Conexiones Aceptadas", f"{total_conex_aceptadas:,}")
            res2.metric("🗣️ Whatsapps Respondidos", f"{total_wa_respondidos:,}")
            res3.metric("🗓️ Sesiones Logradas", f"{total_sesiones:,}")

        st.markdown("---")

        # --- TASAS DE CONVERSIÓN Y EFICACIA ---
        st.subheader("Tasas de Conversión y Eficacia del Embudo")
        with st.container(border=True):
            tasa1, tasa2 = st.columns(2)
            tasa_aceptacion = (total_conex_aceptadas / total_conex_enviadas * 100) if total_conex_enviadas > 0 else 0
            tasa_respuesta_wa = (total_wa_respondidos / total_wa_enviados * 100) if total_wa_enviados > 0 else 0
            tasa1.metric("📈 Tasa de Aceptación (LinkedIn)", f"{tasa_aceptacion:.1f}%", help="De cada 100 conexiones que envías, cuántas te aceptan.")
            tasa2.metric("📈 Tasa de Respuesta (WhatsApp)", f"{tasa_respuesta_wa:.1f}%", help="De cada 100 Whatsapps que envías, cuántos te responden.")

            st.markdown("##### Eficacia por Canal para Generar Sesiones")
            eficacia1, eficacia2 = st.columns(2)
            eficacia_wa = (total_sesiones / total_wa_respondidos * 100) if total_wa_respondidos > 0 else 0
            eficacia_llamadas = (total_sesiones / total_llamadas * 100) if total_llamadas > 0 else 0
            eficacia1.metric("🎯 Sesiones por cada 100 Respuestas de WA", f"{eficacia_wa:.1f}", help="Mide qué tan bueno eres convirtiendo una conversación de WA en una sesión.")
            eficacia2.metric("🎯 Sesiones por cada 100 Llamadas", f"{eficacia_llamadas:.1f}", help="Mide la efectividad de tus llamadas para agendar una sesión.")

        st.markdown("---")
        
        # --- GRÁFICOS AVANZADOS ---
        st.subheader("Análisis de Tendencia Semanal")
        
        df_chart = df_filtered.groupby('FechaSemana').sum(numeric_only=True).reset_index()
        df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
        df_chart = df_chart.sort_values('FechaSemana')
        
        # Gráfico 1: Esfuerzo (Barras) vs. Resultados (Línea)
        with st.container(border=True):
            st.markdown("##### Esfuerzo vs. Resultados por Semana")
            fig1 = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Barras de Esfuerzo
            fig1.add_trace(go.Bar(name='Conexiones Enviadas', x=df_chart['SemanaLabel'], y=df_chart['Conexiones enviadas'], marker_color='#36719F'), secondary_y=False)
            fig1.add_trace(go.Bar(name='Whatsapps Enviados', x=df_chart['SemanaLabel'], y=df_chart['Whatsapps Enviados'], marker_color='#6A8D73'), secondary_y=False)
            fig1.add_trace(go.Bar(name='Llamadas Realizadas', x=df_chart['SemanaLabel'], y=df_chart['Llamadas realizadas'], marker_color='#B4A05B'), secondary_y=False)
            
            # Línea de Resultado Principal
            fig1.add_trace(go.Scatter(name='Sesiones Logradas', x=df_chart['SemanaLabel'], y=df_chart['Sesiones logradas'], mode='lines+markers', line=dict(color='green', width=4)), secondary_y=True)
            
            fig1.update_layout(barmode='stack', title_text="¿Cuánto trabajo se necesitó para generar sesiones?", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig1.update_yaxes(title_text="Volumen de Actividades (Esfuerzo)", secondary_y=False)
            fig1.update_yaxes(title_text="Sesiones Logradas (Resultado)", secondary_y=True, range=[0, max(1, df_chart['Sesiones logradas'].max() * 2)])
            st.plotly_chart(fig1, use_container_width=True)

        # Gráfico 2: Evolución de la Eficacia del Embudo (%)
        with st.container(border=True):
            st.markdown("##### Eficacia del Embudo Semanal (%)")
            df_chart['TasaAceptacion'] = (df_chart['Conexiones aceptadas'] / df_chart['Conexiones enviadas'] * 100).fillna(0)
            df_chart['TasaRespuestaWA'] = (df_chart['Whatsapps Respondidos'] / df_chart['Whatsapps Enviados'] * 100).fillna(0)
            
            fig2 = go.Figure()
            fig2.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['TasaAceptacion'], name='Tasa de Aceptación (LI)', mode='lines+markers', line=dict(color='#36719F')))
            fig2.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['TasaRespuestaWA'], name='Tasa de Respuesta (WA)', mode='lines+markers', line=dict(color='#6A8D73')))
            
            fig2.update_layout(title_text="¿Estoy mejorando mi técnica de conversión cada semana?", yaxis_ticksuffix='%', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            fig2.update_yaxes(title_text="Tasa de Conversión (%)", range=[0, max(10, df_chart['TasaAceptacion'].max(), df_chart['TasaRespuestaWA'].max()) * 1.2])
            st.plotly_chart(fig2, use_container_width=True)

        # --- TABLA DE DATOS ---
        st.markdown("---")
        with st.expander("Ver tabla de datos originales del período seleccionado"):
            cols_a_mostrar = [col for col in original_cols if col in df_filtered.columns]
            st.dataframe(df_filtered[cols_a_mostrar], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
