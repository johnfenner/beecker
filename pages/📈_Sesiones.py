# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import os
import sys
import io
import re
from collections import OrderedDict  # Para eliminar duplicados manteniendo orden

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
    "Métricas basadas en columnas principales: LG, AE, País, Proceso, Calificación SQL, Puesto, Empresa."
)

# --- Constantes ---
SHEET_URL_SESIONES_PRINCIPAL_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902"
SHEET_NAME_SESIONES_PRINCIPAL = "Sesiones 2024-2025"

SHEET_URL_SESIONES_SURAMERICA_DEFAULT = "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854"
SHEET_NAME_SESIONES_SURAMERICA = "SesionesSA 2024-2025"

# Incluir 'Proceso' en la estructura final
COLUMNAS_CENTRALES = [
    "Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL", "SQL_Estandarizado",
    "AE", "LG", "Proceso", "Siguientes Pasos", "Email", "RPA", "LinkedIn",
    "Fuente_Hoja", "Año", "NumSemana", "MesNombre", "AñoMes",
]
SQL_ORDER_OF_IMPORTANCE = ['SQL1', 'SQL2', 'MQL', 'NA', 'SIN CALIFICACIÓN SQL']
DF_FINAL_STRUCTURE_EMPTY = pd.DataFrame(columns=COLUMNAS_CENTRALES)

# --- Gestión de Estado de Sesión para Filtros ---
FILTER_KEYS_PREFIX = "sesiones_sql_lg_pais_proceso_page_v1_"
SES_START_DATE_KEY = f"{FILTER_KEYS_PREFIX}start_date"
SES_END_DATE_KEY = f"{FILTER_KEYS_PREFIX}end_date"
SES_AE_FILTER_KEY = f"{FILTER_KEYS_PREFIX}ae"
SES_LG_FILTER_KEY = f"{FILTER_KEYS_PREFIX}lg"
SES_PAIS_FILTER_KEY = f"{FILTER_KEYS_PREFIX}pais"
SES_PROCESO_FILTER_KEY = f"{FILTER_KEYS_PREFIX}proceso"
SES_YEAR_FILTER_KEY = f"{FILTER_KEYS_PREFIX}year"
SES_WEEK_FILTER_KEY = f"{FILTER_KEYS_PREFIX}week"
SES_SQL_FILTER_KEY = f"{FILTER_KEYS_PREFIX}sql_val"

default_filters_config = {
    SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
    SES_AE_FILTER_KEY: ["– Todos –"], SES_LG_FILTER_KEY: ["– Todos –"],
    SES_PAIS_FILTER_KEY: ["– Todos –"], SES_PROCESO_FILTER_KEY: ["– Todos –"],
    SES_YEAR_FILTER_KEY: "– Todos –",
    SES_WEEK_FILTER_KEY: ["– Todas –"], SES_SQL_FILTER_KEY: ["– Todos –"]
}
# Inicializar el estado de sesión
for key, value in default_filters_config.items():
    if key not in st.session_state:
        st.session_state[key] = value

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

    try:  # Hoja Principal
        workbook_principal = client.open_by_url(SHEET_URL_SESIONES_PRINCIPAL_DEFAULT)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES_PRINCIPAL)
        raw_data_principal_list = sheet_principal.get_all_values()
        if raw_data_principal_list and len(raw_data_principal_list) > 1:
            headers_p = make_unique_headers(raw_data_principal_list[0])
            df_principal_raw = pd.DataFrame(raw_data_principal_list[1:], columns=headers_p)
            df_proc_p = pd.DataFrame()
            for col in ["Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL",
                        "AE", "LG", "Proceso", "Siguientes Pasos", "Email", "RPA", "LinkedIn"]:
                df_proc_p[col] = df_principal_raw.get(col)
            df_proc_p["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_proc_p)
        else:
            processing_warnings.append(f"Hoja Principal ('{SHEET_NAME_SESIONES_PRINCIPAL}') vacía o sin encabezados.")
    except Exception as e:
        processing_warnings.append(f"ADVERTENCIA al cargar Hoja Principal. Error: {e}")

    try:  # Hoja Suramérica
        workbook_suramerica = client.open_by_url(SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        raw_data_suramerica_list = sheet_suramerica.get_all_values()
        if raw_data_suramerica_list and len(raw_data_suramerica_list) > 1:
            headers_sa = make_unique_headers(raw_data_suramerica_list[0])
            df_suramerica_raw = pd.DataFrame(raw_data_suramerica_list[1:], columns=headers_sa)
            if not df_suramerica_raw.empty:
                df_proc_sa = pd.DataFrame()
                map_cols_sa = {"Fecha": "Fecha", "Empresa": "Empresa", "País": "País",
                               "Siguientes Pasos": "Siguientes Pasos",
                               "SQL": "SQL", "Correo": "Email", "LinkedIn": "LinkedIn",
                               "LG": "LG", "AE": "AE"}
                for orig_col, new_col in map_cols_sa.items():
                    df_proc_sa[new_col] = df_suramerica_raw.get(orig_col)
                if "Nombre y Cargo" in df_suramerica_raw.columns:
                    n_c_split = df_suramerica_raw["Nombre y Cargo"].apply(separar_nombre_cargo_suramerica)
                    df_proc_sa["Nombre"] = n_c_split.apply(lambda x: x[0])
                    df_proc_sa["Apellido"] = n_c_split.apply(lambda x: x[1])
                    df_proc_sa["Puesto"] = n_c_split.apply(lambda x: x[2])
                else:
                    df_proc_sa["Nombre"], df_proc_sa["Apellido"], df_proc_sa["Puesto"] = pd.NA, pd.NA, "No Especificado"
                # Mapear Proceso si existe
                if "Proceso" in df_suramerica_raw.columns:
                    df_proc_sa["Proceso"] = df_suramerica_raw.get("Proceso")
                all_dataframes.append(df_proc_sa)
        else:
            processing_warnings.append(f"Hoja Suramérica ('{SHEET_NAME_SESIONES_SURAMERICA}') vacía o sin encabezados.")
    except Exception as e:
        processing_warnings.append(f"ADVERTENCIA al cargar Hoja Suramérica. Error: {e}")

    if processing_warnings:
        for warning_msg in processing_warnings:
            st.warning(warning_msg)
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
        for col_t in ['Año', 'NumSemana', 'MesNombre', 'AñoMes']:
            df_procesado[col_t] = pd.NA

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
        if col_name in ['Fecha', 'Año', 'NumSemana', 'MesNombre', 'AñoMes']:
            continue
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
                if col_name == "AE":
                    df_procesado[col_name] = df_procesado[col_name].replace("No Asignado Ae", "No Asignado AE", regex=False)
                if col_name == "LG":
                    df_procesado[col_name] = df_procesado[col_name].replace("No Asignado Lg", "No Asignado LG", regex=False)

    # Asegurar al menos columna SQL
    if "SQL" not in df_procesado.columns:
        df_procesado["SQL"] = default_values_fill["SQL"]
    df_procesado["SQL"] = df_procesado["SQL"].fillna(default_values_fill["SQL"])\n    df_procesado["SQL"] = df_procesado["SQL"].astype(str).str.strip().str.upper()

    empty_patterns_for_sql = ["", "NAN", "NONE", "<NA>", "N/A", "ND", "N.D", "S/D", "S.D.", "TEMP_EMPTY_SQL", "NO ESPECIFICADO", "NO ASIGNADO SQL"]
    df_procesado["SQL_Estandarizado"] = df_procesado["SQL"].copy()
    for pattern in empty_patterns_for_sql:
        df_procesado.loc[df_procesado["SQL_Estandarizado"] == pattern.upper(), "SQL_Estandarizado"] = "PLACEHOLDER_FOR_SIN_CALIFICACION"
    df_procesado.loc[df_procesado["SQL_Estandarizado"] == "PLACEHOLDER_FOR_SIN_CALIFICACION", "SQL_Estandarizado"] = "SIN CALIFICACIÓN SQL"
    valid_explicit_sql_values = ['SQL1', 'SQL2', 'MQL', 'NA']
    mask_others_to_standardize = ~df_procesado["SQL_Estandarizado"].isin(valid_explicit_sql_values + ["SIN CALIFICACIÓN SQL"])
    df_procesado.loc[mask_others_to_standardize, "SQL_Estandarizado"] = "SIN CALIFICACIÓN SQL"

    # Reconstruir estructura final
    df_final_structure = pd.DataFrame()
    for col in COLUMNAS_CENTRALES:
        if col in df_procesado.columns:
            df_final_structure[col] = df_procesado[col]
        else:
            dtype_map = {'Año': 'Int64', 'NumSemana': 'Int64', 'Fecha': 'datetime64[ns]'}
            df_final_structure[col] = pd.Series(dtype=dtype_map.get(col, 'object'))
    # Ajustar tipos finales
    try:
        if 'Fecha' in df_final_structure.columns:
            df_final_structure['Fecha'] = pd.to_datetime(df_final_structure['Fecha'], errors='coerce')
        if 'Año' in df_final_structure.columns:
            df_final_structure['Año'] = pd.to_numeric(df_final_structure['Año'], errors='coerce').astype('Int64')
        if 'NumSemana' in df_final_structure.columns:
            df_final_structure['NumSemana'] = pd.to_numeric(df_final_structure['NumSemana'], errors='coerce').astype('Int64')
    except Exception as e_type_final:
        st.warning(f"ADVERTENCIA al ajustar tipos finales: {e_type_final}")
    return df_final_structure.reset_index(drop=True)


def clear_ses_filters_callback():
    for key, value in default_filters_config.items():
        st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")


def sidebar_filters_sesiones(df_options):
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")
    # Fechas
    min_d, max_d = (None, None)
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) and not df_options["Fecha"].dropna().empty:
        min_d_series, max_d_series = df_options["Fecha"].dropna().min(), df_options["Fecha"].dropna().max()
        if pd.notna(min_d_series) and pd.notna(max_d_series):
            min_d, max_d = min_d_series.date(), max_d_series.date()
    c1, c2 = st.sidebar.columns(2)
    start_date_val_state = st.session_state.get(SES_START_DATE_KEY)
    end_date_val_state = st.session_state.get(SES_END_DATE_KEY)
    start_date_for_input = start_date_val_state.date() if isinstance(start_date_val_state, datetime.datetime) else (start_date_val_state if isinstance(start_date_val_state, datetime.date) else None)
    end_date_for_input = end_date_val_state.date() if isinstance(end_date_val_state, datetime.datetime) else (end_date_val_state if isinstance(end_date_val_state, datetime.date) else None)
    c1.date_input("Desde", value=start_date_for_input, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    c2.date_input("Hasta", value=end_date_for_input, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_END_DATE_KEY)

    # Año y Semana
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
        current_year_selection_ses = "– Todos –"
        st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses
    selected_year_index_ses = year_options_ses.index(current_year_selection_ses)
    selected_year_str_ses = st.sidebar.selectbox("Año", options=year_options_ses, index=selected_year_index_ses, key=SES_YEAR_FILTER_KEY)
    sel_y = None
    if selected_year_str_ses != "– Todos –":
        try:
            sel_y = int(selected_year_str_ses)
        except ValueError:
            sel_y = None
    week_options_ses = ["– Todas –"]
    df_for_week_ses = df_options[df_options["Año"] == sel_y] if sel_y is not None and "Año" in df_options.columns else df_options
    if df_for_week_ses.get("NumSemana") is not None and not df_for_week_ses["NumSemana"].dropna().empty:
        try:
            unique_weeks_for_year = sorted(df_for_week_ses["NumSemana"].dropna().astype(int).unique())
            week_options_ses.extend([str(w) for w in unique_weeks_for_year])
        except ValueError:
            unique_weeks_str = sorted(df_for_week_ses["NumSemana"].dropna().astype(str).unique())
            week_options_ses.extend(unique_weeks_str)
    current_week_selection = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    st.sidebar.multiselect("Semanas", options=week_options_ses, default=current_week_selection, key=SES_WEEK_FILTER_KEY)

    # Filtros de dimensiones
    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País, Proceso y Calificación")

    def create_multiselect_options_and_set_state(df_col_series, session_key):
        options_list = ["– Todos –"]
        if df_col_series is not None and not df_col_series.dropna().empty:
            unique_vals = df_col_series.astype(str).str.strip().replace('', 'N/D', regex=False).unique()
            cleaned = [val for val in unique_vals if val and val != 'N/D']
            options_list.extend(sorted(list(set(cleaned))))
        current_sel = st.session_state.get(session_key, ["– Todos –"])
        return options_list

    lgs_opts = create_multiselect_options_and_set_state(df_options.get("LG"), SES_LG_FILTER_KEY)
    st.sidebar.multiselect("Analista LG", options=lgs_opts, default=st.session_state[SES_LG_FILTER_KEY], key=SES_LG_FILTER_KEY)

    ae_opts = create_multiselect_options_and_set_state(df_options.get("AE"), SES_AE_FILTER_KEY)
    st.sidebar.multiselect("Account Executive (AE)", options=ae_opts, default=st.session_state[SES_AE_FILTER_KEY], key=SES_AE_FILTER_KEY)

    pais_opts = create_multiselect_options_and_set_state(df_options.get("País"), SES_PAIS_FILTER_KEY)
    st.sidebar.multiselect("País", options=pais_opts, default=st.session_state[SES_PAIS_FILTER_KEY], key=SES_PAIS_FILTER_KEY)

    proceso_opts = create_multiselect_options_and_set_state(df_options.get("Proceso"), SES_PROCESO_FILTER_KEY)
    st.sidebar.multiselect("Proceso", options=proceso_opts, default=st.session_state[SES_PROCESO_FILTER_KEY], key=SES_PROCESO_FILTER_KEY)

    sql_series = df_options.get("SQL_Estandarizado")
    sql_opts = ["– Todos –"] + [s for s in SQL_ORDER_OF_IMPORTANCE if s in sql_series.unique()] + sorted([s for s in sql_series.unique() if s not in SQL_ORDER_OF_IMPORTANCE])
    st.sidebar.multiselect("Calificación SQL", options=sql_opts, default=st.session_state[SES_SQL_FILTER_KEY], key=SES_SQL_FILTER_KEY)

    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback)

    return (
        st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], sel_y,
        st.session_state[SES_WEEK_FILTER_KEY], st.session_state[SES_AE_FILTER_KEY],
        st.session_state[SES_LG_FILTER_KEY], st.session_state[SES_PAIS_FILTER_KEY],
        st.session_state[SES_PROCESO_FILTER_KEY], st.session_state[SES_SQL_FILTER_KEY]
    )


def apply_sesiones_filters(df, start_date, end_date, year_f, week_f_list,
                           ae_f_list, lg_f_list, pais_f_list, proceso_f_list, sql_f_list):
    if df is None or df.empty: return DF_FINAL_STRUCTURE_EMPTY.copy()
    df_f = df.copy()
    # Filtro de fechas
    if "Fecha" in df_f.columns:
        if start_date: df_f = df_f[df_f["Fecha"] >= pd.to_datetime(start_date)]
        if end_date: df_f = df_f[df_f["Fecha"] <= pd.to_datetime(end_date)]
    # Año
    if year_f is not None and "Año" in df_f.columns:
        df_f = df_f[df_f["Año"] == year_f]
    # Semanas
    if week_f_list and "– Todas –" not in week_f_list and "NumSemana" in df_f.columns:
        selected_weeks = [int(w) for w in week_f_list if w.isdigit()]
        df_f = df_f[df_f["NumSemana"].isin(selected_weeks)]
    # Filtros de dimensión
    filter_map = {
        "AE": ae_f_list,
        "LG": lg_f_list,
        "País": pais_f_list,
        "Proceso": proceso_f_list,
        "SQL_Estandarizado": sql_f_list
    }
    for col, vals in filter_map.items():
        if vals and "– Todos –" not in vals:
            df_f = df_f[df_f[col].isin(vals)]
    return df_f


def get_sql_category_order(vals):
    present = list(vals.astype(str).unique())
    return [s for s in SQL_ORDER_OF_IMPORTANCE if s in present] + sorted([s for s in present if s not in SQL_ORDER_OF_IMPORTANCE])


def display_sesiones_summary_sql(df_filtered):
    st.markdown("### 📌 Resumen Principal de Sesiones")
    total = len(df_filtered)
    st.metric("Total Sesiones (filtradas)", f"{total:,}")
    if 'SQL_Estandarizado' in df_filtered.columns:
        st.markdown("#### Distribución por Calificación SQL")
        counts = df_filtered['SQL_Estandarizado'].value_counts().reset_index()
        counts.columns = ['Calificación SQL', 'Número de Sesiones']
        order = get_sql_category_order(counts['Calificación SQL'])
        counts['Calificación SQL'] = pd.Categorical(counts['Calificación SQL'], categories=order, ordered=True)
        counts = counts.sort_values('Calificación SQL')
        fig = px.bar(counts, x='Calificación SQL', y='Número de Sesiones', text_auto=True, color='Calificación SQL')
        fig.update_xaxes(categoryorder='array', categoryarray=order)
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(counts.set_index('Calificación SQL'), use_container_width=True)


def display_analisis_por_dimension(df_filtered, dimension_col, dimension_label, top_n=10):
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns:
        st.info(f"No hay datos para {dimension_label}"); return
    series = df_filtered[dimension_col].astype(str)
    top_vals = series.value_counts().nlargest(top_n).index.tolist()
    df_top = df_filtered[df_filtered[dimension_col].isin(top_vals)]
    summary = df_top.groupby([dimension_col, 'SQL_Estandarizado']).size().reset_index(name='Cantidad')
    order = get_sql_category_order(summary['SQL_Estandarizado'])
    summary['SQL_Estandarizado'] = pd.Categorical(summary['SQL_Estandarizado'], categories=order, ordered=True)
    summary = summary.sort_values([dimension_col, 'SQL_Estandarizado'])
    fig = px.bar(summary, x=dimension_col, y='Cantidad', color='SQL_Estandarizado', barmode='stack', title=f'Distribución de SQL por {dimension_label}')
    fig.update_layout(xaxis={'categoryorder':'array','categoryarray':top_vals}, xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    pivot = summary.pivot_table(index=dimension_col, columns='SQL_Estandarizado', values='Cantidad', fill_value=0)
    pivot['Total'] = pivot.sum(axis=1)
    st.dataframe(pivot, use_container_width=True)


def display_evolucion_sql(df_filtered, time_col, label_col,
                          chart_title, xaxis_label):
    st.markdown(f"### 📈 {chart_title}")
    if df_filtered.empty or time_col not in df_filtered.columns:
        st.info("Datos insuficientes para evolución"); return
    df = df_filtered.copy()
    if time_col == 'NumSemana':
        df[label_col] = df['Año'].astype(str) + '-S' + df['NumSemana'].astype(str).str.zfill(2)
    else:
        df[label_col] = df[time_col]
    summary = df.groupby([label_col,'SQL_Estandarizado']).size().reset_index(name='Sesiones')
    order = get_sql_category_order(summary['SQL_Estandarizado'])
    summary['SQL_Estandarizado'] = pd.Categorical(summary['SQL_Estandarizado'], categories=order, ordered=True)
    fig = px.line(summary, x=label_col, y='Sesiones', color='SQL_Estandarizado', markers=True, title=chart_title)
    fig.update_xaxes(type='category', title=xaxis_label)
    st.plotly_chart(fig, use_container_width=True)


def display_tabla_sesiones_detalle(df_filtered):
    st.markdown("### 📝 Tabla Detallada de Sesiones")
    if df_filtered.empty:
        st.info("No hay sesiones detalladas"); return
    cols = [col for col in ["Fecha","LG","AE","País","Proceso","SQL","SQL_Estandarizado","Empresa","Puesto","Nombre","Apellido","Siguientes Pasos","RPA","Fuente_Hoja","LinkedIn","Email"] if col in df_filtered.columns]
    df_view = df_filtered[cols].copy()
    df_view['Fecha'] = pd.to_datetime(df_view['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y')
    st.dataframe(df_view, height=400, use_container_width=True, hide_index=True)
    buffer = io.BytesIO()
    df_export = df_view.copy()
    df_export.to_excel(buffer, index=False)
    st.download_button("⬇️ Descargar Detalle (Excel)", data=buffer.getvalue(), file_name="detalle_sesiones_sql.xlsx")

# --- Flujo Principal ---
df_base = load_sesiones_data()
start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, proceso_f, sql_f = sidebar_filters_sesiones(df_base)
df_filtrado = apply_sesiones_filters(df_base, start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, proceso_f, sql_f)

# Presentar dashboard existente
display_sesiones_summary_sql(df_filtrado)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_filtrado, dimension_col="LG", dimension_label="Analista LG", top_n=15)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_filtrado, dimension_col="AE", dimension_label="Account Executive", top_n=15)
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_filtrado, dimension_col="País", dimension_label="País", top_n=10)
# Nuevo análisis por Proceso
st.markdown("---")
display_analisis_por_dimension(df_filtered=df_filtrado, dimension_col="Proceso", dimension_label="Proceso", top_n=10)
st.markdown("---")
# Continuar con evolución y detalle
st.markdown("---")
# Evolución semanal de sesiones por calificación SQL
display_evolucion_sql(df_filtrado, 'NumSemana', 'Periodo', 'Evolución Semanal de Sesiones', 'Semana')
st.markdown("---")
# Evolución mensual de sesiones por calificación SQL
display_evolucion_sql(df_filtrado, 'AñoMes', 'Periodo', 'Evolución Mensual de Sesiones', 'Mes')
st.markdown("---")
# Tabla detallada de sesiones
display_tabla_sesiones_detalle(df_filtrado)

# --- FIN DEL SCRIPT ---
