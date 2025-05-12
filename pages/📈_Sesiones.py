import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import datetime
import plotly.express as px
import os
import sys
import io
import re

# --- Configuración Inicial del Proyecto y Título de la Página ---
try:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError:
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

st.set_page_config(layout="wide", page_title="Análisis de Sesiones y SQL")
st.title("📊 Análisis de Sesiones y Calificaciones SQL")
st.markdown(
    "Métricas por LG, AE, País, Calificación SQL (SQL1 > SQL2 > MQL > NA > Sin Calificación), Puesto y Empresa."
)

# --- Constantes ---
SHEET_URL_SESIONES_PRINCIPAL_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902"
SHEET_NAME_SESIONES_PRINCIPAL = "Sesiones 2024-2025"
SHEET_URL_SESIONES_SURAMERICA_DEFAULT = "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854"
SHEET_NAME_SESIONES_SURAMERICA = "BD Sesiones 2024"

COLUMNAS_ESPERADAS = [
    "Semana", "Mes", "Fecha", "SQL", "Empresa", "País", "Nombre", "Apellido",
    "Puesto", "Email", "AE", "LG", "Siguientes Pasos", "RPA"
]
COLUMNAS_DERIVADAS = [
    'Año', 'NumSemana', 'MesNombre', 'AñoMes', 'SQL_Estandarizado'
]
COLUMNAS_FINALES_UNIFICADAS = list(set(COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS + ["Fuente_Hoja", "LinkedIn"]))
SQL_ORDER_OF_IMPORTANCE = ['SQL1', 'SQL2', 'MQL', 'NA', 'SIN CALIFICACIÓN SQL']

# --- Gestión de Estado de Sesión para Filtros ---
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
    SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
    SES_AE_FILTER_KEY: ["– Todos –"], SES_LG_FILTER_KEY: ["– Todos –"],
    SES_PAIS_FILTER_KEY: ["– Todos –"], SES_YEAR_FILTER_KEY: "– Todos –",
    SES_WEEK_FILTER_KEY: ["– Todas –"], SES_SQL_FILTER_KEY: ["– Todos –"]
}
for key, value in default_filters_config.items():
    if key not in st.session_state: st.session_state[key] = value

# --- Funciones de Utilidad ---
def parse_date_robust(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "": return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", 
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", 
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"): 
        try:
            return pd.to_datetime(date_val, format=fmt)
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(date_val, errors='coerce')
    except Exception:
        return None

def separar_nombre_cargo_suramerica(nombre_cargo_str):
    nombre = pd.NA
    apellido = pd.NA
    puesto = "No Especificado"
    if pd.isna(nombre_cargo_str) or not isinstance(nombre_cargo_str, str) or not nombre_cargo_str.strip():
        return nombre, apellido, puesto
    nombre_cargo_str = nombre_cargo_str.strip()
    delimiters_cargo = [' - ', ' / ', ', ', ' – ']
    nombre_completo_str = nombre_cargo_str
    cargo_encontrado_explicitamente = False
    for delim in delimiters_cargo:
        if delim in nombre_cargo_str:
            parts = nombre_cargo_str.split(delim, 1)
            nombre_completo_str = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                puesto = parts[1].strip()
                cargo_encontrado_explicitamente = True
            break 
    name_parts = [part.strip() for part in nombre_completo_str.split() if part.strip()]
    if not name_parts: return pd.NA, pd.NA, puesto
    if len(name_parts) == 1: nombre = name_parts[0]
    elif len(name_parts) == 2: nombre, apellido = name_parts[0], name_parts[1]
    elif len(name_parts) == 3: nombre, apellido = name_parts[0], f"{name_parts[1]} {name_parts[2]}"
    elif len(name_parts) >= 4:
        nombre = f"{name_parts[0]} {name_parts[1]}"
        apellido = " ".join(name_parts[2:])
        if not cargo_encontrado_explicitamente and len(name_parts) > 2:
            temp_nombre_simple, temp_apellido_simple = name_parts[0], name_parts[1]
            temp_cargo_implicito = " ".join(name_parts[2:])
            if len(temp_cargo_implicito) > 2:
                 nombre, apellido, puesto = temp_nombre_simple, temp_apellido_simple, temp_cargo_implicito
    if pd.isna(nombre) and pd.notna(nombre_completo_str) and nombre_completo_str: nombre = nombre_completo_str
    return (str(nombre).strip() if pd.notna(nombre) else pd.NA,
            str(apellido).strip() if pd.notna(apellido) else pd.NA,
            str(puesto).strip() if pd.notna(puesto) and puesto else "No Especificado")

@st.cache_data(ttl=300)
def load_sesiones_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds_dict = {
            "type": st.secrets["google_sheets_credentials"]["type"],
            "project_id": st.secrets["google_sheets_credentials"]["project_id"],
            "private_key_id": st.secrets["google_sheets_credentials"]["private_key_id"],
            "private_key": st.secrets["google_sheets_credentials"]["private_key"],
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
        return pd.DataFrame(columns=COLUMNAS_FINALES_UNIFICADAS)
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets para Sesiones vía Secrets: {e}")
        return pd.DataFrame(columns=COLUMNAS_FINALES_UNIFICADAS)

    all_dataframes = []
    df_final_structure = pd.DataFrame(columns=COLUMNAS_FINALES_UNIFICADAS)

    sheet_url_principal_actual = st.secrets.get("SESIONES_PRINCIPAL_SHEET_URL", SHEET_URL_SESIONES_PRINCIPAL_DEFAULT)
    try:
        workbook_principal = client.open_by_url(sheet_url_principal_actual)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES)
        raw_data_principal = sheet_principal.get_all_records(head=1, default_blank=pd.NA) # Usar get_all_records y default_blank=pd.NA
        if raw_data_principal:
            df_principal = pd.DataFrame(raw_data_principal)
            df_principal["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_principal)
        else:
            st.warning(f"Hoja Principal de Sesiones ('{SHEET_NAME_SESIONES}') vacía.")
    except Exception as e:
        st.error(f"Error al cargar la Hoja Principal de Sesiones: {e}")

    sheet_url_suramerica_actual = st.secrets.get("SESIONES_SURAMERICA_SHEET_URL", SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
    try:
        workbook_suramerica = client.open_by_url(sheet_url_suramerica_actual)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        raw_data_suramerica = sheet_suramerica.get_all_records(head=1, default_blank=pd.NA) # Usar get_all_records
        if raw_data_suramerica:
            df_suramerica_temp = pd.DataFrame(raw_data_suramerica)
            df_suramerica_processed = pd.DataFrame()
            df_suramerica_processed["Fecha"] = df_suramerica_temp["Fecha"].apply(parse_date_robust) if "Fecha" in df_suramerica_temp.columns else pd.NaT
            df_suramerica_processed["Empresa"] = df_suramerica_temp.get("Empresa", pd.NA)
            df_suramerica_processed["País"] = df_suramerica_temp.get("País", pd.NA)
            df_suramerica_processed["Siguientes Pasos"] = df_suramerica_temp.get("Siguientes Pasos", pd.NA)
            df_suramerica_processed["SQL"] = df_suramerica_temp.get("SQL", pd.NA)
            df_suramerica_processed["Email"] = df_suramerica_temp.get("Correo", pd.NA)
            df_suramerica_processed["LinkedIn"] = df_suramerica_temp.get("LinkedIn", pd.NA)
            if "Nombre y Cargo" in df_suramerica_temp.columns:
                nombres_cargos_split = df_suramerica_temp["Nombre y Cargo"].apply(separar_nombre_cargo_suramerica)
                df_suramerica_processed["Nombre"] = nombres_cargos_split.apply(lambda x: x[0])
                df_suramerica_processed["Apellido"] = nombres_cargos_split.apply(lambda x: x[1])
                df_suramerica_processed["Puesto"] = nombres_cargos_split.apply(lambda x: x[2])
            else:
                df_suramerica_processed["Nombre"], df_suramerica_processed["Apellido"], df_suramerica_processed["Puesto"] = pd.NA, pd.NA, "No Especificado"
            df_suramerica_processed["LG"] = df_suramerica_temp.get("Created By", "No Asignado LG (SA)")
            df_suramerica_processed["AE"] = df_suramerica_temp.get("Asistencia BDR´s", "No Asignado AE (SA)")
            df_suramerica_processed["RPA"] = "N/A (SA)"
            df_suramerica_processed["Fuente_Hoja"] = "Suramérica"
            all_dataframes.append(df_suramerica_processed)
        else:
            st.warning(f"Hoja de Sesiones de Suramérica ('{SHEET_NAME_SESIONES_SURAMERICA}') vacía.")
    except Exception as e:
        st.error(f"Error al cargar la Hoja de Sesiones de Suramérica: {e}")

    if not all_dataframes:
        st.error("No se pudieron cargar datos de ninguna hoja de Sesiones.")
        return df_final_structure

    df_consolidado = pd.concat(all_dataframes, ignore_index=True, sort=False)
    
    df_final = df_consolidado.copy()
    if "Fecha" in df_final.columns:
        df_final["Fecha"] = pd.to_datetime(df_final["Fecha"], errors='coerce')
        df_final.dropna(subset=["Fecha"], inplace=True)
    else:
        st.error("Columna 'Fecha' perdida después de la consolidación.")
        return df_final_structure
    if df_final.empty:
        st.warning("No hay sesiones con fechas válidas después de la consolidación.")
        return df_final_structure

    df_final['Año'] = df_final['Fecha'].dt.year.astype('Int64')
    df_final['NumSemana'] = df_final['Fecha'].dt.isocalendar().week.astype('Int64')
    df_final['MesNombre'] = df_final['Fecha'].dt.month_name()
    df_final['AñoMes'] = df_final['Fecha'].dt.strftime('%Y-%m')

    # Antes de la estandarización de SQL, llenar pd.NA con ""
    df_final["SQL"] = df_final["SQL"].fillna("").astype(str).str.strip().str.upper()
    df_final['SQL_Estandarizado'] = df_final['SQL'] # Inicializar
    known_sql_values = [s for s in SQL_ORDER_OF_IMPORTANCE if s != 'SIN CALIFICACIÓN SQL']
    
    # Convertir pd.NA a un string específico antes de isin si es necesario, o asegurar que no haya pd.NA
    # La línea de fillna("") arriba para SQL debería manejar esto.
    mask_empty_sql = ~df_final['SQL_Estandarizado'].isin(known_sql_values) & \
                     (df_final['SQL_Estandarizado'].isin(['', 'NAN', 'NONE', 'NA', '<NA>'])) # Incluir <NA> por si acaso
    df_final.loc[mask_empty_sql, 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'
    df_final.loc[df_final['SQL_Estandarizado'] == '', 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'


    default_values_fill = {
        "AE": "No Asignado AE", "LG": "No Asignado LG", "Puesto": "No Especificado",
        "Empresa": "No Especificado", "País": "No Especificado", "Nombre": "No Especificado",
        "Apellido": "No Especificado", "Siguientes Pasos": "No Especificado",
        "Email": "No Especificado", "RPA": "No Especificado", "LinkedIn": "No Especificado"
    }

    for col, default_val in default_values_fill.items():
        if col not in df_final.columns: # Si la columna no existe, la creamos
            df_final[col] = default_val
        else:
            # Reemplazar pd.NA y np.nan primero
            df_final[col] = df_final[col].fillna(default_val) 
            # Luego convertir a string para las demás operaciones
            df_final[col] = df_final[col].astype(str).str.strip()
            # Ahora reemplazar strings vacíos o que representan nulos
            df_final.loc[df_final[col].isin(['', 'nan', 'none', 'NaN', 'None', 'NA', '<NA>']), col] = default_val
            
    if "Puesto" in df_final.columns: # Asegurar que "Puesto" vacío sea "No Especificado"
         df_final.loc[df_final["Puesto"].str.strip().eq(""), "Puesto"] = "No Especificado"
            
    df_to_return = pd.DataFrame()
    for col in COLUMNAS_FINALES_UNIFICADAS:
        if col in df_final.columns:
            df_to_return[col] = df_final[col]
        else:
            if col in ['Año', 'NumSemana']: df_to_return[col] = pd.Series(dtype='Int64')
            elif col == 'Fecha': df_to_return[col] = pd.Series(dtype='datetime64[ns]')
            elif col in COLUMNAS_ESPERADAS: df_to_return[col] = "No Especificado"
            else: df_to_return[col] = pd.NA
            
    return df_to_return

# --- (El resto de tus funciones: clear_ses_filters_callback, sidebar_filters_sesiones, etc. y el flujo principal se mantienen igual) ---
# --- Copia y pega el resto de tu archivo desde la definición de clear_ses_filters_callback() hasta el final ---

def clear_ses_filters_callback():
    for key, value in default_filters_config.items():
        st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")

def sidebar_filters_sesiones(df_options):
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")
    min_d, max_d = (df_options["Fecha"].min().date(), df_options["Fecha"].max().date()) if "Fecha" in df_options and not df_options["Fecha"].dropna().empty and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) else (None, None)
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", value=st.session_state.get(SES_START_DATE_KEY), min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    c2.date_input("Hasta", value=st.session_state.get(SES_END_DATE_KEY), min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")
    years = ["– Todos –"] + (sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True) if "Año" in df_options and not df_options["Año"].dropna().empty else [])
    st.sidebar.selectbox("Año", years, key=SES_YEAR_FILTER_KEY, index=years.index(st.session_state.get(SES_YEAR_FILTER_KEY, "– Todos –")) if st.session_state.get(SES_YEAR_FILTER_KEY, "– Todos –") in years else 0)
    sel_y = int(st.session_state[SES_YEAR_FILTER_KEY]) if st.session_state[SES_YEAR_FILTER_KEY] != "– Todos –" else None
    
    weeks_df_data = df_options[df_options["Año"] == sel_y] if sel_y is not None and "Año" in df_options.columns else df_options
    weeks = ["– Todas –"] + (sorted(weeks_df_data["NumSemana"].dropna().astype(int).unique()) if "NumSemana" in weeks_df_data and not weeks_df_data["NumSemana"].dropna().empty else [])
    
    current_week_selection = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    valid_week_selection = [val for val in current_week_selection if val in weeks]
    if not valid_week_selection:
        valid_week_selection = ["– Todas –"] if "– Todas –" in weeks else ([weeks[0]] if weeks and weeks[0] != "– Todas –" else [])
    st.sidebar.multiselect("Semanas", weeks, key=SES_WEEK_FILTER_KEY, default=valid_week_selection)

    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")
    
    lgs_options = ["– Todos –"] + (sorted(df_options["LG"].astype(str).dropna().unique()) if "LG" in df_options and not df_options["LG"].dropna().empty else [])
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=st.session_state.get(SES_LG_FILTER_KEY, ["– Todos –"]))
    
    ae_options = ["– Todos –"] + (sorted(df_options["AE"].astype(str).dropna().unique()) if "AE" in df_options and not df_options["AE"].dropna().empty else [])
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=st.session_state.get(SES_AE_FILTER_KEY, ["– Todos –"]))
    
    paises_opts = ["– Todos –"] + (sorted(df_options["País"].astype(str).dropna().unique()) if "País" in df_options and not df_options["País"].dropna().empty else [])
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=st.session_state.get(SES_PAIS_FILTER_KEY, ["– Todos –"]))
    
    sqls_opts = ["– Todos –"] + (sorted(df_options["SQL_Estandarizado"].astype(str).dropna().unique(), key=lambda x: SQL_ORDER_OF_IMPORTANCE.index(x) if x in SQL_ORDER_OF_IMPORTANCE else len(SQL_ORDER_OF_IMPORTANCE)) if "SQL_Estandarizado" in df_options and not df_options["SQL_Estandarizado"].dropna().empty else [])
    st.sidebar.multiselect("Calificación SQL", sqls_opts, key=SES_SQL_FILTER_KEY, default=st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"]))

    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback, use_container_width=True, key=f"{FILTER_KEYS_PREFIX}btn_clear_sesiones_final_v2") # Cambié la key para asegurar que es única
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], sel_y,
            st.session_state[SES_WEEK_FILTER_KEY], st.session_state[SES_AE_FILTER_KEY],
            st.session_state[SES_LG_FILTER_KEY], st.session_state[SES_PAIS_FILTER_KEY],
            st.session_state[SES_SQL_FILTER_KEY])

def apply_sesiones_filters(df, start_date, end_date, year_f, week_f, ae_f, lg_f, pais_f, sql_f):
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
    # Asegurar que las columnas de filtro sean strings antes de .isin() si los datos pueden ser mixtos
    if ae_f and "– Todos –" not in ae_f and "AE" in df_f.columns: df_f = df_f[df_f["AE"].astype(str).isin([str(i) for i in ae_f])]
    if lg_f and "– Todos –" not in lg_f and "LG" in df_f.columns: df_f = df_f[df_f["LG"].astype(str).isin([str(i) for i in lg_f])]
    if pais_f and "– Todos –" not in pais_f and "País" in df_f.columns: df_f = df_f[df_f["País"].astype(str).isin([str(i) for i in pais_f])]
    if sql_f and "– Todos –" not in sql_f and "SQL_Estandarizado" in df_f.columns: df_f = df_f[df_f["SQL_Estandarizado"].astype(str).isin([str(i) for i in sql_f])]
    return df_f

def get_sql_category_order(df_column_or_list):
    present_sqls = pd.Series(df_column_or_list).astype(str).unique() # .astype(str) para manejar pd.NA si aún existiera
    ordered_present_sqls = [s for s in SQL_ORDER_OF_IMPORTANCE if s in present_sqls]
    other_sqls = sorted([s for s in present_sqls if s not in ordered_present_sqls])
    return ordered_present_sqls + other_sqls
    
def display_sesiones_summary_sql(df_filtered):
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
        category_order_sql_summary = get_sql_category_order(sql_counts['Calificación SQL'])
        sql_counts['Calificación SQL'] = pd.Categorical(sql_counts['Calificación SQL'], categories=category_order_sql_summary, ordered=True)
        sql_counts = sql_counts.sort_values('Calificación SQL')
        if not sql_counts.empty:
            fig_sql_summary = px.bar(sql_counts, x='Calificación SQL', y='Número de Sesiones', title='Sesiones por Calificación SQL', text_auto=True, color='Calificación SQL', category_orders={"Calificación SQL": category_order_sql_summary})
            st.plotly_chart(fig_sql_summary, use_container_width=True)
            st.dataframe(sql_counts.set_index('Calificación SQL').style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
    else:
        st.warning("Columna 'SQL_Estandarizado' no encontrada para el resumen.")

def display_analisis_por_dimension(df_filtered, dimension_col, dimension_label, top_n=10):
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para análisis por {dimension_label}.")
        return
    sql_category_order_dim_analysis = get_sql_category_order(df_filtered['SQL_Estandarizado'])
    # Usar observed=False para groupby para asegurar que todas las categorías se mantengan si son categóricas
    summary_dim_sql = df_filtered.groupby([dimension_col, 'SQL_Estandarizado'], as_index=False, observed=False)['Fecha'].count().rename(columns={'Fecha': 'Cantidad_SQL'})
    dim_totals = df_filtered.groupby(dimension_col, as_index=False, observed=False)['Fecha'].count().rename(columns={'Fecha': 'Total_Sesiones'})
    
    top_n_dims = dim_totals.sort_values(by='Total_Sesiones', ascending=False).head(top_n)[dimension_col].tolist()
    summary_dim_sql_top_n = summary_dim_sql[summary_dim_sql[dimension_col].isin(top_n_dims)].copy()
    if summary_dim_sql_top_n.empty:
        st.info(f"No hay datos agregados por {dimension_label} y SQL para el Top {top_n}.")
        return
    summary_dim_sql_top_n['SQL_Estandarizado'] = pd.Categorical(summary_dim_sql_top_n['SQL_Estandarizado'], categories=sql_category_order_dim_analysis, ordered=True)
    if not summary_dim_sql_top_n.empty:
        fig_dim_analysis = px.bar(summary_dim_sql_top_n, x=dimension_col, y='Cantidad_SQL', color='SQL_Estandarizado', title=f'Distribución de SQL por {dimension_label}', barmode='stack', category_orders={dimension_col: top_n_dims, "SQL_Estandarizado": sql_category_order_dim_analysis}, color_discrete_sequence=px.colors.qualitative.Vivid)
        fig_dim_analysis.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Sesiones")
        st.plotly_chart(fig_dim_analysis, use_container_width=True)
    
    pivot_table_dim = summary_dim_sql_top_n.pivot_table(index=dimension_col, columns='SQL_Estandarizado', values='Cantidad_SQL', fill_value=0)
    for sql_cat_pivot_dim in sql_category_order_dim_analysis:
        if sql_cat_pivot_dim not in pivot_table_dim.columns: pivot_table_dim[sql_cat_pivot_dim] = 0
    pivot_table_cols_ordered_dim = [col for col in sql_category_order_dim_analysis if col in pivot_table_dim
