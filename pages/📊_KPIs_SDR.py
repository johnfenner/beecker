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
    y métricas de velocidad.
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

    date_columns_to_process = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha",
        "Fecha de Generacion (no aplica para zoom info)": "Fecha_Generacion",
        "Fecha de Primer Acercamiento": "Fecha_Primer_Acercamiento",
        "Fecha de Primer Respuesta": "Fecha_Primera_Respuesta",
        "Fecha Agendamiento": "Fecha_Agendamiento",
        "Fecha De Recontacto": "Fecha_Recontacto"
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

    df['Acercamientos'] = df['Fecha'].notna().astype(int)
    df['Respuestas_Iniciales'] = df['Fecha_Primera_Respuesta'].notna().astype(int)
    df['Sesiones_Agendadas'] = df["Sesion Agendada?"].apply(lambda x: 1 if str(x).strip().lower() in ['si', 'sí'] else 0) if "Sesion Agendada?" in df.columns else 0
    df['Necesita_Recontacto'] = df['Fecha_Recontacto'].notna().astype(int)
    
    # --- CÁLCULO DE MÉTRICAS DE VELOCIDAD CON CORRECCIÓN DE ERRORES ---
    if 'Fecha_Generacion' in df.columns:
        df['Dias_Gen_a_Contacto'] = (df['Fecha'] - df['Fecha_Generacion']).dt.days
        df['Dias_Gen_a_Contacto'] = df['Dias_Gen_a_Contacto'].clip(lower=0) # Evita días negativos
    if 'Fecha_Primera_Respuesta' in df.columns:
        df['Dias_Contacto_a_Rpta'] = (df['Fecha_Primera_Respuesta'] - df['Fecha']).dt.days
        df['Dias_Contacto_a_Rpta'] = df['Dias_Contacto_a_Rpta'].clip(lower=0)
    if 'Fecha_Agendamiento' in df.columns and 'Fecha_Primera_Respuesta' in df.columns:
        df['Dias_Rpta_a_Agenda'] = (df['Fecha_Agendamiento'] - df['Fecha_Primera_Respuesta']).dt.days
        df['Dias_Rpta_a_Agenda'] = df['Dias_Rpta_a_Agenda'].clip(lower=0)

    df['Año'] = df['Fecha'].dt.year
    df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')

    # --- SIMPLIFICADO: Se limpia solo las columnas necesarias para los filtros y gráficos ---
    for col in ["Fuente de la Lista", "Campaña", "Proceso", "Industria", "Pais", "Puesto"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"

    return df.sort_values(by='Fecha', ascending=False)

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

def clear_all_filters():
    st.session_state.date_filter_mode = "Rango de Fechas"
    st.session_state.month_select = []
    
    prospecting_cols = ["Campaña", "Fuente de la Lista", "Proceso"]
    for col in prospecting_cols:
        key = f"filter_{col.lower().replace(' ', '_')}"
        if key in st.session_state:
            st.session_state[key] = ["– Todos –"]

    if "start_date" in st.session_state: del st.session_state.start_date
    if "end_date" in st.session_state: del st.session_state.end_date

# --- COMPONENTES VISUALES ---

def sidebar_filters(df):
    st.sidebar.header("🔍 Filtros de Análisis")
    if df.empty:
        st.sidebar.warning("No hay datos para filtrar.")
        return None, None, None, None, {}

    st.sidebar.subheader("📅 Filtrar por Fecha")
    filter_mode = st.sidebar.radio(
        "Elige cómo filtrar por fecha:",
        ("Rango de Fechas", "Mes(es) Específico(s)"),
        key="date_filter_mode",
        horizontal=True
    )

    start_date, end_date, selected_months = None, None, None

    if filter_mode == "Rango de Fechas":
        min_date, max_date = df['Fecha'].min().date(), df['Fecha'].max().date()
        col1, col2 = st.sidebar.columns(2)
        with col1:
            start_date = st.date_input("Fecha Inicial", value=min_date, min_value=min_date, max_value=max_date, key="start_date")
        with col2:
            end_date = st.date_input("Fecha Final", value=max_date, min_value=start_date, max_value=max_date, key="end_date")
    else:
        if 'AñoMes' in df.columns:
            meses_disponibles = sorted(df['AñoMes'].unique(), reverse=True)
            selected_months = st.sidebar.multiselect("Selecciona el/los mes(es):", meses_disponibles, key="month_select")

    other_filters = {}
    st.sidebar.subheader("🔎 Por Estrategia de Prospección")
    
    prospecting_cols = ["Campaña", "Fuente de la Lista", "Proceso"]
    for dim_col in prospecting_cols:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtro_key = f"filter_{dim_col.lower().replace(' ', '_')}"
            other_filters[dim_col] = st.sidebar.multiselect(dim_col, opciones, default=["– Todos –"], key=filtro_key)

    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_all_filters, use_container_width=True)

    return filter_mode, start_date, end_date, selected_months, other_filters

def apply_filters(df, filter_mode, start_date, end_date, selected_months, other_filters):
    df_f = df.copy()
    
    if filter_mode == "Rango de Fechas":
        if start_date and end_date:
            df_f = df_f[(df_f['Fecha'].dt.date >= start_date) & (df_f['Fecha'].dt.date <= end_date)]
    elif filter_mode == "Mes(es) Específico(s)":
        if selected_months:
            df_f = df_f[df_f['AñoMes'].isin(selected_months)]

    for col, values in other_filters.items():
        if values and "– Todos –" not in values:
            df_f = df_f[df_f[col].isin(values)]
    return df_f

def display_kpi_summary(df_filtered):
    st.markdown("### 🧮 Resumen de KPIs (Periodo Filtrado)")
    total_acercamientos = int(df_filtered['Acercamientos'].sum())
    total_respuestas = int(df_filtered['Respuestas_Iniciales'].sum())
    total_sesiones = int(df_filtered['Sesiones_Agendadas'].sum())

    tasa_resp_vs_acerc = calculate_rate(total_respuestas, total_acercamientos)
    tasa_sesion_vs_resp = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesion_global = calculate_rate(total_sesiones, total_acercamientos)

    col1, col2, col3 = st.columns(3)
    col1.metric("🚀 Total Acercamientos", f"{total_acercamientos:,}")
    col2.metric("💬 Total Respuestas", f"{total_respuestas:,}")
    col3.metric("🗓️ Total Sesiones Agendadas", f"{total_sesiones:,}")
    
    st.markdown("##### Tasas de Conversión")
    colA, colB, colC = st.columns(3)
    colA.metric("🗣️ Tasa Respuesta / Acercamiento", f"{tasa_resp_vs_acerc:.1f}%")
    colB.metric("🤝 Tasa Sesión / Respuesta", f"{tasa_sesion_vs_resp:.1f}%")
    colC.metric("🏆 Tasa Sesión / Acercamiento (Global)", f"{tasa_sesion_global:.1f}%")

# --- VISUALIZACIONES SIMPLIFICADAS ---

def display_funnel_and_velocity(df_filtered):
    st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
    st.markdown("### 🏺 Funnel y Velocidad del Proceso")

    # --- CÁLCULOS ---
    total_acercamientos = int(df_filtered['Acercamientos'].sum())
    total_respuestas = int(df_filtered['Respuestas_Iniciales'].sum())
    total_sesiones = int(df_filtered['Sesiones_Agendadas'].sum())
    
    avg_gen_contacto = pd.to_numeric(df_filtered['Dias_Gen_a_Contacto'], errors='coerce').mean()
    avg_contacto_rpta = pd.to_numeric(df_filtered['Dias_Contacto_a_Rpta'], errors='coerce').mean()
    avg_rpta_agenda = pd.to_numeric(df_filtered['Dias_Rpta_a_Agenda'], errors='coerce').mean()

    # --- VISUALIZACIÓN ---
    col1, col2 = st.columns([0.4, 0.6])

    with col1:
        st.markdown("##### Flujo de Conversión")
        if total_acercamientos > 0:
            fig = go.Figure(go.Funnel(
                y=["Acercamientos", "Respuestas", "Sesiones"],
                x=[total_acercamientos, total_respuestas, total_sesiones],
                textposition="inside",
                textinfo="value+percent initial",
                marker={"color": ["#4B8BBE", "#30B88A", "#2E6B5A"]}
            ))
            fig.update_layout(margin=dict(t=30, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay datos para el funnel.")

    with col2:
        st.markdown("##### Tiempos Promedio del Proceso")
        st.write("") # Espacio
        if not pd.isna(avg_gen_contacto):
            st.metric("Lead a 1er Contacto", f"{avg_gen_contacto:.1f} días", help="Tiempo promedio desde que se genera un lead hasta que se le contacta.")
        if not pd.isna(avg_contacto_rpta):
            st.metric("Contacto a 1ra Respuesta", f"{avg_contacto_rpta:.1f} días", help="Tiempo promedio desde el primer contacto hasta recibir la primera respuesta.")
        if not pd.isna(avg_rpta_agenda):
            st.metric("Respuesta a Sesión Agendada", f"{avg_rpta_agenda:.1f} días", help="Tiempo promedio desde la primera respuesta hasta que se agenda la sesión.")

def display_grouped_breakdown(df_filtered, group_by_col, title):
    st.markdown(f"### {title} por `{group_by_col}`")
    
    if group_by_col not in df_filtered.columns or df_filtered[group_by_col].nunique() < 2:
        st.info(f"No hay suficientes datos o diversidad para este análisis.")
        return

    summary_df = df_filtered.groupby(group_by_col).agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    summary_df = summary_df[summary_df['Acercamientos'] > 0]
    summary_df['Tasa_Conversion_Global'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Acercamientos), axis=1)
    
    # Tomamos el Top 10 para no saturar los gráficos
    summary_df = summary_df.nlargest(10, 'Sesiones_Agendadas').sort_values('Sesiones_Agendadas', ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=summary_df['Acercamientos'],
        y=summary_df[group_by_col],
        name='Acercamientos',
        orientation='h',
        marker_color='#4B8BBE'
    ))
    fig.add_trace(go.Bar(
        x=summary_df['Sesiones_Agendadas'],
        y=summary_df[group_by_col],
        name='Sesiones Agendadas',
        orientation='h',
        marker_color='#30B88A'
    ))
    fig.update_layout(
        barmode='group',
        title_text=f"Top 10 por Volumen (Acercamientos vs. Sesiones)",
        yaxis_title=group_by_col,
        xaxis_title="Volumen",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_data = load_and_process_sdr_data()

if not df_sdr_data.empty:
    filter_mode, start_date, end_date, selected_months, other_filters = sidebar_filters(df_sdr_data)
    df_sdr_filtered = apply_filters(df_sdr_data, filter_mode, start_date, end_date, selected_months, other_filters)

    if df_sdr_filtered.empty:
        st.warning("No se encontraron datos que coincidan con los filtros seleccionados.")
    else:
        # 1. Resumen de KPIs (se mantiene)
        display_kpi_summary(df_sdr_filtered)

        # 2. Funnel y Velocidad (Simplificado)
        display_funnel_and_velocity(df_sdr_filtered)
        
        # 3. Desgloses por Dimensiones (Simplificado y sin prospectador)
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        st.markdown("## 🔬 Desglose de Rendimiento por Dimensiones")
        
        tab1, tab2, tab3, tab4 = st.tabs(["Por Campaña", "Por Industria", "Por País", "Por Puesto"])
        
        with tab1:
            display_grouped_breakdown(df_sdr_filtered, "Campaña", "Análisis de Rendimiento")
        with tab2:
            display_grouped_breakdown(df_sdr_filtered, "Industria", "Análisis de Rendimiento")
        with tab3:
            display_grouped_breakdown(df_sdr_filtered, "Pais", "Análisis de Rendimiento")
        with tab4:
            display_grouped_breakdown(df_sdr_filtered, "Puesto", "Análisis de Rendimiento")
            
        # 4. Tabla de datos detallados
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        with st.expander("Ver tabla de datos detallados del período filtrado"):
            cols_to_show = [
                'Empresa', 'Nombre', 'Apellido', 'Puesto', 'Industria', 'Pais', 'Fecha', 
                'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Rpta', 'Dias_Rpta_a_Agenda',
                'Sesiones_Agendadas'
            ]
            existing_cols = [col for col in cols_to_show if col in df_sdr_filtered.columns]
            st.dataframe(df_sdr_filtered[existing_cols], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")

st.markdown("---")
st.info("Plataforma de análisis de KPIs de SDR. ✨")
