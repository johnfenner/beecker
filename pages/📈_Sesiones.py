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
SHEET_URL_SESIONES_PRINCIPAL_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902"
SHEET_NAME_SESIONES_PRINCIPAL = "Sesiones 2024-2025"

SHEET_URL_SESIONES_SURAMERICA_DEFAULT = "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854"
SHEET_NAME_SESIONES_SURAMERICA = "BD Sesiones 2024"

COLUMNAS_FINALES_UNIFICADAS = [
    "Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL", "SQL_Estandarizado",
    "AE", "LG", "Siguientes Pasos", "Email", "RPA", "LinkedIn", "Fuente_Hoja",
    "Año", "NumSemana", "MesNombre", "AñoMes"
]
SQL_ORDER_OF_IMPORTANCE = ['SQL1', 'SQL2', 'MQL', 'NA', 'SIN CALIFICACIÓN SQL']

# --- Gestión de Estado de Sesión para Filtros ---
FILTER_KEYS_PREFIX = "sesiones_sql_lg_pais_page_v2_"
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
            if len(temp_cargo_implicito) > 2: # Evitar tomar iniciales como cargo
                 nombre, apellido, puesto = temp_nombre_simple, temp_apellido_simple, temp_cargo_implicito
    if pd.isna(nombre) and pd.notna(nombre_completo_str) and nombre_completo_str: nombre = nombre_completo_str # Si todo fue nombre
    return (str(nombre).strip() if pd.notna(nombre) else pd.NA,
            str(apellido).strip() if pd.notna(apellido) else pd.NA,
            str(puesto).strip() if pd.notna(puesto) and puesto else "No Especificado")

@st.cache_data(ttl=300)
def load_sesiones_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    df_final_structure = pd.DataFrame(columns=COLUMNAS_FINALES_UNIFICADAS)
    
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
        return df_final_structure
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets para Sesiones vía Secrets: {e}")
        return df_final_structure

    all_dataframes = []

    # --- Cargar Hoja Principal de Sesiones ---
    sheet_url_principal_actual = st.secrets.get("SESIONES_PRINCIPAL_SHEET_URL", SHEET_URL_SESIONES_PRINCIPAL_DEFAULT)
    try:
        workbook_principal = client.open_by_url(sheet_url_principal_actual)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES_PRINCIPAL)
        raw_data_principal = sheet_principal.get_all_records(head=1, default_blank=pd.NA) 
        if raw_data_principal:
            df_principal = pd.DataFrame(raw_data_principal)
            # Mapeo explícito para hoja principal para asegurar nombres estándar internos
            df_proc_principal = pd.DataFrame()
            df_proc_principal["Fecha"] = df_principal["Fecha"].apply(parse_date_robust) if "Fecha" in df_principal.columns else pd.NaT
            df_proc_principal["Empresa"] = df_principal.get("Empresa", pd.NA)
            df_proc_principal["País"] = df_principal.get("País", pd.NA)
            df_proc_principal["Nombre"] = df_principal.get("Nombre", pd.NA)
            df_proc_principal["Apellido"] = df_principal.get("Apellido", pd.NA)
            df_proc_principal["Puesto"] = df_principal.get("Puesto", pd.NA)
            df_proc_principal["SQL"] = df_principal.get("SQL", pd.NA)
            df_proc_principal["AE"] = df_principal.get("AE", pd.NA)
            df_proc_principal["LG"] = df_principal.get("LG", pd.NA)
            df_proc_principal["Siguientes Pasos"] = df_principal.get("Siguientes Pasos", pd.NA)
            df_proc_principal["Email"] = df_principal.get("Email", pd.NA) # Asume que se llama Email
            df_proc_principal["RPA"] = df_principal.get("RPA", pd.NA)
            df_proc_principal["LinkedIn"] = df_principal.get("LinkedIn", pd.NA) # Si tienes esta columna
            df_proc_principal["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_proc_principal)
        else:
            st.warning(f"Hoja Principal de Sesiones ('{SHEET_NAME_SESIONES_PRINCIPAL}') vacía.")
    except Exception as e:
        st.error(f"Error al cargar/procesar la Hoja Principal de Sesiones: {e}")

    # --- Cargar Hoja de Sesiones de Suramérica ---
    sheet_url_suramerica_actual = st.secrets.get("SESIONES_SURAMERICA_SHEET_URL", SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
    try:
        workbook_suramerica = client.open_by_url(sheet_url_suramerica_actual)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        raw_data_suramerica = sheet_suramerica.get_all_records(head=1, default_blank=pd.NA)
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
        st.error(f"Error al cargar/procesar la Hoja de Sesiones de Suramérica: {e}")

    if not all_dataframes:
        st.error("No se pudieron cargar datos de ninguna hoja de Sesiones para consolidar.")
        return df_final_structure

    df_consolidado = pd.concat(all_dataframes, ignore_index=True, sort=False)
    
    df_final = df_consolidado.copy()
    if "Fecha" not in df_final.columns or df_final["Fecha"].isnull().all():
        st.error("Columna 'Fecha' crucial no presente o vacía después de la consolidación. No se puede continuar.")
        return df_final_structure
        
    df_final["Fecha"] = pd.to_datetime(df_final["Fecha"], errors='coerce')
    df_final.dropna(subset=["Fecha"], inplace=True)
    
    if df_final.empty:
        st.warning("No hay sesiones con fechas válidas después de la consolidación y procesamiento.")
        return df_final_structure

    df_final['Año'] = df_final['Fecha'].dt.year.astype('Int64')
    df_final['NumSemana'] = df_final['Fecha'].dt.isocalendar().week.astype('Int64')
    df_final['MesNombre'] = df_final['Fecha'].dt.month_name()
    df_final['AñoMes'] = df_final['Fecha'].dt.strftime('%Y-%m')

    df_final["SQL"] = df_final["SQL"].fillna("").astype(str).str.strip().str.upper()
    df_final['SQL_Estandarizado'] = df_final['SQL'] 
    known_sql_values = [s for s in SQL_ORDER_OF_IMPORTANCE if s != 'SIN CALIFICACIÓN SQL']
    
    # Corregir el manejo de pd.NA para .isin()
    # Convertir la columna SQL_Estandarizado a string ANTES de usar .isin con una lista de strings
    sql_estandarizado_str = df_final['SQL_Estandarizado'].astype(str)
    mask_empty_sql = ~sql_estandarizado_str.isin(known_sql_values) & \
                     (sql_estandarizado_str.isin(['', 'NAN', 'NONE', 'NA', '<NA>']))
    
    df_final.loc[mask_empty_sql, 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'
    df_final.loc[df_final['SQL_Estandarizado'] == '', 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'

    default_values_fill = {
        "AE": "No Asignado AE", "LG": "No Asignado LG", "Puesto": "No Especificado",
        "Empresa": "No Especificado", "País": "No Especificado", "Nombre": "No Especificado",
        "Apellido": "No Especificado", "Siguientes Pasos": "No Especificado",
        "Email": "No Especificado", "RPA": "No Especificado", "LinkedIn": "No Especificado"
    }

    for col, default_val in default_values_fill.items():
        if col not in df_final.columns: 
            df_final[col] = default_val 
        else:
            df_final[col] = df_final[col].fillna(default_val) 
            df_final[col] = df_final[col].astype(str).str.strip()
            df_final.loc[df_final[col].isin(['', 'nan', 'none', 'NaN', 'None', 'NA', '<NA>']), col] = default_val
            
    if "Puesto" in df_final.columns:
         df_final.loc[df_final["Puesto"].str.strip().eq(""), "Puesto"] = "No Especificado"
            
    df_to_return = pd.DataFrame()
    for col in COLUMNAS_FINALES_UNIFICADAS:
        if col in df_final.columns:
            df_to_return[col] = df_final[col]
        else:
            if col in ['Año', 'NumSemana']: df_to_return[col] = pd.Series(dtype='Int64')
            elif col == 'Fecha': df_to_return[col] = pd.Series(dtype='datetime64[ns]')
            else: df_to_return[col] = "No Especificado" 
            
    return df_to_return

# --- (El resto de tus funciones: clear_ses_filters_callback, sidebar_filters_sesiones, etc. y el flujo principal se mantienen igual) ---
# --- Copia y pega el resto de tu archivo original desde la definición de clear_ses_filters_callback() hasta el final ---
# --- Pegaré aquí el resto del código que me pasaste para asegurar la completitud ---

def clear_ses_filters_callback():
    for key, value in default_filters_config.items():
        st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")

def sidebar_filters_sesiones(df_options):
    # (Tu código original para sidebar_filters_sesiones)
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")
    min_d, max_d = (df_options["Fecha"].min().date(), df_options["Fecha"].max().date()) if "Fecha" in df_options and not df_options["Fecha"].dropna().empty and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) else (None, None)
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", value=st.session_state.get(SES_START_DATE_KEY), min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    c2.date_input("Hasta", value=st.session_state.get(SES_END_DATE_KEY), min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")
    years = ["– Todos –"] + (sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True) if "Año" in df_options and not df_options["Año"].dropna().empty else [])
    current_year_val_in_state = st.session_state.get(SES_YEAR_FILTER_KEY,"– Todos –")
    if current_year_val_in_state not in years: current_year_val_in_state = "– Todos –" # Corrección
    st.sidebar.selectbox("Año", years, key=SES_YEAR_FILTER_KEY, index=years.index(current_year_val_in_state))
    sel_y = int(st.session_state[SES_YEAR_FILTER_KEY]) if st.session_state[SES_YEAR_FILTER_KEY] != "– Todos –" else None
    weeks_df = df_options[df_options["Año"] == sel_y] if sel_y is not None and "Año" in df_options.columns else df_options
    weeks = ["– Todas –"] + (sorted(weeks_df["NumSemana"].dropna().astype(int).unique()) if "NumSemana" in weeks_df and not weeks_df["NumSemana"].dropna().empty else [])
    current_week_selection_in_state = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    validated_week_selection = [val for val in current_week_selection_in_state if val in weeks]
    if not validated_week_selection:
        st.session_state[SES_WEEK_FILTER_KEY] = ["– Todas –"] if "– Todas –" in weeks else ([weeks[0]] if weeks and weeks[0] != "– Todas –" else [])
    elif len(validated_week_selection) != len(current_week_selection_in_state):
        st.session_state[SES_WEEK_FILTER_KEY] = validated_week_selection
    st.sidebar.multiselect("Semanas", weeks, key=SES_WEEK_FILTER_KEY, default=st.session_state[SES_WEEK_FILTER_KEY])
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")
    def get_multiselect_options_and_default(df_col_series, session_key):
        options = ["– Todos –"] + (sorted(df_col_series.astype(str).dropna().unique()) if not df_col_series.dropna().empty else [])
        current_selection = st.session_state.get(session_key, ["– Todos –"])
        valid_selection = [s for s in current_selection if s in options]
        if not valid_selection: valid_selection = ["– Todos –"] if "– Todos –" in options else ([options[0]] if options and options[0] != "– Todos –" else [])
        return options, valid_selection
    lgs_options, valid_lg_default = get_multiselect_options_and_default(df_options.get("LG", pd.Series(dtype=str)), SES_LG_FILTER_KEY)
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=valid_lg_default)
    ae_options, valid_ae_default = get_multiselect_options_and_default(df_options.get("AE", pd.Series(dtype=str)), SES_AE_FILTER_KEY)
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=valid_ae_default)
    paises_opts, valid_pais_default = get_multiselect_options_and_default(df_options.get("País", pd.Series(dtype=str)), SES_PAIS_FILTER_KEY)
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=valid_pais_default)
    sql_series_for_options = df_options.get("SQL_Estandarizado", pd.Series(dtype=str))
    sqls_unique_vals = sql_series_for_options.astype(str).dropna().unique()
    sqls_opts_ordered = ["– Todos –"] + [s for s in SQL_ORDER_OF_IMPORTANCE if s in sqls_unique_vals] + sorted([s for s in sqls_unique_vals if s not in SQL_ORDER_OF_IMPORTANCE])
    current_sql_selection = st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"])
    valid_sql_default = [s for s in current_sql_selection if s in sqls_opts_ordered]
    if not valid_sql_default: valid_sql_default = ["– Todos –"] if "– Todos –" in sqls_opts_ordered else ([sqls_opts_ordered[0]] if sqls_opts_ordered and sqls_opts_ordered[0] != "– Todos –" else [])
    st.sidebar.multiselect("Calificación SQL", sqls_opts_ordered, key=SES_SQL_FILTER_KEY, default=valid_sql_default)
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback, use_container_width=True, key=f"{FILTER_KEYS_PREFIX}btn_clear") # Tu key original
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], sel_y,
            st.session_state[SES_WEEK_FILTER_KEY], st.session_state[SES_AE_FILTER_KEY],
            st.session_state[SES_LG_FILTER_KEY], st.session_state[SES_PAIS_FILTER_KEY],
            st.session_state[SES_SQL_FILTER_KEY])

def apply_sesiones_filters(df, start_date, end_date, year_f, week_f, ae_f, lg_f, pais_f, sql_f):
    # (Tu código original)
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
    if ae_f and "– Todos –" not in ae_f and "AE" in df_f.columns: df_f = df_f[df_f["AE"].astype(str).isin([str(i) for i in ae_f])] # astype(str)
    if lg_f and "– Todos –" not in lg_f and "LG" in df_f.columns: df_f = df_f[df_f["LG"].astype(str).isin([str(i) for i in lg_f])] # astype(str)
    if pais_f and "– Todos –" not in pais_f and "País" in df_f.columns: df_f = df_f[df_f["País"].astype(str).isin([str(i) for i in pais_f])] # astype(str)
    if sql_f and "– Todos –" not in sql_f and "SQL_Estandarizado" in df_f.columns: df_f = df_f[df_f["SQL_Estandarizado"].astype(str).isin([str(i) for i in sql_f])] # astype(str)
    return df_f

def get_sql_category_order(df_column_or_list):
    # (Tu código original)
    present_sqls = pd.Series(df_column_or_list).astype(str).unique()
    ordered_present_sqls = [s for s in SQL_ORDER_OF_IMPORTANCE if s in present_sqls]
    other_sqls = sorted([s for s in present_sqls if s not in ordered_present_sqls])
    return ordered_present_sqls + other_sqls
    
def display_sesiones_summary_sql(df_filtered):
    # (Tu código original)
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
    # (Tu código original)
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para análisis por {dimension_label}.")
        return
    sql_category_order_dim_analysis = get_sql_category_order(df_filtered['SQL_Estandarizado'])
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
    pivot_table_cols_ordered_dim = [col for col in sql_category_order_dim_analysis if col in pivot_table_dim.columns] + [col for col in pivot_table_dim.columns if col not in sql_category_order_dim_analysis]
    pivot_table_dim = pivot_table_dim.reindex(columns=pivot_table_cols_ordered_dim, fill_value=0)
    if not pivot_table_dim.empty and not top_n_dims and dimension_col in pivot_table_dim.index.names : 
         top_n_dims = pivot_table_dim.index.tolist() 
    if top_n_dims: 
        pivot_table_dim = pivot_table_dim.reindex(index=top_n_dims, fill_value=0)
    pivot_table_dim['Total_Sesiones_Dim'] = pivot_table_dim.sum(axis=1)
    for col_pivot_format_dim in pivot_table_dim.columns:
        try:
            pivot_table_dim[col_pivot_format_dim] = pd.to_numeric(pivot_table_dim[col_pivot_format_dim], errors='coerce').fillna(0).astype(int)
        except ValueError:
            pivot_table_dim[col_pivot_format_dim] = pivot_table_dim[col_pivot_format_dim].astype(str)
    format_dict_dim = {col: "{:,.0f}" for col in pivot_table_dim.columns if pd.api.types.is_numeric_dtype(pivot_table_dim[col])}
    st.dataframe(pivot_table_dim.style.format(format_dict_dim) if format_dict_dim else pivot_table_dim, use_container_width=True)

def display_evolucion_sql(df_filtered, time_agg_col, display_label, chart_title, x_axis_label):
    # (Tu código original)
    st.markdown(f"### 📈 {chart_title}")
    if df_filtered.empty or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para {chart_title.lower()}.")
        return
    df_agg_evol = df_filtered.copy()
    group_col_evol = time_agg_col
    if time_agg_col == 'NumSemana':
        if not ('Año' in df_agg_evol.columns and 'NumSemana' in df_agg_evol.columns):
            st.warning("Faltan Año/NumSemana para evolución.")
            return
        df_agg_evol.dropna(subset=['Año', 'NumSemana'], inplace=True) 
        if df_agg_evol.empty:
            st.info("No hay datos para evolución semanal.")
            return
        df_agg_evol['Año-Semana'] = df_agg_evol['Año'].astype(str) + '-S' + df_agg_evol['NumSemana'].astype(str).str.zfill(2)
        group_col_evol = 'Año-Semana'
        df_agg_evol = df_agg_evol.sort_values(by=group_col_evol)
    elif time_agg_col == 'AñoMes':
        if 'AñoMes' not in df_agg_evol.columns:
            st.warning("Columna 'AñoMes' faltante para evolución.")
            return
        df_agg_evol = df_agg_evol.sort_values(by='AñoMes')
    sql_category_order_evol = get_sql_category_order(df_agg_evol['SQL_Estandarizado'])
    summary_time_sql_evol = df_agg_evol.groupby([group_col_evol, 'SQL_Estandarizado'], as_index=False, observed=False)['Fecha'].count().rename(columns={'Fecha': 'Número de Sesiones'})
    if summary_time_sql_evol.empty:
        st.info(f"No hay datos agregados por {x_axis_label.lower()} y SQL.")
        return
    summary_time_sql_evol['SQL_Estandarizado'] = pd.Categorical(summary_time_sql_evol['SQL_Estandarizado'], categories=sql_category_order_evol, ordered=True)
    summary_time_sql_evol = summary_time_sql_evol.sort_values([group_col_evol, 'SQL_Estandarizado'])
    st.dataframe(summary_time_sql_evol.style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
    try:
        fig_evol_sql = px.line(summary_time_sql_evol, x=group_col_evol, y='Número de Sesiones', color='SQL_Estandarizado', title=f"Evolución por SQL ({x_axis_label})", markers=True, category_orders={"SQL_Estandarizado": sql_category_order_evol})
        st.plotly_chart(fig_evol_sql, use_container_width=True)
    except Exception as e_evol_sql:
        st.warning(f"No se pudo generar gráfico de evolución: {e_evol_sql}")

def display_tabla_sesiones_detalle(df_filtered):
    # (Tu código original)
    st.markdown("### 📝 Tabla Detallada de Sesiones")
    if df_filtered.empty:
        st.info("No hay sesiones detalladas para mostrar con los filtros aplicados.") 
        return
    cols_display_detalle_ses = ["Fecha", "LG", "AE", "País", "SQL", "SQL_Estandarizado", "Empresa", "Puesto", "Nombre", "Apellido", "Siguientes Pasos", "Fuente_Hoja", "LinkedIn"]
    cols_present_detalle_ses = [col for col in cols_display_detalle_ses if col in df_filtered.columns]
    df_view_detalle_ses = df_filtered[cols_present_detalle_ses].copy()
    if "Fecha" in df_view_detalle_ses.columns and pd.api.types.is_datetime64_any_dtype(df_view_detalle_ses["Fecha"]):
        df_view_detalle_ses["Fecha"] = pd.to_datetime(df_view_detalle_ses["Fecha"]).dt.strftime('%d/%m/%Y')
    st.dataframe(df_view_detalle_ses, height=400, use_container_width=True)
    if not df_view_detalle_ses.empty:
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_view_detalle_ses.to_excel(writer, index=False, sheet_name='Detalle_Sesiones')
        st.download_button(
            label="⬇️ Descargar Detalle (Excel)", data=output.getvalue(),
            file_name="detalle_sesiones_sql.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=f"{FILTER_KEYS_PREFIX}btn_download_detalle") # Tu key original

# --- Flujo Principal de la Página ---
# (Tu código original para el flujo principal)
df_sesiones_raw = load_sesiones_data()

if df_sesiones_raw is None or df_sesiones_raw.empty:
    st.error("Fallo Crítico al cargar datos de Sesiones o no hay datos. La página no puede continuar.")
    st.stop()

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
st.info( # Tu pie de página original
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
