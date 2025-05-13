# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import gspread
# from oauth2client.service_account import ServiceAccountCredentials # Comentado, gspread >= 5 usa dict
import datetime
import plotly.express as px
import os
import sys
import io
import re
from collections import OrderedDict # Para eliminar duplicados manteniendo orden

# --- Configuración Inicial del Proyecto y Título de la Página ---
try:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except NameError: # Esto ocurre si __file__ no está definido (ej. en un notebook interactivo)
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

st.set_page_config(layout="wide", page_title="Análisis de Sesiones y SQL")
st.title("📊 Análisis de Sesiones y Calificaciones SQL")
st.markdown(
    "Métricas basadas en columnas principales: LG, AE, País, Calificación SQL, Puesto, Empresa."
)

# --- Constantes ---
SHEET_URL_SESIONES_PRINCIPAL_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902"
SHEET_NAME_SESIONES_PRINCIPAL = "Sesiones 2024-2025"

SHEET_URL_SESIONES_SURAMERICA_DEFAULT = "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854"
SHEET_NAME_SESIONES_SURAMERICA = "SesionesSA 2024-2025" # Asegúrate que este nombre sea EXACTO

COLUMNAS_CENTRALES = [
    "Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL", "SQL_Estandarizado",
    "AE", "LG", "Siguientes Pasos", "Email", "RPA", "LinkedIn",
    "Fuente_Hoja", "Año", "NumSemana", "MesNombre", "AñoMes",
]
SQL_ORDER_OF_IMPORTANCE = ['SQL1', 'SQL2', 'MQL', 'NA', 'SIN CALIFICACIÓN SQL']
DF_FINAL_STRUCTURE_EMPTY = pd.DataFrame(columns=COLUMNAS_CENTRALES)

# --- Gestión de Estado de Sesión para Filtros ---
FILTER_KEYS_PREFIX = "sesiones_sql_lg_pais_page_v5_" # Incrementado v4 a v5 por debug
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
def make_unique_headers(headers_list):
    counts = {}; new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else ""
        if not h_stripped: h_stripped = "Columna_Vacia"
        if h_stripped in counts:
            counts[h_stripped] += 1; new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
        else:
            counts[h_stripped] = 1; new_headers.append(h_stripped)
    return new_headers

def parse_date_robust(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "": return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)): return pd.to_datetime(date_val)
    date_str = str(date_val).strip()
    common_formats = ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
                      "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
                      "%m/%d/%Y %H:%M:%S", "%m/%d/%Y")
    for fmt in common_formats:
        try: return pd.to_datetime(date_str, format=fmt)
        except (ValueError, TypeError): continue
    try: return pd.to_datetime(date_str, errors='coerce')
    except (ValueError, TypeError): return pd.NaT

def separar_nombre_cargo_suramerica(nombre_cargo_str):
    nombre, apellido, puesto = pd.NA, pd.NA, "No Especificado"
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
                puesto = parts[1].strip(); cargo_encontrado_explicitamente = True
            break
    name_parts = [part.strip() for part in nombre_completo_str.split() if part.strip()]
    if not name_parts: return pd.NA, pd.NA, puesto
    if len(name_parts) == 1: nombre = name_parts[0]
    elif len(name_parts) == 2: nombre, apellido = name_parts[0], name_parts[1]
    elif len(name_parts) == 3: nombre, apellido = name_parts[0], f"{name_parts[1]} {name_parts[2]}"
    elif len(name_parts) >= 4:
        nombre = f"{name_parts[0]} {name_parts[1]}"; apellido = " ".join(name_parts[2:])
        if not cargo_encontrado_explicitamente:
            temp_nombre_simple, temp_apellido_simple = name_parts[0], name_parts[1]
            temp_cargo_implicito_parts = name_parts[2:]
            if len(temp_cargo_implicito_parts) >= 1:
                 temp_cargo_str = " ".join(temp_cargo_implicito_parts)
                 if len(temp_cargo_str) > 3 :
                    nombre, apellido, puesto = temp_nombre_simple, temp_apellido_simple, temp_cargo_str
    if pd.isna(nombre) and pd.notna(nombre_completo_str) and nombre_completo_str: nombre = nombre_completo_str
    return (str(nombre).strip() if pd.notna(nombre) else pd.NA,
            str(apellido).strip() if pd.notna(apellido) else pd.NA,
            str(puesto).strip() if pd.notna(puesto) and puesto else "No Especificado")

@st.cache_data(ttl=300)
def load_sesiones_data():
    try:
        creds_dict_sesiones = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict_sesiones)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta [gcp_service_account] en Streamlit Secrets (Sesiones).")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar credenciales para Sesiones: {e}")
        st.stop()

    all_dataframes = []
    processing_warnings = []

    try: # Hoja Principal
        workbook_principal = client.open_by_url(SHEET_URL_SESIONES_PRINCIPAL_DEFAULT)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES_PRINCIPAL)
        raw_data_principal_list = sheet_principal.get_all_values()
        if raw_data_principal_list and len(raw_data_principal_list) > 1:
            headers_p = make_unique_headers(raw_data_principal_list[0])
            df_principal_raw = pd.DataFrame(raw_data_principal_list[1:], columns=headers_p)
            df_proc_p = pd.DataFrame()
            for col in ["Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL", "AE", "LG", "Siguientes Pasos", "Email", "RPA", "LinkedIn"]:
                df_proc_p[col] = df_principal_raw.get(col)
            df_proc_p["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_proc_p)
        else: processing_warnings.append(f"Hoja Principal ('{SHEET_NAME_SESIONES_PRINCIPAL}') vacía o sin encabezados.")
    except Exception as e:
        import traceback
        detailed_error = traceback.format_exc()
        processing_warnings.append(f"ADVERTENCIA al cargar Hoja Principal. Tipo: {type(e)}, Error: {e}, Traceback: {detailed_error}")

    try: # Hoja Suramérica
        workbook_suramerica = client.open_by_url(SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        raw_data_suramerica_list = sheet_suramerica.get_all_values()
        if raw_data_suramerica_list and len(raw_data_suramerica_list) > 1:
            headers_sa = make_unique_headers(raw_data_suramerica_list[0])
            df_suramerica_raw = pd.DataFrame(raw_data_suramerica_list[1:], columns=headers_sa)
            if not df_suramerica_raw.empty:
                df_proc_sa = pd.DataFrame()
                map_cols_sa = {"Fecha": "Fecha", "Empresa": "Empresa", "País": "País", "Siguientes Pasos": "Siguientes Pasos",
                               "SQL": "SQL", "Correo": "Email", "LinkedIn": "LinkedIn", "LG": "LG", "AE": "AE"}
                for orig_col, new_col in map_cols_sa.items():
                    df_proc_sa[new_col] = df_suramerica_raw.get(orig_col)
                if "Nombre y Cargo" in df_suramerica_raw.columns:
                    n_c_split = df_suramerica_raw["Nombre y Cargo"].apply(separar_nombre_cargo_suramerica)
                    df_proc_sa["Nombre"] = n_c_split.apply(lambda x: x[0])
                    df_proc_sa["Apellido"] = n_c_split.apply(lambda x: x[1])
                    df_proc_sa["Puesto"] = n_c_split.apply(lambda x: x[2])
                else: df_proc_sa["Nombre"], df_proc_sa["Apellido"], df_proc_sa["Puesto"] = pd.NA, pd.NA, "No Especificado"
                df_proc_sa["Fuente_Hoja"] = "Suramérica"
                all_dataframes.append(df_proc_sa)
        else: processing_warnings.append(f"Hoja Suramérica ('{SHEET_NAME_SESIONES_SURAMERICA}') vacía o sin encabezados.")
    except Exception as e:
        import traceback
        detailed_error = traceback.format_exc()
        processing_warnings.append(f"ADVERTENCIA al cargar Hoja Suramérica. Tipo: {type(e)}, Error: {e}, Traceback: {detailed_error}")

    if processing_warnings:
        for warning_msg in processing_warnings: st.warning(warning_msg)
    if not all_dataframes:
        st.error("No se pudieron cargar datos de ninguna fuente.")
        return DF_FINAL_STRUCTURE_EMPTY.copy()

    df_consolidado = pd.concat(all_dataframes, ignore_index=True, sort=False)
    if "Fecha" not in df_consolidado.columns or df_consolidado["Fecha"].isnull().all():
        st.error("Columna 'Fecha' no encontrada o vacía en datos consolidados.")
        return DF_FINAL_STRUCTURE_EMPTY.copy()
    df_consolidado["Fecha"] = df_consolidado["Fecha"].apply(parse_date_robust)
    df_consolidado.dropna(subset=["Fecha"], inplace=True)
    if df_consolidado.empty:
        st.info("No hay datos con fechas válidas.")
        return DF_FINAL_STRUCTURE_EMPTY.copy()

    df_procesado = df_consolidado.copy()
    try:
        df_procesado['Año'] = df_procesado['Fecha'].dt.year.astype('Int64')
        df_procesado['NumSemana'] = df_procesado['Fecha'].dt.isocalendar().week.astype('Int64')
        df_procesado['MesNombre'] = df_procesado['Fecha'].dt.strftime('%B')
        df_procesado['AñoMes'] = df_procesado['Fecha'].dt.strftime('%Y-%m')
    except Exception as e_time:
        st.error(f"Error creando columnas de tiempo: {e_time}")
        for col_t in ['Año', 'NumSemana', 'MesNombre', 'AñoMes']: df_procesado[col_t] = pd.NA

    # --- INICIO DE CORRECCIÓN LÓGICA SQL (CON DEPURACIÓN) ---
    default_values_fill = {
        "AE": "No Asignado AE", "LG": "No Asignado LG", "Puesto": "No Especificado",
        "Empresa": "No Especificado", "País": "No Especificado", "Nombre": "No Especificado",
        "Apellido": "No Especificado", "Siguientes Pasos": "No Especificado",
        "Email": "No Especificado", "RPA": "No Aplicable", "LinkedIn": "No Especificado",
        "Fuente_Hoja": "Desconocida",
        "SQL": "TEMP_EMPTY_SQL", 
        "SQL_Estandarizado": "TEMP_EMPTY_SQL"
    }
    generic_empty_na_values_general = ['', 'nan', 'none', 'NaN', 'None', '<NA>', '#N/A', 'N/A', 'na', 'nd', 'n/d', 's/d', 's.d.']

    for col_name in COLUMNAS_CENTRALES:
        if col_name in ['Fecha', 'Año', 'NumSemana', 'MesNombre', 'AñoMes']: continue
        default_val = default_values_fill.get(col_name, "No Especificado")
        if col_name not in df_procesado.columns:
            df_procesado[col_name] = default_val
        else:
            if col_name != "SQL":
                df_procesado[col_name] = df_procesado[col_name].fillna(default_val)
        df_procesado[col_name] = df_procesado[col_name].astype(str)
        if col_name != "SQL":
            current_col_lower = df_procesado[col_name].str.lower()
            for empty_pattern in generic_empty_na_values_general:
                current_col_lower = current_col_lower.replace(empty_pattern, default_val.lower(), regex=False)
            df_procesado[col_name] = current_col_lower.str.strip()
            df_procesado.loc[df_procesado[col_name] == '', col_name] = default_val
            if col_name not in ["SQL_Estandarizado", "Email", "LinkedIn", "RPA", "Fuente_Hoja"]:
                 df_procesado[col_name] = df_procesado[col_name].str.title()
                 df_procesado[col_name] = df_procesado[col_name].replace(default_val.title(), default_val, regex=False)

    st.write("DEBUG: Inicio de Estandarización SQL")

    if "SQL" not in df_procesado.columns:
        df_procesado["SQL"] = default_values_fill["SQL"]
    
    st.write("DEBUG: Valores ÚNICOS en df_procesado['SQL'] ANTES de fillna y limpieza:", df_procesado["SQL"].unique()[:20])
    st.write("DEBUG: Conteos en df_procesado['SQL'] ANTES de fillna y limpieza:", df_procesado["SQL"].value_counts(dropna=False).head(10))

    df_procesado["SQL"] = df_procesado["SQL"].fillna(default_values_fill["SQL"])
    df_procesado["SQL"] = df_procesado["SQL"].astype(str).str.strip().str.upper()

    st.write("DEBUG: Valores ÚNICOS en df_procesado['SQL'] DESPUÉS de fillna, strip, upper:", df_procesado["SQL"].unique()[:20])
    st.write("DEBUG: Conteos en df_procesado['SQL'] DESPUÉS de fillna, strip, upper:", df_procesado["SQL"].value_counts(dropna=False).head(10))

    empty_patterns_for_sql = ["", "NAN", "NONE", "<NA>", "N/A", "ND", "N.D", "S/D", "S.D.", "TEMP_EMPTY_SQL", "NO ESPECIFICADO", "NO ASIGNADO SQL"]
    
    df_procesado["SQL_Estandarizado"] = df_procesado["SQL"].copy()

    for pattern in empty_patterns_for_sql:
        df_procesado.loc[df_procesado["SQL_Estandarizado"] == pattern.upper(), "SQL_Estandarizado"] = "PLACEHOLDER_FOR_SIN_CALIFICACION"
    
    st.write("DEBUG: Valores ÚNICOS en df_procesado['SQL_Estandarizado'] DESPUÉS de marcar placeholders:", df_procesado["SQL_Estandarizado"].unique()[:20])
    st.write("DEBUG: Conteos en df_procesado['SQL_Estandarizado'] DESPUÉS de marcar placeholders:", df_procesado["SQL_Estandarizado"].value_counts(dropna=False).head(10))

    df_procesado.loc[df_procesado["SQL_Estandarizado"] == "PLACEHOLDER_FOR_SIN_CALIFICACION", "SQL_Estandarizado"] = "SIN CALIFICACIÓN SQL"

    st.write("DEBUG: Valores ÚNICOS en df_procesado['SQL_Estandarizado'] DESPUÉS de asignar 'SIN CALIFICACIÓN SQL':", df_procesado["SQL_Estandarizado"].unique()[:20])
    st.write("DEBUG: Conteos en df_procesado['SQL_Estandarizado'] DESPUÉS de asignar 'SIN CALIFICACIÓN SQL':", df_procesado["SQL_Estandarizado"].value_counts(dropna=False).head(10))

    valid_explicit_sql_values = ['SQL1', 'SQL2', 'MQL', 'NA'] 
    st.write(f"DEBUG: valid_explicit_sql_values = {valid_explicit_sql_values}")

    mask_others_to_standardize = ~df_procesado["SQL_Estandarizado"].isin(valid_explicit_sql_values + ["SIN CALIFICACIÓN SQL"])
    
    st.write(f"DEBUG: Número de filas que cumplen 'mask_others_to_standardize': {mask_others_to_standardize.sum()}")
    st.write("DEBUG: Valores ÚNICOS en 'SQL_Estandarizado' que serán cambiados por 'mask_others_to_standardize':", df_procesado.loc[mask_others_to_standardize, "SQL_Estandarizado"].unique()[:20])

    df_procesado.loc[mask_others_to_standardize, "SQL_Estandarizado"] = "SIN CALIFICACIÓN SQL"

    st.write("DEBUG: Valores ÚNICOS FINALES en df_procesado['SQL_Estandarizado']:", df_procesado["SQL_Estandarizado"].unique()[:20])
    st.write("DEBUG: Conteos FINALES en df_procesado['SQL_Estandarizado']:", df_procesado["SQL_Estandarizado"].value_counts(dropna=False).head(10))
    st.write("--- FIN DEBUG SQL ---")
    # --- FIN DE CORRECCIÓN LÓGICA SQL (CON DEPURACIÓN) ---

    df_final_structure = pd.DataFrame()
    for col in COLUMNAS_CENTRALES:
        if col in df_procesado.columns:
            df_final_structure[col] = df_procesado[col]
        else:
            if col in ['Año', 'NumSemana']: df_final_structure[col] = pd.Series(dtype='Int64')
            elif col == 'Fecha': df_final_structure[col] = pd.Series(dtype='datetime64[ns]')
            else: df_final_structure[col] = pd.Series(dtype='object')
    try:
        if 'Fecha' in df_final_structure.columns: df_final_structure['Fecha'] = pd.to_datetime(df_final_structure['Fecha'], errors='coerce')
        if 'Año' in df_final_structure.columns: df_final_structure['Año'] = pd.to_numeric(df_final_structure['Año'], errors='coerce').astype('Int64')
        if 'NumSemana' in df_final_structure.columns: df_final_structure['NumSemana'] = pd.to_numeric(df_final_structure['NumSemana'], errors='coerce').astype('Int64')
    except Exception as e_type_final: st.warning(f"ADVERTENCIA al ajustar tipos finales: {e_type_final}")
    return df_final_structure.reset_index(drop=True)

def clear_ses_filters_callback():
    for key, value in default_filters_config.items(): st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")

def sidebar_filters_sesiones(df_options):
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")
    min_d, max_d = (None, None)
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) and not df_options["Fecha"].dropna().empty:
        min_d_series, max_d_series = df_options["Fecha"].dropna().min(), df_options["Fecha"].dropna().max()
        if pd.notna(min_d_series) and pd.notna(max_d_series): min_d, max_d = min_d_series.date(), max_d_series.date()
    c1, c2 = st.sidebar.columns(2)
    start_date_val_state, end_date_val_state = st.session_state.get(SES_START_DATE_KEY), st.session_state.get(SES_END_DATE_KEY)
    start_date_for_input = start_date_val_state.date() if isinstance(start_date_val_state, datetime.datetime) else (start_date_val_state if isinstance(start_date_val_state, datetime.date) else None)
    end_date_for_input = end_date_val_state.date() if isinstance(end_date_val_state, datetime.datetime) else (end_date_val_state if isinstance(end_date_val_state, datetime.date) else None)
    c1.date_input("Desde", value=start_date_for_input, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    c2.date_input("Hasta", value=end_date_for_input, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Por Año y Semana")
    year_options_ses = ["– Todos –"]
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
        try:
            unique_years_int = sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True)
            year_options_ses.extend([str(year) for year in unique_years_int])
        except ValueError:
            unique_years_str = sorted(df_options["Año"].dropna().astype(str).unique(), reverse=True)
            year_options_ses.extend(unique_years_str)
    current_year_selection_ses = str(st.session_state.get(SES_YEAR_FILTER_KEY, "– Todos –"))
    if current_year_selection_ses not in year_options_ses:
        current_year_selection_ses = "– Todos –"; st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses
    selected_year_index_ses = 0
    try: selected_year_index_ses = year_options_ses.index(current_year_selection_ses)
    except ValueError:
        if year_options_ses: current_year_selection_ses = year_options_ses[0]; st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses
        else: year_options_ses = ["(No hay años)"]; current_year_selection_ses = year_options_ses[0]; st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses
        selected_year_index_ses = 0
    selected_year_str_ses = st.sidebar.selectbox("Año", options=year_options_ses, index=selected_year_index_ses, key=SES_YEAR_FILTER_KEY)
    sel_y = None
    if selected_year_str_ses != "– Todos –":
        try: sel_y = int(selected_year_str_ses)
        except ValueError: sel_y = None
    week_options_ses = ["– Todas –"]
    df_for_week_ses = df_options[df_options["Año"] == sel_y] if sel_y is not None and "Año" in df_options.columns else df_options
    num_semana_series = df_for_week_ses.get("NumSemana")
    if num_semana_series is not None and not num_semana_series.dropna().empty:
        try:
            unique_weeks_for_year = sorted(num_semana_series.dropna().astype(int).unique())
            week_options_ses.extend([str(w) for w in unique_weeks_for_year])
        except ValueError:
             unique_weeks_str = sorted(num_semana_series.dropna().astype(str).unique())
             week_options_ses.extend(unique_weeks_str)
    current_week_selection_state_ses = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    if not isinstance(current_week_selection_state_ses, list): current_week_selection_state_ses = ["– Todas –"]
    valid_week_selection_ses = [s for s in current_week_selection_state_ses if s in week_options_ses]
    if not valid_week_selection_ses:
        if "– Todas –" in week_options_ses: valid_week_selection_ses = ["– Todas –"]
        elif week_options_ses and week_options_ses[0] != "– Todas –": valid_week_selection_ses = []
        else: valid_week_selection_ses = []
    if set(valid_week_selection_ses) != set(st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])):
        st.session_state[SES_WEEK_FILTER_KEY] = valid_week_selection_ses
    st.sidebar.multiselect("Semanas", options=week_options_ses, key=SES_WEEK_FILTER_KEY, default=valid_week_selection_ses)
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")
    def create_multiselect_options(df_col_series, session_key):
        options_list = ["– Todos –"]
        if df_col_series is not None and not df_col_series.dropna().empty:
            unique_vals = df_col_series.astype(str).str.strip().replace('', 'N/D', regex=False).unique()
            unique_vals_cleaned = [val for val in unique_vals if val and val != 'N/D']
            options_list.extend(sorted(list(set(unique_vals_cleaned))))
            if 'N/D' in unique_vals and 'N/D' not in options_list : options_list.append('N/D')
        current_sel = st.session_state.get(session_key, ["– Todos –"])
        if not isinstance(current_sel, list): current_sel = ["– Todos –"]
        valid_sel = [s for s in current_sel if s in options_list]
        if not valid_sel:
            if "– Todos –" in options_list: valid_sel = ["– Todos –"]
            elif options_list and options_list[0] != "– Todos –" : valid_sel = []
            else: valid_sel = []
        if set(valid_sel) != set(st.session_state.get(session_key, ["– Todos –"])): st.session_state[session_key] = valid_sel
        return options_list, valid_sel
    lgs_options, valid_lg_default = create_multiselect_options(df_options.get("LG"), SES_LG_FILTER_KEY)
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=valid_lg_default)
    ae_options, valid_ae_default = create_multiselect_options(df_options.get("AE"), SES_AE_FILTER_KEY)
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=valid_ae_default)
    paises_opts, valid_pais_default = create_multiselect_options(df_options.get("País"), SES_PAIS_FILTER_KEY)
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=valid_pais_default)
    sql_series_for_options = df_options.get("SQL_Estandarizado")
    sqls_opts_ordered = ["– Todos –"]
    if sql_series_for_options is not None and not sql_series_for_options.dropna().empty:
        sqls_unique_vals = sql_series_for_options.astype(str).dropna().unique()
        sqls_opts_ordered.extend([s for s in SQL_ORDER_OF_IMPORTANCE if s in sqls_unique_vals])
        others_sqls = sorted([s for s in sqls_unique_vals if s not in SQL_ORDER_OF_IMPORTANCE and s != "– Todos –"])
        sqls_opts_ordered.extend(others_sqls)
        sqls_opts_ordered = list(OrderedDict.fromkeys(sqls_opts_ordered))
    current_sql_selection = st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"])
    if not isinstance(current_sql_selection, list): current_sql_selection = ["– Todos –"]
    valid_sql_default = [s for s in current_sql_selection if s in sqls_opts_ordered]
    if not valid_sql_default:
        if "– Todos –" in sqls_opts_ordered: valid_sql_default = ["– Todos –"]
        elif sqls_opts_ordered and sqls_opts_ordered[0] != "– Todos –": valid_sql_default = []
        else: valid_sql_default = []
    if set(valid_sql_default) != set(st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"])): st.session_state[SES_SQL_FILTER_KEY] = valid_sql_default
    st.sidebar.multiselect("Calificación SQL", sqls_opts_ordered, key=SES_SQL_FILTER_KEY, default=valid_sql_default)
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback, use_container_width=True, key=f"{FILTER_KEYS_PREFIX}btn_clear")
    return (st.session_state.get(SES_START_DATE_KEY), st.session_state.get(SES_END_DATE_KEY), sel_y,
            st.session_state.get(SES_WEEK_FILTER_KEY), st.session_state.get(SES_AE_FILTER_KEY),
            st.session_state.get(SES_LG_FILTER_KEY), st.session_state.get(SES_PAIS_FILTER_KEY),
            st.session_state.get(SES_SQL_FILTER_KEY))

def apply_sesiones_filters(df, start_date, end_date, year_f, week_f_list, ae_f_list, lg_f_list, pais_f_list, sql_f_list):
    if df is None or df.empty: return DF_FINAL_STRUCTURE_EMPTY.copy()
    df_f = df.copy()
    if "Fecha" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f["Fecha"]):
        start_dt = pd.to_datetime(start_date, errors='coerce').normalize() if start_date else None
        end_dt = pd.to_datetime(end_date, errors='coerce').normalize() if end_date else None
        fecha_series_norm = df_f["Fecha"].dt.normalize()
        if start_dt and end_dt: df_f = df_f[(fecha_series_norm >= start_dt) & (fecha_series_norm <= end_dt)]
        elif start_dt: df_f = df_f[fecha_series_norm >= start_dt]
        elif end_dt: df_f = df_f[fecha_series_norm <= end_dt]
    if year_f is not None and "Año" in df_f.columns:
        try: df_f = df_f[df_f["Año"].astype(int) == year_f]
        except (ValueError, TypeError): st.warning("No se pudo aplicar filtro de año por tipo incompatible.")
    if week_f_list and "– Todas –" not in week_f_list and "NumSemana" in df_f.columns:
        try:
            selected_weeks_int = [int(w) for w in week_f_list if isinstance(w, str) and w.isdigit()]
            if selected_weeks_int: df_f = df_f[df_f["NumSemana"].astype(int).isin(selected_weeks_int)]
        except (ValueError, TypeError): st.warning("Semanas seleccionadas contienen valores no numéricos o 'NumSemana' no es numérico.")
    filter_map = {"AE": ae_f_list, "LG": lg_f_list, "País": pais_f_list, "SQL_Estandarizado": sql_f_list}
    for col_name, filter_values in filter_map.items():
        if filter_values and "– Todos –" not in filter_values and col_name in df_f.columns:
            df_f = df_f[df_f[col_name].astype(str).isin([str(val) for val in filter_values])]
    return df_f

def get_sql_category_order(df_column_or_list):
    present_sqls_series = pd.Series(df_column_or_list).astype(str).dropna().unique()
    ordered_present_sqls = [s for s in SQL_ORDER_OF_IMPORTANCE if s in present_sqls_series]
    other_sqls = sorted([s for s in present_sqls_series if s not in SQL_ORDER_OF_IMPORTANCE])
    return ordered_present_sqls + other_sqls

def display_sesiones_summary_sql(df_filtered):
    st.markdown("### 📌 Resumen Principal de Sesiones")
    if df_filtered.empty: st.info("No hay sesiones para resumen con los filtros aplicados."); return
    total_sesiones = len(df_filtered); st.metric("Total Sesiones (filtradas)", f"{total_sesiones:,}")
    if 'SQL_Estandarizado' in df_filtered.columns:
        st.markdown("#### Distribución por Calificación SQL")
        sql_counts = df_filtered['SQL_Estandarizado'].value_counts().reset_index()
        sql_counts.columns = ['Calificación SQL', 'Número de Sesiones']
        category_order_sql_summary = get_sql_category_order(sql_counts['Calificación SQL'])
        sql_counts['Calificación SQL'] = pd.Categorical(sql_counts['Calificación SQL'], categories=category_order_sql_summary, ordered=True)
        sql_counts = sql_counts.sort_values('Calificación SQL').reset_index(drop=True)
        if not sql_counts.empty:
            fig_sql_summary = px.bar(sql_counts, x='Calificación SQL', y='Número de Sesiones', title='Sesiones por Calificación SQL', text_auto=True, color='Calificación SQL')
            fig_sql_summary.update_xaxes(categoryorder='array', categoryarray=category_order_sql_summary)
            st.plotly_chart(fig_sql_summary, use_container_width=True)
            st.dataframe(sql_counts.set_index('Calificación SQL').style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
        else: st.info("No hay datos de calificación SQL para mostrar.")
    else: st.warning("Columna 'SQL_Estandarizado' no encontrada para el resumen.")

def display_analisis_por_dimension(df_filtered, dimension_col, dimension_label, top_n=10):
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para análisis por {dimension_label}."); return
    df_filtered_copy = df_filtered.copy()
    df_filtered_copy[dimension_col] = df_filtered_copy[dimension_col].astype(str)
    dim_totals = df_filtered_copy[dimension_col].value_counts().nlargest(top_n)
    top_n_dims_list = dim_totals.index.tolist()
    df_top_n = df_filtered_copy[df_filtered_copy[dimension_col].isin(top_n_dims_list)]
    if df_top_n.empty: st.info(f"No hay datos para el Top {top_n} de {dimension_label}."); return
    summary_dim_sql = df_top_n.groupby([dimension_col, 'SQL_Estandarizado'], observed=False).size().reset_index(name='Cantidad_SQL')
    if summary_dim_sql.empty: st.info(f"No hay datos agregados por {dimension_label} y SQL para el Top {top_n}."); return
    sql_category_order_dim_analysis = get_sql_category_order(summary_dim_sql['SQL_Estandarizado'])
    summary_dim_sql['SQL_Estandarizado'] = pd.Categorical(summary_dim_sql['SQL_Estandarizado'], categories=sql_category_order_dim_analysis, ordered=True)
    summary_dim_sql[dimension_col] = pd.Categorical(summary_dim_sql[dimension_col], categories=top_n_dims_list, ordered=True)
    summary_dim_sql = summary_dim_sql.sort_values(by=[dimension_col, 'SQL_Estandarizado'])
    fig_dim_analysis = px.bar(summary_dim_sql, x=dimension_col, y='Cantidad_SQL', color='SQL_Estandarizado', title=f'Distribución de SQL por {dimension_label} (Top {top_n})', barmode='stack', color_discrete_sequence=px.colors.qualitative.Vivid)
    fig_dim_analysis.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Sesiones", xaxis={'categoryorder':'array', 'categoryarray':top_n_dims_list}, legend_title_text='Calificación SQL')
    st.plotly_chart(fig_dim_analysis, use_container_width=True)
    try:
        pivot_table_dim = summary_dim_sql.pivot_table(index=dimension_col, columns='SQL_Estandarizado', values='Cantidad_SQL', fill_value=0, observed=False)
        pivot_table_dim = pivot_table_dim.reindex(columns=sql_category_order_dim_analysis, fill_value=0).reindex(index=top_n_dims_list, fill_value=0)
        pivot_table_dim['Total_Sesiones_Dim'] = pivot_table_dim.sum(axis=1)
        format_dict_dim = {col: "{:,.0f}" for col in pivot_table_dim.columns}
        st.dataframe(pivot_table_dim.style.format(format_dict_dim), use_container_width=True)
    except Exception as e_pivot: st.warning(f"No se pudo generar la tabla pivot para {dimension_label}: {e_pivot}")

def display_evolucion_sql(df_filtered, time_agg_col, display_label_col_name, chart_title, x_axis_label): # Renombrado display_label a display_label_col_name
    st.markdown(f"### 📈 {chart_title}")
    required_cols = ['SQL_Estandarizado', time_agg_col]
    if time_agg_col == 'NumSemana' and ('Año' not in df_filtered.columns or 'NumSemana' not in df_filtered.columns) :
        st.info(f"Datos insuficientes. Se requieren 'Año' y 'NumSemana'."); return
    if df_filtered.empty or not all(col in df_filtered.columns for col in required_cols):
        st.info(f"Datos insuficientes. Columnas requeridas: {required_cols}"); return

    df_agg_evol = df_filtered.copy()
    group_col_for_plot = time_agg_col # Por defecto, agrupar por la columna de tiempo original

    if time_agg_col == 'NumSemana':
        try:
            df_agg_evol.dropna(subset=['Año', 'NumSemana'], inplace=True)
            df_agg_evol['Año'] = df_agg_evol['Año'].astype(int)
            df_agg_evol['NumSemana'] = df_agg_evol['NumSemana'].astype(int)
            # display_label_col_name es el nombre de la nueva columna, ej: 'Año-Semana'
            df_agg_evol[display_label_col_name] = df_agg_evol['Año'].astype(str) + '-S' + df_agg_evol['NumSemana'].astype(str).str.zfill(2)
            group_col_for_plot = display_label_col_name # Usar la nueva columna para agrupar y para el eje X
        except (ValueError, TypeError) as e: st.warning(f"Problema con 'Año'/'NumSemana': {e}"); return
    elif time_agg_col == 'AñoMes':
        df_agg_evol[display_label_col_name] = df_agg_evol[time_agg_col] # Usar AñoMes como está
        group_col_for_plot = display_label_col_name

    df_agg_evol.dropna(subset=[group_col_for_plot, 'SQL_Estandarizado'], inplace=True)
    if df_agg_evol.empty: st.info(f"No hay datos válidos para '{group_col_for_plot}' y 'SQL_Estandarizado'."); return

    summary_time_sql_evol = df_agg_evol.groupby([group_col_for_plot, 'SQL_Estandarizado'], observed=False).size().reset_index(name='Número de Sesiones')
    if summary_time_sql_evol.empty: st.info(f"No hay datos agregados por {x_axis_label.lower()} y SQL."); return
    
    # Ordenar por la columna de agrupación (que ahora es el display_label_col_name)
    summary_time_sql_evol = summary_time_sql_evol.sort_values(by=[group_col_for_plot])
    sql_category_order_evol = get_sql_category_order(summary_time_sql_evol['SQL_Estandarizado'])
    summary_time_sql_evol['SQL_Estandarizado'] = pd.Categorical(summary_time_sql_evol['SQL_Estandarizado'], categories=sql_category_order_evol, ordered=True)
    summary_time_sql_evol = summary_time_sql_evol.sort_values(by=[group_col_for_plot, 'SQL_Estandarizado'])
    try:
        fig_evol_sql = px.line(summary_time_sql_evol, x=group_col_for_plot, y='Número de Sesiones', color='SQL_Estandarizado', title=f"Evolución por SQL ({x_axis_label})", markers=True)
        fig_evol_sql.update_xaxes(type='category', title_text=x_axis_label)
        fig_evol_sql.update_layout(yaxis_title="Número de Sesiones", legend_title_text='Calificación SQL')
        st.plotly_chart(fig_evol_sql, use_container_width=True)
    except Exception as e_evol_sql: st.warning(f"No se pudo generar gráfico de evolución para {x_axis_label}: {e_evol_sql}")

def display_tabla_sesiones_detalle(df_filtered):
    st.markdown("### 📝 Tabla Detallada de Sesiones")
    if df_filtered.empty: st.info("No hay sesiones detalladas para mostrar con los filtros aplicados."); return
    cols_deseadas_detalle_ses = ["Fecha", "LG", "AE", "País", "SQL", "SQL_Estandarizado", "Empresa", "Puesto", "Nombre", "Apellido", "Siguientes Pasos", "RPA", "Fuente_Hoja", "LinkedIn", "Email"]
    cols_present_detalle_ses = [col for col in cols_deseadas_detalle_ses if col in df_filtered.columns]
    df_view_detalle_ses = df_filtered[cols_present_detalle_ses].copy()
    if "Fecha" in df_view_detalle_ses.columns and pd.api.types.is_datetime64_any_dtype(df_view_detalle_ses["Fecha"]):
         try:
            df_view_detalle_ses["Fecha"] = pd.to_datetime(df_view_detalle_ses["Fecha"], errors='coerce').dt.strftime('%d/%m/%Y')
            df_view_detalle_ses["Fecha"] = df_view_detalle_ses["Fecha"].fillna("Fecha Inválida")
         except AttributeError: pass
    st.dataframe(df_view_detalle_ses, height=400, use_container_width=True, hide_index=True)
    if not df_view_detalle_ses.empty:
        output = io.BytesIO()
        try:
            df_excel = df_view_detalle_ses.copy()
            if "Fecha" in df_excel.columns and df_excel["Fecha"].dtype == 'object': # Revertir a datetime para Excel
                df_excel["Fecha_Original"] = pd.to_datetime(df_excel["Fecha"], format='%d/%m/%Y', errors='coerce') # Guardar como nueva columna para no perder la formateada
                # Opcionalmente, reemplazar la columna 'Fecha' si se prefiere el tipo datetime en Excel
                # df_excel["Fecha"] = pd.to_datetime(df_excel["Fecha"], format='%d/%m/%Y', errors='coerce')
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_excel.to_excel(writer, index=False, sheet_name='Detalle_Sesiones')
            st.download_button(label="⬇️ Descargar Detalle (Excel)", data=output.getvalue(), file_name="detalle_sesiones_sql.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{FILTER_KEYS_PREFIX}btn_download_detalle")
        except Exception as e_excel: st.error(f"Error al generar archivo Excel: {e_excel}")

# --- Flujo Principal de la Página ---
try:
    df_sesiones_base = load_sesiones_data()
except Exception as e: # Captura más genérica si load_sesiones_data falla catastróficamente
    st.error(f"Error crítico al cargar datos iniciales: {e}")
    st.stop()

if df_sesiones_base is None or df_sesiones_base.empty:
    st.error("Fallo Crítico: No se pudieron cargar o procesar datos de Sesiones. La página no puede continuar.")
    st.stop()

start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, sql_f_val = sidebar_filters_sesiones(df_sesiones_base)
df_sesiones_filtered = apply_sesiones_filters(df_sesiones_base, start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, sql_f_val)

# --- Presentación del Dashboard ---
display_sesiones_summary_sql(df_sesiones_filtered)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="LG", dimension_label="Analista LG", top_n=15)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="AE", dimension_label="Account Executive", top_n=15)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="País", dimension_label="País", top_n=10)
st.markdown("---")
# display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="Puesto", dimension_label="Cargo (Puesto)", top_n=10) # Comentado en tu original
# st.markdown("---")
# display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="Empresa", dimension_label="Empresa", top_n=10) # Comentado en tu original
# st.markdown("---")

display_evolucion_sql(df_sesiones_filtered, 'NumSemana', 'Año-Semana', "Evolución Semanal por Calificación SQL", "Semana del Año")
st.markdown("---")
display_evolucion_sql(df_sesiones_filtered, 'AñoMes', 'Año-Mes', "Evolución Mensual por Calificación SQL", "Mes del Año")
st.markdown("---")
display_tabla_sesiones_detalle(df_sesiones_filtered)

st.markdown("---")
st.info("Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊")
