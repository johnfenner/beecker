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
    Carga y procesa datos desde la hoja 'Evelyn', creando un embudo de conversión
    y métricas específicas, incluyendo el análisis de recontacto.
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

    # --- Creación del Embudo Lógico y Métricas ---
    
    date_columns_to_process = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha",
        "Fecha de Primer Acercamiento": "Fecha_Primer_Acercamiento",
        "Fecha de Primer Respuesta": "Fecha_Primera_Respuesta",
        "Fecha De Recontacto": "Fecha_Recontacto" # Columna para la métrica de seguimiento
    }
    
    for original_col, new_col in date_columns_to_process.items():
        if original_col in df.columns:
            df[new_col] = pd.to_datetime(df[original_col], format='%d/%m/%Y', errors='coerce')
        else:
            df[new_col] = pd.NaT

    if "Fecha" not in df.columns or df["Fecha"].isnull().all():
        st.error("Columna 'Fecha Primer contacto (...)' no encontrada o vacía. Es esencial para el análisis.")
        return pd.DataFrame()
    
    df.dropna(subset=['Fecha'], inplace=True)

    # Contadores basados en la existencia de fechas o valores 'si'
    df['Acercamientos'] = df['Fecha'].notna().astype(int)
    df['Mensajes_Enviados'] = df['Fecha_Primer_Acercamiento'].notna().astype(int)
    df['Respuestas_Iniciales'] = df['Fecha_Primera_Respuesta'].notna().astype(int)
    df['Sesiones_Agendadas'] = df["Sesion Agendada?"].apply(lambda x: 1 if str(x).strip().lower() in ['si', 'sí'] else 0) if "Sesion Agendada?" in df.columns else 0
    df['Necesita_Recontacto'] = df['Fecha_Recontacto'].notna().astype(int) # Contador para seguimiento

    # Dimensiones de tiempo
    df['Año'] = df['Fecha'].dt.year
    df['Mes'] = df['Fecha'].dt.month # Nueva columna para filtrar por mes
    df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
    df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')

    # Limpieza de columnas de filtro
    for col in ["Fuente de la Lista", "Campaña", "Proceso", "Industria"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"

    return df.sort_values(by='Fecha', ascending=False)

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- COMPONENTES VISUALES ---

def sidebar_filters(df):
    st.sidebar.header("🔍 Filtros de Análisis")
    if df.empty:
        st.sidebar.warning("No hay datos para filtrar.")
        return {}

    filtros = {}
    st.sidebar.subheader("📅 Por Fecha de Acercamiento")

    # --- NUEVOS FILTROS POR AÑO Y MES ---
    if 'Año' in df.columns:
        años_disponibles = sorted(df['Año'].unique().tolist(), reverse=True)
        filtros['Año'] = st.sidebar.multiselect("Seleccionar Año(s)", ["– Todos –"] + años_disponibles, default=["– Todos –"])

    if 'Mes' in df.columns:
        meses_map = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
            7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        # Guardamos los nombres de los meses seleccionados
        filtros['Mes_Nombre'] = st.sidebar.multiselect("Seleccionar Mes(es)", ["– Todos –"] + list(meses_map.values()), default=["– Todos –"])

    st.sidebar.subheader("🔎 Por Estrategia de Prospección")
    for dim_col in ["Campaña", "Fuente de la Lista", "Proceso", "Industria"]:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtros[dim_col] = st.sidebar.multiselect(dim_col, opciones, default=["– Todos –"])

    if st.sidebar.button("🧹 Limpiar Todos los Filtros", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    return filtros

def apply_filters(df, filtros):
    df_f = df.copy()

    # Mapeo para convertir nombres de mes a números
    meses_map_inverso = {
        'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4, 'Mayo': 5, 'Junio': 6,
        'Julio': 7, 'Agosto': 8, 'Septiembre': 9, 'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
    }
    
    # Lógica de filtro para los meses (usando la nueva columna 'Mes')
    selected_month_names = filtros.get('Mes_Nombre', [])
    if selected_month_names and "– Todos –" not in selected_month_names:
        selected_month_numbers = [meses_map_inverso[name] for name in selected_month_names]
        df_f = df_f[df_f['Mes'].isin(selected_month_numbers)]

    # Lógica de filtro para el resto de las dimensiones (incluyendo 'Año')
    for col, values in filtros.items():
        if col != 'Mes_Nombre' and values and "– Todos –" not in values:
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


def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    st.markdown(f"### {chart_icon} {title_prefix}")
    if group_by_col not in df_filtered.columns or df_filtered.empty or df_filtered[group_by_col].nunique() <= 1:
        st.info(f"No hay suficientes datos o diversidad en la columna '{group_by_col}' para generar un desglose.")
        return

    summary_df = df_filtered.groupby(group_by_col).agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    summary_df['Tasa Sesión / Acercamiento (%)'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Acercamientos), axis=1)

    st.markdown("##### Tabla de Rendimiento")
    st.dataframe(summary_df[summary_df['Acercamientos'] > 0].style.format({'Tasa Sesión / Acercamiento (%)': '{:.1f}%'}), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Sesiones Agendadas (Volumen)")
        fig_abs = px.bar(summary_df.sort_values('Sesiones_Agendadas', ascending=False),
                         x=group_by_col, y='Sesiones_Agendadas', text_auto=True,
                         title=f"Volumen de Sesiones por {group_by_col}", color="Sesiones_Agendadas",
                         color_continuous_scale=px.colors.sequential.Teal)
        st.plotly_chart(fig_abs, use_container_width=True)
    with col2:
        st.markdown("##### Tasa Sesión / Acercamiento (Eficiencia)")
        fig_rate = px.bar(summary_df.sort_values('Tasa Sesión / Acercamiento (%)', ascending=False),
                          x=group_by_col, y='Tasa Sesión / Acercamiento (%)', text_auto='.1f',
                          title=f"Eficiencia por {group_by_col}", color="Tasa Sesión / Acercamiento (%)",
                          color_continuous_scale=px.colors.sequential.Mint)
        fig_rate.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
        fig_rate.update_layout(yaxis_range=[0, max(10, summary_df['Tasa Sesión / Acercamiento (%)'].max() * 1.1)])
        st.plotly_chart(fig_rate, use_container_width=True)

def display_time_evolution(df_filtered, time_col, title):
    st.markdown(f"### 📈 {title}")
    if df_filtered.empty or time_col not in df_filtered.columns: return

    df_agg = df_filtered.groupby(time_col).agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()
    df_agg = df_agg.sort_values(by=time_col)

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_agg[time_col], y=df_agg['Acercamientos'], name='Acercamientos', marker_color='#4B8BBE'))
    fig.add_trace(go.Scatter(x=df_agg[time_col], y=df_agg['Sesiones_Agendadas'], name='Sesiones Agendadas', mode='lines+markers', line=dict(color='#30B88A', width=3), yaxis='y2'))

    fig.update_layout(
        title_text=f"Evolución de Acercamientos vs. Sesiones",
        yaxis=dict(title='Volumen de Acercamientos'),
        yaxis2=dict(title='N° de Sesiones', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_data = load_and_process_sdr_data()

if not df_sdr_data.empty:
    filtros = sidebar_filters(df_sdr_data)
    df_sdr_filtered = apply_filters(df_sdr_data, filtros)

    if df_sdr_filtered.empty:
        st.warning("No se encontraron datos que coincidan con los filtros seleccionados.")
    else:
        display_kpi_summary(df_sdr_filtered)
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)

        # SECCIÓN DE ANÁLISIS DE SEGUIMIENTO RESTAURADA
        display_follow_up_metrics(df_sdr_filtered)
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)

        display_grouped_breakdown(df_sdr_filtered, "Campaña", "Análisis por Campaña", "📊")
        st.markdown("---")
        display_grouped_breakdown(df_sdr_filtered, "Fuente de la Lista", "Análisis por Fuente de Lista", "📂")
        st.markdown("---")
        display_grouped_breakdown(df_sdr_filtered, "Proceso", "Análisis por Proceso", "⚙️")
        
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        
        display_time_evolution(df_sdr_filtered, 'AñoMes', "Evolución Mensual")
        st.markdown("---")

        with st.expander("Ver tabla de datos detallados del período filtrado"):
            st.dataframe(df_sdr_filtered, hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")

st.markdown("---")
