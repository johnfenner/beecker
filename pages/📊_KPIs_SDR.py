# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
import locale
import numpy as np

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="KPIs del SDR", layout="wide")
st.title("🚀 Dashboard de KPIs para SDR - Evelyn")
st.markdown("Análisis de rendimiento basado en la trazabilidad del embudo de prospección.")

# --- CONFIGURACIÓN REGIONAL PARA FECHAS EN ESPAÑOL ---
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    # Si la configuración regional en español no está disponible, se omite.
    pass

# --- FUNCIÓN DE LIMPIEZA Y CARGA DE DATOS (Sin cambios, ya era robusta) ---
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

    # Se eliminan columnas pre-calculadas para asegurar que la app haga los cálculos.
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
            # Si una columna numérica no existe en el sheet, se crea con ceros para evitar errores.
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
        # Si 'Todas' está seleccionada junto a otras, se priorizan las específicas.
        return [s for s in selected_semanas if s != todas_las_semanas_opcion]
    elif not selected_semanas:
        # Si el usuario deselecciona todo, se vuelve a 'Todas'.
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
        total_empresas = int(df_filtered['Empresas agregadas'].sum())
        meta_empresas = int(df_filtered['Meta empresas'].sum())
        total_conexiones_enviadas = int(df_filtered['Conexiones enviadas'].sum())
        total_conexiones_aceptadas = int(df_filtered['Conexiones aceptadas'].sum())
        total_wa_enviados = int(df_filtered['Whatsapps Enviados'].sum())
        total_wa_respondidos = int(df_filtered['Whatsapps Respondidos'].sum())
        total_llamadas = int(df_filtered['Llamadas realizadas'].sum())
        total_sesiones = int(df_filtered['Sesiones logradas'].sum())
        meta_sesiones = int(df_filtered['Meta sesiones'].sum())

        # --- RESUMEN GENERAL ---
        st.subheader("Resumen General del Período Seleccionado")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("🏢 Empresas Agregadas", f"{total_empresas:,}")
        col2.metric("🔗 Conexiones Aceptadas", f"{total_conexiones_aceptadas:,}")
        col3.metric("💬 Whatsapps Respondidos", f"{total_wa_respondidos:,}")
        col4.metric("🗓️ Sesiones Logradas", f"{total_sesiones:,}")
        st.markdown("---")

        # --- PASO 1: PROSPECCIÓN DE EMPRESAS ---
        with st.container(border=True):
            st.subheader("Paso 1: Prospección de Empresas")
            st.markdown("El primer paso del embudo: agregar nuevas empresas al pipeline.")
            
            cumplimiento_empresas = (total_empresas / meta_empresas * 100) if meta_empresas > 0 else 0
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("<h6>Meta de Empresas</h6>", unsafe_allow_html=True)
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = total_empresas,
                    title = {'text': f"Logro vs Meta ({meta_empresas})"},
                    gauge = {'axis': {'range': [None, max(meta_empresas, total_empresas, 1) * 1.2]}, 'bar': {'color': "#36719F"},
                             'threshold': {'line': {'color': "red", 'width': 4}, 'thickness': 0.75, 'value': meta_empresas}}))
                fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True, key="gauge_empresas_sdr")
                st.metric("Tasa de Cumplimiento", f"{cumplimiento_empresas:.1f}%")
            
            with col2:
                st.markdown("<h6>Evolución Semanal de Prospección</h6>", unsafe_allow_html=True)
                df_chart = df_filtered.groupby('FechaSemana', as_index=False)[['Empresas agregadas', 'Contactos agregados']].sum()
                df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Empresas agregadas'], name='Empresas Agregadas'))
                fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Contactos agregados'], name='Contactos Agregados'))
                fig.update_layout(barmode='group', height=300, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)

        # --- PASO 2: CONTACTO INICIAL Y ACEPTACIÓN ---
        with st.container(border=True):
            st.subheader("Paso 2: Contacto Inicial y Tasa de Aceptación")
            st.markdown("Medimos cuántos de los contactos iniciales aceptan la conexión. Este es el primer punto de conversión.")
            
            acceptance_rate = (total_conexiones_aceptadas / total_conexiones_enviadas * 100) if total_conexiones_enviadas > 0 else 0
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("<h6>Embudo de Conexión</h6>", unsafe_allow_html=True)
                fig = go.Figure(go.Funnel(
                    y = ["Enviadas", "Aceptadas"], 
                    x = [total_conexiones_enviadas, total_conexiones_aceptadas],
                    textinfo = "value+percent initial"))
                fig.update_layout(height=250, margin=dict(l=50, r=50, t=30, b=10))
                st.plotly_chart(fig, use_container_width=True, key="funnel_conexiones_sdr")
                st.metric("Tasa de Aceptación", f"{acceptance_rate:.1f}%")
                st.caption("Calculado como: Aceptadas / Enviadas")

            with col2:
                st.markdown("<h6>Evolución Semanal de Conexiones</h6>", unsafe_allow_html=True)
                df_chart = df_filtered.groupby('FechaSemana', as_index=False)[['Conexiones enviadas', 'Conexiones aceptadas']].sum()
                df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Conexiones enviadas'], name='Enviadas'))
                fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Conexiones aceptadas'], name='Aceptadas'))
                fig.update_layout(barmode='group', height=300, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)

        # --- PASO 3: SEGUIMIENTO Y ENGAGEMENT ---
        with st.container(border=True):
            st.subheader("Paso 3: Seguimiento y Engagement")
            st.markdown("Una vez conectados, analizamos la efectividad de las actividades de seguimiento para generar una conversación.")
            
            response_rate_wa = (total_wa_respondidos / total_wa_enviados * 100) if total_wa_enviados > 0 else 0
            
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<h6>Embudo de WhatsApp</h6>", unsafe_allow_html=True)
                fig = go.Figure(go.Funnel(
                    y = ["Enviados", "Respondidos"], 
                    x = [total_wa_enviados, total_wa_respondidos],
                    textinfo = "value+percent initial", marker={"color": ["#6A8D73", "#8AAF7A"]}))
                fig.update_layout(height=250, margin=dict(l=50, r=50, t=30, b=10))
                st.plotly_chart(fig, use_container_width=True, key="funnel_whatsapp_sdr")
                st.metric("Tasa de Respuesta (WA)", f"{response_rate_wa:.1f}%")
                st.caption("Calculado como: Respondidos / Enviados")

            with col2:
                st.markdown("<h6>Actividades de Seguimiento</h6>", unsafe_allow_html=True)
                df_chart = df_filtered.groupby('FechaSemana', as_index=False)[['Whatsapps Enviados', 'Llamadas realizadas']].sum()
                df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
                fig = go.Figure()
                fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Whatsapps Enviados'], name='Whatsapps Enviados'))
                fig.add_trace(go.Bar(x=df_chart['SemanaLabel'], y=df_chart['Llamadas realizadas'], name='Llamadas Realizadas'))
                fig.update_layout(barmode='stack', height=300, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                  title_text="Volumen de Seguimiento Semanal")
                st.plotly_chart(fig, use_container_width=True)


        # --- PASO 4: CONVERSIÓN A SESIONES ---
        with st.container(border=True):
            st.subheader("Paso 4: El Resultado Final - Sesiones Logradas")
            st.markdown("La métrica clave: cuántas de nuestras interacciones se convierten en una sesión de descubrimiento o demo.")
            
            cumplimiento_sesiones = (total_sesiones / meta_sesiones * 100) if meta_sesiones > 0 else 0
            # Tasa de conversión: Sesiones logradas a partir de las conexiones que SÍ fueron aceptadas.
            conversion_rate_sesion = (total_sesiones / total_conexiones_aceptadas * 100) if total_conexiones_aceptadas > 0 else 0

            col1, col2 = st.columns([1, 2])
            with col1:
                st.markdown("<h6>Meta de Sesiones</h6>", unsafe_allow_html=True)
                fig = go.Figure(go.Indicator(
                    mode = "gauge+number", value = total_sesiones,
                    title = {'text': f"Logro vs Meta ({meta_sesiones})"},
                    gauge = {'axis': {'range': [None, max(meta_sesiones, total_sesiones, 1) * 1.2]}, 'bar': {'color': "#36719F"},
                             'threshold': {'line': {'color': "green", 'width': 4}, 'thickness': 0.75, 'value': meta_sesiones}}))
                fig.update_layout(height=250, margin=dict(l=20, r=20, t=50, b=20))
                st.plotly_chart(fig, use_container_width=True, key="gauge_sesiones_sdr")
                st.metric("Tasa de Cumplimiento", f"{cumplimiento_sesiones:.1f}%")
                st.metric("Tasa de Conversión a Sesión", f"{conversion_rate_sesion:.1f}%")
                st.caption("Calculado como: Sesiones / Conexiones Aceptadas")
            
            with col2:
                st.markdown("<h6>Evolución Semanal de Resultados Clave</h6>", unsafe_allow_html=True)
                df_chart = df_filtered.groupby('FechaSemana', as_index=False)[['Conexiones aceptadas', 'Whatsapps Respondidos', 'Sesiones logradas']].sum()
                df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Conexiones aceptadas'], mode='lines+markers', name='Conexiones Aceptadas'))
                fig.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Whatsapps Respondidos'], mode='lines+markers', name='Whatsapps Respondidos'))
                fig.add_trace(go.Scatter(x=df_chart['SemanaLabel'], y=df_chart['Sesiones logradas'], mode='lines+markers', name='Sesiones Logradas', line=dict(color='green', width=4, dash='dot')))
                fig.update_layout(height=350, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
                st.plotly_chart(fig, use_container_width=True)

        # --- TABLA DE DATOS ORIGINALES ---
        st.markdown("---")
        with st.expander("Ver tabla de datos originales del Google Sheet (Período Seleccionado)"):
            st.caption("Esta tabla muestra los datos tal como se ingresaron en la hoja de cálculo, para referencia y auditoría.")
            
            # Filtramos la lista de columnas originales para mostrar solo las que existen en el DataFrame final.
            cols_a_mostrar = [col for col in original_cols if col in df_filtered.columns]
            
            st.dataframe(df_filtered[cols_a_mostrar], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
