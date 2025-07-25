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
    y métricas específicas.
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
        "Fecha de Primer Acercamiento": "Fecha_Primer_Acercamiento",
        "Fecha de Primer Respuesta": "Fecha_Primera_Respuesta",
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
    df['Mensajes_Enviados'] = df['Fecha_Primer_Acercamiento'].notna().astype(int)
    df['Respuestas_Iniciales'] = df['Fecha_Primera_Respuesta'].notna().astype(int)
    df['Sesiones_Agendadas'] = df["Sesion Agendada?"].apply(lambda x: 1 if str(x).strip().lower() in ['si', 'sí'] else 0) if "Sesion Agendada?" in df.columns else 0
    df['Necesita_Recontacto'] = df['Fecha_Recontacto'].notna().astype(int)

    df['Año'] = df['Fecha'].dt.year
    df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
    
    meses_espanol = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    df['AñoMes'] = df['Fecha'].dt.month.map(meses_espanol) + ' ' + df['Fecha'].dt.year.astype(str)

    # --- CAMBIO AQUÍ: Se elimina "Industria" de la lista de limpieza ---
    for col in ["Fuente de la Lista", "Campaña", "Proceso"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"

    return df.sort_values(by='Fecha', ascending=False)

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

# --- CAMBIO AQUÍ: Se define una función callback para limpiar los filtros ---
# Esta es la forma más robusta de manejar acciones de botones en Streamlit.
def clear_all_filters():
    """Resetea todos los widgets a su estado por defecto."""
    
    # Resetea el selector de modo de fecha al primer item ("Rango de Fechas")
    st.session_state.date_filter_mode = "Rango de Fechas"
    
    # Resetea el multiselect de meses a una lista vacía
    st.session_state.month_select = []

    # Lista de filtros de prospección (sin "Industria")
    prospecting_cols = ["Campaña", "Fuente de la Lista", "Proceso"]
    for col in prospecting_cols:
        key = f"filter_{col.lower().replace(' ', '_')}"
        # Resetea cada multiselect a su valor por defecto
        st.session_state[key] = ["– Todos –"]

    # Para los selectores de fecha, es mejor eliminarlos de la sesión
    # para que se recalculen con las fechas min/max del dataframe en la recarga.
    if "start_date" in st.session_state:
        del st.session_state.start_date
    if "end_date" in st.session_state:
        del st.session_state.end_date

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
            meses_disponibles = df.sort_values('Fecha', ascending=False)['AñoMes'].unique().tolist()
            selected_months = st.sidebar.multiselect("Selecciona el/los mes(es):", meses_disponibles, key="month_select")

    other_filters = {}
    st.sidebar.subheader("🔎 Por Estrategia de Prospección")
    
    # --- CAMBIO AQUÍ: Se elimina "Industria" de la lista de filtros ---
    prospecting_cols = ["Campaña", "Fuente de la Lista", "Proceso"]
    for dim_col in prospecting_cols:
        if dim_col in df.columns and df[dim_col].nunique() > 1:
            opciones = ["– Todos –"] + sorted(df[dim_col].unique().tolist())
            filtro_key = f"filter_{dim_col.lower().replace(' ', '_')}"
            other_filters[dim_col] = st.sidebar.multiselect(dim_col, opciones, default=["– Todos –"], key=filtro_key)

    # --- CAMBIO AQUÍ: El botón ahora llama a la función callback "on_click" ---
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_all_filters, use_container_width=True)

    return filter_mode, start_date, end_date, selected_months, other_filters

def apply_filters(df, filter_mode, start_date, end_date, selected_months, other_filters):
    df_f = df.copy()
    
    if filter_mode == "Rango de Fechas":
        if start_date and end_date:
            if start_date > end_date:
                st.sidebar.error("La fecha inicial no puede ser posterior a la fecha final.")
                return pd.DataFrame()
            df_f = df_f[(df_f['Fecha'].dt.date >= start_date) & (df_f['Fecha'].dt.date <= end_date)]
    elif filter_mode == "Mes(es) Específico(s)":
        if selected_months:
            df_f = df_f[df_f['AñoMes'].isin(selected_months)]

    for col, values in other_filters.items():
        if values and "– Todos –" not in values:
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

    df_temp = df_filtered.copy()
    df_temp['FechaRef'] = pd.to_datetime(df_temp['Fecha'].dt.strftime('%Y-%m-01'))
    
    df_agg = df_temp.groupby('FechaRef').agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()
    
    label_map = df_temp[['FechaRef', 'AñoMes']].drop_duplicates()
    df_agg = pd.merge(df_agg, label_map, on='FechaRef')
    df_agg = df_agg.sort_values(by='FechaRef')

    fig = go.Figure()
    fig.add_trace(go.Bar(x=df_agg['AñoMes'], y=df_agg['Acercamientos'], name='Acercamientos', marker_color='#4B8BBE'))
    fig.add_trace(go.Scatter(x=df_agg['AñoMes'], y=df_agg['Sesiones_Agendadas'], name='Sesiones Agendadas', mode='lines+markers', line=dict(color='#30B88A', width=3), yaxis='y2'))

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
    filter_mode, start_date, end_date, selected_months, other_filters = sidebar_filters(df_sdr_data)
    
    df_sdr_filtered = apply_filters(df_sdr_data, filter_mode, start_date, end_date, selected_months, other_filters)

    if df_sdr_filtered.empty:
        st.warning("No se encontraron datos que coincidan con los filtros seleccionados.")
    else:
        display_kpi_summary(df_sdr_filtered)
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)

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
st.info("Plataforma de análisis de KPIs de SDR realizada por Johnsito ✨ 😊")
