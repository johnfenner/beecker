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
    Carga y procesa datos desde la hoja 'Evelyn', creando un embudo de conversión,
    métricas de velocidad y dimensiones de análisis enriquecidas.
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
        "Fecha Sesion": "Fecha_Sesion",
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
    
    if 'Fecha_Generacion' in df.columns:
        df['Dias_Gen_a_Contacto'] = (df['Fecha'] - df['Fecha_Generacion']).dt.days
    if 'Fecha_Primera_Respuesta' in df.columns:
        df['Dias_Contacto_a_Rpta'] = (df['Fecha_Primera_Respuesta'] - df['Fecha']).dt.days
    if 'Fecha_Agendamiento' in df.columns and 'Fecha_Primera_Respuesta' in df.columns:
        df['Dias_Rpta_a_Agenda'] = (df['Fecha_Agendamiento'] - df['Fecha_Primera_Respuesta']).dt.days

    df['Año'] = df['Fecha'].dt.year
    df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
    meses_espanol = {
        1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril", 5: "Mayo", 6: "Junio",
        7: "Julio", 8: "Agosto", 9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre"
    }
    df['AñoMes'] = df['Fecha'].dt.month.map(meses_espanol) + ' ' + df['Fecha'].dt.year.astype(str)

    for col in ["Fuente de la Lista", "Campaña", "Proceso", "Industria", "Pais", "Puesto", "¿Quién Prospecto?"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D").replace("", "N/D")
        else:
            df[col] = "N/D"

    return df.sort_values(by='Fecha', ascending=False)

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

def clear_all_filters():
    """Resetea todos los widgets a su estado por defecto."""
    st.session_state.date_filter_mode = "Rango de Fechas"
    st.session_state.month_select = []
    
    # --- CORRECCIÓN FINAL: Se usa únicamente la lista de filtros original ---
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
            meses_disponibles = df.sort_values('Fecha', ascending=False)['AñoMes'].unique().tolist()
            selected_months = st.sidebar.multiselect("Selecciona el/los mes(es):", meses_disponibles, key="month_select")

    other_filters = {}
    st.sidebar.subheader("🔎 Por Estrategia de Prospección")
    
    # --- CORRECCIÓN FINAL: Se usa únicamente la lista de filtros original ---
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

def display_conversion_funnel(df_filtered):
    st.markdown("### 🏺 Funnel de Conversión del Periodo")
    
    total_acercamientos = int(df_filtered['Acercamientos'].sum())
    total_respuestas = int(df_filtered['Respuestas_Iniciales'].sum())
    total_sesiones = int(df_filtered['Sesiones_Agendadas'].sum())

    if total_acercamientos == 0:
        st.info("No hay acercamientos en el periodo seleccionado para mostrar un funnel.")
        return

    stages_data = {
        'Etapa': ["Acercamientos", "Respuestas Obtenidas", "Sesiones Agendadas"],
        'Valores': [total_acercamientos, total_respuestas, total_sesiones]
    }
    
    fig = go.Figure(go.Funnel(
        y = stages_data['Etapa'],
        x = stages_data['Valores'],
        textposition = "inside",
        textinfo = "value+percent initial",
        marker = {"color": ["#4B8BBE", "#30B88A", "#2E6B5A"],
                  "line": {"width": [4, 3, 2, 1], "color": "white"}},
        connector = {"line": {"color": "royalblue", "dash": "dot", "width": 3}}
    ))

    fig.update_layout(title="Flujo de Conversión: De Acercamiento a Sesión", title_x=0.5)
    st.plotly_chart(fig, use_container_width=True)

def display_velocity_metrics(df_filtered):
    st.markdown("### ⏱️ Análisis de Velocidad del Proceso")
    
    col1, col2, col3 = st.columns(3)
    
    avg_gen_contacto = pd.to_numeric(df_filtered['Dias_Gen_a_Contacto'], errors='coerce').mean()
    avg_contacto_rpta = pd.to_numeric(df_filtered['Dias_Contacto_a_Rpta'], errors='coerce').mean()
    avg_rpta_agenda = pd.to_numeric(df_filtered['Dias_Rpta_a_Agenda'], errors='coerce').mean()
    
    with col1:
        if 'Dias_Gen_a_Contacto' in df_filtered.columns and not pd.isna(avg_gen_contacto):
            st.metric("Lead a 1er Contacto", f"{avg_gen_contacto:.1f} días", help="Tiempo promedio desde que se genera un lead hasta que se le contacta por primera vez.")
        else: st.info("No hay datos de 'Fecha de Generación' para este cálculo.")

    with col2:
        if 'Dias_Contacto_a_Rpta' in df_filtered.columns and not pd.isna(avg_contacto_rpta):
            st.metric("Contacto a 1ra Respuesta", f"{avg_contacto_rpta:.1f} días", help="Tiempo promedio desde el primer contacto hasta recibir la primera respuesta.")
        else: st.info("No hay datos de 'Fecha de Primera Respuesta' para este cálculo.")
            
    with col3:
        if 'Dias_Rpta_a_Agenda' in df_filtered.columns and not pd.isna(avg_rpta_agenda):
            st.metric("Respuesta a Sesión", f"{avg_rpta_agenda:.1f} días", help="Tiempo promedio desde la primera respuesta hasta que se agenda la sesión.")
        else: st.info("No hay datos de 'Fecha Agendamiento' para este cálculo.")
            
    st.markdown("##### Distribución de los Tiempos de Conversión")
    
    df_vel = pd.DataFrame()
    if 'Dias_Gen_a_Contacto' in df_filtered.columns: df_vel = pd.concat([df_vel, df_filtered[['Dias_Gen_a_Contacto']].rename(columns={'Dias_Gen_a_Contacto':'Días'}).assign(Metrica='Lead a Contacto')])
    if 'Dias_Contacto_a_Rpta' in df_filtered.columns: df_vel = pd.concat([df_vel, df_filtered[['Dias_Contacto_a_Rpta']].rename(columns={'Dias_Contacto_a_Rpta':'Días'}).assign(Metrica='Contacto a Respuesta')])
    if 'Dias_Rpta_a_Agenda' in df_filtered.columns: df_vel = pd.concat([df_vel, df_filtered[['Dias_Rpta_a_Agenda']].rename(columns={'Dias_Rpta_a_Agenda':'Días'}).assign(Metrica='Respuesta a Agenda')])

    if not df_vel.empty:
        df_vel_filtered = df_vel[df_vel['Días'].between(0, 90)]
        fig = px.box(df_vel_filtered, x='Metrica', y='Días', color='Metrica', title="Distribución de Tiempos del Funnel (en días)", points="all")
        fig.update_layout(showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

def display_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    st.markdown(f"### {chart_icon} {title_prefix} por `{group_by_col}`")
    
    if group_by_col not in df_filtered.columns or df_filtered[group_by_col].nunique() < 2:
        st.info(f"No hay suficientes datos o diversidad en la columna '{group_by_col}' para generar este análisis.")
        return

    summary_df = df_filtered.groupby(group_by_col).agg(
        Acercamientos=('Acercamientos', 'sum'),
        Sesiones_Agendadas=('Sesiones_Agendadas', 'sum')
    ).reset_index()

    summary_df = summary_df[summary_df['Acercamientos'] > 0]
    summary_df['Tasa_Conversion_Global'] = summary_df.apply(lambda r: calculate_rate(r.Sesiones_Agendadas, r.Acercamientos), axis=1)
    
    summary_df_top = summary_df.nlargest(10, 'Sesiones_Agendadas')

    col1, col2 = st.columns([0.6, 0.4])
    
    with col1:
        st.markdown("##### Volumen: Acercamientos vs. Sesiones")
        fig = go.Figure()
        fig.add_trace(go.Bar(x=summary_df_top[group_by_col], y=summary_df_top['Acercamientos'], name='Acercamientos', marker_color='#4B8BBE'))
        fig.add_trace(go.Bar(x=summary_df_top[group_by_col], y=summary_df_top['Sesiones_Agendadas'], name='Sesiones Agendadas', marker_color='#30B88A'))
        fig.update_layout(barmode='group', title=f"Top 10 por Volumen de Sesiones", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.markdown("##### Eficiencia (Tasa de Conversión)")
        summary_df_eff = summary_df.nlargest(10, 'Tasa_Conversion_Global')
        fig_rate = px.bar(summary_df_eff.sort_values('Tasa_Conversion_Global', ascending=True),
                          x='Tasa_Conversion_Global', y=group_by_col, orientation='h',
                          text='Tasa_Conversion_Global', title="Top 10 por Eficiencia",
                          color="Tasa_Conversion_Global", color_continuous_scale=px.colors.sequential.Mint)
        fig_rate.update_traces(texttemplate='%{x:.1f}%', textposition='outside')
        st.plotly_chart(fig_rate, use_container_width=True)

    with st.expander(f"Ver tabla de datos completa por '{group_by_col}'"):
        st.dataframe(summary_df.sort_values('Sesiones_Agendadas', ascending=False).style.format({'Tasa_Conversion_Global': '{:.1f}%'}), use_container_width=True)

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

        col_funnel, col_velocity = st.columns([0.4, 0.6])
        with col_funnel:
            display_conversion_funnel(df_sdr_filtered)
        with col_velocity:
            display_velocity_metrics(df_sdr_filtered)

        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        
        st.markdown("## 🔬 Desglose de Rendimiento por Dimensiones")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["Por Campaña", "Por Industria", "Por País", "Por Puesto", "Por SDR"])
        
        with tab1:
            display_grouped_breakdown(df_sdr_filtered, "Campaña", "Análisis de Rendimiento", "🎯")
        with tab2:
            display_grouped_breakdown(df_sdr_filtered, "Industria", "Análisis de Rendimiento", "🏭")
        with tab3:
            display_grouped_breakdown(df_sdr_filtered, "Pais", "Análisis de Rendimiento", "🌍")
        with tab4:
            display_grouped_breakdown(df_sdr_filtered, "Puesto", "Análisis de Rendimiento", "👔")
        with tab5:
            display_grouped_breakdown(df_sdr_filtered, "¿Quién Prospecto?", "Análisis de Rendimiento", "🧑‍💻")
            
        st.markdown("<hr style='border:2px solid #2D3038'>", unsafe_allow_html=True)
        
        with st.expander("Ver tabla de datos detallados del período filtrado"):
            cols_to_show = [
                'Empresa', 'Nombre', 'Apellido', 'Puesto', 'Industria', 'Pais', 'Fecha', 
                'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Rpta', 'Dias_Rpta_a_Agenda',
                'Sesiones_Agendadas', '¿Quién Prospecto?'
            ]
            existing_cols = [col for col in cols_to_show if col in df_sdr_filtered.columns]
            st.dataframe(df_sdr_filtered[existing_cols], hide_index=True)
else:
    st.error("No se pudieron cargar o procesar los datos para el dashboard de SDR.")

st.markdown("---")
st.info("Plataforma de análisis de KPIs de SDR realizada por Johnsito ✨ 😊")
