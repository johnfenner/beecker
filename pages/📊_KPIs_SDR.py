# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import locale
from datetime import datetime

# --- CONFIGURACIÓN DE LA PÁGINA --
st.set_page_config(page_title="Dashboard de KPIs", layout="wide")
st.title("📊 Dashboard de KPIs de Evelyn")
st.markdown("Análisis de métricas absolutas y tasas de conversión siguiendo el proceso de generación de leads.")

# --- CONFIGURACIÓN REGIONAL ---
try:
    locale.setlocale(locale.LC_TIME, 'es_ES.UTF-8')
except locale.Error:
    pass

# --- FUNCIÓN DE CARGA Y LIMPIEZA DE DATOS ---
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
            return pd.DataFrame()
        
        headers = [h.strip() for h in values[0]]
        df = pd.DataFrame(values[1:], columns=headers)

    except Exception as e:
        st.error(f"No se pudo cargar la hoja de Google Sheets. Error: {e}")
        return pd.DataFrame()

    if 'Semana' not in df.columns or df['Semana'].eq('').all():
        st.error("Error crítico: La columna 'Semana' es indispensable y no se encontró o está vacía.")
        return pd.DataFrame()

    def parse_custom_week(week_str):
        month_map = {
            'enero': 1, 'febrero': 2, 'marzo': 3, 'abril': 4, 'mayo': 5, 'junio': 6,
            'julio': 7, 'agosto': 8, 'septiembre': 9, 'octubre': 10, 'noviembre': 11, 'diciembre': 12
        }
        try:
            parts = week_str.lower().split(' de ')
            month_name = parts[-1].strip()
            week_num = int(''.join(filter(str.isdigit, parts[0])))
            month_num = month_map[month_name]
            year = datetime.now().year
            day = (week_num - 1) * 7 + 1
            return pd.to_datetime(f"{year}-{month_num:02d}-{day:02d}", errors='coerce')
        except:
            return pd.NaT
            
    df['FechaSemana'] = df['Semana'].apply(parse_custom_week)
    df.dropna(subset=['FechaSemana'], inplace=True)
    
    if df.empty:
        st.error("Error: No se encontró ninguna fila con un formato de semana reconocible (ej: 'Semana #1 de julio').")
        return pd.DataFrame()

    numeric_cols = [
        'Llamadas Realizadas', 'Llamada Respondidas', 'Mensajes de Whats app', 
        'Mensajes de whats app contestados', 'Conexiones enviadas', 'Conexiones Aceptadas', 
        'Sesiones Logradas', 'Mensajes de seguimiento enviados por linkedin', 
        'Empresas en seguimiento el siguiente año', 'Empresas en seguimiento', 
        'Empresas descartadas', 'Correos enviados', 'Empresas nuevas agregadas esta semana'
    ]
    
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_numeric)
        else:
            df[col] = 0

    return df.sort_values(by='FechaSemana', ascending=False)

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
df_sdr_raw = load_sdr_data()

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
        total_conex_aceptadas = int(df_filtered['Conexiones Aceptadas'].sum())
        total_wa_enviados = int(df_filtered['Mensajes de Whats app'].sum())
        total_wa_respondidos = int(df_filtered['Mensajes de whats app contestados'].sum())
        total_llamadas_realizadas = int(df_filtered['Llamadas Realizadas'].sum())
        total_llamadas_respondidas = int(df_filtered['Llamada Respondidas'].sum())
        total_sesiones = int(df_filtered['Sesiones Logradas'].sum())
        total_seguimiento_li = int(df_filtered['Mensajes de seguimiento enviados por linkedin'].sum())
        total_correos = int(df_filtered['Correos enviados'].sum())
        total_empresas_nuevas = int(df_filtered['Empresas nuevas agregadas esta semana'].sum())
        total_empresas_seguimiento = int(df_filtered['Empresas en seguimiento'].sum())
        total_empresas_descartadas = int(df_filtered['Empresas descartadas'].sum())

        # --- SECCIÓN 1: RESUMEN DE KPIS ---
        st.subheader("Resumen de KPIs (Período Filtrado)")
        with st.container(border=True):
            st.markdown("##### Actividades Clave")
            kpi1, kpi2, kpi3, kpi4 = st.columns(4)
            kpi1.metric("🔗 Conexiones Enviadas (LI)", f"{total_conex_enviadas:,}")
            kpi2.metric("💬 Whatsapps Enviados", f"{total_wa_enviados:,}")
            kpi3.metric("📞 Llamadas Realizadas", f"{total_llamadas_realizadas:,}")
            kpi4.metric("👔 Msjs. Seguimiento (LI)", f"{total_seguimiento_li:,}", help="Mensajes de seguimiento enviados por LinkedIn")

            st.markdown("##### Resultados Obtenidos")
            res1, res2, res3, res4 = st.columns(4)
            res1.metric("✅ Conexiones Aceptadas", f"{total_conex_aceptadas:,}")
            res2.metric("🗣️ Whatsapps Respondidos", f"{total_wa_respondidos:,}")
            res3.metric("📣 Llamadas Respondidas", f"{total_llamadas_respondidas:,}")
            res4.metric("🗓️ Sesiones Logradas", f"{total_sesiones:,}")
        
        st.markdown("---")

        # --- SECCIÓN 2: TASAS DE CONVERSIÓN ---
        st.subheader("Tasas de Conversión y Eficacia")
        with st.container(border=True):
            tasa_aceptacion = (total_conex_aceptadas / total_conex_enviadas * 100) if total_conex_enviadas > 0 else 0
            tasa_resp_wa = (total_wa_respondidos / total_wa_enviados * 100) if total_wa_enviados > 0 else 0
            tasa_resp_llamada = (total_llamadas_respondidas / total_llamadas_realizadas * 100) if total_llamadas_realizadas > 0 else 0
            tasa_agendamiento_wa = (total_sesiones / total_wa_respondidos * 100) if total_wa_respondidos > 0 else 0
            
            tc1, tc2, tc3, tc4 = st.columns(4)
            tc1.metric("🔗 Tasa de Aceptación (LI)", f"{tasa_aceptacion:.1f}%", help="De 100 conexiones enviadas, cuántas son aceptadas.")
            tc2.metric("💬 Tasa de Respuesta (WA)", f"{tasa_resp_wa:.1f}%", help="De 100 WhatsApps enviados, cuántos son respondidos.")
            tc3.metric("📞 Tasa de Respuesta (Llamada)", f"{tasa_resp_llamada:.1f}%", help="De 100 llamadas hechas, cuántas son respondidas.")
            tc4.metric("🎯 Tasa de Agendamiento (WA)", f"{tasa_agendamiento_wa:.1f}%", help="De los WhatsApps respondidos, qué % se convierte en sesión.")
        
        st.markdown("---")
        
        # --- SECCIÓN 3: VISUALIZACIÓN DEL EMBUDO Y PIPELINE ---
        col_funnel, col_pipeline = st.columns(2)
        with col_funnel:
            st.subheader("Embudo de Conversión General")
            with st.container(border=True):
                # Datos para el embudo de conversión
                funnel_values = [total_conex_enviadas, total_conex_aceptadas, total_wa_enviados, total_wa_respondidos, total_sesiones]
                funnel_labels = ['Conexiones Enviadas', 'Conexiones Aceptadas', 'Whatsapps Enviados', 'Whatsapps Respondidos', 'Sesiones Logradas']
                
                # Filtrar etapas con valor 0 para no mostrarlas
                valid_indices = [i for i, v in enumerate(funnel_values) if v > 0]
                funnel_values = [funnel_values[i] for i in valid_indices]
                funnel_labels = [funnel_labels[i] for i in valid_indices]

                if funnel_values:
                    fig_funnel = go.Figure(go.Funnel(
                        y = funnel_labels,
                        x = funnel_values,
                        textposition = "inside",
                        textinfo = "value+percent initial",
                        opacity = 0.8,
                        marker = {"color": ["#004c6d", "#346b87", "#588ca3", "#7eafc0", "#a6d3de"],
                                  "line": {"width": [2, 2, 2, 2, 2], "color": "white"}},
                        connector = {"line": {"color": "royalblue", "dash": "dot", "width": 3}}
                    ))
                    fig_funnel.update_layout(height=400, margin=dict(l=50, r=20, t=20, b=20))
                    st.plotly_chart(fig_funnel, use_container_width=True)
                else:
                    st.info("No hay datos suficientes para mostrar el embudo de conversión.")

        with col_pipeline:
            st.subheader("Estado del Pipeline de Empresas")
            with st.container(border=True):
                fig_donut = make_subplots(rows=1, cols=3, specs=[[{'type':'domain'}, {'type':'domain'}, {'type':'domain'}]])
                
                fig_donut.add_trace(go.Pie(labels=[''], values=[total_empresas_nuevas], name="Nuevas", hole=.7,
                                           marker_colors=['#00a896'], textinfo='none'), 1, 1)
                fig_donut.add_trace(go.Pie(labels=[''], values=[total_empresas_seguimiento], name="Seguimiento", hole=.7,
                                           marker_colors=['#f0a202'], textinfo='none'), 1, 2)
                fig_donut.add_trace(go.Pie(labels=[''], values=[total_empresas_descartadas], name="Descartadas", hole=.7,
                                           marker_colors=['#d9534f'], textinfo='none'), 1, 3)

                fig_donut.update_layout(
                    height=200,
                    showlegend=False,
                    margin=dict(l=10, r=10, t=50, b=10),
                    annotations=[
                        dict(text=f'<b>{total_empresas_nuevas}</b><br>Nuevas', x=0.12, y=0.5, font_size=16, showarrow=False),
                        dict(text=f'<b>{total_empresas_seguimiento}</b><br>Seguimiento', x=0.5, y=0.5, font_size=16, showarrow=False),
                        dict(text=f'<b>{total_empresas_descartadas}</b><br>Descartadas', x=0.89, y=0.5, font_size=16, showarrow=False)
                    ]
                )
                st.plotly_chart(fig_donut, use_container_width=True)
                st.markdown(
                    """
                    <style>
                    [data-testid="stVerticalBlock"] > [data-testid="stHorizontalBlock"] > [data-testid="stVerticalBlock"] {
                        border: 1px solid #2D3038;
                        border-radius: 10px;
                        padding: 10px;
                    }
                    </style>
                    """, unsafe_allow_html=True
                )
        
        st.markdown("---")

        # --- SECCIÓN 4: ANÁLISIS DE TENDENCIA SEMANAL ---
        st.subheader("Análisis de Tendencia Semanal")
        df_chart = df_filtered.groupby('FechaSemana').sum(numeric_only=True).reset_index()
        df_chart['SemanaLabel'] = df_chart['FechaSemana'].dt.strftime("Semana del %d/%b")
        df_chart = df_chart.sort_values('FechaSemana')

        with st.container(border=True):
            st.markdown("##### Volumen de Actividades Clave por Semana")
            fig_act = go.Figure()
            fig_act.add_trace(go.Bar(name='Conexiones Enviadas', x=df_chart['SemanaLabel'], y=df_chart['Conexiones enviadas'], marker_color='#004c6d'))
            fig_act.add_trace(go.Bar(name='Whatsapps Enviados', x=df_chart['SemanaLabel'], y=df_chart['Mensajes de Whats app'], marker_color='#588ca3'))
            fig_act.add_trace(go.Bar(name='Llamadas Realizadas', x=df_chart['SemanaLabel'], y=df_chart['Llamadas Realizadas'], marker_color='#a6d3de'))
            fig_act.update_layout(barmode='group', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_act, use_container_width=True)

        with st.container(border=True):
            st.markdown("##### Actividades de Seguimiento por Semana")
            fig_seg = go.Figure()
            fig_seg.add_trace(go.Scatter(name='Msjs. Seguimiento (LI)', x=df_chart['SemanaLabel'], y=df_chart['Mensajes de seguimiento enviados por linkedin'], mode='lines+markers', line=dict(color='#f0a202', width=3)))
            fig_seg.add_trace(go.Scatter(name='Correos Enviados', x=df_chart['SemanaLabel'], y=df_chart['Correos enviados'], mode='lines+markers', line=dict(color='#f7b84b', dash='dash')))
            fig_seg.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_seg, use_container_width=True)

        # --- SECCIÓN 5: TABLA DE DATOS ---
        st.markdown("---")
        with st.expander("Ver tabla de datos detallados del período seleccionado"):
            st.dataframe(df_filtered, hide_index=True)
else:
    # Este mensaje se muestra si la carga inicial de datos falla por permisos o si la hoja está vacía.
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")


