import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials # Tu código usa esta
import datetime
import plotly.express as px
import os
import sys
import io

# --- Configuración Inicial del Proyecto y Título de la Página ---
# Comentado, asumiendo que el path principal se maneja en 🏠_Dashboard_Principal.py
# try:
#     project_root = os.path.abspath(
#         os.path.join(os.path.dirname(__file__), os.pardir))
#     if project_root not in sys.path:
#         sys.path.insert(0, project_root)
# except NameError:
#     project_root = os.getcwd()
#     if project_root not in sys.path:
#         sys.path.insert(0, project_root)

st.set_page_config(layout="wide", page_title="Análisis de Sesiones y SQL")
st.title("📊 Análisis de Sesiones y Calificaciones SQL")
st.markdown(
    "Métricas por LG, AE, País, Calificación SQL (SQL1 > SQL2 > MQL > NA > Sin Calificación), Puesto y Empresa."
)

# --- Constantes ---
# CREDS_PATH ya no se usará directamente, pero mantenemos las otras constantes
# CREDS_PATH = "credenciales.json" # Ya no se usa
SHEET_URL_SESIONES_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902"
SHEET_NAME_SESIONES = "Sesiones 2024-2025" # Asegúrate que este sea el nombre exacto de tu pestaña

COLUMNAS_ESPERADAS = [
    "Semana", "Mes", "Fecha", "SQL", "Empresa", "País", "Nombre", "Apellido",
    "Puesto", "Email", "AE", "LG", "Siguientes Pasos", "RPA"
]
COLUMNAS_DERIVADAS = [
    'Año', 'NumSemana', 'MesNombre', 'AñoMes', 'SQL_Estandarizado'
]
SQL_ORDER_OF_IMPORTANCE = ['SQL1', 'SQL2', 'MQL', 'NA', 'SIN CALIFICACIÓN SQL']

# --- Gestión de Estado de Sesión para Filtros ---
# (Tu código original para FILTER_KEYS_PREFIX, etc.)
FILTER_KEYS_PREFIX = "sesiones_sql_lg_pais_page_v1_"
SES_START_DATE_KEY = f"{FILTER_KEYS_PREFIX}start_date"
SES_END_DATE_KEY = f"{FILTER_KEYS_PREFIX}end_date"
SES_AE_FILTER_KEY = f"{FILTER_KEYS_PREFIX}ae"
SES_LG_FILTER_KEY = f"{FILTER_KEYS_PREFIX}lg"
SES_PAIS_FILTER_KEY = f"{FILTER_KEYS_PREFIX}pais"
SES_YEAR_FILTER_KEY = f"{FILTER_KEYS_PREFIX}year"
SES_WEEK_FILTER_KEY = f"{FILTER_KEYS_PREFIX}week"
SES_SQL_FILTER_KEY = f"{FILTER_KEYS_PREFIX}sql_val"

default_filters_config = {
    SES_START_DATE_KEY: None,
    SES_END_DATE_KEY: None,
    SES_AE_FILTER_KEY: ["– Todos –"],
    SES_LG_FILTER_KEY: ["– Todos –"],
    SES_PAIS_FILTER_KEY: ["– Todos –"],
    SES_YEAR_FILTER_KEY: "– Todos –",
    SES_WEEK_FILTER_KEY: ["– Todas –"],
    SES_SQL_FILTER_KEY: ["– Todos –"]
}
for key, value in default_filters_config.items():
    if key not in st.session_state: st.session_state[key] = value


# --- Funciones de Utilidad ---
# (Tu función parse_date_robust original)
def parse_date_robust(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "": return None
    try:
        return pd.to_datetime(date_val, format='%d/%m/%Y', errors='raise')
    except ValueError:
        try:
            return pd.to_datetime(date_val, errors='raise')
        except Exception:
            return None
    except Exception:
        return None


@st.cache_data(ttl=300)
def load_sesiones_data():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # --- INICIO DEL CAMBIO: Cargar credenciales desde Streamlit Secrets ---
    try:
        creds_dict = {
            "type": st.secrets["google_sheets_credentials"]["type"],
            "project_id": st.secrets["google_sheets_credentials"]["project_id"],
            "private_key_id": st.secrets["google_sheets_credentials"]["private_key_id"],
            "private_key": st.secrets["google_sheets_credentials"]["private_key"], # Asume comillas triples en TOML
            "client_email": st.secrets["google_sheets_credentials"]["client_email"],
            "client_id": st.secrets["google_sheets_credentials"]["client_id"],
            "auth_uri": st.secrets["google_sheets_credentials"]["auth_uri"],
            "token_uri": st.secrets["google_sheets_credentials"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["google_sheets_credentials"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["google_sheets_credentials"]["client_x509_cert_url"],
            "universe_domain": st.secrets["google_sheets_credentials"]["universe_domain"]
        }
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
    except KeyError as e:
        st.error(f"Error: Falta la clave '{e}' en los 'Secrets' de Streamlit (Sesiones). Verifica la configuración.")
        # Retornar un DataFrame vacío con la estructura esperada para evitar más errores en la UI
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS) 
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets para Sesiones vía Secrets: {e}")
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)
    # --- FIN DEL CAMBIO ---

    # Opcional: Leer URL de la hoja desde secrets
    sheet_url_sesiones_actual = st.secrets.get(
        "SESIONES_SHEET_URL", # Nombre del secret si lo defines
        SHEET_URL_SESIONES_DEFAULT # Tu constante original como valor por defecto
    )

    try:
        workbook = client.open_by_url(sheet_url_sesiones_actual)
        try:
            sheet = workbook.worksheet(SHEET_NAME_SESIONES)
        except gspread.exceptions.WorksheetNotFound:
            st.error(f"Pestaña '{SHEET_NAME_SESIONES}' no encontrada en la hoja de Sesiones: {sheet_url_sesiones_actual}")
            return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)
        
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <=1: # Si no hay datos o solo encabezados
            st.error(f"Pestaña '{SHEET_NAME_SESIONES}' vacía o solo con encabezados.")
            return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)

        headers_cleaned = [str(h).strip() for h in raw_data[0]]
        # final_df_headers = [h for h in headers_cleaned if h] # Esta línea podría ser problemática si tienes columnas vacías intencionalmente
        final_df_headers = headers_cleaned # Usar todos los encabezados limpiados
        
        # Ajustar filas al número de encabezados para evitar errores si hay más datos que encabezados
        num_headers = len(final_df_headers)
        data_rows = [row[:num_headers] for row in raw_data[1:]]
        df = pd.DataFrame(data_rows, columns=final_df_headers)

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error Crítico: Hoja de Sesiones no encontrada en la URL: {sheet_url_sesiones_actual}")
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)
    except gspread.exceptions.APIError as e: # Capturar errores específicos de la API de Google
        st.error(f"Error Crítico API Google (Sesiones): {e}")
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)
    except Exception as e: # Captura general para otros errores de carga
        st.error(f"Error inesperado en carga de datos de Sesiones: {e}")
        # st.exception(e) # Descomentar para depuración detallada si es necesario
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)


    # --- Inicio de tu lógica de procesamiento de datos (se mantiene igual) ---
    if "Fecha" not in df.columns:
        st.error("Columna 'Fecha' no encontrada en datos de Sesiones.")
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)
    df["Fecha"] = df["Fecha"].apply(parse_date_robust)
    df.dropna(subset=["Fecha"], inplace=True)
    if df.empty:
        st.warning("No hay sesiones con fechas válidas después de la conversión.")
        return pd.DataFrame(columns=COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)

    df['Año'] = df['Fecha'].dt.year.astype('Int64')
    df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype('Int64')
    df['MesNombre'] = df['Fecha'].dt.month_name()
    df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')

    if "SQL" not in df.columns: df["SQL"] = ""
    df['SQL_Estandarizado'] = df['SQL'].astype(str).str.strip().str.upper()
    known_sql_values = [
        s for s in SQL_ORDER_OF_IMPORTANCE if s != 'SIN CALIFICACIÓN SQL'
    ]
    mask_empty_sql = ~df['SQL_Estandarizado'].isin(known_sql_values) & (
        df['SQL_Estandarizado'].isin(['', 'NAN', 'NONE', 'NA']) # Añadido NA por si acaso
        | df['SQL_Estandarizado'].isna())
    df.loc[mask_empty_sql, 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'
    df.loc[df['SQL_Estandarizado'] == '', 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'

    for col_actor, default_actor_name in [("AE", "No Asignado AE"),
                                          ("LG", "No Asignado LG")]:
        if col_actor not in df.columns: df[col_actor] = default_actor_name
        df[col_actor] = df[col_actor].astype(str).str.strip()
        df.loc[df[col_actor].isin(['', 'nan', 'none', 'NaN', 'None']), # Considerar 'NA' también si es un valor posible
               col_actor] = default_actor_name

    for col_clean in ["Puesto", "Empresa", "País"]: # Y otras que necesiten limpieza
        if col_clean not in df.columns: df[col_clean] = "No Especificado"
        df[col_clean] = df[col_clean].astype(str).str.strip()
        df.loc[df[col_clean].isin(['', 'nan', 'none', 'NaN', 'None']), # Considerar 'NA'
               col_clean] = 'No Especificado'

    # Crear df_final asegurando todas las columnas esperadas y derivadas
    df_final = pd.DataFrame()
    # Usar set para asegurar columnas únicas si hay solapamiento entre esperadas y derivadas
    all_final_cols = list(set(COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS)) 
    
    for col in all_final_cols:
        if col in df.columns: 
            df_final[col] = df[col]
        else:
            # Si la columna original esperada no está, se crea vacía
            # if col in COLUMNAS_ESPERADAS and col not in df.columns:
            #     st.warning(f"Col. original '{col}' no encontrada en datos de Sesiones. Se creará vacía.")
            
            # Definir tipos por defecto para columnas que podrían faltar
            if col in ['Año', 'NumSemana']:
                df_final[col] = pd.Series(dtype='Int64')
            elif col == 'Fecha':
                df_final[col] = pd.Series(dtype='datetime64[ns]')
            else: # Para otras columnas (strings, objetos)
                df_final[col] = pd.Series(dtype='object')
    return df_final
    # --- Fin de tu lógica de procesamiento de datos ---

# --- El resto de tus funciones y flujo principal de la página se mantiene igual ---
# (Tu código original para clear_ses_filters_callback, sidebar_filters_sesiones, apply_sesiones_filters, 
#  get_sql_category_order, display_sesiones_summary_sql, display_analisis_por_dimension, 
#  display_evolucion_sql, display_tabla_sesiones_detalle)
def clear_ses_filters_callback():
    for key, value in default_filters_config.items():
        st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")

def sidebar_filters_sesiones(df_options):
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")
    min_d, max_d = (df_options["Fecha"].min().date(), df_options["Fecha"].max(
    ).date()) if "Fecha" in df_options and not df_options["Fecha"].dropna(
    ).empty and pd.api.types.is_datetime64_any_dtype(
        df_options["Fecha"]) else (None, None)
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde",
                  value=st.session_state[SES_START_DATE_KEY],
                  min_value=min_d,
                  max_value=max_d,
                  format="DD/MM/YYYY",
                  key=SES_START_DATE_KEY)
    c2.date_input("Hasta",
                  value=st.session_state[SES_END_DATE_KEY],
                  min_value=min_d,
                  max_value=max_d,
                  format="DD/MM/YYYY",
                  key=SES_END_DATE_KEY)

    st.sidebar.markdown("---")
    years = ["– Todos –"
             ] + (sorted(df_options["Año"].dropna().astype(int).unique(),
                         reverse=True) if "Año" in df_options
                  and not df_options["Año"].dropna().empty else [])
    current_year_val_in_state = st.session_state[SES_YEAR_FILTER_KEY]
    if current_year_val_in_state not in years:
        st.session_state[SES_YEAR_FILTER_KEY] = "– Todos –"
    st.sidebar.selectbox("Año", years, key=SES_YEAR_FILTER_KEY)
    sel_y = int(
        st.session_state[SES_YEAR_FILTER_KEY]
    ) if st.session_state[SES_YEAR_FILTER_KEY] != "– Todos –" else None

    weeks_df = df_options[
        df_options["Año"] ==
        sel_y] if sel_y is not None and "Año" in df_options.columns else df_options
    weeks = ["– Todas –"
             ] + (sorted(weeks_df["NumSemana"].dropna().astype(int).unique())
                  if "NumSemana" in weeks_df
                  and not weeks_df["NumSemana"].dropna().empty else [])
    current_week_selection_in_state = st.session_state[SES_WEEK_FILTER_KEY]
    validated_week_selection = [
        val for val in current_week_selection_in_state if val in weeks
    ]
    if not validated_week_selection: # Si la selección actual no es válida (ej. por cambio de año)
        st.session_state[SES_WEEK_FILTER_KEY] = ["– Todas –"] if "– Todas –" in weeks else ([weeks[0]] if weeks and weeks[0] != "– Todas –" else [])
    elif len(validated_week_selection) != len(current_week_selection_in_state): # Si se invalidaron algunas opciones
        st.session_state[SES_WEEK_FILTER_KEY] = validated_week_selection

    st.sidebar.multiselect("Semanas", weeks, key=SES_WEEK_FILTER_KEY)

    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")

    # Lógica para LGS (simplificada para brevedad, tu código original está bien)
    lgs_options = ["– Todos –"] + (sorted(df_options["LG"].dropna().unique()) if "LG" in df_options and not df_options["LG"].dropna().empty else [])
    # ... (tu lógica de validación de selección para LG) ...
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=st.session_state.get(SES_LG_FILTER_KEY, ["– Todos –"]))


    # Lógica para AE (simplificada para brevedad)
    ae_options = ["– Todos –"] + (sorted(df_options["AE"].dropna().unique()) if "AE" in df_options and not df_options["AE"].dropna().empty else [])
    # ... (tu lógica de validación de selección para AE) ...
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=st.session_state.get(SES_AE_FILTER_KEY, ["– Todos –"]))


    # Lógica para País (simplificada para brevedad)
    paises_opts = ["– Todos –"] + (sorted(df_options["País"].dropna().unique()) if "País" in df_options and not df_options["País"].dropna().empty else [])
    # ... (tu lógica de validación de selección para País) ...
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=st.session_state.get(SES_PAIS_FILTER_KEY, ["– Todos –"]))


    # Lógica para SQL (simplificada para brevedad)
    sqls_opts = ["– Todos –"] + (sorted(df_options["SQL_Estandarizado"].dropna().unique(), key=lambda x: SQL_ORDER_OF_IMPORTANCE.index(x) if x in SQL_ORDER_OF_IMPORTANCE else len(SQL_ORDER_OF_IMPORTANCE)) if "SQL_Estandarizado" in df_options and not df_options["SQL_Estandarizado"].dropna().empty else [])
    # ... (tu lógica de validación de selección para SQL) ...
    st.sidebar.multiselect("Calificación SQL", sqls_opts, key=SES_SQL_FILTER_KEY, default=st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"]))


    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros",
                      on_click=clear_ses_filters_callback,
                      use_container_width=True,
                      key=f"{FILTER_KEYS_PREFIX}btn_clear_sesiones") # Clave única para este botón
    return (st.session_state[SES_START_DATE_KEY],
            st.session_state[SES_END_DATE_KEY], sel_y,
            st.session_state[SES_WEEK_FILTER_KEY],
            st.session_state[SES_AE_FILTER_KEY],
            st.session_state[SES_LG_FILTER_KEY],
            st.session_state[SES_PAIS_FILTER_KEY],
            st.session_state[SES_SQL_FILTER_KEY])

def apply_sesiones_filters(df, start_date, end_date, year_f, week_f, ae_f, lg_f, pais_f, sql_f):
    # ... (tu código original)
    if df is None or df.empty: return pd.DataFrame()
    df_f = df.copy()
    if "Fecha" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f["Fecha"]):
        if start_date and end_date:
            df_f = df_f[(df_f["Fecha"].dt.date >= start_date) & (df_f["Fecha"].dt.date <= end_date)]
        elif start_date:
            df_f = df_f[df_f["Fecha"].dt.date >= start_date]
        elif end_date:
            df_f = df_f[df_f["Fecha"].dt.date <= end_date]
    if year_f is not None and "Año" in df_f.columns: df_f = df_f[df_f["Año"] == year_f]
    if week_f and "– Todas –" not in week_f and "NumSemana" in df_f.columns:
        valid_w = [int(w) for w in week_f if (isinstance(w, str) and w.isdigit()) or isinstance(w, int)]
        if valid_w: df_f = df_f[df_f["NumSemana"].isin(valid_w)]
    if ae_f and "– Todos –" not in ae_f and "AE" in df_f.columns: df_f = df_f[df_f["AE"].isin(ae_f)]
    if lg_f and "– Todos –" not in lg_f and "LG" in df_f.columns: df_f = df_f[df_f["LG"].isin(lg_f)]
    if pais_f and "– Todos –" not in pais_f and "País" in df_f.columns: df_f = df_f[df_f["País"].isin(pais_f)]
    if sql_f and "– Todos –" not in sql_f and "SQL_Estandarizado" in df_f.columns: df_f = df_f[df_f["SQL_Estandarizado"].isin(sql_f)]
    return df_f

def get_sql_category_order(df_column_or_list):
    # ... (tu código original)
    present_sqls = pd.Series(df_column_or_list).unique()
    ordered_present_sqls = [s for s in SQL_ORDER_OF_IMPORTANCE if s in present_sqls]
    other_sqls = sorted([s for s in present_sqls if s not in ordered_present_sqls])
    return ordered_present_sqls + other_sqls
    
def display_sesiones_summary_sql(df_filtered):
    # ... (tu código original)
    st.markdown("### 📌 Resumen Principal de Sesiones")
    if df_filtered.empty:
        st.info("No hay sesiones para resumen con los filtros aplicados.")
        return
    total_sesiones = len(df_filtered)
    st.metric("Total Sesiones (filtradas)", f"{total_sesiones:,}")
    if 'SQL_Estandarizado' in df_filtered.columns:
        st.markdown("#### Distribución por Calificación SQL")
        sql_counts = df_filtered['SQL_Estandarizado'].value_counts().reset_index()
        sql_counts.columns = ['Calificación SQL', 'Número de Sesiones']
        category_order = get_sql_category_order(sql_counts['Calificación SQL'])
        sql_counts['Calificación SQL'] = pd.Categorical(sql_counts['Calificación SQL'], categories=category_order, ordered=True)
        sql_counts = sql_counts.sort_values('Calificación SQL')
        if not sql_counts.empty:
            fig = px.bar(sql_counts, x='Calificación SQL', y='Número de Sesiones', title='Sesiones por Calificación SQL', text_auto=True, color='Calificación SQL', category_orders={"Calificación SQL": category_order})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(sql_counts.set_index('Calificación SQL').style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
    else:
        st.warning("Columna 'SQL_Estandarizado' no encontrada para el resumen.")

def display_analisis_por_dimension(df_filtered, dimension_col, dimension_label, top_n=10):
    # ... (tu código original)
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para análisis por {dimension_label}.")
        return
    sql_category_order_dim = get_sql_category_order(df_filtered['SQL_Estandarizado']) # Renombrado para evitar conflicto
    summary_dim_sql = df_filtered.groupby([dimension_col, 'SQL_Estandarizado'], as_index=False, observed=True)['Fecha'].count().rename(columns={'Fecha': 'Cantidad_SQL'})
    dim_totals = df_filtered.groupby(dimension_col, as_index=False, observed=True)['Fecha'].count().rename(columns={'Fecha': 'Total_Sesiones'})
    top_n_dims = dim_totals.sort_values(by='Total_Sesiones', ascending=False).head(top_n)[dimension_col].tolist()
    summary_dim_sql_top_n = summary_dim_sql[summary_dim_sql[dimension_col].isin(top_n_dims)].copy()
    if summary_dim_sql_top_n.empty:
        st.info(f"No hay datos agregados por {dimension_label} y SQL para el Top {top_n}.")
        return
    summary_dim_sql_top_n['SQL_Estandarizado'] = pd.Categorical(summary_dim_sql_top_n['SQL_Estandarizado'], categories=sql_category_order_dim, ordered=True)
    if not summary_dim_sql_top_n.empty:
        fig_dim = px.bar(summary_dim_sql_top_n, x=dimension_col, y='Cantidad_SQL', color='SQL_Estandarizado', title=f'Distribución de SQL por {dimension_label}', barmode='stack', category_orders={dimension_col: top_n_dims, "SQL_Estandarizado": sql_category_order_dim}, color_discrete_sequence=px.colors.qualitative.Vivid)
        fig_dim.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Sesiones")
        st.plotly_chart(fig_dim, use_container_width=True)
    pivot_table = summary_dim_sql_top_n.pivot_table(index=dimension_col, columns='SQL_Estandarizado', values='Cantidad_SQL', fill_value=0)
    for sql_cat_pivot in sql_category_order_dim: # Renombrado
        if sql_cat_pivot not in pivot_table.columns: pivot_table[sql_cat_pivot] = 0
    pivot_table_cols_ordered = [col_pivot for col_pivot in sql_category_order_dim if col_pivot in pivot_table.columns] + [col_pivot for col_pivot in pivot_table.columns if col_pivot not in sql_category_order_dim]
    pivot_table = pivot_table.reindex(columns=pivot_table_cols_ordered, fill_value=0)
    pivot_table = pivot_table.reindex(index=top_n_dims, fill_value=0) # Asegurar orden de la dimensión
    pivot_table['Total_Sesiones_Dim'] = pivot_table.sum(axis=1)
    for col_pivot_format in pivot_table.columns: # Renombrado
        try:
            pivot_table[col_pivot_format] = pd.to_numeric(pivot_table[col_pivot_format], errors='coerce').fillna(0).astype(int)
        except ValueError: # No hacer st.warning aquí para no saturar
            pivot_table[col_pivot_format] = pivot_table[col_pivot_format].astype(str)
    format_dict = {col_format: "{:,.0f}" for col_format in pivot_table.columns if pd.api.types.is_numeric_dtype(pivot_table[col_format])}
    st.dataframe(pivot_table.style.format(format_dict) if format_dict else pivot_table, use_container_width=True)


def display_evolucion_sql(df_filtered, time_agg_col, display_label, chart_title, x_axis_label):
    # ... (tu código original)
    st.markdown(f"### 📈 {chart_title}")
    if df_filtered.empty or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para {chart_title.lower()}.")
        return
    df_agg_evol = df_filtered.copy() # Renombrado
    group_col_evol = time_agg_col # Renombrado
    if time_agg_col == 'NumSemana':
        if not ('Año' in df_agg_evol.columns and 'NumSemana' in df_agg_evol.columns):
            st.warning("Faltan Año/NumSemana para evolución.")
            return
        df_agg_evol.dropna(subset=['Año', 'NumSemana'], inplace=True)
        if df_agg_evol.empty:
            st.info("No hay datos para evolución semanal.")
            return
        df_agg_evol['Año-Semana'] = df_agg_evol['Año'].astype(int).astype(str) + '-S' + df_agg_evol['NumSemana'].astype(int).astype(str).str.zfill(2)
        group_col_evol = 'Año-Semana'
        df_agg_evol = df_agg_evol.sort_values(by=group_col_evol)
    elif time_agg_col == 'AñoMes':
        if 'AñoMes' not in df_agg_evol.columns:
            st.warning("Columna 'AñoMes' faltante para evolución.")
            return
        df_agg_evol = df_agg_evol.sort_values(by='AñoMes')
    sql_category_order_evol = get_sql_category_order(df_agg_evol['SQL_Estandarizado']) # Renombrado
    summary_time_sql = df_agg_evol.groupby([group_col_evol, 'SQL_Estandarizado'], as_index=False, observed=True)['Fecha'].count().rename(columns={'Fecha': 'Número de Sesiones'})
    if summary_time_sql.empty:
        st.info(f"No hay datos agregados por {x_axis_label.lower()} y SQL.")
        return
    summary_time_sql['SQL_Estandarizado'] = pd.Categorical(summary_time_sql['SQL_Estandarizado'], categories=sql_category_order_evol, ordered=True)
    summary_time_sql = summary_time_sql.sort_values([group_col_evol, 'SQL_Estandarizado'])
    st.dataframe(summary_time_sql.style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
    try:
        fig_evol = px.line(summary_time_sql, x=group_col_evol, y='Número de Sesiones', color='SQL_Estandarizado', title=f"Evolución por SQL ({x_axis_label})", markers=True, category_orders={"SQL_Estandarizado": sql_category_order_evol})
        st.plotly_chart(fig_evol, use_container_width=True)
    except Exception as e_evol: # Renombrado
        st.warning(f"No se pudo generar gráfico de evolución: {e_evol}")


def display_tabla_sesiones_detalle(df_filtered):
    # ... (tu código original)
    st.markdown("### 📝 Tabla Detallada de Sesiones")
    if df_filtered.empty:
        st.info("No hay sesiones detalladas para mostrar con los filtros aplicados.")
        return
    cols_display_detalle = ["Fecha", "LG", "AE", "País", "SQL", "SQL_Estandarizado", "Empresa", "Puesto", "Nombre", "Apellido", "Siguientes Pasos"] # Renombrado
    cols_present_detalle = [col for col in cols_display_detalle if col in df_filtered.columns] # Renombrado
    df_view_detalle = df_filtered[cols_present_detalle].copy() # Renombrado
    if "Fecha" in df_view_detalle.columns and pd.api.types.is_datetime64_any_dtype(df_view_detalle["Fecha"]):
        df_view_detalle["Fecha"] = pd.to_datetime(df_view_detalle["Fecha"]).dt.strftime('%d/%m/%Y')
    st.dataframe(df_view_detalle, height=400, use_container_width=True)
    if not df_view_detalle.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_view_detalle.to_excel(writer, index=False, sheet_name='Detalle_Sesiones')
        st.download_button(
            label="⬇️ Descargar Detalle (Excel)", data=output.getvalue(),
            file_name="detalle_sesiones_sql.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{FILTER_KEYS_PREFIX}btn_download_detalle_sesiones") # Clave única


# --- Flujo Principal de la Página ---
# (Tu código original para el flujo principal)
df_sesiones_raw = load_sesiones_data() # Esta función ahora usa st.secrets

if df_sesiones_raw is None or df_sesiones_raw.empty: # Añadida comprobación de None
    st.error("Fallo Crítico al cargar datos de Sesiones. La página no puede continuar.")
    st.stop()

# Tu lógica de filtros y display (he simplificado los defaults en multiselect para el ejemplo)
start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, sql_f_val = sidebar_filters_sesiones(df_sesiones_raw)
df_sesiones_filtered = apply_sesiones_filters(df_sesiones_raw, start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, sql_f_val)

display_sesiones_summary_sql(df_sesiones_filtered)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="LG", dimension_label="Analista LG", top_n=15)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="AE", dimension_label="Account Executive", top_n=15)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="País", dimension_label="País", top_n=10)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="Puesto", dimension_label="Cargo (Puesto)", top_n=10)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="Empresa", dimension_label="Empresa", top_n=10)
st.markdown("---")
display_evolucion_sql(df_sesiones_filtered, 'NumSemana', 'Año-Semana', "Evolución Semanal por Calificación SQL", "Semana del Año")
st.markdown("---")
display_evolucion_sql(df_sesiones_filtered, 'AñoMes', 'Año-Mes', "Evolución Mensual por Calificación SQL", "Mes del Año")
st.markdown("---")
display_tabla_sesiones_detalle(df_sesiones_filtered)

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info( # Cambiado de st.caption a st.info para más visibilidad si es un mensaje importante
    "Dashboard de Sesiones: Análisis por LG, AE, País, Calificación SQL, Puesto y Empresa."
)
