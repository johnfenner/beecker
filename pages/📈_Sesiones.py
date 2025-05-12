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
    "Métricas basadas en columnas principales: LG, AE, País, Calificación SQL, Puesto, Empresa."
)

# --- Constantes ---
SHEET_URL_SESIONES_PRINCIPAL_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902"
SHEET_NAME_SESIONES_PRINCIPAL = "Sesiones 2024-2025"

SHEET_URL_SESIONES_SURAMERICA_DEFAULT = "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854"
SHEET_NAME_SESIONES_SURAMERICA = "BD Sesiones 2024"

# --- COLUMNAS CENTRALES ---
# Definidas según la estructura de la hoja Principal + Derivadas necesarias
# Estas son las ÚNICAS columnas que existirán en el DataFrame final para análisis
COLUMNAS_CENTRALES = [
    "Fecha", "Empresa", "País", "Nombre", "Apellido", "Puesto", "SQL", "SQL_Estandarizado",
    "AE", "LG", "Siguientes Pasos", "Email", "RPA", "LinkedIn", # LinkedIn es opcional, quitar si no se usa
    "Fuente_Hoja", # Identifica el origen
    "Año", "NumSemana", "MesNombre", "AñoMes", # Derivadas de tiempo
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
    """Intenta parsear fechas en varios formatos comunes."""
    if pd.isna(date_val) or str(date_val).strip() == "": return None
    # Priorizar formatos día/mes/año
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
              # Formatos año-mes-día
              "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
              # Formatos mes/día/año
              "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try: return pd.to_datetime(date_val, format=fmt)
        except (ValueError, TypeError): continue
    # Intento genérico final si los formatos específicos fallan
    try: return pd.to_datetime(date_val, errors='coerce')
    except (ValueError, TypeError): return None

def separar_nombre_cargo_suramerica(nombre_cargo_str):
    """Separa Nombre, Apellido y Puesto desde la columna 'Nombre y Cargo' de Suramérica."""
    nombre, apellido, puesto = pd.NA, pd.NA, "No Especificado"
    if pd.isna(nombre_cargo_str) or not isinstance(nombre_cargo_str, str) or not nombre_cargo_str.strip():
        return nombre, apellido, puesto

    nombre_cargo_str = nombre_cargo_str.strip()
    # Delimitadores comunes entre nombre y cargo
    delimiters_cargo = [' - ', ' / ', ', ', ' – ']
    nombre_completo_str = nombre_cargo_str
    cargo_encontrado_explicitamente = False

    # Buscar delimitador para separar cargo explícito
    for delim in delimiters_cargo:
        if delim in nombre_cargo_str:
            parts = nombre_cargo_str.split(delim, 1)
            nombre_completo_str = parts[0].strip()
            if len(parts) > 1 and parts[1].strip():
                puesto = parts[1].strip()
                cargo_encontrado_explicitamente = True
            break # Usar el primer delimitador encontrado

    # Separar nombre y apellido
    name_parts = [part.strip() for part in nombre_completo_str.split() if part.strip()]

    if not name_parts: return pd.NA, pd.NA, puesto # Sin nombre

    # Lógica de asignación de nombre/apellido basada en número de partes
    if len(name_parts) == 1:
        nombre = name_parts[0]
    elif len(name_parts) == 2:
        nombre, apellido = name_parts[0], name_parts[1]
    elif len(name_parts) == 3: # Asumir Nombre Apellido1 Apellido2
        nombre, apellido = name_parts[0], f"{name_parts[1]} {name_parts[2]}"
    elif len(name_parts) >= 4: # Asumir Nombre1 Nombre2 Apellido1 Apellido2...
        nombre = f"{name_parts[0]} {name_parts[1]}"
        apellido = " ".join(name_parts[2:])
        # Si no se encontró cargo explícito antes, intentar inferirlo de las últimas partes
        if not cargo_encontrado_explicitamente:
             # Considerar si las últimas partes podrían ser un cargo
            temp_nombre_simple, temp_apellido_simple = name_parts[0], name_parts[1]
            temp_cargo_implicito = " ".join(name_parts[2:])
            # Heurística simple: si el 'cargo implícito' tiene más de X caracteres, asumirlo como tal
            if len(temp_cargo_implicito) > 3 and len(temp_cargo_implicito.split()) > 1: # Evitar iniciales o palabras cortas
                nombre, apellido, puesto = temp_nombre_simple, temp_apellido_simple, temp_cargo_implicito

    # Si después de todo, el nombre sigue vacío pero había algo en nombre_completo_str
    if pd.isna(nombre) and pd.notna(nombre_completo_str) and nombre_completo_str:
        nombre = nombre_completo_str # Asignar todo como nombre

    return (str(nombre).strip() if pd.notna(nombre) else pd.NA,
            str(apellido).strip() if pd.notna(apellido) else pd.NA,
            str(puesto).strip() if pd.notna(puesto) and puesto else "No Especificado")


@st.cache_data(ttl=300)
def load_sesiones_data():
    """Carga datos de ambas hojas, consolida y devuelve un DataFrame SOLO con COLUMNAS_CENTRALES."""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    df_final_structure = pd.DataFrame(columns=COLUMNAS_CENTRALES) # Estructura final deseada
    try:
        # --- Autenticación ---
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
        st.error(f"Error: Falta la clave '{e}' en los 'Secrets' (Sesiones). Revisa la configuración.")
        return df_final_structure
    except Exception as e:
        st.error(f"Error al autenticar con Google Sheets (Sesiones): {e}")
        return df_final_structure

    all_dataframes = []

    # --- 1. Cargar Hoja Principal ("Sesiones 2024-2025") ---
    # Columnas esperadas: Fecha, SQL, Empresa, País, Nombre, Apellido, Puesto, Email, AE, LG, Siguientes Pasos, RPA, [LinkedIn]
    sheet_url_principal_actual = st.secrets.get("SESIONES_PRINCIPAL_SHEET_URL", SHEET_URL_SESIONES_PRINCIPAL_DEFAULT)
    try:
        workbook_principal = client.open_by_url(sheet_url_principal_actual)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES_PRINCIPAL)
        # Usar get_all_values + make_unique para manejar posibles encabezados duplicados
        raw_data_principal_list = sheet_principal.get_all_values()

        if raw_data_principal_list and len(raw_data_principal_list) > 1:
            def make_unique_headers(headers_list):
                counts = {}
                new_headers = []
                for h in headers_list:
                    h_stripped = str(h).strip()
                    if h_stripped in counts:
                        counts[h_stripped] += 1
                        new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
                    else:
                        counts[h_stripped] = 1
                        new_headers.append(h_stripped)
                return new_headers

            headers_p = make_unique_headers(raw_data_principal_list[0])
            df_principal_raw = pd.DataFrame(raw_data_principal_list[1:], columns=headers_p)

            df_proc_principal = pd.DataFrame()
            # Mapeo explícito usando los nombres de columna de la hoja Principal
            df_proc_principal["Fecha"] = df_principal_raw.get("Fecha")
            df_proc_principal["Empresa"] = df_principal_raw.get("Empresa")
            df_proc_principal["País"] = df_principal_raw.get("País")
            df_proc_principal["Nombre"] = df_principal_raw.get("Nombre")
            df_proc_principal["Apellido"] = df_principal_raw.get("Apellido")
            df_proc_principal["Puesto"] = df_principal_raw.get("Puesto")
            df_proc_principal["SQL"] = df_principal_raw.get("SQL")
            df_proc_principal["AE"] = df_principal_raw.get("AE")
            df_proc_principal["LG"] = df_principal_raw.get("LG")
            df_proc_principal["Siguientes Pasos"] = df_principal_raw.get("Siguientes Pasos")
            df_proc_principal["Email"] = df_principal_raw.get("Email")
            df_proc_principal["RPA"] = df_principal_raw.get("RPA")
            df_proc_principal["LinkedIn"] = df_principal_raw.get("LinkedIn") # Mapear si existe/es deseada
            df_proc_principal["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_proc_principal)
        else:
            st.warning(f"Hoja Principal ('{SHEET_NAME_SESIONES_PRINCIPAL}') vacía o solo con encabezados.")
    except gspread.exceptions.GSpreadException as e:
        st.error(f"Error gspread al cargar Hoja Principal: {e}. Verifica URL, nombre de hoja y permisos.")
    except Exception as e:
        st.error(f"Error general al cargar/procesar Hoja Principal: {e}")

    # --- 2. Cargar Hoja Suramérica ("BD Sesiones 2024") ---
    # Columnas hoja: Fecha, Empresa, País, Siguientes Pasos, SQL, Asistencia BDR´s, Nombre y Cargo,
    # Interes del Lead, Estado, Correo, Teléfono, Tipo, LinkedIn, LG, AE, Web, Dirección
    sheet_url_suramerica_actual = st.secrets.get("SESIONES_SURAMERICA_SHEET_URL", SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
    try:
        workbook_suramerica = client.open_by_url(sheet_url_suramerica_actual)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        # Usar get_all_records asumiendo encabezados únicos en Suramérica. ¡VERIFICAR ESTO!
        # Si no son únicos, cambiar a get_all_values + make_unique_headers como en Principal.
        raw_data_suramerica = sheet_suramerica.get_all_records(head=1, default_blank=pd.NA)

        if raw_data_suramerica:
            df_suramerica_raw = pd.DataFrame(raw_data_suramerica)
            df_suramerica_processed = pd.DataFrame()

            # Mapear columnas de Suramérica a nombres estándar (si coinciden con COLUMNAS_CENTRALES)
            df_suramerica_processed["Fecha"] = df_suramerica_raw.get("Fecha")
            df_suramerica_processed["Empresa"] = df_suramerica_raw.get("Empresa")
            df_suramerica_processed["País"] = df_suramerica_raw.get("País")
            df_suramerica_processed["Siguientes Pasos"] = df_suramerica_raw.get("Siguientes Pasos")
            df_suramerica_processed["SQL"] = df_suramerica_raw.get("SQL")
            df_suramerica_processed["Email"] = df_suramerica_raw.get("Correo") # Desde "Correo"
            df_suramerica_processed["LinkedIn"] = df_suramerica_raw.get("LinkedIn")
            df_suramerica_processed["LG"] = df_suramerica_raw.get("LG")
            df_suramerica_processed["AE"] = df_suramerica_raw.get("AE")

            # Procesar "Nombre y Cargo"
            if "Nombre y Cargo" in df_suramerica_raw.columns:
                 nombres_cargos_split = df_suramerica_raw["Nombre y Cargo"].apply(separar_nombre_cargo_suramerica)
                 df_suramerica_processed["Nombre"] = nombres_cargos_split.apply(lambda x: x[0])
                 df_suramerica_processed["Apellido"] = nombres_cargos_split.apply(lambda x: x[1])
                 df_suramerica_processed["Puesto"] = nombres_cargos_split.apply(lambda x: x[2])
            else:
                 df_suramerica_processed["Nombre"], df_suramerica_processed["Apellido"], df_suramerica_processed["Puesto"] = pd.NA, pd.NA, "No Especificado"

            # RPA no existe en Suramérica, se llenará con NA y luego con Default si "RPA" está en COLUMNAS_CENTRALES
            # df_suramerica_processed["RPA"] = "N/A (SA)" # Alternativa: dejar que fillna actúe

            # Se cargan columnas adicionales de Suramérica TEMPORALMENTE.
            # Si NO están en COLUMNAS_CENTRALES, se eliminarán al final.
            df_suramerica_processed["Interes_del_Lead_SA"] = df_suramerica_raw.get("Interes del Lead") # Renombrar para evitar colisión si hubiera una columna igual en Principal
            df_suramerica_processed["Estado_SA"] = df_suramerica_raw.get("Estado")
            df_suramerica_processed["Telefono_SA"] = df_suramerica_raw.get("Teléfono")
            df_suramerica_processed["Tipo_SA"] = df_suramerica_raw.get("Tipo")
            df_suramerica_processed["Asistencia_BDRs_SA"] = df_suramerica_raw.get("Asistencia BDR´s")
            df_suramerica_processed["Web_SA"] = df_suramerica_raw.get("Web")
            df_suramerica_processed["Direccion_SA"] = df_suramerica_raw.get("Dirección")

            df_suramerica_processed["Fuente_Hoja"] = "Suramérica"
            all_dataframes.append(df_suramerica_processed)
        else:
            st.warning(f"Hoja Suramérica ('{SHEET_NAME_SESIONES_SURAMERICA}') vacía.")
    except gspread.exceptions.GSpreadException as e:
        st.error(f"Error gspread al cargar Hoja Suramérica: {e}. Verifica nombre, URL, permisos y si los encabezados son únicos.")
    except Exception as e:
        st.error(f"Error general al cargar/procesar Hoja Suramérica: {e}")

    # --- 3. Consolidación y Limpieza Inicial ---
    if not all_dataframes:
        st.error("No se pudieron cargar datos de ninguna hoja para consolidar.")
        return df_final_structure # Devuelve estructura vacía

    # df_consolidado tiene todas las columnas mapeadas de ambas fuentes
    df_consolidado = pd.concat(all_dataframes, ignore_index=True, sort=False)

    # Validar y parsear 'Fecha'
    if "Fecha" not in df_consolidado.columns or df_consolidado["Fecha"].isnull().all():
         st.error("Columna 'Fecha' esencial no encontrada o vacía en los datos consolidados.")
         return df_final_structure
    df_consolidado["Fecha"] = df_consolidado["Fecha"].apply(parse_date_robust)
    df_consolidado.dropna(subset=["Fecha"], inplace=True, ignore_index=True)

    if df_consolidado.empty:
        st.warning("No hay sesiones con fechas válidas después de la consolidación y parseo.")
        return df_final_structure

    # --- 4. Procesamiento Post-Consolidación ---
    df_procesado = df_consolidado.copy()

    # Crear columnas derivadas (Año, Semana, Mes, SQL Estandarizado)
    df_procesado['Año'] = df_procesado['Fecha'].dt.year.astype('Int64')
    df_procesado['NumSemana'] = df_procesado['Fecha'].dt.isocalendar().week.astype('Int64')
    df_procesado['MesNombre'] = df_procesado['Fecha'].dt.month_name()
    df_procesado['AñoMes'] = df_procesado['Fecha'].dt.strftime('%Y-%m')

    # Estandarizar SQL
    if "SQL" not in df_procesado.columns: df_procesado["SQL"] = ""
    df_procesado["SQL"] = df_procesado["SQL"].fillna("").astype(str).str.strip().str.upper()
    df_procesado['SQL_Estandarizado'] = df_procesado['SQL']
    known_sql_values = [s for s in SQL_ORDER_OF_IMPORTANCE if s != 'SIN CALIFICACIÓN SQL']
    sql_estandarizado_str = df_procesado['SQL_Estandarizado'].astype(str)
    mask_empty_sql = ~sql_estandarizado_str.isin(known_sql_values) & \
                     (sql_estandarizado_str.isin(['', 'NAN', 'NONE', 'NA', '<NA>', 'N/A'])) # Añadir N/A
    df_procesado.loc[mask_empty_sql, 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'
    df_procesado.loc[df_procesado['SQL_Estandarizado'] == '', 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'

    # --- 5. Llenar NaNs y aplicar Defaults (SOLO para COLUMNAS_CENTRALES) ---
    default_values_fill = {
        "AE": "No Asignado AE", "LG": "No Asignado LG", "Puesto": "No Especificado",
        "Empresa": "No Especificado", "País": "No Especificado", "Nombre": "No Especificado",
        "Apellido": "No Especificado", "Siguientes Pasos": "No Especificado",
        "Email": "No Especificado", "RPA": "No Aplicable", # Cambiado default de RPA
        "LinkedIn": "No Especificado", "Fuente_Hoja": "Desconocida",
        "SQL": "SIN CALIFICACIÓN SQL", "SQL_Estandarizado": "SIN CALIFICACIÓN SQL"
    }
    for col in COLUMNAS_CENTRALES:
        if col in df_procesado.columns:
            # Obtener valor por defecto específico o uno genérico
            default_val = default_values_fill.get(col, "No Especificado")
            # Convertir a string para manejar tipos mixtos antes de fillna y strip
            df_procesado[col] = df_procesado[col].astype(str)
            # Reemplazar varios tipos de "vacío" con el default ANTES de fillna
            df_procesado[col] = df_procesado[col].replace(['', 'nan', 'none', 'NaN', 'None', 'NA', '<NA>', '#N/A', 'N/A'], default_val, regex=False)
            # Aplicar strip después de reemplazar vacíos
            df_procesado[col] = df_procesado[col].str.strip()
            # Asegurar que si después del strip queda vacío, se ponga el default
            df_procesado.loc[df_procesado[col] == '', col] = default_val
            # Llenar cualquier NA restante (aunque los reemplazos anteriores deberían cubrir la mayoría)
            df_procesado[col] = df_procesado[col].fillna(default_val)

    # --- 6. SELECCIÓN FINAL DE COLUMNAS ---
    # Crear el DataFrame final solo con las columnas deseadas
    df_final_filtrado = pd.DataFrame()
    columnas_existentes_en_procesado = df_procesado.columns.tolist()

    for col in COLUMNAS_CENTRALES:
        if col in columnas_existentes_en_procesado:
            df_final_filtrado[col] = df_procesado[col]
        else:
            # Si una columna central falta por completo, crearla con un valor por defecto
            st.warning(f"Columna central '{col}' no encontrada en datos procesados. Se creará vacía/default.")
            if col in ['Año', 'NumSemana']:
                 df_final_filtrado[col] = pd.NA # Usar pd.NA para Int64
            elif col == 'Fecha':
                 df_final_filtrado[col] = pd.NaT # Usar NaT para datetime
            else:
                 df_final_filtrado[col] = default_values_fill.get(col, "No Disponible")

    # --- 7. Ajuste Final de Tipos (Opcional pero recomendado) ---
    try:
        if 'Fecha' in df_final_filtrado.columns:
             df_final_filtrado['Fecha'] = pd.to_datetime(df_final_filtrado['Fecha'], errors='coerce')
        if 'Año' in df_final_filtrado.columns:
             df_final_filtrado['Año'] = pd.to_numeric(df_final_filtrado['Año'], errors='coerce').astype('Int64')
        if 'NumSemana' in df_final_filtrado.columns:
             df_final_filtrado['NumSemana'] = pd.to_numeric(df_final_filtrado['NumSemana'], errors='coerce').astype('Int64')
        # Convertir otras columnas a string para evitar errores de tipo mixto en visualizaciones
        for col in df_final_filtrado.columns:
             if col not in ['Fecha', 'Año', 'NumSemana']:
                 df_final_filtrado[col] = df_final_filtrado[col].astype(str)

    except Exception as e_type:
        st.warning(f"Error al ajustar tipos finales: {e_type}")


    return df_final_filtrado # Devuelve DF solo con COLUMNAS_CENTRALES

# --- Funciones de Visualización y Filtros ---

def clear_ses_filters_callback():
    """Resetea todos los filtros a sus valores por defecto."""
    for key, value in default_filters_config.items():
        st.session_state[key] = value
    st.toast("Filtros reiniciados ✅", icon="🧹")

def sidebar_filters_sesiones(df_options):
    """Crea los filtros en el sidebar usando las opciones del DataFrame."""
    st.sidebar.header("🔍 Filtros de Sesiones")
    st.sidebar.markdown("---")

    # --- Filtro de Fechas ---
    min_d, max_d = (None, None)
    if "Fecha" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha"]):
        min_d_series = df_options["Fecha"].dropna().min()
        max_d_series = df_options["Fecha"].dropna().max()
        if pd.notna(min_d_series) and pd.notna(max_d_series):
            min_d, max_d = min_d_series.date(), max_d_series.date()

    c1, c2 = st.sidebar.columns(2)
    start_date_val = st.session_state.get(SES_START_DATE_KEY)
    end_date_val = st.session_state.get(SES_END_DATE_KEY)
    c1.date_input("Desde", value=start_date_val, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    c2.date_input("Hasta", value=end_date_val, min_value=min_d, max_value=max_d, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")

    # --- Filtro Año y Semana (Basado en COLUMNAS_CENTRALES) ---
    years_series = df_options.get("Año", pd.Series(dtype='Int64'))
    years = ["– Todos –"] + (sorted(years_series.dropna().astype(int).unique(), reverse=True) if not years_series.dropna().empty else [])
    current_year_val_in_state = str(st.session_state.get(SES_YEAR_FILTER_KEY,"– Todos –")) # Convertir a str para comparación
    if current_year_val_in_state not in map(str, years): current_year_val_in_state = "– Todos –"
    selected_year_str = st.sidebar.selectbox("Año", map(str, years), key=SES_YEAR_FILTER_KEY, index=list(map(str, years)).index(current_year_val_in_state))

    sel_y = int(selected_year_str) if selected_year_str != "– Todos –" else None
    weeks_df = df_options[df_options["Año"] == sel_y] if sel_y is not None and "Año" in df_options.columns else df_options
    num_semana_series = weeks_df.get("NumSemana", pd.Series(dtype='Int64'))
    weeks_available = sorted(num_semana_series.dropna().astype(int).unique()) if not num_semana_series.dropna().empty else []
    weeks_options = ["– Todas –"] + [str(w) for w in weeks_available] # Opciones como strings

    current_week_selection_in_state = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    # Validar selección actual contra opciones disponibles (como strings)
    validated_week_selection = [val for val in current_week_selection_in_state if val in weeks_options]
    if not validated_week_selection or (len(validated_week_selection) == 1 and validated_week_selection[0] not in weeks_options and "– Todas –" in weeks_options):
         validated_week_selection = ["– Todas –"] if "– Todas –" in weeks_options else []
    elif not validated_week_selection and weeks_options:
        validated_week_selection = [weeks_options[0]] if weeks_options and weeks_options[0] != "– Todas –" else []

    st.sidebar.multiselect("Semanas", weeks_options, key=SES_WEEK_FILTER_KEY, default=validated_week_selection)
    st.sidebar.markdown("---")

    # --- Filtros por Dimensiones (LG, AE, País, SQL - de COLUMNAS_CENTRALES) ---
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")
    def create_multiselect_options(df_col_series, session_key):
        # Asegurarse de que la serie sea de strings y manejar NAs antes de unique()
        options = ["– Todos –"] + (sorted(df_col_series.astype(str).dropna().unique()) if not df_col_series.dropna().empty else [])
        current_selection = st.session_state.get(session_key, ["– Todos –"])
        valid_selection = [s for s in current_selection if s in options]
        # Lógica de validación si la selección guardada ya no es válida
        if not valid_selection:
            valid_selection = ["– Todos –"] if "– Todos –" in options else ([options[0]] if options and options[0] != "– Todos –" else [])
        return options, valid_selection

    # Usar .get() para seguridad si alguna columna faltara inesperadamente
    lgs_options, valid_lg_default = create_multiselect_options(df_options.get("LG", pd.Series(dtype=str)), SES_LG_FILTER_KEY)
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=valid_lg_default)

    ae_options, valid_ae_default = create_multiselect_options(df_options.get("AE", pd.Series(dtype=str)), SES_AE_FILTER_KEY)
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=valid_ae_default)

    paises_opts, valid_pais_default = create_multiselect_options(df_options.get("País", pd.Series(dtype=str)), SES_PAIS_FILTER_KEY)
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=valid_pais_default)

    # Filtro SQL
    sql_series_for_options = df_options.get("SQL_Estandarizado", pd.Series(dtype=str))
    sqls_unique_vals = sql_series_for_options.astype(str).dropna().unique()
    # Ordenar según importancia y luego alfabéticamente
    sqls_opts_ordered = ["– Todos –"] + [s for s in SQL_ORDER_OF_IMPORTANCE if s in sqls_unique_vals] + sorted([s for s in sqls_unique_vals if s not in SQL_ORDER_OF_IMPORTANCE])
    current_sql_selection = st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"])
    valid_sql_default = [s for s in current_sql_selection if s in sqls_opts_ordered]
    if not valid_sql_default: valid_sql_default = ["– Todos –"] if "– Todos –" in sqls_opts_ordered else ([sqls_opts_ordered[0]] if sqls_opts_ordered and sqls_opts_ordered[0] != "– Todos –" else [])
    st.sidebar.multiselect("Calificación SQL", sqls_opts_ordered, key=SES_SQL_FILTER_KEY, default=valid_sql_default)

    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback, use_container_width=True, key=f"{FILTER_KEYS_PREFIX}btn_clear")

    # Devolver los valores actuales de los filtros en session_state
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], sel_y,
            st.session_state[SES_WEEK_FILTER_KEY], st.session_state[SES_AE_FILTER_KEY],
            st.session_state[SES_LG_FILTER_KEY], st.session_state[SES_PAIS_FILTER_KEY],
            st.session_state[SES_SQL_FILTER_KEY])


def apply_sesiones_filters(df, start_date, end_date, year_f, week_f, ae_f, lg_f, pais_f, sql_f):
    """Aplica los filtros seleccionados al DataFrame."""
    if df is None or df.empty: return pd.DataFrame(columns=COLUMNAS_CENTRALES) # Devuelve estructura vacía
    df_f = df.copy()

    # Filtro Fecha
    if "Fecha" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f["Fecha"]):
        if start_date and end_date:
             # Convertir a datetime para comparación segura si no lo son
            start_dt = pd.to_datetime(start_date).normalize()
            end_dt = pd.to_datetime(end_date).normalize()
            df_f = df_f[(df_f["Fecha"].dt.normalize() >= start_dt) & (df_f["Fecha"].dt.normalize() <= end_dt)]
        elif start_date:
             start_dt = pd.to_datetime(start_date).normalize()
             df_f = df_f[df_f["Fecha"].dt.normalize() >= start_dt]
        elif end_date:
             end_dt = pd.to_datetime(end_date).normalize()
             df_f = df_f[df_f["Fecha"].dt.normalize() <= end_dt]

    # Filtro Año
    if year_f is not None and "Año" in df_f.columns:
         # Asegurarse de comparar tipos iguales (int vs int)
        df_f = df_f[df_f["Año"].astype(int) == year_f]

    # Filtro Semana
    if week_f and "– Todas –" not in week_f and "NumSemana" in df_f.columns:
        # Convertir semanas seleccionadas (que son strings) a int para comparar
        valid_w = [int(w) for w in week_f if w.isdigit()]
        if valid_w:
            # Asegurarse de que la columna NumSemana sea int
            df_f = df_f[df_f["NumSemana"].astype(int).isin(valid_w)]

    # Filtros de Dimensiones (AE, LG, País, SQL) - Comparar como strings
    if ae_f and "– Todos –" not in ae_f and "AE" in df_f.columns:
        df_f = df_f[df_f["AE"].astype(str).isin([str(i) for i in ae_f])]
    if lg_f and "– Todos –" not in lg_f and "LG" in df_f.columns:
        df_f = df_f[df_f["LG"].astype(str).isin([str(i) for i in lg_f])]
    if pais_f and "– Todos –" not in pais_f and "País" in df_f.columns:
        df_f = df_f[df_f["País"].astype(str).isin([str(i) for i in pais_f])]
    if sql_f and "– Todos –" not in sql_f and "SQL_Estandarizado" in df_f.columns:
        df_f = df_f[df_f["SQL_Estandarizado"].astype(str).isin([str(i) for i in sql_f])]

    return df_f

def get_sql_category_order(df_column_or_list):
    """Obtiene el orden deseado para las categorías SQL presentes."""
    present_sqls = pd.Series(df_column_or_list).astype(str).unique()
    ordered_present_sqls = [s for s in SQL_ORDER_OF_IMPORTANCE if s in present_sqls]
    other_sqls = sorted([s for s in present_sqls if s not in ordered_present_sqls])
    return ordered_present_sqls + other_sqls

def display_sesiones_summary_sql(df_filtered):
    """Muestra el resumen total y la distribución por SQL."""
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
        sql_counts = sql_counts.sort_values('Calificación SQL').reset_index(drop=True)

        if not sql_counts.empty:
            fig_sql_summary = px.bar(sql_counts, x='Calificación SQL', y='Número de Sesiones',
                                     title='Sesiones por Calificación SQL', text_auto=True, color='Calificación SQL',
                                     category_orders={"Calificación SQL": category_order_sql_summary})
            fig_sql_summary.update_layout(xaxis={'categoryorder':'array', 'categoryarray':category_order_sql_summary})
            st.plotly_chart(fig_sql_summary, use_container_width=True)

            st.dataframe(sql_counts.set_index('Calificación SQL').style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)
        else:
            st.info("No hay datos de calificación SQL para mostrar.")
    else:
        st.warning("Columna 'SQL_Estandarizado' no encontrada para el resumen.")

def display_analisis_por_dimension(df_filtered, dimension_col, dimension_label, top_n=10):
    """Muestra el análisis agrupado por una dimensión y SQL."""
    st.markdown(f"### 📊 Análisis por {dimension_label} y Calificación SQL (Top {top_n})")
    if df_filtered.empty or dimension_col not in df_filtered.columns or 'SQL_Estandarizado' not in df_filtered.columns:
        st.info(f"Datos insuficientes para análisis por {dimension_label}.")
        return

    # Asegurarse de que la columna de dimensión es string para el group by
    df_filtered[dimension_col] = df_filtered[dimension_col].astype(str)

    # Calcular totales por dimensión para obtener el Top N
    dim_totals = df_filtered[dimension_col].value_counts().head(top_n)
    top_n_dims_list = dim_totals.index.tolist()

    # Filtrar el DataFrame para incluir solo el Top N de la dimensión
    df_top_n = df_filtered[df_filtered[dimension_col].isin(top_n_dims_list)]

    if df_top_n.empty:
        st.info(f"No hay datos para el Top {top_n} de {dimension_label}.")
        return

    # Agrupar por dimensión y SQL (ya filtrado por Top N)
    summary_dim_sql = df_top_n.groupby([dimension_col, 'SQL_Estandarizado'], observed=False).size().reset_index(name='Cantidad_SQL')

    if summary_dim_sql.empty:
        st.info(f"No hay datos agregados por {dimension_label} y SQL para el Top {top_n}.")
        return

    # Ordenar categorías SQL
    sql_category_order_dim_analysis = get_sql_category_order(summary_dim_sql['SQL_Estandarizado'])
    summary_dim_sql['SQL_Estandarizado'] = pd.Categorical(summary_dim_sql['SQL_Estandarizado'], categories=sql_category_order_dim_analysis, ordered=True)

    # Ordenar la dimensión principal según el Top N calculado
    summary_dim_sql[dimension_col] = pd.Categorical(summary_dim_sql[dimension_col], categories=top_n_dims_list, ordered=True)
    summary_dim_sql = summary_dim_sql.sort_values(by=[dimension_col, 'SQL_Estandarizado'])

    # Gráfico de barras apiladas
    fig_dim_analysis = px.bar(summary_dim_sql, x=dimension_col, y='Cantidad_SQL', color='SQL_Estandarizado',
                              title=f'Distribución de SQL por {dimension_label} (Top {top_n})', barmode='stack',
                              category_orders={dimension_col: top_n_dims_list, "SQL_Estandarizado": sql_category_order_dim_analysis},
                              color_discrete_sequence=px.colors.qualitative.Vivid)
    fig_dim_analysis.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Sesiones")
    st.plotly_chart(fig_dim_analysis, use_container_width=True)

    # Tabla Pivot
    try:
        pivot_table_dim = summary_dim_sql.pivot_table(index=dimension_col, columns='SQL_Estandarizado',
                                                    values='Cantidad_SQL', fill_value=0, observed=False)
        # Asegurar que todas las categorías SQL estén presentes y en orden
        pivot_table_dim = pivot_table_dim.reindex(columns=sql_category_order_dim_analysis, fill_value=0)
        # Asegurar que el índice (dimensión) esté ordenado por Top N
        pivot_table_dim = pivot_table_dim.reindex(index=top_n_dims_list, fill_value=0)

        # Calcular total por fila (dimensión)
        pivot_table_dim['Total_Sesiones_Dim'] = pivot_table_dim.sum(axis=1)

        # Formatear números
        format_dict_dim = {col: "{:,.0f}" for col in pivot_table_dim.columns if pd.api.types.is_numeric_dtype(pivot_table_dim[col])}
        st.dataframe(pivot_table_dim.style.format(format_dict_dim), use_container_width=True)
    except Exception as e_pivot:
        st.warning(f"No se pudo generar la tabla pivot para {dimension_label}: {e_pivot}")


def display_evolucion_sql(df_filtered, time_agg_col, display_label, chart_title, x_axis_label):
    """Muestra la evolución temporal por SQL."""
    st.markdown(f"### 📈 {chart_title}")
    if df_filtered.empty or 'SQL_Estandarizado' not in df_filtered.columns or time_agg_col not in df_filtered.columns:
        st.info(f"Datos insuficientes para {chart_title.lower()}. Se requieren 'SQL_Estandarizado' y '{time_agg_col}'.")
        return

    df_agg_evol = df_filtered.copy()

    # Crear columna combinada Año-Semana si es necesario
    group_col_evol = time_agg_col
    sort_col_evol = time_agg_col
    if time_agg_col == 'NumSemana':
        if not ('Año' in df_agg_evol.columns and 'NumSemana' in df_agg_evol.columns):
            st.warning("Faltan Año/NumSemana para evolución semanal.")
            return
        # Convertir a string y asegurar padding para orden correcto
        df_agg_evol['Año-Semana'] = df_agg_evol['Año'].astype(str) + '-S' + df_agg_evol['NumSemana'].astype(str).str.zfill(2)
        group_col_evol = 'Año-Semana'
        sort_col_evol = 'Año-Semana' # Ordenar por esta nueva columna

    df_agg_evol.dropna(subset=[sort_col_evol, 'SQL_Estandarizado'], inplace=True)
    if df_agg_evol.empty:
         st.info(f"No hay datos válidos para '{sort_col_evol}' y 'SQL_Estandarizado' para la evolución.")
         return

    # Agrupar por período de tiempo y SQL
    summary_time_sql_evol = df_agg_evol.groupby([group_col_evol, 'SQL_Estandarizado'], observed=False).size().reset_index(name='Número de Sesiones')

    if summary_time_sql_evol.empty:
        st.info(f"No hay datos agregados por {x_axis_label.lower()} y SQL.")
        return

    # Ordenar categorías SQL
    sql_category_order_evol = get_sql_category_order(summary_time_sql_evol['SQL_Estandarizado'])
    summary_time_sql_evol['SQL_Estandarizado'] = pd.Categorical(summary_time_sql_evol['SQL_Estandarizado'], categories=sql_category_order_evol, ordered=True)

    # Ordenar por período de tiempo y luego por SQL para consistencia
    summary_time_sql_evol = summary_time_sql_evol.sort_values(by=[sort_col_evol, 'SQL_Estandarizado'])

    # Mostrar tabla de datos agregados (opcional)
    # st.dataframe(summary_time_sql_evol.style.format({"Número de Sesiones": "{:,}"}), use_container_width=True)

    # Gráfico de líneas
    try:
        fig_evol_sql = px.line(summary_time_sql_evol, x=group_col_evol, y='Número de Sesiones', color='SQL_Estandarizado',
                               title=f"Evolución por SQL ({x_axis_label})", markers=True,
                               category_orders={"SQL_Estandarizado": sql_category_order_evol})
        # Asegurar que el eje X se trate como categórico y se ordene correctamente
        fig_evol_sql.update_xaxes(type='category') # Tratar eje X como categoría para mantener orden
        fig_evol_sql.update_layout(xaxis_title=x_axis_label)
        st.plotly_chart(fig_evol_sql, use_container_width=True)
    except Exception as e_evol_sql:
        st.warning(f"No se pudo generar gráfico de evolución para {x_axis_label}: {e_evol_sql}")

def display_tabla_sesiones_detalle(df_filtered):
    """Muestra la tabla detallada con columnas seleccionadas."""
    st.markdown("### 📝 Tabla Detallada de Sesiones")
    if df_filtered.empty:
        st.info("No hay sesiones detalladas para mostrar con los filtros aplicados.")
        return

    # Seleccionar columnas CENTRALES específicas para mostrar en la tabla detallada
    cols_display_detalle_ses = [
        "Fecha", "LG", "AE", "País", "SQL", "SQL_Estandarizado", "Empresa",
        "Puesto", "Nombre", "Apellido", "Siguientes Pasos", "RPA", "Fuente_Hoja", "LinkedIn" # Ajusta según necesidad
    ]
    # Filtrar por columnas que realmente existen en el DataFrame (ya debería ser subconjunto de CENTRALES)
    cols_present_detalle_ses = [col for col in cols_display_detalle_ses if col in df_filtered.columns]
    df_view_detalle_ses = df_filtered[cols_present_detalle_ses].copy()

    # Formatear Fecha a dd/mm/yyyy para visualización
    if "Fecha" in df_view_detalle_ses.columns and pd.api.types.is_datetime64_any_dtype(df_view_detalle_ses["Fecha"]):
        df_view_detalle_ses["Fecha"] = df_view_detalle_ses["Fecha"].dt.strftime('%d/%m/%Y')

    st.dataframe(df_view_detalle_ses, height=400, use_container_width=True)

    # Botón de Descarga Excel
    if not df_view_detalle_ses.empty:
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_view_detalle_ses.to_excel(writer, index=False, sheet_name='Detalle_Sesiones')
            output.seek(0) # Mover al inicio del stream
            st.download_button(
                label="⬇️ Descargar Detalle (Excel)", data=output,
                file_name="detalle_sesiones_sql.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{FILTER_KEYS_PREFIX}btn_download_detalle")
        except Exception as e_excel:
            st.error(f"Error al generar archivo Excel: {e_excel}")


# --- Flujo Principal de la Página ---

# Carga los datos, devuelve DataFrame solo con COLUMNAS_CENTRALES
df_sesiones_base = load_sesiones_data()

if df_sesiones_base is None or df_sesiones_base.empty:
    st.error("Fallo Crítico: No se pudieron cargar o procesar datos de Sesiones. La página no puede continuar.")
    st.stop() # Detener ejecución si no hay datos base

# Configura y obtiene filtros del sidebar, usando el DataFrame base para las opciones
start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, sql_f_val = sidebar_filters_sesiones(df_sesiones_base)

# Aplica filtros al DataFrame base
df_sesiones_filtered = apply_sesiones_filters(df_sesiones_base, start_f, end_f, year_f, week_f, ae_f, lg_f, pais_f, sql_f_val)

# Muestra visualizaciones basadas en los datos filtrados (que solo tienen columnas centrales)
display_sesiones_summary_sql(df_sesiones_filtered)
st.markdown("---")
# Las dimensiones usadas aquí son columnas centrales
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
# Las columnas de tiempo usadas aquí son centrales
display_evolucion_sql(df_sesiones_filtered, 'NumSemana', 'Año-Semana', "Evolución Semanal por Calificación SQL", "Semana del Año")
st.markdown("---")
display_evolucion_sql(df_sesiones_filtered, 'AñoMes', 'Año-Mes', "Evolución Mensual por Calificación SQL", "Mes del Año")
st.markdown("---")
# La tabla detallada ahora solo muestra columnas centrales seleccionadas
display_tabla_sesiones_detalle(df_sesiones_filtered)

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
