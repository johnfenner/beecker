# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
from collections import Counter

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Dashboard de KPIs SDR", layout="wide")
st.title("📊 Dashboard de KPIs de Prospección (SDR)")
st.markdown("Análisis de métricas y tasas de conversión para el equipo de SDR, basado en la hoja de trabajo 'Evelyn'.")

# --- FUNCIONES DE CARGA Y PROCESAMIENTO DE DATOS ---

def make_unique(headers_list):
    """Garantiza que los encabezados de columna sean únicos añadiendo sufijos si es necesario."""
    counts = Counter()
    new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped:
            h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1:
            new_headers.append(h_stripped)
        else:
            new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

@st.cache_data(ttl=300)
def load_and_process_sdr_data():
    """
    Carga y procesa datos desde la hoja 'Evelyn' del Google Sheet principal.
    Interpreta las columnas específicas de SDR y las transforma en un embudo de conversión
    con métricas claras para el análisis.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        client = gspread.service_account_from_dict(creds_dict)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet("Evelyn")
        values = sheet.get_all_values()

        if len(values) < 2:
            st.warning("La hoja de cálculo 'Evelyn' está vacía o solo tiene encabezados.")
            return pd.DataFrame()

        headers = make_unique(values[0])
        df = pd.DataFrame(values[1:], columns=headers)

    except gspread.exceptions.WorksheetNotFound:
        st.error("Error Crítico: No se encontró la hoja 'Evelyn' en el Google Sheet principal. Verifica el nombre.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"No se pudo cargar la hoja 'Evelyn'. Error: {e}")
        return pd.DataFrame()

    # --- Mapeo y Limpieza de Columnas Clave ---
    column_mapping = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha",
        "¿Quién Prospecto?": "Analista",
        "Pais": "Región",
        "Respuesta Primer contacto": "Respuesta_Inicial",
        "Sesion Agendada?": "Sesion_Agendada"
    }
    df.rename(columns=column_mapping, inplace=True)

    # La fecha del primer contacto es la base de todo el embudo
    if "Fecha" not in df.columns or df["Fecha"].eq('').all():
        st.error("Error crítico: La columna 'Fecha Primer contacto (...)' es indispensable y no se encontró o está vacía.")
        return pd.DataFrame()

    df["Fecha"] = pd.to_datetime(df["Fecha"], format='%d/%m/%Y', errors='coerce')
    df.dropna(subset=['Fecha'], inplace=True)
    df['Año'] = df['Fecha'].dt.year
    df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
    df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')

    # --- Definición del Embudo de Conversión de SDR ---
    # 1. Contactos: Cada fila con fecha válida es un contacto.
    df['Contactos'] = 1

    # 2. Respuestas y Sesiones: Convertir 'si'/'no'/vacío a 1/0 para poder sumar.
    for col, new_col_name in [("Respuesta_Inicial", "Respuestas"), ("Sesion_Agendada", "Sesiones_Agendadas")]:
        if col in df.columns:
            df[new_col_name] = df[col].apply(lambda x: 1 if str(x).strip().lower() in ['si', 'sí', 'yes', 'true', '1'] else 0)
        else:
            st.warning(f"Columna de conversión '{col}' no encontrada. Se creará con ceros.")
            df[new_col_name] = 0

    # Limpieza de columnas de filtro (Dimensiones)
    for col in ["Analista", "Región"]:
        if col not in df.columns: df[col] = "N/D"
        df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")

    return df.sort_values(by='Fecha', ascending=False)

def calculate_rate(numerator, denominator, round_to=1):
    """Calcula una tasa como porcentaje, manejando la división por cero."""
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- Funciones Visuales (Inspiradas en KPIs.py pero adaptadas a las nuevas métricas) ---

def sidebar_filters(df):
    """Muestra los filtros en la barra lateral, poblados con los datos de SDR."""
    st.sidebar.header("🔍 Filtros de SDR")
    if df.empty or 'Fecha' not in df.columns:
        st.sidebar.warning("No hay datos para filtrar.")
        return ["– Todos –"], ["– Todos –"], "– Todos –", ["– Todos –"], None, None

    # Lógica de filtros (similar a la original pero aplicada a los datos de SDR)
    opciones_analista = ["– Todos –"] + sorted(df['Analista'].unique().tolist())
    opciones_region = ["– Todos –"] + sorted(df['Región'].unique().tolist())
    opciones_año = ["– Todos –"] + sorted(df['Año'].unique().tolist(), reverse=True)

    selected_analistas = st.sidebar.multiselect("Analista", opciones_analista, default=["– Todos –"])
    selected_regiones = st.sidebar.multiselect("Región", opciones_region, default=["– Todos –"])
    selected_año = st.sidebar.selectbox("Año", opciones_año, index=0)

    semanas_disponibles = ["– Todas –"]
    if selected_año != "– Todos –":
        semanas_disponibles.extend(sorted(df[df['Año'] == selected_año]['NumSemana'].unique().tolist()))
    selected_semanas = st.sidebar.multiselect("Semanas", semanas_disponibles, default=["– Todas –"])

    min_date = df['Fecha'].min().date()
    max_date = df['Fecha'].max().date()
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Desde", min_date, min_value=min_date, max_value=max_date)
    end_date = col2.date_input("Hasta", max_date, min_value=min_date, max_value=max_date)

    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True):
        st.session_state.clear()
        st.rerun()

    return selected_analistas, selected_regiones, selected_año, selected_semanas, start_date, end_date

def apply_filters(df, analistas, regiones, año, semanas, start_date, end_date):
    """Aplica los filtros seleccionados al DataFrame."""
    df_f = df.copy()
    if "– Todos –" not in analistas:
        df_f = df_f[df_f['Analista'].isin(analistas)]
    if "– Todos –" not in regiones:
        df_f = df_f[df_f['Región'].isin(regiones)]
    if año != "– Todos –":
        df_f = df_f[df_f['Año'] == año]
    if "– Todas –" not in semanas:
        df_f = df_f[df_f['NumSemana'].isin(semanas)]
    if start_date and end_date:
        df_f = df_f[(df_f['Fecha'].dt.date >= start_date) & (df_f['Fecha'].dt.date <= end_date)]
    return df_f

def display_kpi_summary(df_filtered):
    """Muestra el resumen de KPIs y las tasas de conversión clave."""
    st.markdown("### 🧮 Resumen de KPIs Totales (Periodo Filtrado)")

    total_contactos = int(df_filtered['Contactos'].sum())
    total_respuestas = int(df_filtered['Respuestas'].sum())
    total_sesiones = int(df_filtered['Sesiones_Agendadas'].sum())

    kpi_cols = st.columns(3)
    kpi_cols[0].metric("🚀 Total Contactos Realizados", f"{total_contactos:,}")
    kpi_cols[1].metric("💬 Total Respuestas Recibidas", f"{total_respuestas:,}")
    kpi_cols[2].metric("🗓️ Total Sesiones Agendadas", f"{total_sesiones:,}")

    st.markdown("---")
    st.markdown("#### Tasas de Conversión del Embudo")

    tasa_resp_vs_contacto = calculate_rate(total_respuestas, total_contactos)
    tasa_sesion_vs_respuesta = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesion_global = calculate_rate(total_sesiones, total_contactos)

    rate_cols = st.columns(3)
    rate_cols[0].metric("🗣️ Tasa de Respuesta", f"{tasa_resp_vs_contacto:.1f}%", help="Eficacia del primer contacto: (Respuestas / Contactos)")
    rate_cols[1].metric("🤝 Tasa de Cierre por Respuesta", f"{tasa_sesion_vs_respuesta:.1f}%", help="Habilidad para convertir interés en reuniones: (Sesiones / Respuestas)")
    rate_cols[2].metric("🏆 Tasa de Éxito Global", f"{tasa_sesion_global:.1f}%", help="Eficiencia general del proceso: (Sesiones / Contactos)")

def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    """Muestra KPIs y gráficos desglosados por una dimensión (Analista o Región)."""
    st.markdown(f"### {chart_icon} {title_prefix}")
    if group_by_col not in df_filtered.columns or df_filtered.empty:
        st.warning(f"No hay datos para el desglose por {group_by_col}.")
        return

    summary_df = df_filtered.groupby(group_by_col).agg(
        Contactos=('Contactos', 'sum'),
        Respuestas=('Respuestas', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    summary_df['Tasa de Respuesta (%)'] = summary_df.apply(lambda r: calculate_rate(r.Respuestas, r.Contactos), axis=1)
    summary_df['Tasa de Agendamiento Global (%)'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Contactos), axis=1)

    st.markdown("##### Tabla de Rendimiento")
    st.dataframe(summary_df.style.format({
        'Tasa de Respuesta (%)': '{:.1f}%',
        'Tasa de Agendamiento Global (%)': '{:.1f}%'
    }), use_container_width=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Sesiones Agendadas (Volumen)")
        fig_abs = px.bar(summary_df.sort_values('Sesiones_Agendadas', ascending=False),
                         x=group_by_col, y='Sesiones_Agendadas', text_auto=True,
                         title=f"Sesiones por {group_by_col}")
        st.plotly_chart(fig_abs, use_container_width=True)
    with col2:
        st.markdown("##### Tasa de Éxito Global (Eficiencia)")
        fig_rate = px.bar(summary_df.sort_values('Tasa de Agendamiento Global (%)', ascending=False),
                          x=group_by_col, y='Tasa de Agendamiento Global (%)', text_auto='.1f',
                          title=f"Tasa de Éxito por {group_by_col}")
        fig_rate.update_traces(texttemplate='%{y:.1f}%')
        st.plotly_chart(fig_rate, use_container_width=True)

def display_time_evolution(df_filtered, time_col, title):
    """Muestra la evolución temporal de las métricas clave."""
    st.markdown(f"### 📈 {title}")
    if df_filtered.empty or time_col not in df_filtered.columns: return

    df_agg = df_filtered.groupby(time_col).agg(
        Contactos=('Contactos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    df_agg = df_agg.sort_values(by=time_col)

    fig = px.bar(df_agg, x=time_col, y='Contactos', title=title)
    fig.add_scatter(x=df_agg[time_col], y=df_agg['Sesiones_Agendadas'], mode='lines+markers', name='Sesiones Agendadas', yaxis='y2')

    fig.update_layout(
        yaxis=dict(title='Volumen de Contactos'),
        yaxis2=dict(title='Sesiones Agendadas', overlaying='y', side='right', showgrid=False),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_data = load_and_process_sdr_data()

if not df_sdr_data.empty:
    (
        selected_analistas, selected_regiones, selected_año,
        selected_semanas, start_date, end_date
    ) = sidebar_filters(df_sdr_data)

    df_sdr_filtered = apply_filters(
        df_sdr_data, selected_analistas, selected_regiones,
        selected_año, selected_semanas, start_date, end_date
    )

    if df_sdr_filtered.empty:
        st.warning("No se encontraron datos para los filtros seleccionados.")
    else:
        # --- RENDERIZADO DEL DASHBOARD ---
        display_kpi_summary(df_sdr_filtered)
        st.markdown("---")

        col_breakdown1, col_breakdown2 = st.columns(2)
        with col_breakdown1:
            display_grouped_breakdown(df_sdr_filtered, "Analista", "Desglose por Analista", "🧑‍💻")
        with col_breakdown2:
            display_grouped_breakdown(df_sdr_filtered, "Región", "Desglose por Región", "🌎")
        st.markdown("---")

        display_time_evolution(df_sdr_filtered, 'AñoMes', "Evolución Mensual")
        st.markdown("---")

        with st.expander("Ver tabla de datos detallados del período seleccionado"):
            st.dataframe(df_sdr_filtered, hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")

st.markdown("---")

