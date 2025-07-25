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
    Carga y procesa datos desde la hoja 'Evelyn', utilizando la presencia de fechas
    en columnas clave para contar los eventos en cada etapa del embudo de conversión.
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

    # --- Creación del Embudo de 4 Etapas basado en la existencia de fechas ---
    
    date_columns_to_process = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha_Acercamiento_Inicial",
        "Fecha de Primer Acercamiento": "Fecha_Mensaje_Enviado",
        "Fecha de Primer Respuesta": "Fecha_Respuesta_Inicial"
    }
    
    for original_col, new_col in date_columns_to_process.items():
        if original_col in df.columns:
            df[new_col] = pd.to_datetime(df[original_col], format='%d/%m/%Y', errors='coerce')
        else:
            df[new_col] = pd.NaT

    if "Fecha_Acercamiento_Inicial" not in df.columns or df["Fecha_Acercamiento_Inicial"].isnull().all():
        st.error("Columna 'Fecha Primer contacto (...)' no encontrada o vacía. Es esencial para el análisis.")
        return pd.DataFrame()
    
    df.rename(columns={'Fecha_Acercamiento_Inicial': 'Fecha'}, inplace=True)
    df.dropna(subset=['Fecha'], inplace=True)

    # Contadores basados en la existencia de fechas o valores 'si'
    df['Acercamientos'] = df['Fecha'].notna().astype(int)
    df['Mensajes_Enviados'] = df['Fecha_Mensaje_Enviado'].notna().astype(int)
    df['Respuestas_Iniciales'] = df['Fecha_Respuesta_Inicial'].notna().astype(int)
    df['Sesiones_Agendadas'] = df["Sesion Agendada?"].apply(lambda x: 1 if str(x).strip().lower() in ['si', 'sí'] else 0) if "Sesion Agendada?" in df.columns else 0

    # Dimensiones de tiempo
    df['Año'] = df['Fecha'].dt.year
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
        return {}, None, None

    filtros = {}
    st.sidebar.subheader("📅 Por Fecha de Primer Contacto")
    min_date, max_date = df['Fecha'].min().date(), df['Fecha'].max().date()
    start_date, end_date = st.sidebar.date_input("Rango de Fechas", [min_date, max_date], min_value=min_date, max_value=max_date)

    st.sidebar.subheader("🔎 Por Estrategia de Prospección")
    for dim_col in ["Campaña", "Fuente de la Lista", "Proceso", "Industria"]:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtros[dim_col] = st.sidebar.multiselect(dim_col, opciones, default=["– Todos –"])

    if st.sidebar.button("🧹 Limpiar Todos los Filtros", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    return filtros, start_date, end_date

def apply_filters(df, filtros, start_date, end_date):
    df_f = df.copy()
    if start_date and end_date:
        df_f = df_f[(df_f['Fecha'].dt.date >= start_date) & (df_f['Fecha'].dt.date <= end_date)]

    for col, values in filtros.items():
        if values and "– Todos –" not in values:
            df_f = df_f[df_f[col].isin(values)]
    return df_f

def display_kpi_summary(df_filtered):
    st.markdown("### 🧮 Resumen del Embudo (Periodo Filtrado)")

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
    st.markdown("#### Tasas de Conversión del Proceso")

    tasa_mens_vs_acerc = calculate_rate(total_mensajes, total_acercamientos)
    tasa_resp_vs_msj = calculate_rate(total_respuestas, total_mensajes)
    tasa_sesion_vs_resp = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesion_global = calculate_rate(total_sesiones, total_acercamientos)

    rate_cols = st.columns(4)
    rate_cols[0].metric("Tasa de Mensajes / Acercamiento", f"{tasa_mens_vs_acerc:.1f}%")
    rate_cols[1].metric("Tasa de Respuesta / Mensaje", f"{tasa_resp_vs_msj:.1f}%")
    rate_cols[2].metric("Tasa de Sesión / Respuesta", f"{tasa_sesion_vs_resp:.1f}%")
    rate_cols[3].metric("Tasa de Éxito Global", f"{tasa_sesion_global:.1f}%", help="Eficiencia total: (Sesiones / Acercamientos)")

def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    st.markdown(f"### {chart_icon} {title_prefix}")
    if group_by_col not in df_filtered.columns or df_filtered.empty or df_filtered[group_by_col].nunique() <= 1:
        st.info(f"No hay suficientes datos o diversidad en la columna '{group_by_col}' para generar un desglose.")
        return

    summary_df = df_filtered.groupby(group_by_col).agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    summary_df['Tasa de Éxito Global (%)'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Acercamientos), axis=1)

    st.markdown("##### Tabla de Rendimiento")
    st.dataframe(summary_df[summary_df['Acercamientos'] > 0].style.format({'Tasa de Éxito Global (%)': '{:.1f}%'}), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Sesiones Agendadas (Volumen)")
        fig_abs = px.bar(summary_df.sort_values('Sesiones_Agendadas', ascending=False),
                         x=group_by_col, y='Sesiones_Agendadas', text_auto=True,
                         title=f"Volumen de Sesiones por {group_by_col}", color="Sesiones_Agendadas",
                         color_continuous_scale=px.colors.sequential.Teal)
        st.plotly_chart(fig_abs, use_container_width=True)
    with col2:
        st.markdown("##### Tasa de Éxito Global (Eficiencia)")
        fig_rate = px.bar(summary_df.sort_values('Tasa de Éxito Global (%)', ascending=False),
                          x=group_by_col, y='Tasa de Éxito Global (%)', text_auto='.1f',
                          title=f"Eficiencia por {group_by_col}", color="Tasa de Éxito Global (%)",
                          color_continuous_scale=px.colors.sequential.Mint)
        fig_rate.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
        fig_rate.update_layout(yaxis_range=[0, max(10, summary_df['Tasa de Éxito Global (%)'].max() * 1.1)])
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
    filtros, start_date, end_date = sidebar_filters(df_sdr_data)
    df_sdr_filtered = apply_filters(df_sdr_data, filtros, start_date, end_date)

    if df_sdr_filtered.empty:
        st.warning("No se encontraron datos que coincidan con los filtros seleccionados.")
    else:
        display_kpi_summary(df_sdr_filtered)
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
st.info("Plataforma de análisis de KPIs de SDR realizada por Johnsito ✨ 😊")
