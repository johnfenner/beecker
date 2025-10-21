# pages/📊_KPIs_Pipeline.py
import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import datetime
import sys
import os

# --- Configuración de la Página ---
st.set_page_config(
    page_title="KPIs Pipeline (Prospects)",
    page_icon=" BPN", # Puedes cambiar este ícono
    layout="wide"
)

# --- Constantes y Mapeo de Columnas ---
# Columnas clave del set de datos proporcionado
COL_COMPANY = "Company"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT_LEVEL = "Management Level"
COL_LEAD_DATE = "Lead Generated (Date)" # Se carga pero no se usa como filtro principal
COL_CONECTION_SENT = "Conection Sent Date" # <-- COLUMNA CLAVE PARA FILTRADO BASE
COL_CONTACTED = "Contacted?"
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"
COL_MEETING_DATE = "Meeting Date"

# Columna de fecha principal para filtros de sidebar y análisis temporal
COL_DATE_FILTER = COL_CONECTION_SENT

# Columnas booleanas internas que crearemos
COL_CONECTION_SENT_BOOL = "Conection_Sent_Bool" # Para verificar si hay fecha
COL_CONTACTED_BOOL = "Contacted_Bool"
COL_RESPONDED_BOOL = "Responded_Bool"
COL_MEETING_BOOL = "Meeting_Bool"

# Claves de Estado de Sesión para Filtros (con prefijo único)
FILTER_KEYS_PREFIX = "pipeline_kpi_page_v2_" # Versión actualizada para reflejar cambios
PIPE_START_DATE_KEY = f"{FILTER_KEYS_PREFIX}start_date"
PIPE_END_DATE_KEY = f"{FILTER_KEYS_PREFIX}end_date"
PIPE_INDUSTRY_FILTER_KEY = f"{FILTER_KEYS_PREFIX}industry"
PIPE_COMPANY_FILTER_KEY = f"{FILTER_KEYS_PREFIX}company"
PIPE_MANAGEMENT_FILTER_KEY = f"{FILTER_KEYS_PREFIX}management_level"
PIPE_YEAR_FILTER_KEY = f"{FILTER_KEYS_PREFIX}year"
PIPE_WEEK_FILTER_KEY = f"{FILTER_KEYS_PREFIX}week"

# --- Carga y Limpieza de Datos ---
@st.cache_data(ttl=600)
def load_pipeline_data():
    """
    Carga y procesa datos desde la hoja de "Prospects".
    Ahora filtra inicialmente por Conection Sent Date.
    """
    WORKSHEET_NAME = "Prospects" # Asume el nombre de la hoja
    try:
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)
    except Exception as e:
        st.error(f"Error al autenticar con Google (gcp_service_account): {e}")
        st.stop()

    try:
        # Asume una nueva clave de secret para esta URL
        sheet_url = st.secrets["prospects_sheet_url"]
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(WORKSHEET_NAME)
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos de la hoja '{WORKSHEET_NAME}'.")
            return pd.DataFrame()

        headers = raw_data[0]
        rows = raw_data[1:]

        # Limpieza básica de filas y padding
        cleaned_rows = [row for row in rows if any(cell.strip() for cell in row)]
        num_cols = len(headers)
        cleaned_rows_padded = []
        for row in cleaned_rows:
            row_len = len(row)
            if row_len < num_cols: row.extend([''] * (num_cols - row_len))
            cleaned_rows_padded.append(row[:num_cols])

        df = pd.DataFrame(cleaned_rows_padded, columns=headers)

    except Exception as e:
        st.error(f"Error al cargar/leer la hoja '{WORKSHEET_NAME}': {e}")
        st.stop()

    # --- Limpieza Específica para KPIs ---

    # 1. Convertir booleanos (TRUE/FALSE como strings)
    bool_cols_map = {
        COL_CONTACTED: COL_CONTACTED_BOOL,
        COL_RESPONDED: COL_RESPONDED_BOOL
    }
    for original, new in bool_cols_map.items():
        if original in df.columns:
            df[new] = df[original].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)
        else:
            df[new] = False

    # 2. Convertir 'Meeting?' (Asumiendo 'Yes'/'No')
    if COL_MEETING in df.columns:
        df[COL_MEETING_BOOL] = df[COL_MEETING].apply(lambda x: True if str(x).strip().upper() == 'YES' else False)
    else:
        df[COL_MEETING_BOOL] = False

    # 3. Convertir Connection Sent Date (Primary Date Filter) y crear bool
    if COL_CONECTION_SENT in df.columns:
        df[COL_CONECTION_SENT] = pd.to_datetime(df[COL_CONECTION_SENT], errors='coerce', dayfirst=True)
        # Crear columna booleana para saber si la fecha es válida *antes* de filtrar
        df[COL_CONECTION_SENT_BOOL] = df[COL_CONECTION_SENT].notna()
    else:
        # Si la columna no existe, no podemos continuar con este enfoque
        st.error(f"Error Crítico: La columna '{COL_CONECTION_SENT}' es necesaria y no se encontró en la hoja.")
        st.stop() # Detener la ejecución si falta la columna clave

    # --- FILTRO BASE: Mantener solo leads con fecha de conexión enviada ---
    # Este es el cambio clave: la base de datos para todo el dashboard
    # solo incluirá filas con una fecha de conexión válida.
    df_filtered_base = df[df[COL_CONECTION_SENT_BOOL] == True].copy()

    # Verificar si quedaron datos después del filtro base
    if df_filtered_base.empty:
        # Usar st.warning en lugar de st.error para que no detenga la app si es temporal
        st.warning("No se encontraron leads con una 'Conection Sent Date' válida. El dashboard estará vacío o mostrará ceros.")
        # Devolver un DataFrame vacío pero con la estructura esperada puede ser útil
        # O simplemente devolver el df vacío y manejarlo en las funciones de display
        return pd.DataFrame() # Devolver DataFrame vacío

    # A partir de aquí, usar df_filtered_base
    df = df_filtered_base

    # 4. Limpiar columnas de texto para filtros/desglose
    text_cols_clean = [COL_COMPANY, COL_INDUSTRY, COL_MANAGEMENT_LEVEL]
    for col in text_cols_clean:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D")
            df.loc[df[col] == '', col] = "N/D"
        else:
            df[col] = "N/D"

    # 5. Crear columnas de Año/Mes/Semana (basado en COL_DATE_FILTER)
    # Asegurarse de que la columna de fecha todavía existe y es de tipo fecha
    if COL_DATE_FILTER in df.columns and pd.api.types.is_datetime64_any_dtype(df[COL_DATE_FILTER]):
        # No necesitamos filtrar NaNs aquí porque ya lo hicimos con el filtro base
        df['Año'] = df[COL_DATE_FILTER].dt.year.astype('Int64')
        df['NumSemana'] = df[COL_DATE_FILTER].dt.isocalendar().week.astype('Int64')
        df['AñoMes'] = df[COL_DATE_FILTER].dt.strftime('%Y-%m')
    else:
        # Si algo falló, asignar valores por defecto
        df['Año'], df['NumSemana'], df['AñoMes'] = 0, 0, 'N/D'

    return df

# --- Funciones de Filtros (Sidebar) ---
# (reset_pipeline_kpi_filters_state y crear_multiselect_pipeline_kpi permanecen iguales)
def reset_pipeline_kpi_filters_state():
    """Resetea los filtros de esta página."""
    st.session_state[PIPE_START_DATE_KEY] = None
    st.session_state[PIPE_END_DATE_KEY] = None
    st.session_state[PIPE_INDUSTRY_FILTER_KEY] = ["– Todos –"]
    st.session_state[PIPE_COMPANY_FILTER_KEY] = ["– Todos –"]
    st.session_state[PIPE_MANAGEMENT_FILTER_KEY] = ["– Todos –"]
    st.session_state[PIPE_YEAR_FILTER_KEY] = "– Todos –"
    st.session_state[PIPE_WEEK_FILTER_KEY] = ["– Todas –"]
    st.toast("Filtros de KPIs del Pipeline reiniciados ✅")

def crear_multiselect_pipeline_kpi(df, columna, etiqueta, key):
    """Función genérica para crear un multiselect."""
    if key not in st.session_state: st.session_state[key] = ["– Todos –"]
    options = ["– Todos –"]
    if columna in df.columns and not df[columna].dropna().empty:
        options.extend(sorted(list(set(df[columna].astype(str).tolist()))))

    current_value = st.session_state[key]
    if not isinstance(current_value, list): current_value = ["– Todos –"]
    valid_selection = [v for v in current_value if v in options]
    if not valid_selection: valid_selection = ["– Todos –"]
    st.session_state[key] = valid_selection

    return st.multiselect(etiqueta, options, key=key)


def sidebar_filters_pipeline_kpi(df_options):
    """Muestra todos los filtros en la barra lateral."""
    st.sidebar.header("🔍 Filtros de KPIs (Pipeline)")
    st.sidebar.markdown("---")

    # Inicializar estado si es necesario
    keys_to_init = {
        PIPE_INDUSTRY_FILTER_KEY: ["– Todos –"],
        PIPE_COMPANY_FILTER_KEY: ["– Todos –"],
        PIPE_MANAGEMENT_FILTER_KEY: ["– Todos –"],
        PIPE_YEAR_FILTER_KEY: "– Todos –",
        PIPE_WEEK_FILTER_KEY: ["– Todas –"],
        PIPE_START_DATE_KEY: None,
        PIPE_END_DATE_KEY: None
    }
    for k, v in keys_to_init.items():
        if k not in st.session_state: st.session_state[k] = v

    # Filtros por Atributo
    st.sidebar.subheader("Por Atributo")
    crear_multiselect_pipeline_kpi(df_options, COL_INDUSTRY, "Industria", PIPE_INDUSTRY_FILTER_KEY)
    crear_multiselect_pipeline_kpi(df_options, COL_COMPANY, "Compañía", PIPE_COMPANY_FILTER_KEY)
    crear_multiselect_pipeline_kpi(df_options, COL_MANAGEMENT_LEVEL, "Management Level", PIPE_MANAGEMENT_FILTER_KEY)

    # Filtros de Fecha (Basado en COL_DATE_FILTER = Conection Sent Date)
    st.sidebar.subheader(f"🗓️ Por Fecha ({COL_DATE_FILTER})") # Título dinámico
    min_d, max_d = None, None
    # Usar COL_DATE_FILTER para obtener min/max
    if COL_DATE_FILTER in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options[COL_DATE_FILTER]):
        valid_dates = df_options[COL_DATE_FILTER].dropna()
        if not valid_dates.empty:
            min_d, max_d = valid_dates.min().date(), valid_dates.max().date()

    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1: st.date_input("Desde", format='DD/MM/YYYY', key=PIPE_START_DATE_KEY, min_value=min_d, max_value=max_d)
    with col_f2: st.date_input("Hasta", format='DD/MM/YYYY', key=PIPE_END_DATE_KEY, min_value=min_d, max_value=max_d)

    # Filtros de Año/Semana (basados en la fecha de conexión)
    st.sidebar.subheader(f"📅 Por Año y Semana ({COL_DATE_FILTER})") # Título dinámico

    year_options = ["– Todos –"]
    # Usar columna 'Año' derivada de COL_DATE_FILTER
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
         # Excluir el 0 que usamos para NaNs
        year_options.extend(sorted([str(y) for y in df_options["Año"].unique() if y != 0], reverse=True))

    selected_year_str = st.sidebar.selectbox("Año", year_options, key=PIPE_YEAR_FILTER_KEY)
    selected_year_int = int(selected_year_str) if selected_year_str != "– Todos –" else None

    week_options = ["– Todas –"]
    df_for_week = df_options[df_options["Año"] == selected_year_int] if selected_year_int else df_options
    # Usar columna 'NumSemana' derivada de COL_DATE_FILTER
    if "NumSemana" in df_for_week.columns and not df_for_week["NumSemana"].dropna().empty:
         # Excluir el 0 que usamos para NaNs
        week_options.extend(sorted([str(w) for w in df_for_week["NumSemana"].unique() if w != 0]))

    st.sidebar.multiselect("Semanas", week_options, key=PIPE_WEEK_FILTER_KEY)

    # Botón Limpiar
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros", on_click=reset_pipeline_kpi_filters_state, use_container_width=True)

    # Devolver valores del estado
    return (
        st.session_state[PIPE_START_DATE_KEY], st.session_state[PIPE_END_DATE_KEY],
        selected_year_int, st.session_state[PIPE_WEEK_FILTER_KEY],
        st.session_state[PIPE_INDUSTRY_FILTER_KEY], st.session_state[PIPE_COMPANY_FILTER_KEY],
        st.session_state[PIPE_MANAGEMENT_FILTER_KEY]
    )

def apply_pipeline_kpi_filters(df, start_dt, end_dt, year_val, week_list, industry_list, company_list, management_list):
    """Aplica todos los filtros seleccionados al DataFrame."""
    # Importante: df ya está pre-filtrado por Conection Sent Date válido
    df_f = df.copy()

    # Filtro de Fecha (Rango) - Basado en COL_DATE_FILTER
    # Verificar si la columna existe y es de fecha (aunque debería serlo por el pre-filtrado)
    if COL_DATE_FILTER in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f[COL_DATE_FILTER]):
        # Convertir start_dt y end_dt a date si no lo son
        start_date_obj = start_dt if isinstance(start_dt, datetime.date) else None
        end_date_obj = end_dt if isinstance(end_dt, datetime.date) else None

        date_series = df_f[COL_DATE_FILTER].dt.date

        if start_date_obj and end_date_obj:
            df_f = df_f[(date_series >= start_date_obj) & (date_series <= end_date_obj)]
        elif start_date_obj:
            df_f = df_f[date_series >= start_date_obj]
        elif end_date_obj:
            df_f = df_f[date_series <= end_date_obj]

    # Filtro de Año
    if year_val is not None and "Año" in df_f.columns:
        # Asegurarse de que la comparación sea con el tipo correcto (Int64)
        df_f = df_f[df_f["Año"] == year_val]

    # Filtro de Semana
    if week_list and "– Todas –" not in week_list and "NumSemana" in df_f.columns:
        try:
            selected_weeks_int = [int(w) for w in week_list if w.isdigit()]
            if selected_weeks_int:
                # Asegurarse de que la comparación sea con el tipo correcto (Int64)
                df_f = df_f[df_f["NumSemana"].isin(selected_weeks_int)]
        except Exception as e:
            st.warning(f"Error al aplicar filtro de semana: {e}. Asegúrate que 'NumSemana' sea numérico.")


    # Filtros Multi-select
    if industry_list and "– Todos –" not in industry_list:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industry_list)]
    if company_list and "– Todos –" not in company_list:
        df_f = df_f[df_f[COL_COMPANY].isin(company_list)]
    if management_list and "– Todos –" not in management_list:
        df_f = df_f[df_f[COL_MANAGEMENT_LEVEL].isin(management_list)]

    return df_f


# --- Funciones de Visualización de KPIs ---
# (calculate_rate permanece igual)
def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

def display_pipeline_kpi_summary_metrics(df_filtered):
    """Muestra las métricas KPi y tasas de conversión."""
    st.markdown("### 🧮 Resumen de KPIs Totales (Periodo Filtrado)")
    if df_filtered.empty:
        st.info("No hay datos para mostrar KPIs con los filtros actuales.")
        # Mostrar métricas en cero si no hay datos
        total_leads, total_contacted, total_responded, total_meetings = 0, 0, 0, 0
        contact_rate, response_rate, meeting_rate_vs_resp, meeting_rate_vs_leads = 0.0, 0.0, 0.0, 0.0
    else:
        # Cálculos usando las columnas booleanas limpias
        total_leads = len(df_filtered) # Ya representa leads con conexión enviada y filtrados
        total_contacted = df_filtered[COL_CONTACTED_BOOL].sum()
        total_responded = df_filtered[COL_RESPONDED_BOOL].sum()
        total_meetings = df_filtered[COL_MEETING_BOOL].sum()

        # Tasas
        contact_rate = calculate_rate(total_contacted, total_leads)
        response_rate = calculate_rate(total_responded, total_contacted) # vs Contactados
        meeting_rate_vs_resp = calculate_rate(total_meetings, total_responded) # vs Respondieron
        meeting_rate_vs_leads = calculate_rate(total_meetings, total_leads) # vs Leads (Global)

    # Mostrar métricas absolutas
    st.markdown("#### Métricas Absolutas")
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    m_col1.metric("Leads (Conexión Enviada)", f"{total_leads:,.0f}")
    m_col2.metric("Contactados", f"{total_contacted:,.0f}")
    m_col3.metric("Respondieron", f"{total_responded:,.0f}")
    m_col4.metric("Reuniones Agendadas", f"{total_meetings:,.0f}")

    st.markdown("---")
    st.markdown("#### Tasas de Conversión del Embudo")
    r_col1, r_col2, r_col3, r_col4 = st.columns(4)
    r_col1.metric("Tasa Contacto", f"{contact_rate:.1f}%", help="Contactados / Leads (Conexión Enviada)")
    r_col2.metric("Tasa Respuesta", f"{response_rate:.1f}%", help="Respondieron / Contactados")
    r_col3.metric("Tasa Reunión (vs Resp.)", f"{meeting_rate_vs_resp:.1f}%", help="Reuniones / Respondieron")
    r_col4.metric("Tasa Reunión (Global)", f"{meeting_rate_vs_leads:.1f}%", help="Reuniones / Leads (Conexión Enviada)")

# (display_pipeline_grouped_breakdown permanece igual en lógica, solo cambia el nombre de la columna base)
def display_pipeline_grouped_breakdown(df_filtered, group_by_col, title_prefix, chart_icon="📊"):
    """Muestra una tabla y gráfico de barras para una dimensión dada."""
    st.markdown(f"### {chart_icon} {title_prefix}")
    if group_by_col not in df_filtered.columns or df_filtered.empty:
        st.warning(f"No hay datos o falta la columna '{group_by_col}'.")
        return

    # KPIs a sumar
    kpi_cols_to_agg = [COL_CONTACTED_BOOL, COL_RESPONDED_BOOL, COL_MEETING_BOOL]
    present_kpi_cols = [col for col in kpi_cols_to_agg if col in df_filtered.columns]

    # Agrupar y sumar KPIs booleanos (sum() cuenta los True)
    summary_df = df_filtered.groupby(group_by_col, as_index=False).agg(
        # Cambiar nombre de 'Total_Leads' a 'Leads (Conexión Enviada)'
        **{'Leads (Conexión Enviada)': (group_by_col, 'size')},
        **{col: (col, 'sum') for col in present_kpi_cols}
    )

    # Renombrar columnas sumadas para claridad
    rename_map = {
        COL_CONTACTED_BOOL: 'Contactados',
        COL_RESPONDED_BOOL: 'Respondieron',
        COL_MEETING_BOOL: 'Reuniones'
    }
    summary_df.rename(columns=rename_map, inplace=True)

    # Calcular tasas para cada grupo, usando el nuevo nombre de columna base
    summary_df['Tasa Reunión (Global %)'] = summary_df.apply(
        lambda row: calculate_rate(row.get('Reuniones', 0), row.get('Leads (Conexión Enviada)', 0)), axis=1
    )
    summary_df['Tasa Respuesta (vs Cont. %)'] = summary_df.apply(
         lambda row: calculate_rate(row.get('Respondieron', 0), row.get('Contactados', 0)), axis=1
    )

    if not summary_df.empty:
        st.markdown(f"##### Tabla Resumen por {group_by_col}")
        # Actualizar lista de columnas para la tabla
        cols_for_table = [group_by_col, 'Leads (Conexión Enviada)'] + list(rename_map.values()) + ['Tasa Respuesta (vs Cont. %)', 'Tasa Reunión (Global %)']
        existing_cols_for_table = [c for c in cols_for_table if c in summary_df.columns]
        summary_df_display = summary_df[existing_cols_for_table].copy()

        # Actualizar diccionario de formato
        format_dict = {
            'Leads (Conexión Enviada)': '{:,}', 'Contactados': '{:,}',
            'Respondieron': '{:,}', 'Reuniones': '{:,}',
            'Tasa Respuesta (vs Cont. %)': '{:.1f}%',
            'Tasa Reunión (Global %)': '{:.1f}%'
        }
        valid_format_dict = {k: v for k, v in format_dict.items() if k in summary_df_display.columns}

        st.dataframe(summary_df_display.set_index(group_by_col).style.format(valid_format_dict), use_container_width=True)

        # Gráfico (ej. Tasa de Reunión Global por grupo)
        if 'Reuniones' in summary_df.columns and summary_df['Reuniones'].sum() > 0:
             st.markdown(f"##### Gráfico: Tasa de Reunión Global por {group_by_col} (Top 15)")
             # Filtrar grupos con pocos leads para que la tasa sea significativa
             summary_df_sorted = summary_df[summary_df['Leads (Conexión Enviada)'] >= 3].sort_values(by='Tasa Reunión (Global %)', ascending=False).head(15)
             if not summary_df_sorted.empty:
                fig = px.bar(summary_df_sorted, x=group_by_col, y='Tasa Reunión (Global %)',
                             title=f"Tasa de Reunión Global por {group_by_col}",
                             text='Tasa Reunión (Global %)', color='Tasa Reunión (Global %)')
                fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig.update_layout(yaxis_title="Tasa Reunión Global (%)", xaxis_title=group_by_col, yaxis_ticksuffix="%")
                st.plotly_chart(fig, use_container_width=True)
             else:
                st.caption("No hay suficientes datos (>3 leads por grupo) para graficar la tasa de reunión.")
    else:
        st.info(f"No hay datos suficientes para desglosar por {group_by_col}.")

# (display_time_evolution permanece igual en lógica, solo cambia el nombre de la columna base)
def display_time_evolution(df_filtered, time_col_agg, time_col_label, chart_title, x_axis_label, chart_icon="📈"):
    """Muestra la evolución temporal de los KPIs clave."""
    st.markdown(f"### {chart_icon} {chart_title}")

    kpi_cols_to_sum = [COL_CONTACTED_BOOL, COL_RESPONDED_BOOL, COL_MEETING_BOOL]
    kpi_cols_present = [col for col in kpi_cols_to_sum if col in df_filtered.columns]

    if (time_col_agg not in df_filtered.columns) or (not kpi_cols_present):
        st.info(f"Datos insuficientes para la evolución por {x_axis_label.lower()}.")
        return

    # Contar leads (conexiones enviadas) por período
    df_agg_time_leads = df_filtered.groupby(time_col_agg, as_index=False).size().rename(columns={'size': 'Leads (Conexión Enviada)'})
    # Sumar los otros KPIs
    df_agg_time_kpis = df_filtered.groupby(time_col_agg, as_index=False)[kpi_cols_present].sum()

    # Unir ambas
    df_agg_time = pd.merge(df_agg_time_leads, df_agg_time_kpis, on=time_col_agg, how='left').fillna(0) # Rellenar con 0 si un KPI no aparece en un período

    if time_col_agg == 'NumSemana' and 'Año' in df_filtered.columns:
        # Repetir agrupación para incluir el Año
        df_agg_time_leads_yr = df_filtered.groupby(['Año', 'NumSemana'], as_index=False).size().rename(columns={'size': 'Leads (Conexión Enviada)'})
        df_agg_time_kpis_yr = df_filtered.groupby(['Año', 'NumSemana'], as_index=False)[kpi_cols_present].sum()
        df_agg_time_year = pd.merge(df_agg_time_leads_yr, df_agg_time_kpis_yr, on=['Año', 'NumSemana'], how='left').fillna(0)

        df_agg_time_year[time_col_label] = df_agg_time_year['Año'].astype(str) + '-S' + df_agg_time_year['NumSemana'].astype(str).str.zfill(2)
        df_agg_time = df_agg_time_year.sort_values(by=['Año', 'NumSemana'])
    else: # Para AñoMes
        df_agg_time[time_col_label] = df_agg_time[time_col_agg]
        df_agg_time = df_agg_time.sort_values(by=time_col_label)

    # Renombrar para el gráfico
    df_agg_time.rename(columns={
        'Contacted_Bool': 'Contactados',
        'Responded_Bool': 'Respondieron',
        'Meeting_Bool': 'Reuniones'
    }, inplace=True)

    kpis_for_chart = [col for col in ['Leads (Conexión Enviada)', 'Contactados', 'Respondieron', 'Reuniones'] if col in df_agg_time.columns]

    if df_agg_time.empty:
        st.info(f"No hay datos agregados para la evolución por {x_axis_label.lower()}.")
        return

    # Gráfico de líneas
    fig_time = px.line(df_agg_time, x=time_col_label, y=kpis_for_chart,
                       title=f"Evolución de KPIs por {x_axis_label}",
                       labels={time_col_label: x_axis_label, 'value': 'Cantidad'},
                       markers=True)
    fig_time.update_xaxes(type='category')
    st.plotly_chart(fig_time, use_container_width=True)


# --- Flujo Principal de la Página ---
st.title("📊 KPIs Pipeline (Prospects)")
st.markdown("Métricas clave del embudo de ventas, comenzando desde 'Conection Sent Date'.")

# Cargar datos (ya incluye el filtro base por Conection Sent Date)
df_pipeline_base = load_pipeline_data()

# Solo continuar si hay datos después del filtro base
if df_pipeline_base.empty:
    st.error("Fallo Crítico: No se pudieron cargar datos del Pipeline con 'Conection Sent Date' válidas. El dashboard no puede continuar.")
    # Mostrar filtros vacíos para evitar errores, pero no hacer nada más
    sidebar_filters_pipeline_kpi(pd.DataFrame()) # Pasar DF vacío
    st.stop() # Detener ejecución

# Mostrar filtros y obtener selecciones (ahora sobre datos pre-filtrados)
(start_f, end_f, year_f, week_f,
 industry_f, company_f, management_f) = sidebar_filters_pipeline_kpi(df_pipeline_base.copy())

# Aplicar filtros de sidebar
df_pipeline_filtered = apply_pipeline_kpi_filters(
    df_pipeline_base.copy(), start_f, end_f, year_f, week_f,
    industry_f, company_f, management_f
)

# Mostrar KPIs y Desgloses
display_pipeline_kpi_summary_metrics(df_pipeline_filtered)
st.markdown("---")

# Desgloses por Dimensiones
display_pipeline_grouped_breakdown(df_pipeline_filtered, COL_INDUSTRY, "Desglose por Industria", chart_icon="🏭")
st.markdown("---")
display_pipeline_grouped_breakdown(df_pipeline_filtered, COL_COMPANY, "Desglose por Compañía (Top 15)", chart_icon="🏢")
st.markdown("---")
display_pipeline_grouped_breakdown(df_pipeline_filtered, COL_MANAGEMENT_LEVEL, "Desglose por Management Level", chart_icon="🧑‍💼")
st.markdown("---")

# Evoluciones Temporales
display_time_evolution(df_pipeline_filtered, 'AñoMes', 'Año-Mes', "Evolución Mensual de KPIs", "Mes")
st.markdown("---")
display_time_evolution(df_pipeline_filtered, 'NumSemana', 'Año-Semana', "Evolución Semanal de KPIs", "Semana")
st.markdown("---")


# Mostrar Tabla Detallada (Opcional)
with st.expander("Ver Tabla de Datos Detallados Filtrados"):
    # Añadir columna Conection Sent Date formateada si no existe para visualización
    df_display = df_pipeline_filtered.copy()
    if COL_DATE_FILTER in df_display.columns and pd.api.types.is_datetime64_any_dtype(df_display[COL_DATE_FILTER]):
         df_display[f'{COL_DATE_FILTER} (Fmt)'] = df_display[COL_DATE_FILTER].dt.strftime('%d/%m/%Y')
    st.dataframe(df_display, use_container_width=True)

# Pie de página
st.markdown("---")
st.info("Dashboard de KPIs del Pipeline (Base: Conection Sent Date).")

