# pages/📊_KPIs_SDR.py

import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter

# --- CONFIGURACIÓN DE LA PÁGINA --
st.set_page_config(page_title="Dashboard de Desempeño SDR", layout="wide")
st.title("📊 Dashboard de Desempeño SDR")
st.markdown("Análisis de efectividad y conversión con doble perspectiva: por **Cohorte** y por **Actividad del Período**.")

# --- FUNCIONES DE UTILIDAD ---

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

def calculate_rate(numerator, denominator, round_to=1):
    """Calcula una tasa como porcentaje, manejando la división por cero."""
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- CARGA Y PROCESAMIENTO DE DATOS ---

@st.cache_data(ttl=300)
def load_and_process_sdr_data():
    """
    Carga y procesa datos desde la hoja 'Evelyn'.
    Parsea todas las columnas de fecha clave para permitir un análisis de doble perspectiva.
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

    # CAMBIO: Se elimina 'Fecha De Recontacto' del procesamiento
    date_columns_to_process = {
        "Fecha Primer contacto (Linkedin, correo, llamada, WA)": "Fecha_Contacto_Inicial",
        "Fecha de Primer Respuesta": "Fecha_Primera_Respuesta",
        "Fecha Agendamiento": "Fecha_Sesion_Agendada",
    }
    
    for original_col, new_col in date_columns_to_process.items():
        if original_col in df.columns:
            df[new_col] = pd.to_datetime(df[original_col], dayfirst=True, errors='coerce')
        else:
            df[new_col] = pd.NaT
            st.warning(f"Advertencia: No se encontró la columna '{original_col}'. Las métricas relacionadas pueden ser 0.")

    if "Fecha_Contacto_Inicial" not in df.columns or df["Fecha_Contacto_Inicial"].isnull().all():
        st.error("Columna 'Fecha Primer contacto (...)' no encontrada o vacía. Es esencial para el análisis.")
        return pd.DataFrame()
    
    df.dropna(subset=['Fecha_Contacto_Inicial'], inplace=True)

    # CAMBIO: Se elimina la métrica 'Necesita_Recontacto'
    df['Acercamientos'] = df['Fecha_Contacto_Inicial'].notna()
    df['Respuestas_Iniciales'] = df['Fecha_Primera_Respuesta'].notna()
    df['Sesiones_Agendadas'] = df['Fecha_Sesion_Agendada'].notna() & (df["Sesion Agendada?"].str.strip().str.lower().isin(['si', 'sí']))
    
    df['AñoMes_Contacto'] = df['Fecha_Contacto_Inicial'].dt.strftime('%Y-%m')

    for col in ["Fuente de la Lista", "Campaña", "Proceso", "Industria", "Pais", "Puesto"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"

    return df.sort_values(by='Fecha_Contacto_Inicial', ascending=False)

# --- COMPONENTES DE LA UI Y FILTROS ---

def clear_all_filters():
    """Limpia todos los filtros en el estado de la sesión."""
    st.session_state.start_date = None
    st.session_state.end_date = None
    
    # CAMBIO: Nos aseguramos de que solo limpie el filtro de la lista
    prospecting_cols = ["Fuente de la Lista"]
    for col in prospecting_cols:
        key = f"filter_{col.lower().replace(' ', '_')}"
        if key in st.session_state:
            st.session_state[key] = ["– Todos –"]

def sidebar_filters(df, global_min_date, global_max_date):
    """Renderiza los filtros de la barra lateral con fechas vacías por defecto."""
    st.sidebar.header("🔍 Filtros de Análisis")
    if df.empty:
        st.sidebar.warning("No hay datos para filtrar.")
        return None, None, {}

    st.sidebar.subheader("📅 Filtrar por Fecha")
    col1, col2 = st.sidebar.columns(2)
    with col1:
        start_date = st.date_input("Fecha Inicial", value=None, min_value=global_min_date, max_value=global_max_date, key="start_date", help="Dejar vacío para incluir todo desde el inicio.")
    with col2:
        end_date = st.date_input("Fecha Final", value=None, min_value=start_date if start_date else global_min_date, max_value=global_max_date, key="end_date", help="Dejar vacío para incluir todo hasta el final.")

    other_filters = {}
    st.sidebar.subheader("🔎 Filtrar por Dimensiones")
    
    # CAMBIO: Volvemos a tener solo el filtro que tenías originalmente
    dimension_cols = ["Fuente de la Lista"]
    
    for dim_col in dimension_cols:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtro_key = f"filter_{dim_col.lower().replace(' ', '_')}"
            other_filters[dim_col] = st.sidebar.multiselect(dim_col, opciones, default=["– Todos –"], key=filtro_key)

    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_all_filters, use_container_width=True)

    return start_date, end_date, other_filters

def apply_dimension_filters(df, other_filters):
    """Aplica solo los filtros de dimensiones (no los de fecha)."""
    df_f = df.copy()
    for col, values in other_filters.items():
        if values and "– Todos –" not in values:
            df_f = df_f[df_f[col].isin(values)]
    return df_f

# --- COMPONENTES DE VISUALIZACIÓN --- (Sin cambios en estas funciones)

def display_kpi_summary(total_acercamientos, total_respuestas, total_sesiones):
    st.markdown("### 🧮 Resumen de KPIs Totales (Período Filtrado)")
    kpi_cols = st.columns(3)
    kpi_cols[0].metric("🚀 Total Acercamientos", f"{total_acercamientos:,}")
    kpi_cols[1].metric("💬 Total Respuestas Iniciales", f"{total_respuestas:,}")
    kpi_cols[2].metric("🗓️ Total Sesiones Agendadas", f"{total_sesiones:,}")

    st.markdown("---")
    st.markdown("#### 📊 Tasas de Conversión")
    tasa_resp_vs_acerc = calculate_rate(total_respuestas, total_acercamientos)
    tasa_sesion_vs_resp = calculate_rate(total_sesiones, total_respuestas)
    tasa_sesion_global = calculate_rate(total_sesiones, total_acercamientos)

    rate_cols = st.columns(3)
    rate_cols[0].metric("🗣️ Tasa Respuesta / Acercamiento", f"{tasa_resp_vs_acerc:.1f}%", help="De todos los acercamientos, qué % generó una respuesta.")
    rate_cols[1].metric("🤝 Tasa Sesión / Respuesta", f"{tasa_sesion_vs_resp:.1f}%", help="De todas las respuestas, qué % condujo a una sesión.")
    rate_cols[2].metric("🏆 Tasa Sesión / Acercamiento (Global)", f"{tasa_sesion_global:.1f}%", help="Eficiencia total del proceso: (Sesiones Agendadas / Acercamientos)")

def display_grouped_breakdown(df_to_analyze, group_by_col, perspective, start_date, end_date):
    st.markdown(f"#### Análisis por `{group_by_col}`")
    if group_by_col not in df_to_analyze.columns or df_to_analyze[group_by_col].nunique() < 2:
        st.info(f"No hay suficientes datos o diversidad para analizar por '{group_by_col}'.")
        return

    start_dt, end_dt = pd.to_datetime(start_date), pd.to_datetime(end_date) + pd.Timedelta(days=1)

    if perspective == 'Fecha de Contacto Inicial (Cohorte)':
        df_period = df_to_analyze[df_to_analyze['Fecha_Contacto_Inicial'].between(start_dt, end_dt)]
        summary_df = df_period.groupby(group_by_col).agg(
            Acercamientos=('Acercamientos', 'sum'),
            Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
        ).reset_index()
    else:
        summary_df = df_to_analyze.groupby(group_by_col).agg(
            Acercamientos=('Fecha_Contacto_Inicial', lambda x: x.between(start_dt, end_dt).sum()),
            Sesiones_Agendadas=('Fecha_Sesion_Agendada', lambda x: x.between(start_dt, end_dt).sum())
        ).reset_index()

    summary_df = summary_df.astype({'Acercamientos': 'int', 'Sesiones_Agendadas': 'int'})
    summary_df = summary_df[summary_df['Acercamientos'] > 0]
    
    if summary_df.empty:
        st.info(f"No hay datos de acercamientos para '{group_by_col}' en el período seleccionado.")
        return

    summary_df['Tasa_Conversion'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Acercamientos), axis=1)
    
    col1, col2 = st.columns([0.5, 0.5])
    with col1:
        st.markdown("##### Top 10 por Volumen de Sesiones")
        top_10_volumen = summary_df.nlargest(10, 'Sesiones_Agendadas')
        st.dataframe(top_10_volumen.style.format({'Tasa_Conversion': '{:.1f}%'}), hide_index=True, use_container_width=True)
    with col2:
        st.markdown("##### Top 10 por Eficiencia (Tasa de Conversión)")
        top_10_eficiencia = summary_df[summary_df['Sesiones_Agendadas'] > 0].nlargest(10, 'Tasa_Conversion')
        if top_10_eficiencia.empty:
            st.info("No hay datos para mostrar el top de eficiencia.")
            return
        fig = px.bar(top_10_eficiencia.sort_values('Tasa_Conversion', ascending=True),
                     x='Tasa_Conversion', y=group_by_col, orientation='h', text='Tasa_Conversion',
                     title="Tasa de Sesión Agendada / Acercamiento")
        fig.update_traces(texttemplate='%{x:.1f}%', textposition='outside', marker_color='#30B88A')
        fig.update_layout(yaxis_title=None, xaxis_title="Tasa de Conversión (%)", showlegend=False,
                          margin=dict(t=30, b=10, l=10, r=10), height=400)
        st.plotly_chart(fig, use_container_width=True)

# --- FLUJO PRINCIPAL DE LA PÁGINA ---
df_sdr_data = load_and_process_sdr_data()

if df_sdr_data.empty:
    st.error("No se pudieron cargar o procesar los datos para el dashboard.")
else:
    st.sidebar.subheader("🎯 Perspectiva de Análisis")
    analysis_perspective = st.sidebar.radio(
        "Ver métricas basadas en:",
        ('Fecha de Contacto Inicial (Cohorte)', 'Fecha del Evento (Actividad del Período)'),
        key='analysis_perspective',
        help="""
        - **Cohorte:** Analiza el resultado final de los prospectos contactados en el rango de fechas.
        - **Actividad del Período:** Muestra toda la actividad (contactos, respuestas, sesiones) que ocurrió en el rango de fechas.
        """
    )
    
    # CAMBIO: Se elimina 'Fecha_Recontacto' de la lista para el rango global
    date_cols_for_range = ['Fecha_Contacto_Inicial', 'Fecha_Primera_Respuesta', 'Fecha_Sesion_Agendada']
    existing_date_cols = [col for col in date_cols_for_range if col in df_sdr_data.columns and df_sdr_data[col].notna().any()]
    
    if not existing_date_cols:
        st.error("No se encontraron columnas de fecha válidas para establecer el rango del dashboard.")
    else:
        global_min_date = df_sdr_data[existing_date_cols].min().min().date()
        global_max_date = df_sdr_data[existing_date_cols].max().max().date()

        start_date, end_date, other_filters = sidebar_filters(df_sdr_data, global_min_date, global_max_date)
        
        # CAMBIO: Si las fechas están vacías (None), usamos el rango global para los cálculos internos
        start_date_filter = start_date if start_date is not None else global_min_date
        end_date_filter = end_date if end_date is not None else global_max_date

        df_filtered_by_dims = apply_dimension_filters(df_sdr_data, other_filters)
        
        start_dt = pd.to_datetime(start_date_filter)
        end_dt = pd.to_datetime(end_date_filter) + pd.Timedelta(days=1)

        if analysis_perspective == 'Fecha de Contacto Inicial (Cohorte)':
            df_final = df_filtered_by_dims[df_filtered_by_dims['Fecha_Contacto_Inicial'].between(start_dt, end_dt)]
            if df_final.empty:
                st.warning("No se encontraron datos de contacto inicial que coincidan con los filtros seleccionados.")
            total_acercamientos = int(df_final['Acercamientos'].sum())
            total_respuestas = int(df_final['Respuestas_Iniciales'].sum())
            total_sesiones = int(df_final['Sesiones_Agendadas'].sum())
        else: # 'Fecha del Evento (Actividad del Período)'
            df_final = df_filtered_by_dims
            total_acercamientos = df_final[df_final['Fecha_Contacto_Inicial'].between(start_dt, end_dt)].shape[0]
            total_respuestas = df_final[df_final['Fecha_Primera_Respuesta'].between(start_dt, end_dt)].shape[0]
            total_sesiones = df_final[df_final['Fecha_Sesion_Agendada'].between(start_dt, end_dt)].shape[0]

        if 'total_acercamientos' in locals():
            display_kpi_summary(total_acercamientos, total_respuestas, total_sesiones)
            st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
            
            st.markdown("## 🔬 Desglose de Rendimiento por Dimensiones")
            tabs_list = ["Campaña", "Proceso", "Industria", "Pais", "Puesto", "Fuente de la Lista"]
            tabs = st.tabs([f"📊 Por {t}" for t in tabs_list])
            
            for i, dimension in enumerate(tabs_list):
                with tabs[i]:
                    display_grouped_breakdown(df_filtered_by_dims, dimension, analysis_perspective, start_date_filter, end_date_filter)

            st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
            with st.expander("Ver tabla de datos detallados del período filtrado"):
                st.dataframe(df_final, hide_index=True)
        else:
            st.info("Selecciona un rango de fechas y filtros para ver los resultados.")

st.markdown("---")
