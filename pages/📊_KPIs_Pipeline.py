# pages/📊_KPIs_Pipeline.py
import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import datetime
import sys
import os

# --- Añadir raíz del proyecto al path ---
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError:
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# --- IMPORTS DE TU PROYECTO ---
try:
    # Reutilizamos tu componente de tabla si lo necesitas al final
    from componentes.tabla_prospectos import mostrar_tabla_filtrada
except ImportError as e:
    st.error(f"Error importando módulos del proyecto: {e}")
    st.stop()

# --- Configuración de la Página ---
st.set_page_config(
    page_title="KPIs Pipeline (Prospects)",
    page_icon=" BPN",
    layout="wide"
)

# --- Constantes y Mapeo de Columnas ---
COL_COMPANY = "Company"
COL_INDUSTRY = "Industry"
COL_LEAD_DATE = "Lead Generated (Date)"
COL_CONTACTED = "Contacted?"
COL_RESPONDED = "Responded?"
COL_RESPONSE_CHANNEL = "Response Channel" # Aunque no sea KPI, útil para desglose
COL_MEETING = "Meeting?"
COL_MEETING_DATE = "Meeting Date" # Útil si quieres filtrar por fecha de reunión en el futuro
# Columnas booleanas internas que crearemos
COL_CONTACTED_BOOL = "Contacted_Bool"
COL_RESPONDED_BOOL = "Responded_Bool"
COL_MEETING_BOOL = "Meeting_Bool"

# Claves de Estado de Sesión para Filtros
FILTER_KEYS_PREFIX = "pipeline_kpi_page_v2_" # Nueva versión para evitar conflictos
PIPE_START_DATE_KEY = f"{FILTER_KEYS_PREFIX}start_date"
PIPE_END_DATE_KEY = f"{FILTER_KEYS_PREFIX}end_date"
PIPE_INDUSTRY_FILTER_KEY = f"{FILTER_KEYS_PREFIX}industry"
PIPE_COMPANY_FILTER_KEY = f"{FILTER_KEYS_PREFIX}company"
# (Puedes añadir más filtros si los necesitas, ej. por Role, Management Level)

# --- Carga y Limpieza de Datos ---
@st.cache_data(ttl=600)
def load_pipeline_data():
    WORKSHEET_NAME = "Prospects"
    try:
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)
    except Exception as e:
        st.error(f"Error al autenticar con Google (gcp_service_account): {e}")
        st.stop()

    try:
        sheet_url = st.secrets["prospects_sheet_url"]
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(WORKSHEET_NAME)
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos de la hoja '{WORKSHEET_NAME}'.")
            return pd.DataFrame()
        headers = raw_data[0]
        rows = raw_data[1:]
        # Limpieza básica de filas y padding (igual que antes)
        cleaned_rows = [row for row in rows if any(cell.strip() for cell in row)]
        num_cols = len(headers)
        cleaned_rows_padded = []
        for row in cleaned_rows:
            row_len = len(row)
            if row_len < num_cols: row.extend([''] * (num_cols - row_len))
            cleaned_rows_padded.append(row[:num_cols])
        df = pd.DataFrame(cleaned_rows_padded, columns=headers)
    except Exception as e: # Captura errores genéricos y específicos
        st.error(f"Error al cargar/leer la hoja '{WORKSHEET_NAME}': {e}")
        st.stop()

    # --- Limpieza Específica para KPIs ---
    # Convertir booleanos (TRUE/FALSE como strings)
    bool_cols_map = {COL_CONTACTED: COL_CONTACTED_BOOL, COL_RESPONDED: COL_RESPONDED_BOOL}
    for original, new in bool_cols_map.items():
        if original in df.columns:
            df[new] = df[original].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)
        else:
            df[new] = False # Asegura que la columna exista

    # === CORRECCIÓN CLAVE para Meeting? ===
    if COL_MEETING in df.columns:
         # Compara con 'Yes' ignorando mayúsculas/minúsculas y espacios
        df[COL_MEETING_BOOL] = df[COL_MEETING].apply(lambda x: True if str(x).strip().upper() == 'YES' else False)
    else:
        df[COL_MEETING_BOOL] = False # Asegura que la columna exista

    # Convertir fechas (solo la necesaria para filtros ahora)
    if COL_LEAD_DATE in df.columns:
        df[COL_LEAD_DATE] = pd.to_datetime(df[COL_LEAD_DATE], errors='coerce', dayfirst=True)
    else:
        df[COL_LEAD_DATE] = pd.NaT # Asegura que exista como fecha

    # Limpiar columnas de texto para filtros/desglose
    text_cols_clean = [COL_COMPANY, COL_INDUSTRY]
    for col in text_cols_clean:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D")
            df.loc[df[col] == '', col] = "N/D"
        else:
            df[col] = "N/D" # Asegura que existan

    # Crear columnas Año/Mes si es posible
    if pd.api.types.is_datetime64_any_dtype(df[COL_LEAD_DATE]):
        df_valid_dates = df.dropna(subset=[COL_LEAD_DATE])
        if not df_valid_dates.empty:
            df['Año'] = df_valid_dates[COL_LEAD_DATE].dt.year
            df['AñoMes'] = df_valid_dates[COL_LEAD_DATE].dt.strftime('%Y-%m')
            # Llenar NaNs en las nuevas columnas para filas sin fecha válida
            df['Año'] = df['Año'].fillna(0).astype(int)
            df['AñoMes'] = df['AñoMes'].fillna('N/D')
        else: df['Año'], df['AñoMes'] = 0, 'N/D'
    else: df['Año'], df['AñoMes'] = 0, 'N/D'


    return df

# --- Funciones de Filtros (Simplificadas para KPIs) ---
def reset_pipeline_kpi_filters_state():
    # Solo resetea los filtros definidos para esta página
    st.session_state[PIPE_START_DATE_KEY] = None
    st.session_state[PIPE_END_DATE_KEY] = None
    st.session_state[PIPE_INDUSTRY_FILTER_KEY] = ["– Todos –"]
    st.session_state[PIPE_COMPANY_FILTER_KEY] = ["– Todos –"]
    st.toast("Filtros de KPIs del Pipeline reiniciados ✅")

# Reutilizamos la función genérica de multiselect que ya tenías
def crear_multiselect_pipeline_kpi(df, columna, etiqueta, key):
    if key not in st.session_state: st.session_state[key] = ["– Todos –"]
    options = ["– Todos –"]
    if columna in df.columns and not df[columna].dropna().empty:
        # Usamos set para eliminar duplicados y luego sort
        options.extend(sorted(list(set(df[columna].astype(str).tolist()))))

    # Validación y corrección del estado antes de renderizar
    current_value = st.session_state[key]
    if not isinstance(current_value, list): current_value = ["– Todos –"]
    valid_selection = [v for v in current_value if v in options]
    if not valid_selection: valid_selection = ["– Todos –"]
    st.session_state[key] = valid_selection # Actualiza el estado ANTES del widget

    return st.multiselect(etiqueta, options, key=key) # Default se toma del estado

def sidebar_filters_pipeline_kpi(df_options):
    st.sidebar.header("🔍 Filtros de KPIs (Pipeline)")
    st.sidebar.markdown("---")

    # Inicializar estado si es necesario
    for k, v in {PIPE_INDUSTRY_FILTER_KEY: ["– Todos –"], PIPE_COMPANY_FILTER_KEY: ["– Todos –"]}.items():
        if k not in st.session_state: st.session_state[k] = v
    if PIPE_START_DATE_KEY not in st.session_state: st.session_state[PIPE_START_DATE_KEY] = None
    if PIPE_END_DATE_KEY not in st.session_state: st.session_state[PIPE_END_DATE_KEY] = None

    # Filtros por Atributo
    st.sidebar.subheader("Por Atributo")
    crear_multiselect_pipeline_kpi(df_options, COL_INDUSTRY, "Industria", PIPE_INDUSTRY_FILTER_KEY)
    crear_multiselect_pipeline_kpi(df_options, COL_COMPANY, "Compañía", PIPE_COMPANY_FILTER_KEY)

    # Filtros de Fecha (Lead Generated Date)
    st.sidebar.subheader("🗓️ Por Fecha de Generación")
    min_d, max_d = None, None
    if COL_LEAD_DATE in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options[COL_LEAD_DATE]):
        valid_dates = df_options[COL_LEAD_DATE].dropna()
        if not valid_dates.empty:
            min_d, max_d = valid_dates.min().date(), valid_dates.max().date()
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1: st.date_input("Desde", format='DD/MM/YYYY', key=PIPE_START_DATE_KEY, min_value=min_d, max_value=max_d)
    with col_f2: st.date_input("Hasta", format='DD/MM/YYYY', key=PIPE_END_DATE_KEY, min_value=min_d, max_value=max_d)

    # Botón Limpiar
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros", on_click=reset_pipeline_kpi_filters_state, use_container_width=True)

    # Devolver valores del estado
    return (st.session_state[PIPE_START_DATE_KEY], st.session_state[PIPE_END_DATE_KEY],
            st.session_state[PIPE_INDUSTRY_FILTER_KEY], st.session_state[PIPE_COMPANY_FILTER_KEY])

def apply_pipeline_kpi_filters(df, start_dt, end_dt, industry_list, company_list):
    df_f = df.copy()
    # Filtros Multi-select
    if industry_list and "– Todos –" not in industry_list:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industry_list)]
    if company_list and "– Todos –" not in company_list:
        df_f = df_f[df_f[COL_COMPANY].isin(company_list)]
    # Filtro de Fecha
    if pd.api.types.is_datetime64_any_dtype(df_f[COL_LEAD_DATE]):
        date_series = df_f[COL_LEAD_DATE].dt.date
        if start_dt and end_dt:
            df_f = df_f[(date_series >= start_dt) & (date_series <= end_dt)]
        elif start_dt:
            df_f = df_f[date_series >= start_dt]
        elif end_dt:
            df_f = df_f[date_series <= end_dt]
    return df_f

# --- Funciones de Visualización de KPIs (Similar a tus otras páginas) ---
def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

def display_pipeline_kpi_summary_metrics(df_filtered):
    st.markdown("### 🧮 Resumen de KPIs Totales (Periodo Filtrado)")
    if df_filtered.empty:
        st.info("No hay datos para mostrar KPIs con los filtros actuales.")
        return

    # Cálculos usando las columnas booleanas limpias
    total_leads = len(df_filtered)
    total_contacted = df_filtered[COL_CONTACTED_BOOL].sum()
    total_responded = df_filtered[COL_RESPONDED_BOOL].sum()
    total_meetings = df_filtered[COL_MEETING_BOOL].sum()

    # Tasas
    contact_rate = calculate_rate(total_contacted, total_leads)
    response_rate = calculate_rate(total_responded, total_contacted) # vs Contactados
    meeting_rate_vs_resp = calculate_rate(total_meetings, total_responded) # vs Respondieron
    meeting_rate_vs_contacted = calculate_rate(total_meetings, total_contacted) # vs Contactados (opcional)
    meeting_rate_vs_leads = calculate_rate(total_meetings, total_leads) # vs Leads (Global)

    # Mostrar métricas absolutas
    st.markdown("#### Métricas Absolutas")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Leads (Filtrados)", f"{total_leads:,.0f}")
    m_col2.metric("Contactados", f"{total_contacted:,.0f}")
    m_col3.metric("Respondieron", f"{total_responded:,.0f}")
    m_col4.metric("Reuniones Agendadas", f"{total_meetings:,.0f}") # CORREGIDO

    st.markdown("---")
    st.markdown("#### Tasas de Conversión del Embudo")
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("Tasa Contacto", f"{contact_rate:.1f}%", help="Contactados / Leads")
    r_col2.metric("Tasa Respuesta", f"{response_rate:.1f}%", help="Respondieron / Contactados")
    r_col3.metric("Tasa Reunión (vs Resp.)", f"{meeting_rate_vs_resp:.1f}%", help="Reuniones / Respondieron") # CORREGIDO
    r_col4.metric("Tasa Reunión (Global)", f"{meeting_rate_vs_leads:.1f}%", help="Reuniones / Leads")

def display_pipeline_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    st.markdown(f"### {chart_icon} {title_prefix}")
    if group_by_col not in df_filtered.columns or df_filtered.empty:
        st.warning(f"No hay datos o falta la columna '{group_by_col}'.")
        return

    # KPIs a sumar
    kpi_cols_to_agg = [COL_CONTACTED_BOOL, COL_RESPONDED_BOOL, COL_MEETING_BOOL]
    present_kpi_cols = [col for col in kpi_cols_to_agg if col in df_filtered.columns]

    # Agrupar y sumar KPIs booleanos (sum() cuenta los True)
    summary_df = df_filtered.groupby(group_by_col, as_index=False).agg(
        Total_Leads=(group_by_col, 'size'), # Contar leads por grupo
        **{col: (col, 'sum') for col in present_kpi_cols} # Sumar KPIs booleanos
    )

    # Renombrar columnas sumadas para claridad
    rename_map = {
        COL_CONTACTED_BOOL: 'Contactados',
        COL_RESPONDED_BOOL: 'Respondieron',
        COL_MEETING_BOOL: 'Reuniones'
    }
    summary_df.rename(columns=rename_map, inplace=True)

    # Calcular tasas para cada grupo
    summary_df['Tasa Reunión (Global %)'] = summary_df.apply(
        lambda row: calculate_rate(row.get('Reuniones', 0), row.get('Total_Leads', 0)), axis=1
    )
    # Puedes añadir más tasas si son relevantes (ej. Tasa Respuesta vs Contactados por grupo)
    summary_df['Tasa Respuesta (vs Cont. %)'] = summary_df.apply(
         lambda row: calculate_rate(row.get('Respondieron', 0), row.get('Contactados', 0)), axis=1
    )

    if not summary_df.empty:
        st.markdown(f"##### Tabla Resumen por {group_by_col}")
        # Seleccionar y ordenar columnas para la tabla
        cols_for_table = [group_by_col, 'Total_Leads'] + list(rename_map.values()) + ['Tasa Respuesta (vs Cont. %)', 'Tasa Reunión (Global %)']
        existing_cols_for_table = [c for c in cols_for_table if c in summary_df.columns]
        summary_df_display = summary_df[existing_cols_for_table].copy()

        # Formatear números y porcentajes
        format_dict = {'Total_Leads': '{:,}', 'Contactados': '{:,}', 'Respondieron': '{:,}', 'Reuniones': '{:,}',
                       'Tasa Respuesta (vs Cont. %)': '{:.1f}%', 'Tasa Reunión (Global %)': '{:.1f}%'}
        # Filtrar el diccionario de formato para incluir solo columnas existentes
        valid_format_dict = {k: v for k, v in format_dict.items() if k in summary_df_display.columns}

        st.dataframe(summary_df_display.set_index(group_by_col).style.format(valid_format_dict), use_container_width=True)

        # Gráfico (ej. Tasa de Reunión Global por grupo)
        if 'Reuniones' in summary_df.columns and summary_df['Reuniones'].sum() > 0:
             st.markdown(f"##### Gráfico: Tasa de Reunión Global por {group_by_col} (Top 15)")
             summary_df_sorted = summary_df[summary_df['Total_Leads'] >= 3].sort_values(by='Tasa Reunión (Global %)', ascending=False).head(15) # Filtrar por mínimo leads y top N
             if not summary_df_sorted.empty:
                fig = px.bar(summary_df_sorted, x=group_by_col, y='Tasa Reunión (Global %)',
                             title=f"Tasa de Reunión Global por {group_by_col}",
                             text='Tasa Reunión (Global %)', color='Tasa Reunión (Global %)')
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(yaxis_title="Tasa Reunión Global (%)", xaxis_title=group_by_col, yaxis_ticksuffix="%")
                st.plotly_chart(fig, use_container_width=True)
             else: st.caption("No hay suficientes datos (>3 leads por grupo) para graficar la tasa de reunión.")

    else:
        st.info(f"No hay datos suficientes para desglosar por {group_by_col}.")


# --- Flujo Principal de la Página ---
st.title("📊 KPIs Pipeline (Prospects)")
st.markdown("Métricas clave del embudo de ventas de la hoja 'Prospects'.")

# Cargar datos
df_pipeline_base = load_pipeline_data()

if df_pipeline_base.empty:
    st.error("Fallo Crítico: No se pudieron cargar datos del Pipeline.")
    st.stop()

# Mostrar filtros y obtener selecciones
start_f, end_f, industry_f, company_f = sidebar_filters_pipeline_kpi(df_pipeline_base.copy())

# Aplicar filtros
df_pipeline_filtered = apply_pipeline_kpi_filters(
    df_pipeline_base.copy(), start_f, end_f, industry_f, company_f
)

# Mostrar KPIs y Desgloses
display_pipeline_kpi_summary_metrics(df_pipeline_filtered)
st.markdown("---")

# Desgloses por Industria y Compañía (similar a tus otras páginas)
display_pipeline_grouped_breakdown(df_pipeline_filtered, COL_INDUSTRY, "Desglose por Industria", chart_icon="🏭")
st.markdown("---")
display_pipeline_grouped_breakdown(df_pipeline_filtered, COL_COMPANY, "Desglose por Compañía", chart_icon="🏢")
st.markdown("---")

# Mostrar Tabla Detallada (Opcional, usando tu componente)
with st.expander("Ver Tabla de Datos Detallados Filtrados"):
    mostrar_tabla_filtrada(df_pipeline_filtered.copy(), key_suffix="pipeline_kpi") # Sufijo único

# Pie de página
st.markdown("---")
st.info("Dashboard de KPIs del Pipeline.")

