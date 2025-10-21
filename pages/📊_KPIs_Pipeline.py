# pages/📊_KPIs_Pipeline.py
import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import plotly.graph_objects as go # Para el embudo
import datetime
import sys
import os

# --- Añadir raíz del proyecto al path (importante para importar módulos) ---
try:
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError: # Fallback si __file__ no está definido
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# --- IMPORTS DE TU PROYECTO ---
# (Asegúrate de que las rutas sean correctas respecto a la carpeta 'pages')
try:
    from utils.limpieza import limpiar_valor_kpi # Reutilizamos tu función de limpieza si aplica
    from componentes.tabla_prospectos import mostrar_tabla_filtrada # Reutilizamos tu componente de tabla
    # Podríamos añadir más componentes si fuera necesario (ej. filtros_sidebar si lo refactorizamos)
except ImportError as e:
    st.error(f"Error importando módulos del proyecto: {e}")
    st.info("Asegúrate de que la estructura de carpetas sea correcta y los archivos __init__.py existan si son necesarios.")
    st.stop()

# --- Configuración de la Página ---
st.set_page_config(
    page_title="KPIs Pipeline (Prospects)",
    page_icon=" BPN",
    layout="wide"
)

# --- Constantes y Mapeo de Columnas (Adaptado a tu hoja 'Prospects') ---
# Nombres exactos de las columnas en tu hoja 'Prospects'
COL_COMPANY = "Company"
COL_FULL_NAME = "Full Name"
COL_ROLE = "Role/Title"
COL_MANAGEMENT = "Management Level"
COL_INDUSTRY = "Industry"
COL_LEAD_DATE = "Lead Generated (Date)"
COL_CONTACTED = "Contacted?"
COL_RESPONDED = "Responded?"
COL_RESPONSE_CHANNEL = "Response Channel"
COL_MEETING = "Meeting?"
COL_MEETING_DATE = "Meeting Date"
COL_FIRST_CONTACT = "First Contact Date"
COL_LAST_CONTACT = "Last Contact Date"
# ... puedes añadir más columnas si las necesitas para filtros o análisis

# Claves de Estado de Sesión para Filtros (con prefijo único para esta página)
FILTER_KEYS_PREFIX = "pipeline_page_v1_"
PIPE_START_DATE_KEY = f"{FILTER_KEYS_PREFIX}start_date"
PIPE_END_DATE_KEY = f"{FILTER_KEYS_PREFIX}end_date"
PIPE_INDUSTRY_FILTER_KEY = f"{FILTER_KEYS_PREFIX}industry"
PIPE_COMPANY_FILTER_KEY = f"{FILTER_KEYS_PREFIX}company"
PIPE_CONTACTED_FILTER_KEY = f"{FILTER_KEYS_PREFIX}contacted"
PIPE_RESPONDED_FILTER_KEY = f"{FILTER_KEYS_PREFIX}responded"
PIPE_MEETING_FILTER_KEY = f"{FILTER_KEYS_PREFIX}meeting"
PIPE_BUSQUEDA_KEY = f"{FILTER_KEYS_PREFIX}busqueda"

# --- Carga y Limpieza de Datos ---
@st.cache_data(ttl=600) # Cache de 10 minutos
def load_pipeline_data():
    WORKSHEET_NAME = "Prospects"
    try:
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)
    except Exception as e:
        st.error(f"Error al autenticar con Google (gcp_service_account): {e}")
        st.stop()

    try:
        sheet_url = st.secrets["prospects_sheet_url"] # Asegúrate que este secret exista
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(WORKSHEET_NAME)
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos de la hoja '{WORKSHEET_NAME}'.")
            return pd.DataFrame()
        headers = raw_data[0]
        rows = raw_data[1:]
        cleaned_rows = [row for row in rows if any(cell.strip() for cell in row)]
        num_cols = len(headers)
        cleaned_rows_padded = []
        for row in cleaned_rows:
            row_len = len(row)
            if row_len < num_cols: row.extend([''] * (num_cols - row_len))
            cleaned_rows_padded.append(row[:num_cols])
        df = pd.DataFrame(cleaned_rows_padded, columns=headers)
    except KeyError:
        st.error("Error de Configuración: Falta 'prospects_sheet_url' en los 'Secrets'.")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Error: No se encontró la hoja '{WORKSHEET_NAME}'.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja '{WORKSHEET_NAME}': {e}")
        st.stop()

    # --- Limpieza Específica para 'Prospects' ---
    # Convertir booleanos (TRUE/FALSE como strings)
    bool_cols_map = {COL_CONTACTED: 'Contacted_Bool', COL_RESPONDED: 'Responded_Bool'}
    for original, new in bool_cols_map.items():
        if original in df.columns:
            df[new] = df[original].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)
        else:
            df[new] = False # Crear columna con False si no existe

    # Limpiar Meeting? (Yes/No)
    COL_MEETING_BOOL = "Meeting_Bool"
    if COL_MEETING in df.columns:
        df[COL_MEETING_BOOL] = df[COL_MEETING].apply(lambda x: True if str(x).strip().upper() == 'YES' else False)
    else:
        df[COL_MEETING_BOOL] = False

    # Convertir fechas (asumiendo D/M/YYYY o formatos reconocibles)
    date_cols_pipeline = [COL_LEAD_DATE, COL_FIRST_CONTACT, COL_LAST_CONTACT, COL_MEETING_DATE]
    for col in date_cols_pipeline:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True) # dayfirst=True si es D/M/YYYY
        else:
            df[col] = pd.NaT # Crear columna NaT si no existe

    # Limpiar columnas de texto importantes
    text_cols_clean = [COL_COMPANY, COL_INDUSTRY, COL_RESPONSE_CHANNEL, COL_FULL_NAME, COL_ROLE]
    for col in text_cols_clean:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().fillna("N/D")
            df.loc[df[col] == '', col] = "N/D" # Reemplazar vacíos después de strip
        else:
            df[col] = "N/D" # Crear columna N/D si no existe

    # Crear columnas de tiempo para filtros (si COL_LEAD_DATE existe y es válida)
    if COL_LEAD_DATE in df.columns and pd.api.types.is_datetime64_any_dtype(df[COL_LEAD_DATE]):
         df_valid_dates = df.dropna(subset=[COL_LEAD_DATE])
         if not df_valid_dates.empty:
            df['Año'] = df_valid_dates[COL_LEAD_DATE].dt.year
            df['MesNum'] = df_valid_dates[COL_LEAD_DATE].dt.month
            df['AñoMes'] = df_valid_dates[COL_LEAD_DATE].dt.strftime('%Y-%m')
            # Llenar NaNs en las columnas de tiempo para el resto del df
            df['Año'] = df['Año'].fillna(0).astype(int) # O algún valor por defecto
            df['MesNum'] = df['MesNum'].fillna(0).astype(int)
            df['AñoMes'] = df['AñoMes'].fillna('N/D')
         else: # Si todas las fechas son NaT
             df['Año'], df['MesNum'], df['AñoMes'] = 0, 0, 'N/D'
    else: # Si la columna de fecha no existe o no es tipo fecha
        st.warning(f"Columna '{COL_LEAD_DATE}' no encontrada o no es de tipo fecha. No se pueden crear filtros de Año/Mes.")
        df['Año'], df['MesNum'], df['AñoMes'] = 0, 0, 'N/D'

    return df

# --- Funciones de Filtros (Adaptadas de tu proyecto) ---
def reset_pipeline_filters_state():
    st.session_state[PIPE_START_DATE_KEY] = None
    st.session_state[PIPE_END_DATE_KEY] = None
    st.session_state[PIPE_INDUSTRY_FILTER_KEY] = ["– Todos –"]
    st.session_state[PIPE_COMPANY_FILTER_KEY] = ["– Todos –"]
    st.session_state[PIPE_CONTACTED_FILTER_KEY] = "– Todos –"
    st.session_state[PIPE_RESPONDED_FILTER_KEY] = "– Todos –"
    st.session_state[PIPE_MEETING_FILTER_KEY] = "– Todos –"
    st.session_state[PIPE_BUSQUEDA_KEY] = ""
    st.toast("Filtros del Pipeline reiniciados ✅")

def crear_multiselect_pipeline(df, columna, etiqueta, key):
    # Similar a tu función, adaptada para esta página
    if key not in st.session_state: st.session_state[key] = ["– Todos –"]
    options = ["– Todos –"]
    if columna in df.columns and not df[columna].dropna().empty:
        options.extend(sorted(df[columna].astype(str).unique()))
    current_value = st.session_state[key]
    # Simple validación: si el valor guardado no es una lista o está vacío, resetea
    if not isinstance(current_value, list) or not current_value:
        st.session_state[key] = ["– Todos –"]
    # Asegurar que las selecciones aún existan en las opciones actuales
    valid_selection = [v for v in current_value if v in options]
    if not valid_selection: valid_selection = ["– Todos –"] # Si ninguna selección es válida, resetea
    if valid_selection != current_value: st.session_state[key] = valid_selection

    return st.multiselect(etiqueta, options, key=key) # Streamlit usa el valor de session_state[key] como default

def crear_selectbox_pipeline(df, columna, etiqueta, key, options_override=None):
    # Similar a tu función, adaptada para esta página
    if key not in st.session_state: st.session_state[key] = "– Todos –"
    if options_override:
        options = options_override
    else:
        options = ["– Todos –"]
        if columna in df.columns and not df[columna].dropna().empty:
             options.extend(sorted(df[columna].astype(str).unique()))

    current_value = st.session_state[key]
    if current_value not in options: # Si el valor guardado ya no es válido
        st.session_state[key] = "– Todos –"

    # Streamlit usa session_state[key] como 'value' implícitamente si 'key' es pasado
    return st.selectbox(etiqueta, options, key=key)

def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")
    st.sidebar.markdown("---")

    # Inicializar estado si es necesario (ya debería estar hecho al inicio)
    for k, v in {
        PIPE_INDUSTRY_FILTER_KEY: ["– Todos –"], PIPE_COMPANY_FILTER_KEY: ["– Todos –"],
        PIPE_CONTACTED_FILTER_KEY: "– Todos –", PIPE_RESPONDED_FILTER_KEY: "– Todos –",
        PIPE_MEETING_FILTER_KEY: "– Todos –", PIPE_BUSQUEDA_KEY: ""
    }.items():
        if k not in st.session_state: st.session_state[k] = v
    if PIPE_START_DATE_KEY not in st.session_state: st.session_state[PIPE_START_DATE_KEY] = None
    if PIPE_END_DATE_KEY not in st.session_state: st.session_state[PIPE_END_DATE_KEY] = None

    # Filtros de Atributos
    st.sidebar.subheader("Atributos del Prospecto")
    crear_multiselect_pipeline(df_options, COL_INDUSTRY, "Industria", PIPE_INDUSTRY_FILTER_KEY)
    crear_multiselect_pipeline(df_options, COL_COMPANY, "Compañía", PIPE_COMPANY_FILTER_KEY)

    # Filtros de Estado (Booleanos)
    st.sidebar.subheader("Estado en el Embudo")
    bool_options = ["– Todos –", "Sí", "No"]
    # Para usar el selectbox, necesitamos mapear True/False a Sí/No internamente
    crear_selectbox_pipeline(df_options, COL_CONTACTED, "Contactado?", PIPE_CONTACTED_FILTER_KEY, options_override=bool_options)
    crear_selectbox_pipeline(df_options, COL_RESPONDED, "Respondió?", PIPE_RESPONDED_FILTER_KEY, options_override=bool_options)
    crear_selectbox_pipeline(df_options, COL_MEETING, "Reunión Agendada?", PIPE_MEETING_FILTER_KEY, options_override=bool_options)

    # Filtros de Fecha (usando COL_LEAD_DATE)
    st.sidebar.subheader("Fecha de Generación del Lead")
    min_date_lead, max_date_lead = None, None
    if COL_LEAD_DATE in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options[COL_LEAD_DATE]):
        valid_dates = df_options[COL_LEAD_DATE].dropna()
        if not valid_dates.empty:
            min_date_lead = valid_dates.min().date()
            max_date_lead = valid_dates.max().date()
    col_f1, col_f2 = st.sidebar.columns(2)
    with col_f1:
        st.date_input("Desde", format='DD/MM/YYYY', key=PIPE_START_DATE_KEY, min_value=min_date_lead, max_value=max_date_lead)
    with col_f2:
        st.date_input("Hasta", format='DD/MM/YYYY', key=PIPE_END_DATE_KEY, min_value=min_date_lead, max_value=max_date_lead)

    # Búsqueda por Texto
    st.sidebar.subheader("Búsqueda por Texto")
    st.text_input("Buscar (Nombre, Rol, Compañía)", key=PIPE_BUSQUEDA_KEY)

    # Botón Limpiar
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Filtros", on_click=reset_pipeline_filters_state, use_container_width=True)

    # Devolver valores directamente del estado de sesión
    return (
        st.session_state[PIPE_START_DATE_KEY], st.session_state[PIPE_END_DATE_KEY],
        st.session_state[PIPE_INDUSTRY_FILTER_KEY], st.session_state[PIPE_COMPANY_FILTER_KEY],
        st.session_state[PIPE_CONTACTED_FILTER_KEY], st.session_state[PIPE_RESPONDED_FILTER_KEY],
        st.session_state[PIPE_MEETING_FILTER_KEY], st.session_state[PIPE_BUSQUEDA_KEY]
    )

def apply_pipeline_filters(df, start_dt, end_dt, industry_list, company_list, contacted_sel, responded_sel, meeting_sel, busqueda_txt):
    df_f = df.copy()

    # Filtros Multi-select
    if industry_list and "– Todos –" not in industry_list:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industry_list)]
    if company_list and "– Todos –" not in company_list:
        df_f = df_f[df_f[COL_COMPANY].isin(company_list)]

    # Filtros Selectbox (Booleanos) - Mapear Sí/No a True/False
    if contacted_sel != "– Todos –":
        contacted_bool = True if contacted_sel == "Sí" else False
        df_f = df_f[df_f['Contacted_Bool'] == contacted_bool]
    if responded_sel != "– Todos –":
        responded_bool = True if responded_sel == "Sí" else False
        df_f = df_f[df_f['Responded_Bool'] == responded_bool]
    if meeting_sel != "– Todos –":
        meeting_bool = True if meeting_sel == "Sí" else False
        df_f = df_f[df_f['Meeting_Bool'] == meeting_bool]

    # Filtro de Fecha (COL_LEAD_DATE)
    if start_dt and end_dt and COL_LEAD_DATE in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f[COL_LEAD_DATE]):
        # Asegurarse que start_dt y end_dt sean solo date
        start_date_only = start_dt # st.date_input ya devuelve date
        end_date_only = end_dt
        # Comparar solo la parte de fecha de la columna
        df_f = df_f[(df_f[COL_LEAD_DATE].dt.date >= start_date_only) & (df_f[COL_LEAD_DATE].dt.date <= end_date_only)]
    elif start_dt and COL_LEAD_DATE in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f[COL_LEAD_DATE]):
         start_date_only = start_dt
         df_f = df_f[df_f[COL_LEAD_DATE].dt.date >= start_date_only]
    elif end_dt and COL_LEAD_DATE in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f[COL_LEAD_DATE]):
         end_date_only = end_dt
         df_f = df_f[df_f[COL_LEAD_DATE].dt.date <= end_date_only]


    # Filtro Búsqueda Texto
    if busqueda_txt:
        term = busqueda_txt.lower().strip()
        search_cols = [COL_FULL_NAME, COL_ROLE, COL_COMPANY]
        mask = pd.Series([False] * len(df_f), index=df_f.index)
        for col in search_cols:
            if col in df_f.columns:
                mask |= df_f[col].astype(str).str.lower().str.contains(term, na=False)
        df_f = df_f[mask]

    return df_f

# --- Funciones de Visualización (Adaptadas) ---
def display_pipeline_kpi_summary(df_filtered):
    st.header("KPIs del Embudo (Pipeline) 📈")
    if df_filtered.empty:
        st.info("No hay datos para mostrar KPIs con los filtros actuales.")
        return

    total_leads = len(df_filtered)
    total_contacted = df_filtered['Contacted_Bool'].sum()
    total_responded = df_filtered['Responded_Bool'].sum()
    total_meetings = df_filtered['Meeting_Bool'].sum()

    # Tasas
    contact_rate = (total_contacted / total_leads) * 100 if total_leads > 0 else 0
    response_rate = (total_responded / total_contacted) * 100 if total_contacted > 0 else 0
    meeting_rate = (total_meetings / total_responded) * 100 if total_responded > 0 else 0

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric("Total Leads Filtrados", f"{total_leads:,.0f}")
    with col2: st.metric("Tasa Contacto", f"{contact_rate:.1f}%", help=f"{total_contacted:,.0f} contactados")
    with col3: st.metric("Tasa Respuesta (s/ Contactados)", f"{response_rate:.1f}%", help=f"{total_responded:,.0f} respondieron")
    with col4: st.metric("Tasa Reunión (s/ Respondieron)", f"{meeting_rate:.1f}%", help=f"{total_meetings:,.0f} reuniones")

def display_pipeline_funnel(df_filtered):
    st.header("Embudo de Conversión (Pipeline) 🚀")
    if df_filtered.empty:
        st.info("No hay datos para mostrar el embudo con los filtros actuales.")
        return

    total_leads = len(df_filtered)
    total_contacted = df_filtered['Contacted_Bool'].sum()
    total_responded = df_filtered['Responded_Bool'].sum()
    total_meetings = df_filtered['Meeting_Bool'].sum()

    # Crear DataFrame para el embudo
    funnel_data = pd.DataFrame({
        "Etapa": ["Leads Filtrados", "Contactados", "Respondieron", "Reuniones Agendadas"],
        "Cantidad": [total_leads, total_contacted, total_responded, total_meetings]
    })

    fig = go.Figure(go.Funnel(
        y = funnel_data["Etapa"],
        x = funnel_data["Cantidad"],
        textposition = "inside",
        textinfo = "value+percent initial" # Muestra valor y % respecto al inicio
        # marker = {"color": ["#FECB52", "#FEA152", "#FE8652", "#FE6B52"]} # Colores ejemplo
    ))
    fig.update_layout(title="Visualización del Embudo")
    st.plotly_chart(fig, use_container_width=True)

def display_charts(df_filtered):
    st.header("Análisis Gráfico 📊")
    if df_filtered.empty:
        st.info("No hay datos para mostrar gráficos con los filtros actuales.")
        return

    viz1, viz2 = st.columns(2)

    with viz1:
        st.subheader("Canales de Respuesta Más Efectivos")
        responded_df = df_filtered[df_filtered['Responded_Bool'] == True]
        if not responded_df.empty and COL_RESPONSE_CHANNEL in responded_df.columns:
            channel_data = responded_df[COL_RESPONSE_CHANNEL].value_counts().reset_index()
            channel_data.columns = ['Canal', 'Cantidad']
            if not channel_data.empty:
                fig_pie = px.pie(channel_data, names='Canal', values='Cantidad', title="Distribución de Respuestas por Canal")
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
            else: st.info("No hay datos de canales de respuesta.")
        else: st.info("No hay respuestas registradas o falta la columna de canal.")

    with viz2:
        st.subheader("Top Industrias por Leads")
        if COL_INDUSTRY in df_filtered.columns:
            industry_counts = df_filtered[COL_INDUSTRY].value_counts().reset_index()
            industry_counts.columns = ['Industria', 'Cantidad']
            if not industry_counts.empty:
                fig_bar = px.bar(industry_counts.head(10), # Top 10
                                 x='Industria', y='Cantidad', title="Volumen de Leads por Industria (Top 10)")
                st.plotly_chart(fig_bar, use_container_width=True)
            else: st.info("No hay datos de industria.")
        else: st.info("Columna 'Industria' no encontrada.")

    # Gráfico de Tendencia Temporal (Leads Generados)
    if COL_LEAD_DATE in df_filtered.columns and not df_filtered[COL_LEAD_DATE].dropna().empty:
        st.subheader("Tendencia de Generación de Leads")
        df_time = df_filtered.dropna(subset=[COL_LEAD_DATE]).copy()
        df_time = df_time.set_index(COL_LEAD_DATE)
        # Resample por semana (W) o mes (M). Usaremos Mes (M) para empezar
        leads_over_time = df_time.resample('M').size().reset_index(name='Nuevos Leads')
        # Asegurar que la columna de fecha sea string para plotly si hay problemas
        leads_over_time[COL_LEAD_DATE] = leads_over_time[COL_LEAD_DATE].dt.strftime('%Y-%m')

        if not leads_over_time.empty:
            fig_line = px.line(leads_over_time, x=COL_LEAD_DATE, y='Nuevos Leads', title='Leads Generados por Mes', markers=True)
            fig_line.update_layout(xaxis_title="Mes", yaxis_title="Cantidad de Leads")
            st.plotly_chart(fig_line, use_container_width=True)
        else: st.info("No hay datos suficientes para mostrar la tendencia temporal.")
    else: st.info(f"No hay fechas válidas en '{COL_LEAD_DATE}' para mostrar tendencia.")


# --- Flujo Principal de la Página ---
st.title("📊 Dashboard KPIs Pipeline (Prospects)")
st.markdown("Análisis del embudo de ventas basado en la hoja 'Prospects'.")

# Cargar datos
df_pipeline_base = load_pipeline_data()

if df_pipeline_base.empty:
    st.error("No se pudieron cargar o procesar los datos del pipeline. Revisa la configuración y la hoja 'Prospects'.")
    st.stop()

# Mostrar filtros y obtener selecciones
(start_f, end_f, industry_f, company_f,
 contacted_f, responded_f, meeting_f, busqueda_f) = sidebar_filters_pipeline(df_pipeline_base.copy())

# Aplicar filtros
df_pipeline_filtered = apply_pipeline_filters(
    df_pipeline_base.copy(), start_f, end_f, industry_f, company_f,
    contacted_f, responded_f, meeting_f, busqueda_f
)

# Mostrar KPIs y Visualizaciones
display_pipeline_kpi_summary(df_pipeline_filtered)
st.markdown("---")
display_pipeline_funnel(df_pipeline_filtered)
st.markdown("---")
display_charts(df_pipeline_filtered)
st.markdown("---")

# Mostrar Tabla Detallada (Usando tu componente)
st.header("Detalle de Prospectos Filtrados 🕵️")
# Asegúrate de pasar las columnas correctas a tu componente si es necesario
# La función mostrar_tabla_filtrada maneja la selección de columnas internamente
mostrar_tabla_filtrada(df_pipeline_filtered.copy(), key_suffix="pipeline") # Usamos un sufijo único

