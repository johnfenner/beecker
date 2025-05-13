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
SHEET_NAME_SESIONES_SURAMERICA = "SesionesSA 2024-2025"

COLUMNAS_CENTRALES = [
    "Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL", "SQL_Estandarizado",
    "AE", "LG", "Siguientes Pasos", "Email", "RPA", "LinkedIn",
    "Fuente_Hoja", "Año", "NumSemana", "MesNombre", "AñoMes", # MesNombre no estaba, añadido para consistencia
]
SQL_ORDER_OF_IMPORTANCE = ['SQL1', 'SQL2', 'MQL', 'NA', 'SIN CALIFICACIÓN SQL']
DF_FINAL_STRUCTURE_EMPTY = pd.DataFrame(columns=COLUMNAS_CENTRALES) # Estructura para retornar si falla la carga

# --- Gestión de Estado de Sesión para Filtros ---
FILTER_KEYS_PREFIX = "sesiones_sql_lg_pais_page_v3_" # Incrementado v2 a v3 por cambios
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
    SES_PAIS_FILTER_KEY: ["– Todos –"], SES_YEAR_FILTER_KEY: "– Todos –", # String para año
    SES_WEEK_FILTER_KEY: ["– Todas –"], # Lista de strings para semana
    SES_SQL_FILTER_KEY: ["– Todos –"] # Lista de strings para SQL
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
    try: # Intento genérico final
        return pd.to_datetime(date_str, errors='coerce')
    except (ValueError, TypeError): return pd.NaT

def separar_nombre_cargo_suramerica(nombre_cargo_str):
    nombre, apellido, puesto = pd.NA, pd.NA, "No Especificado"
    if pd.isna(nombre_cargo_str) or not isinstance(nombre_cargo_str, str) or not nombre_cargo_str.strip():
        return nombre, apellido, puesto
    nombre_cargo_str = nombre_cargo_str.strip()
    delimiters_cargo = [' - ', ' / ', ', ', ' – '] # Lista de delimitadores
    nombre_completo_str = nombre_cargo_str
    cargo_encontrado_explicitamente = False

    for delim in delimiters_cargo:
        if delim in nombre_cargo_str:
            parts = nombre_cargo_str.split(delim, 1)
            nombre_completo_str = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                puesto = parts[1].strip()
                cargo_encontrado_explicitamente = True
            break # Tomar el primer delimitador encontrado

    name_parts = [part.strip() for part in nombre_completo_str.split() if part.strip()]
    if not name_parts: return pd.NA, pd.NA, puesto

    if len(name_parts) == 1: nombre = name_parts[0]
    elif len(name_parts) == 2: nombre, apellido = name_parts[0], name_parts[1]
    elif len(name_parts) == 3: # Asumir Nombre ApellidoPaterno ApellidoMaterno o Nombre Compuesto Apellido
        nombre, apellido = name_parts[0], f"{name_parts[1]} {name_parts[2]}"
    elif len(name_parts) >= 4:
        # Intentar una heurística: Nombre Apellido1 Apellido2 CargoImplícito...
        # o NombreCompuesto Apellido1 Apellido2 ...
        nombre = f"{name_parts[0]} {name_parts[1]}" # Primeros dos como nombre
        apellido = " ".join(name_parts[2:]) # El resto como apellido
        # Si no se encontró cargo explícito, ver si los últimos componentes parecen un cargo
        if not cargo_encontrado_explicitamente:
            # Heurística simple: si las últimas 2+ palabras no son parte del apellido común
            temp_nombre_simple, temp_apellido_simple = name_parts[0], name_parts[1]
            temp_cargo_implicito_parts = name_parts[2:]
            # Considerar cargo implícito si tiene más de una palabra y no es demasiado corto
            if len(temp_cargo_implicito_parts) >= 1: # Ajustado a >=1 para capturar más
                 temp_cargo_str = " ".join(temp_cargo_implicito_parts)
                 # Podrías tener una lista de palabras comunes en cargos aquí para mejorar
                 if len(temp_cargo_str) > 3 : # Evitar cargos muy cortos como "de"
                    nombre, apellido, puesto = temp_nombre_simple, temp_apellido_simple, temp_cargo_str

    # Fallback si el nombre aún es NA pero tenemos nombre_completo_str
    if pd.isna(nombre) and pd.notna(nombre_completo_str) and nombre_completo_str:
        nombre = nombre_completo_str

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
    processing_warnings = [] # Para recolectar advertencias no críticas

    # --- Cargar Hoja Principal ---
    try:
        workbook_principal = client.open_by_url(SHEET_URL_SESIONES_PRINCIPAL_DEFAULT)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES_PRINCIPAL)
        raw_data_principal_list = sheet_principal.get_all_values()
        if raw_data_principal_list and len(raw_data_principal_list) > 1:
            headers_p = make_unique_headers(raw_data_principal_list[0])
            df_principal_raw = pd.DataFrame(raw_data_principal_list[1:], columns=headers_p)

            df_proc_principal = pd.DataFrame() # Crear con columnas esperadas directamente
            df_proc_principal["Fecha"] = df_principal_raw.get("Fecha")
            df_proc_principal["Empresa"] = df_principal_raw.get("Empresa")
            df_proc_principal["País"] = df_principal_raw.get("País")
            df_proc_principal["Nombre"] = df_principal_raw.get("Nombre")
            df_proc_principal["Apellido"] = df_principal_raw.get("Apellido")
            df_proc_principal["Puesto"] = df_principal_raw.get("Puesto")
            df_proc_principal["SQL"] = df_principal_raw.get("SQL") # Calificación SQL original
            df_proc_principal["AE"] = df_principal_raw.get("AE")
            df_proc_principal["LG"] = df_principal_raw.get("LG")
            df_proc_principal["Siguientes Pasos"] = df_principal_raw.get("Siguientes Pasos")
            df_proc_principal["Email"] = df_principal_raw.get("Email")
            df_proc_principal["RPA"] = df_principal_raw.get("RPA") # Asumo que es una columna
            df_proc_principal["LinkedIn"] = df_principal_raw.get("LinkedIn")
            df_proc_principal["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_proc_principal)
        else:
            processing_warnings.append(f"Hoja Principal ('{SHEET_NAME_SESIONES_PRINCIPAL}') vacía o sin encabezados.")
    except Exception as e:
        processing_warnings.append(f"ADVERTENCIA al cargar Hoja Principal: {e}")

    # --- Cargar Hoja Suramérica ---
    try:
        workbook_suramerica = client.open_by_url(SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        raw_data_suramerica_list = sheet_suramerica.get_all_values()
        if raw_data_suramerica_list and len(raw_data_suramerica_list) > 1:
            headers_sa = make_unique_headers(raw_data_suramerica_list[0])
            df_suramerica_raw = pd.DataFrame(raw_data_suramerica_list[1:], columns=headers_sa)

            if not df_suramerica_raw.empty:
                df_suramerica_processed = pd.DataFrame()
                df_suramerica_processed["Fecha"] = df_suramerica_raw.get("Fecha")
                df_suramerica_processed["Empresa"] = df_suramerica_raw.get("Empresa")
                df_suramerica_processed["País"] = df_suramerica_raw.get("País")
                df_suramerica_processed["Siguientes Pasos"] = df_suramerica_raw.get("Siguientes Pasos")
                df_suramerica_processed["SQL"] = df_suramerica_raw.get("SQL")
                df_suramerica_processed["Email"] = df_suramerica_raw.get("Correo") # Mapeo de columna
                df_suramerica_processed["LinkedIn"] = df_suramerica_raw.get("LinkedIn")
                df_suramerica_processed["LG"] = df_suramerica_raw.get("LG")
                df_suramerica_processed["AE"] = df_suramerica_raw.get("AE")
                # RPA no parece estar en esta hoja, se llenará con default
                if "Nombre y Cargo" in df_suramerica_raw.columns:
                    n_c_split = df_suramerica_raw["Nombre y Cargo"].apply(separar_nombre_cargo_suramerica)
                    df_suramerica_processed["Nombre"] = n_c_split.apply(lambda x: x[0])
                    df_suramerica_processed["Apellido"] = n_c_split.apply(lambda x: x[1])
                    df_suramerica_processed["Puesto"] = n_c_split.apply(lambda x: x[2])
                else:
                    df_suramerica_processed["Nombre"], df_suramerica_processed["Apellido"], df_suramerica_processed["Puesto"] = pd.NA, pd.NA, "No Especificado"
                df_suramerica_processed["Fuente_Hoja"] = "Suramérica"
                all_dataframes.append(df_suramerica_processed)
        else:
            processing_warnings.append(f"Hoja Suramérica ('{SHEET_NAME_SESIONES_SURAMERICA}') vacía o sin encabezados.")
    except Exception as e:
        processing_warnings.append(f"ADVERTENCIA al cargar Hoja Suramérica: {e}")

    if processing_warnings: # Mostrar advertencias no críticas
        for warning_msg in processing_warnings:
            st.warning(warning_msg)

    if not all_dataframes:
        st.error("No se pudieron cargar datos de ninguna fuente. Verifique las URLs y nombres de las hojas.")
        return DF_FINAL_STRUCTURE_EMPTY.copy() # Retornar estructura vacía

    df_consolidado = pd.concat(all_dataframes, ignore_index=True, sort=False)

    # Limpieza de Fechas y eliminación de filas sin fecha válida
    if "Fecha" not in df_consolidado.columns or df_consolidado["Fecha"].isnull().all():
        st.error("Columna 'Fecha' no encontrada o completamente vacía en los datos consolidados.")
        return DF_FINAL_STRUCTURE_EMPTY.copy()
    df_consolidado["Fecha"] = df_consolidado["Fecha"].apply(parse_date_robust)
    df_consolidado.dropna(subset=["Fecha"], inplace=True)
    if df_consolidado.empty:
        st.info("No hay datos con fechas válidas después de la limpieza inicial.")
        return DF_FINAL_STRUCTURE_EMPTY.copy()

    # Creación de columnas de tiempo
    df_procesado = df_consolidado.copy()
    try:
        df_procesado['Año'] = df_procesado['Fecha'].dt.year.astype('Int64')
        df_procesado['NumSemana'] = df_procesado['Fecha'].dt.isocalendar().week.astype('Int64')
        df_procesado['MesNombre'] = df_procesado['Fecha'].dt.strftime('%B') # Nombre del mes completo
        df_procesado['AñoMes'] = df_procesado['Fecha'].dt.strftime('%Y-%m')
    except Exception as e_time:
        st.error(f"Error creando columnas de tiempo: {e_time}")
        # Continuar sin estas columnas si fallan, o retornar estructura vacía
        for col_time in ['Año', 'NumSemana', 'MesNombre', 'AñoMes']:
            if col_time not in df_procesado: df_procesado[col_time] = pd.NA
        # return DF_FINAL_STRUCTURE_EMPTY.copy() # Descomentar si es crítico

    # Llenado de valores por defecto y limpieza de strings
    default_values_fill = {
        "AE": "No Asignado AE", "LG": "No Asignado LG", "Puesto": "No Especificado",
        "Empresa": "No Especificado", "País": "No Especificado", "Nombre": "No Especificado",
        "Apellido": "No Especificado", "Siguientes Pasos": "No Especificado",
        "Email": "No Especificado", "RPA": "No Aplicable", "LinkedIn": "No Especificado",
        "Fuente_Hoja": "Desconocida", "SQL": "SIN CALIFICACIÓN SQL",
        "SQL_Estandarizado": "SIN CALIFICACIÓN SQL"
    }
    generic_empty_na_values = ['', 'nan', 'none', 'NaN', 'None', '<NA>', '#N/A', 'N/A', 'na', 'nd', 'n/d', 's/d', 's.d.']

    for col_name in COLUMNAS_CENTRALES:
        if col_name in ['Fecha', 'Año', 'NumSemana', 'MesNombre', 'AñoMes']: continue # Ya procesadas o son numéricas/fecha

        default_val = default_values_fill.get(col_name, "No Especificado")
        if col_name not in df_procesado.columns:
            df_procesado[col_name] = default_val
        else:
            df_procesado[col_name] = df_procesado[col_name].fillna(default_val).astype(str)
            # Normalizar reemplazando múltiples representaciones de "vacío" o "NA"
            for empty_val_pattern in generic_empty_na_values:
                 # Usar regex=False para reemplazo literal, y lower() para insensibilidad a mayúsculas
                df_procesado[col_name] = df_procesado[col_name].str.lower().replace(empty_val_pattern, default_val.lower(), regex=False)
            df_procesado[col_name] = df_procesado[col_name].str.strip()
            # Si después de strip queda vacío, llenar con default
            df_procesado.loc[df_procesado[col_name] == '', col_name] = default_val
            # Capitalizar para presentación (opcional, ajusta según necesidad)
            if col_name not in ["SQL", "SQL_Estandarizado", "Email", "LinkedIn", "RPA"]: # Columnas que no se capitalizan
                 df_procesado[col_name] = df_procesado[col_name].str.title() # Capitaliza cada palabra
                 df_procesado[col_name] = df_procesado[col_name].replace("N/D", "N/D", regex=False) # Revertir N/D si se capitalizó
                 df_procesado[col_name] = df_procesado[col_name].replace("No Especificado", "No Especificado", regex=False)
                 df_procesado[col_name] = df_procesado[col_name].replace("No Asignado Lg", "No Asignado LG", regex=False)
                 df_procesado[col_name] = df_procesado[col_name].replace("No Asignado Ae", "No Asignado AE", regex=False)


    # Estandarización de SQL
    df_procesado["SQL"] = df_procesado["SQL"].astype(str).str.strip().str.upper()
    df_procesado["SQL_Estandarizado"] = df_procesado["SQL"] # Iniciar con el valor original
    # Mapear valores vacíos o no reconocidos a "SIN CALIFICACIÓN SQL"
    # Considerar también valores que no están en SQL_ORDER_OF_IMPORTANCE como "Otros" o mapearlos si es posible
    known_sql_values_upper = [s.upper() for s in SQL_ORDER_OF_IMPORTANCE]
    mask_unknown_sql = ~df_procesado['SQL_Estandarizado'].isin(known_sql_values_upper)
    df_procesado.loc[mask_unknown_sql, 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL' # Opcionalmente "Otros" y añadir a SQL_ORDER_OF_IMPORTANCE

    # Seleccionar y ordenar columnas finales
    df_final_structure = pd.DataFrame()
    for col in COLUMNAS_CENTRALES:
        if col in df_procesado.columns:
            df_final_structure[col] = df_procesado[col]
        else: # Si alguna columna central no existe por alguna razón, crearla vacía con tipo apropiado
            if col in ['Año', 'NumSemana']: df_final_structure[col] = pd.Series(dtype='Int64')
            elif col == 'Fecha': df_final_structure[col] = pd.Series(dtype='datetime64[ns]')
            else: df_final_structure[col] = pd.Series(dtype='object') # String por defecto

    # Ajuste final de tipos (algunos pueden haberse perdido)
    try:
        if 'Fecha' in df_final_structure.columns:
             df_final_structure['Fecha'] = pd.to_datetime(df_final_structure['Fecha'], errors='coerce')
        if 'Año' in df_final_structure.columns:
             df_final_structure['Año'] = pd.to_numeric(df_final_structure['Año'], errors='coerce').astype('Int64')
        if 'NumSemana' in df_final_structure.columns:
             df_final_structure['NumSemana'] = pd.to_numeric(df_final_structure['NumSemana'], errors='coerce').astype('Int64')
        # Las demás columnas ya deberían ser string o el tipo correcto por el llenado de defaults
    except Exception as e_type_final:
        st.warning(f"ADVERTENCIA al ajustar tipos finales: {e_type_final}")

    return df_final_structure.reset_index(drop=True)


def clear_ses_filters_callback():
    """Resetea todos los filtros a sus valores por defecto."""
    for key, value in default_filters_config.items():
        st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")

def sidebar_filters_sesiones(df_options):
    """Crea los filtros en el sidebar usando las opciones del DataFrame."""
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")
    # Filtro de Fecha
    min_d, max_d = (None, None)
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]) and not df_options["Fecha"].dropna().empty:
        min_d_series = df_options["Fecha"].dropna().min()
        max_d_series = df_options["Fecha"].dropna().max()
        if pd.notna(min_d_series) and pd.notna(max_d_series):
            min_d, max_d = min_d_series.date(), max_d_series.date()

    c1, c2 = st.sidebar.columns(2)
    start_date_val_state = st.session_state.get(SES_START_DATE_KEY)
    end_date_val_state = st.session_state.get(SES_END_DATE_KEY)

    start_date_for_input = start_date_val_state
    if isinstance(start_date_val_state, datetime.datetime): start_date_for_input = start_date_val_state.date()
    elif start_date_val_state is not None and not isinstance(start_date_val_state, datetime.date): start_date_for_input = None

    end_date_for_input = end_date_val_state
    if isinstance(end_date_val_state, datetime.datetime): end_date_for_input = end_date_val_state.date()
    elif end_date_val_state is not None and not isinstance(end_date_val_state, datetime.date): end_date_for_input = None

    c1.date_input("Desde", value=start_date_for_input, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    c2.date_input("Hasta", value=end_date_for_input, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")

    # --- INICIO DE LÓGICA MEJORADA PARA AÑO Y SEMANA ---
    st.sidebar.subheader("📅 Por Año y Semana")

    year_options_ses = ["– Todos –"]
    if "Año" in df_options.columns and not df_options["Año"].dropna().empty:
        try:
            unique_years_int = sorted(df_options["Año"].dropna().astype(int).unique(), reverse=True)
            year_options_ses.extend([str(year) for year in unique_years_int])
        except ValueError: # Si 'Año' no se puede convertir a int, usar como string
            unique_years_str = sorted(df_options["Año"].dropna().astype(str).unique(), reverse=True)
            year_options_ses.extend(unique_years_str)


    current_year_selection_ses = st.session_state.get(SES_YEAR_FILTER_KEY, "– Todos –")
    if not isinstance(current_year_selection_ses, str):
        current_year_selection_ses = str(current_year_selection_ses)

    if current_year_selection_ses not in year_options_ses:
        current_year_selection_ses = "– Todos –"
        st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses

    selected_year_index_ses = 0
    try:
        selected_year_index_ses = year_options_ses.index(current_year_selection_ses)
    except ValueError:
        if year_options_ses:
            selected_year_index_ses = 0
            current_year_selection_ses = year_options_ses[selected_year_index_ses]
            st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses
        else:
            year_options_ses = ["(No hay años)"]
            current_year_selection_ses = year_options_ses[0]
            st.session_state[SES_YEAR_FILTER_KEY] = current_year_selection_ses
            selected_year_index_ses = 0

    selected_year_str_ses = st.sidebar.selectbox(
        "Año",
        options=year_options_ses,
        index=selected_year_index_ses,
        key=SES_YEAR_FILTER_KEY
    )
    
    sel_y = None # Inicializar sel_y
    if selected_year_str_ses != "– Todos –":
        try:
            sel_y = int(selected_year_str_ses)
        except ValueError: # Si el año no es un entero (ej. si vino de un error de casteo)
            sel_y = None # O manejar el error de otra forma

    week_options_ses = ["– Todas –"]
    if sel_y is not None and "Año" in df_options.columns:
        df_for_week_ses = df_options[df_options["Año"] == sel_y] # Comparar int con int
    else:
        df_for_week_ses = df_options

    num_semana_series = df_for_week_ses.get("NumSemana")
    if num_semana_series is not None and not num_semana_series.dropna().empty:
        try:
            unique_weeks_for_year = sorted(num_semana_series.dropna().astype(int).unique())
            week_options_ses.extend([str(w) for w in unique_weeks_for_year])
        except ValueError: # Si 'NumSemana' no se puede convertir a int
             unique_weeks_str = sorted(num_semana_series.dropna().astype(str).unique())
             week_options_ses.extend(unique_weeks_str)


    current_week_selection_state_ses = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    if not isinstance(current_week_selection_state_ses, list):
        current_week_selection_state_ses = ["– Todas –"]

    valid_week_selection_ses = [s for s in current_week_selection_state_ses if s in week_options_ses]
    if not valid_week_selection_ses:
        if "– Todas –" in week_options_ses: valid_week_selection_ses = ["– Todas –"]
        elif week_options_ses and week_options_ses[0] != "– Todas –": valid_week_selection_ses = [] # O [week_options_ses[0]]
        else: valid_week_selection_ses = []


    if set(valid_week_selection_ses) != set(st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])):
        st.session_state[SES_WEEK_FILTER_KEY] = valid_week_selection_ses

    st.sidebar.multiselect(
        "Semanas",
        options=week_options_ses,
        key=SES_WEEK_FILTER_KEY,
        default=valid_week_selection_ses
    )
    # --- FIN DE LÓGICA MEJORADA PARA AÑO Y SEMANA ---

    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")

    def create_multiselect_options(df_col_series, session_key, label_for_options=""): # label_for_options no se usa aquí
        options_list = ["– Todos –"]
        if df_col_series is not None and not df_col_series.dropna().empty:
            # Limpiar y obtener únicos, luego ordenar (manejar N/D si existe)
            unique_vals = df_col_series.astype(str).str.strip()
            # Reemplazar vacíos con 'N/D' solo si 'N/D' es un valor esperado o para agrupar vacíos
            # Si 'N/D' no es deseado como opción, se puede filtrar aquí.
            # Por ahora, asumimos que si '' se convierte a 'N/D', está bien.
            unique_vals = unique_vals.replace('', 'N/D').unique()

            unique_vals_cleaned = [val for val in unique_vals if val and val != 'N/D']
            options_list.extend(sorted(list(set(unique_vals_cleaned))))
            if 'N/D' in unique_vals and 'N/D' not in options_list : # Asegurar que 'N/D' esté si era un valor original
                options_list.append('N/D')
        
        current_sel = st.session_state.get(session_key, ["– Todos –"])
        if not isinstance(current_sel, list): current_sel = ["– Todos –"]

        valid_sel = [s for s in current_sel if s in options_list]
        if not valid_sel:
            if "– Todos –" in options_list: valid_sel = ["– Todos –"]
            elif options_list and options_list[0] != "– Todos –" : valid_sel = [] # O [options_list[0]]
            else: valid_sel = []


        if set(valid_sel) != set(st.session_state.get(session_key, ["– Todos –"])):
            st.session_state[session_key] = valid_sel
        
        return options_list, valid_sel

    lgs_options, valid_lg_default = create_multiselect_options(df_options.get("LG"), SES_LG_FILTER_KEY)
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=valid_lg_default)

    ae_options, valid_ae_default = create_multiselect_options(df_options.get("AE"), SES_AE_FILTER_KEY)
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=valid_ae_default)

    paises_opts, valid_pais_default = create_multiselect_options(df_options.get("País"), SES_PAIS_FILTER_KEY)
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=valid_pais_default)

    sql_series_for_options = df_options.get("SQL_Estandarizado") # No convertir a str aún si es None
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
        elif sqls_opts_ordered and sqls_opts_ordered[0] != "– Todos –": valid_sql_default = [] # O [sqls_opts_ordered[0]]
        else: valid_sql_default = []


    if set(valid_sql_default) != set(st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"])):
        st.session_state[SES_SQL_FILTER_KEY] = valid_sql_default

    st.sidebar.multiselect("Calificación SQL", sqls_opts_ordered, key=SES_SQL_FILTER_KEY, default=valid_sql_default)
    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback, use_container_width=True, key=f"{FILTER_KEYS_PREFIX}btn_clear")

    return (
        st.session_state.get(SES_START_DATE_KEY),
        st.session_state.get(SES_END_DATE_KEY),
        sel_y,
        st.session_state.get(SES_WEEK_FILTER_KEY),
        st.session_state.get(SES_AE_FILTER_KEY),
        st.session_state.get(SES_LG_FILTER_KEY),
        st.session_state.get(SES_PAIS_FILTER_KEY),
        st.session_state.get(SES_SQL_FILTER_KEY)
    )

def apply_sesiones_filters(df, start_date, end_date, year_f, week_f_list, ae_f_list, lg_f_list, pais_f_list, sql_f_list):
    if df is None or df.empty: return DF_FINAL_STRUCTURE_EMPTY.copy()
    df_f = df.copy()

    # Filtro de Fecha
    if "Fecha" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f["Fecha"]):
        # Convertir start_date y end_date a pd.Timestamp si son datetime.date para comparación correcta
        start_dt = pd.to_datetime(start_date, errors='coerce').normalize() if start_date else None
        end_dt = pd.to_datetime(end_date, errors='coerce').normalize() if end_date else None
        
        fecha_series_norm = df_f["Fecha"].dt.normalize() # Normalizar también la columna del DF

        if start_dt and end_dt:
            df_f = df_f[(fecha_series_norm >= start_dt) & (fecha_series_norm <= end_dt)]
        elif start_dt:
            df_f = df_f[fecha_series_norm >= start_dt]
        elif end_dt:
            df_f = df_f[fecha_series_norm <= end_dt]

    # Filtro de Año
    if year_f is not None and "Año" in df_f.columns:
        # Asegurar que la columna 'Año' sea numérica para la comparación si year_f es int
        if pd.api.types.is_numeric_dtype(df_f["Año"]):
            df_f = df_f[df_f["Año"] == year_f]
        else: # Si la columna 'Año' no es numérica pero year_f sí, intentar convertirla
            try:
                df_f = df_f[df_f["Año"].astype(int) == year_f]
            except ValueError:
                st.warning("No se pudo aplicar el filtro de año debido a tipos incompatibles.")


    # Filtro de Semana
    if week_f_list and "– Todas –" not in week_f_list and "NumSemana" in df_f.columns:
        # Convertir semanas seleccionadas a entero para la comparación
        try:
            selected_weeks_int = [int(w) for w in week_f_list if isinstance(w, str) and w.isdigit()]
            if selected_weeks_int:
                 # Asegurar que la columna 'NumSemana' sea numérica
                if pd.api.types.is_numeric_dtype(df_f["NumSemana"]):
                    df_f = df_f[df_f["NumSemana"].isin(selected_weeks_int)]
                else: # Intentar convertir 'NumSemana' a entero
                    try:
                        df_f = df_f[df_f["NumSemana"].astype(int).isin(selected_weeks_int)]
                    except ValueError:
                         st.warning("No se pudo aplicar el filtro de semana debido a tipos incompatibles en 'NumSemana'.")
        except ValueError:
            st.warning("Las semanas seleccionadas contienen valores no numéricos.")


    # Filtros de Multiselect (AE, LG, País, SQL)
    filter_map = {
        "AE": ae_f_list, "LG": lg_f_list, "País": pais_f_list, "SQL_Estandarizado": sql_f_list
    }
    for col_name, filter_values in filter_map.items():
        if filter_values and "– Todos –" not in filter_values and col_name in df_f.columns:
            # Asegurar que tanto la columna como los valores de filtro sean strings para isin
            df_f = df_f[df_f[col_name].astype(str).isin([str(val) for val in filter_values])]
    return df_f


def get_sql_category_order(df_column_or_list):
    """Obtiene el orden correcto para las categorías SQL, priorizando SQL_ORDER_OF_IMPORTANCE."""
    present_sqls_series = pd.Series(df_column_or_list).astype(str).dropna().unique()
    # Filtrar para asegurar que solo los valores realmente presentes en los datos se usen para ordenar
    ordered_present_sqls = [s for s in SQL_ORDER_OF_IMPORTANCE if s in present_sqls_series]
    # Añadir otros SQLs que puedan existir en los datos pero no estén en la lista priorizada, ordenados alfabéticamente
    other_sqls = sorted([s for s in present_sqls_series if s not in SQL_ORDER_OF_IMPORTANCE])
    return ordered_present_sqls + other_sqls


def display_sesiones_summary_sql(df_filtered):
    st.markdown("### 📌 Resumen Principal de Sesiones")
    if df_filtered.empty: st.info("No hay sesiones para resumen con los filtros aplicados."); return

    total_sesiones = len(df_filtered)
    st.metric("Total Sesiones (filtradas)", f"{total_sesiones:,}")

    if 'SQL_Estandarizado' in df_filtered.columns:
        st.markdown("#### Distribución por Calificación SQL")
        sql_counts = df_filtered['SQL_Estandarizado'].value_counts().reset_index()
        sql_counts.columns = ['Calificación SQL', 'Número de Sesiones'] # Renombrar columnas

        # Obtener el orden correcto de las categorías SQL presentes en los datos filtrados
        category_order_sql_summary = get_sql_category_order(sql_counts['Calificación SQL'])

        # Convertir 'Calificación SQL' a tipo categórico con el orden correcto
        sql_counts['Calificación SQL'] = pd.Categorical(
            sql_counts['Calificación SQL'],
            categories=category_order_sql_summary,
            ordered=True
        )
        sql_counts = sql_counts.sort_values('Calificación SQL').reset_index(drop=True)

        if not sql_counts.empty:
            fig_sql_summary = px.bar(
                sql_counts,
                x='Calificación SQL',
                y='Número de Sesiones',
                title='Sesiones por Calificación SQL',
                text_auto=True,
                color='Calificación SQL',
                # No es necesario category_orders aquí si ya hemos ordenado el DataFrame
                # y la columna X es categórica ordenada. Plotly respetará ese orden.
            )
            # Asegurar que el eje X use el orden categórico si Plotly no lo hace automáticamente
            fig_sql_summary.update_xaxes(categoryorder='array', categoryarray=category_order_sql_summary)
            st.plotly_chart(fig_sql_summary, use_container_width=True)
            st.dataframe(sql_counts.set_index('Calificación SQL').style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
        else:
            st.info("No hay datos de calificación SQL para mostrar.")
    else:
        st.warning("Columna 'SQL_Estandarizado' no encontrada para el resumen.")


def display_analisis_por_dimension(df_filtered, dimension_col, dimension_label, top_n=10):
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para análisis por {dimension_label}.")
        return

    # Asegurar que la columna de dimensión sea string para evitar problemas con .value_counts() y .isin()
    df_filtered_copy = df_filtered.copy() # Trabajar con una copia para evitar SettingWithCopyWarning
    df_filtered_copy[dimension_col] = df_filtered_copy[dimension_col].astype(str)

    # Obtener el Top N de la dimensión basado en el total de sesiones
    dim_totals = df_filtered_copy[dimension_col].value_counts().nlargest(top_n)
    top_n_dims_list = dim_totals.index.tolist()

    # Filtrar el DataFrame para incluir solo el Top N de la dimensión
    df_top_n = df_filtered_copy[df_filtered_copy[dimension_col].isin(top_n_dims_list)]

    if df_top_n.empty:
        st.info(f"No hay datos para el Top {top_n} de {dimension_label}.")
        return

    # Agrupar por la dimensión y SQL_Estandarizado
    summary_dim_sql = df_top_n.groupby([dimension_col, 'SQL_Estandarizado'], observed=False).size().reset_index(name='Cantidad_SQL')

    if summary_dim_sql.empty:
        st.info(f"No hay datos agregados por {dimension_label} y SQL para el Top {top_n}.")
        return

    # Ordenar para el gráfico y la tabla
    sql_category_order_dim_analysis = get_sql_category_order(summary_dim_sql['SQL_Estandarizado'])
    summary_dim_sql['SQL_Estandarizado'] = pd.Categorical(summary_dim_sql['SQL_Estandarizado'], categories=sql_category_order_dim_analysis, ordered=True)
    # La dimensión también se puede hacer categórica para asegurar el orden del Top N
    summary_dim_sql[dimension_col] = pd.Categorical(summary_dim_sql[dimension_col], categories=top_n_dims_list, ordered=True)
    summary_dim_sql = summary_dim_sql.sort_values(by=[dimension_col, 'SQL_Estandarizado'])

    # Gráfico de barras apiladas
    fig_dim_analysis = px.bar(
        summary_dim_sql,
        x=dimension_col,
        y='Cantidad_SQL',
        color='SQL_Estandarizado',
        title=f'Distribución de SQL por {dimension_label} (Top {top_n})',
        barmode='stack',
        color_discrete_sequence=px.colors.qualitative.Vivid # O cualquier otra secuencia de color
    )
    fig_dim_analysis.update_layout(
        xaxis_tickangle=-45,
        yaxis_title="Número de Sesiones",
        xaxis={'categoryorder':'array', 'categoryarray':top_n_dims_list}, # Asegurar orden del eje X
        legend_title_text='Calificación SQL'
    )
    st.plotly_chart(fig_dim_analysis, use_container_width=True)

    # Tabla pivote para mostrar los datos
    try:
        pivot_table_dim = summary_dim_sql.pivot_table(
            index=dimension_col,
            columns='SQL_Estandarizado',
            values='Cantidad_SQL',
            fill_value=0,
            observed=False # Importante con columnas categóricas
        )
        # Reordenar columnas y filas para consistencia con el gráfico
        pivot_table_dim = pivot_table_dim.reindex(columns=sql_category_order_dim_analysis, fill_value=0)
        pivot_table_dim = pivot_table_dim.reindex(index=top_n_dims_list, fill_value=0) # Asegurar orden del Top N

        pivot_table_dim['Total_Sesiones_Dim'] = pivot_table_dim.sum(axis=1)
        format_dict_dim = {col: "{:,.0f}" for col in pivot_table_dim.columns} # Formato para todos los números
        st.dataframe(pivot_table_dim.style.format(format_dict_dim), use_container_width=True)
    except Exception as e_pivot:
        st.warning(f"No se pudo generar la tabla pivot para {dimension_label}: {e_pivot}")


def display_evolucion_sql(df_filtered, time_agg_col, display_label, chart_title, x_axis_label):
    st.markdown(f"### 📈 {chart_title}")

    required_cols = ['SQL_Estandarizado', time_agg_col]
    if time_agg_col == 'NumSemana' and ('Año' not in df_filtered.columns or 'NumSemana' not in df_filtered.columns) :
        st.info(f"Datos insuficientes para {chart_title.lower()}. Se requieren 'Año' y 'NumSemana'.")
        return
    if df_filtered.empty or not all(col in df_filtered.columns for col in required_cols):
        st.info(f"Datos insuficientes para {chart_title.lower()}. Columnas requeridas: {required_cols}")
        return

    df_agg_evol = df_filtered.copy()
    group_col_evol = time_agg_col
    sort_cols_evol = [time_agg_col] # Lista para ordenar

    if time_agg_col == 'NumSemana':
        # Asegurar que Año y NumSemana sean numéricos antes de crear Año-Semana
        try:
            df_agg_evol.dropna(subset=['Año', 'NumSemana'], inplace=True) # Quitar NaNs antes de astype
            df_agg_evol['Año'] = df_agg_evol['Año'].astype(int)
            df_agg_evol['NumSemana'] = df_agg_evol['NumSemana'].astype(int)
            df_agg_evol[display_label] = df_agg_evol['Año'].astype(str) + '-S' + df_agg_evol['NumSemana'].astype(str).str.zfill(2)
            group_col_evol = display_label
            sort_cols_evol = ['Año', 'NumSemana'] # Ordenar por Año y luego NumSemana
        except (ValueError, TypeError) as e:
            st.warning(f"No se pudo crear la columna '{display_label}' debido a problemas con 'Año' o 'NumSemana': {e}")
            return
    elif time_agg_col == 'AñoMes': # AñoMes ya es YYYY-MM y es ordenable como string
        df_agg_evol[display_label] = df_agg_evol[time_agg_col] # Usar la columna directamente
        # sort_cols_evol ya es [time_agg_col] que es 'AñoMes'

    df_agg_evol.dropna(subset=[group_col_evol, 'SQL_Estandarizado'], inplace=True)
    if df_agg_evol.empty:
        st.info(f"No hay datos válidos para '{group_col_evol}' y 'SQL_Estandarizado'.")
        return

    summary_time_sql_evol = df_agg_evol.groupby([group_col_evol, 'SQL_Estandarizado'], observed=False).size().reset_index(name='Número de Sesiones')
    if summary_time_sql_evol.empty:
        st.info(f"No hay datos agregados por {x_axis_label.lower()} y SQL.")
        return

    # Ordenar el DataFrame antes de graficar para que las líneas se dibujen correctamente
    # Si es Año-Semana, necesitamos ordenar por las columnas numéricas originales de Año y NumSemana
    if time_agg_col == 'NumSemana' and 'Año' in df_agg_evol.columns and 'NumSemana' in df_agg_evol.columns :
         # Para esto, necesitamos Año y NumSemana en summary_time_sql_evol.
         # Es mejor hacer el sort en df_agg_evol ANTES del groupby si el group_col_evol ya es el string final.
         # O, si group_col_evol es Año y NumSemana, el groupby ya los tiene y podemos usarlo para el sort.
         # En este caso, group_col_evol es 'Año-Semana', así que el sort_values por él mismo funciona.
         summary_time_sql_evol = summary_time_sql_evol.sort_values(by=[group_col_evol]) # Sort by the display label
    elif time_agg_col == 'AñoMes':
         summary_time_sql_evol = summary_time_sql_evol.sort_values(by=[group_col_evol])


    sql_category_order_evol = get_sql_category_order(summary_time_sql_evol['SQL_Estandarizado'])
    summary_time_sql_evol['SQL_Estandarizado'] = pd.Categorical(summary_time_sql_evol['SQL_Estandarizado'], categories=sql_category_order_evol, ordered=True)
    # Re-sort si es necesario después de categorizar SQL para leyendas ordenadas
    summary_time_sql_evol = summary_time_sql_evol.sort_values(by=[group_col_evol, 'SQL_Estandarizado'])


    try:
        fig_evol_sql = px.line(
            summary_time_sql_evol,
            x=group_col_evol,
            y='Número de Sesiones',
            color='SQL_Estandarizado',
            title=f"Evolución por SQL ({x_axis_label})",
            markers=True,
            # category_orders={"SQL_Estandarizado": sql_category_order_evol} # Puede no ser necesario si se ordena antes
        )
        fig_evol_sql.update_xaxes(type='category', title_text=x_axis_label) # Asegurar que se trate como categoría
        fig_evol_sql.update_layout(yaxis_title="Número de Sesiones", legend_title_text='Calificación SQL')
        st.plotly_chart(fig_evol_sql, use_container_width=True)
    except Exception as e_evol_sql:
        st.warning(f"No se pudo generar gráfico de evolución para {x_axis_label}: {e_evol_sql}")


def display_tabla_sesiones_detalle(df_filtered):
    st.markdown("### 📝 Tabla Detallada de Sesiones")
    if df_filtered.empty: st.info("No hay sesiones detalladas para mostrar con los filtros aplicados."); return

    # Seleccionar solo las columnas que existen en df_filtered del listado deseado
    cols_deseadas_detalle_ses = ["Fecha", "LG", "AE", "País", "SQL", "SQL_Estandarizado", "Empresa", "Puesto", "Nombre", "Apellido", "Siguientes Pasos", "RPA", "Fuente_Hoja", "LinkedIn", "Email"]
    cols_present_detalle_ses = [col for col in cols_deseadas_detalle_ses if col in df_filtered.columns]
    df_view_detalle_ses = df_filtered[cols_present_detalle_ses].copy()

    if "Fecha" in df_view_detalle_ses.columns and pd.api.types.is_datetime64_any_dtype(df_view_detalle_ses["Fecha"]):
         try: # Formatear la fecha a DD/MM/YYYY
            df_view_detalle_ses["Fecha"] = pd.to_datetime(df_view_detalle_ses["Fecha"], errors='coerce').dt.strftime('%d/%m/%Y')
            df_view_detalle_ses["Fecha"] = df_view_detalle_ses["Fecha"].fillna("Fecha Inválida") # Si era NaT
         except AttributeError: pass # Si la columna Fecha no tiene .dt (ej. ya es string o todo NaT)

    st.dataframe(df_view_detalle_ses, height=400, use_container_width=True, hide_index=True) # hide_index=True es común

    if not df_view_detalle_ses.empty:
        output = io.BytesIO()
        try:
            # Crear una copia para no modificar la que se muestra, si se hacen cambios para Excel
            df_excel = df_view_detalle_ses.copy()
            # Podrías querer revertir el formato de fecha a datetime para Excel si es preferible
            if "Fecha" in df_excel.columns and df_excel["Fecha"].dtype == 'object':
                df_excel["Fecha"] = pd.to_datetime(df_excel["Fecha"], format='%d/%m/%Y', errors='coerce')

            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_excel.to_excel(writer, index=False, sheet_name='Detalle_Sesiones')
            # output.seek(0) # No es necesario para getvalue()

            st.download_button(
                label="⬇️ Descargar Detalle (Excel)",
                data=output.getvalue(),
                file_name="detalle_sesiones_sql.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{FILTER_KEYS_PREFIX}btn_download_detalle"
            )
        except Exception as e_excel:
            st.error(f"Error al generar archivo Excel: {e_excel}")

# --- Flujo Principal de la Página ---
try:
    df_sesiones_base = load_sesiones_data()
except ValueError as ve:
    st.error(f"Error Crítico en la Carga de Datos: {ve}")
    st.stop()
except Exception as e:
    st.error(f"Error Inesperado durante la Carga de Datos: {e}")
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
# display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="Puesto", dimension_label="Cargo (Puesto)", top_n=10)
# st.markdown("---")
# display_analisis_por_dimension(df_filtered=df_sesiones_filtered, dimension_col="Empresa", dimension_label="Empresa", top_n=10)
# st.markdown("---")

# Graficos de evolución
display_evolucion_sql(df_sesiones_filtered, 'NumSemana', 'Año-Semana', "Evolución Semanal por Calificación SQL", "Semana del Año")
st.markdown("---")
display_evolucion_sql(df_sesiones_filtered, 'AñoMes', 'Año-Mes', "Evolución Mensual por Calificación SQL", "Mes del Año")
st.markdown("---")

# Tabla de detalle al final
display_tabla_sesiones_detalle(df_sesiones_filtered)

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info("Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊")
