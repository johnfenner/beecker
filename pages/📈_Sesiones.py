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
# (Tu bloque try-except para project_root se mantiene)
try:
    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), os.pardir))
    if project_root not in sys.path: # Evitar añadirlo si ya está por el script principal
        sys.path.insert(0, project_root)
except NameError: # Manejar si __file__ no está definido (ej. en algunos notebooks)
    project_root = os.getcwd()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

st.set_page_config(layout="wide", page_title="Análisis de Sesiones y SQL")
st.title("📊 Análisis de Sesiones y Calificaciones SQL")
st.markdown(
    "Métricas por LG, AE, País, Calificación SQL (SQL1 > SQL2 > MQL > NA > Sin Calificación), Puesto y Empresa."
)

# --- Constantes ---
# CREDS_PATH ya no se usará directamente en load_sesiones_data para el despliegue online
# CREDS_PATH = "credenciales.json" # Lo mantenemos por si ejecutas localmente sin secrets configurados
SHEET_URL_SESIONES_DEFAULT = "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902" # Tu URL original
SHEET_NAME_SESIONES = "Sesiones 2024-2025" # Tu nombre de pestaña original

# NUEVAS CONSTANTES PARA LA HOJA DE SURAMÉRICA (con tus valores)
SHEET_URL_SESIONES_SURAMERICA_DEFAULT = "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854"
SHEET_NAME_SESIONES_SURAMERICA = "BD Sesiones 2024"


COLUMNAS_ESPERADAS = [ # Estas son las columnas que tu código original espera después del procesamiento
    "Semana", "Mes", "Fecha", "SQL", "Empresa", "País", "Nombre", "Apellido",
    "Puesto", "Email", "AE", "LG", "Siguientes Pasos", "RPA"
]
COLUMNAS_DERIVADAS = [ # Estas son las que tu código original deriva
    'Año', 'NumSemana', 'MesNombre', 'AñoMes', 'SQL_Estandarizado'
]
# Esta será la estructura final objetivo después de unir y procesar ambas hojas
COLUMNAS_FINALES_UNIFICADAS = list(set(COLUMNAS_ESPERADAS + COLUMNAS_DERIVADAS + ["Fuente_Hoja", "LinkedIn"]))


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
def parse_date_robust(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "": return None
    # Ampliar los formatos que se intentan, incluyendo aquellos con hora
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", 
                "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", 
                "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"): 
        try:
            return pd.to_datetime(date_val, format=fmt)
        except (ValueError, TypeError):
            continue
    try: # Último intento sin formato específico, útil para formatos ISO estándar
        return pd.to_datetime(date_val, errors='coerce')
    except Exception:
        return None

def separar_nombre_cargo_suramerica(nombre_cargo_str):
    # (Tu función original, o la versión mejorada que te pasé antes. Pego la mejorada)
    nombre = pd.NA
    apellido = pd.NA
    puesto = "No Especificado"
    
    if pd.isna(nombre_cargo_str) or not isinstance(nombre_cargo_str, str) or not nombre_cargo_str.strip():
        return nombre, apellido, puesto

    nombre_cargo_str = nombre_cargo_str.strip()
    # Delimitadores comunes entre nombre y cargo. El orden importa si pueden coexistir.
    delimiters_cargo = [' - ', ' / ', ', ', ' – '] # Delimitadores más probables para cargo
    
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

    if not name_parts: # Si después de quitar el cargo, la parte del nombre está vacía
        return pd.NA, pd.NA, puesto

    if len(name_parts) == 1:
        nombre = name_parts[0]
    elif len(name_parts) == 2:
        nombre = name_parts[0]
        apellido = name_parts[1]
    elif len(name_parts) == 3:
        nombre = name_parts[0]
        apellido = f"{name_parts[1]} {name_parts[2]}" # Común: Nombre ApellidoPaterno ApellidoMaterno
    elif len(name_parts) >= 4: # Nombres compuestos y/o apellidos compuestos
        nombre = f"{name_parts[0]} {name_parts[1]}" # Asumir nombre compuesto
        apellido = " ".join(name_parts[2:]) # Resto como apellido(s)
        # Si no se encontró cargo y aún sobran palabras tras un nombre y un apellido simple, tomar como cargo
        if not cargo_encontrado_explicitamente and len(name_parts) > 2:
            # Re-evaluar si hay un cargo implícito
            temp_nombre_simple = name_parts[0]
            temp_apellido_simple = name_parts[1]
            temp_cargo_implicito = " ".join(name_parts[2:])
            if len(temp_cargo_implicito) > 2: # Evitar tomar una inicial como cargo
                 nombre = temp_nombre_simple
                 apellido = temp_apellido_simple
                 puesto = temp_cargo_implicito
                 cargo_encontrado_explicitamente = True # Considerarlo encontrado

    # Si el puesto sigue siendo "No Especificado" y el apellido es muy largo, puede contener el puesto
    if puesto == "No Especificado" and apellido and len(str(apellido).split()) > 2 and not cargo_encontrado_explicitamente:
        apellido_parts = str(apellido).split()
        apellido = apellido_parts[0] # Tomar solo la primera palabra como apellido principal
        puesto = " ".join(apellido_parts[1:])

    return (
        str(nombre).strip() if pd.notna(nombre) else pd.NA,
        str(apellido).strip() if pd.notna(apellido) else pd.NA,
        str(puesto).strip() if pd.notna(puesto) and puesto else "No Especificado"
    )

@st.cache_data(ttl=300)
def load_sesiones_data():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # --- INICIO DEL CAMBIO: Cargar credenciales desde Streamlit Secrets ---
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
    # --- FIN DEL CAMBIO ---

    all_dataframes = []
    df_final_structure = pd.DataFrame(columns=COLUMNAS_FINALES_UNIFICADAS)


    # --- Cargar Hoja Principal de Sesiones ---
    sheet_url_principal_actual = st.secrets.get("SESIONES_SHEET_URL", SHEET_URL_SESIONES_DEFAULT)
    try:
        workbook_principal = client.open_by_url(sheet_url_principal_actual)
        sheet_principal = workbook_principal.worksheet(SHEET_NAME_SESIONES) # Usando tu constante original
        
        # Usar get_all_values() y procesar encabezados como en tu código original
        raw_data_principal = sheet_principal.get_all_values()
        if raw_data_principal and len(raw_data_principal) > 1:
            headers_principal_cleaned = [str(h).strip() for h in raw_data_principal[0]]
            final_df_headers_principal = [h for h in headers_principal_cleaned if h] # Tu lógica original
            
            num_effective_headers_principal = len(final_df_headers_principal)
            data_rows_principal = [row[:num_effective_headers_principal] for row in raw_data_principal[1:]]
            
            df_principal = pd.DataFrame(data_rows_principal, columns=final_df_headers_principal)
            df_principal["Fuente_Hoja"] = "Principal"
            all_dataframes.append(df_principal)
        else:
            st.warning(f"Hoja Principal de Sesiones ('{SHEET_NAME_SESIONES}') vacía o solo con encabezados.")
    except Exception as e:
        st.error(f"Error al cargar la Hoja Principal de Sesiones: {e}")

    # --- Cargar Hoja de Sesiones de Suramérica ---
    sheet_url_suramerica_actual = st.secrets.get("SESIONES_SURAMERICA_SHEET_URL", SHEET_URL_SESIONES_SURAMERICA_DEFAULT)
    try:
        workbook_suramerica = client.open_by_url(sheet_url_suramerica_actual)
        sheet_suramerica = workbook_suramerica.worksheet(SHEET_NAME_SESIONES_SURAMERICA)
        
        raw_data_suramerica = sheet_suramerica.get_all_values() # Usar get_all_values como en tu original para consistencia
        if raw_data_suramerica and len(raw_data_suramerica) > 1:
            headers_suramerica_cleaned = [str(h).strip() for h in raw_data_suramerica[0]]
            final_df_headers_suramerica = [h for h in headers_suramerica_cleaned if h] # Tu lógica original

            num_effective_headers_suramerica = len(final_df_headers_suramerica)
            data_rows_suramerica = [row[:num_effective_headers_suramerica] for row in raw_data_suramerica[1:]]
            
            df_suramerica_temp = pd.DataFrame(data_rows_suramerica, columns=final_df_headers_suramerica)
            
            # Mapeo y transformación para Suramérica
            df_suramerica_processed = pd.DataFrame()
            df_suramerica_processed["Fecha"] = df_suramerica_temp["Fecha"].apply(parse_date_robust) if "Fecha" in df_suramerica_temp.columns else pd.NaT
            df_suramerica_processed["Empresa"] = df_suramerica_temp.get("Empresa")
            df_suramerica_processed["País"] = df_suramerica_temp.get("País")
            df_suramerica_processed["Siguientes Pasos"] = df_suramerica_temp.get("Siguientes Pasos")
            df_suramerica_processed["SQL"] = df_suramerica_temp.get("SQL")
            df_suramerica_processed["Email"] = df_suramerica_temp.get("Correo") 
            df_suramerica_processed["LinkedIn"] = df_suramerica_temp.get("LinkedIn")
            
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
            st.warning(f"Hoja de Sesiones de Suramérica ('{SHEET_NAME_SESIONES_SURAMERICA}') vacía o solo con encabezados.")
    except Exception as e:
        st.error(f"Error al cargar la Hoja de Sesiones de Suramérica: {e}")

    if not all_dataframes:
        st.error("No se pudieron cargar datos de ninguna hoja de Sesiones.")
        return df_final_structure

    df_consolidado = pd.concat(all_dataframes, ignore_index=True, sort=False)
        
    # --- Limpieza y Derivación Final sobre el DataFrame Consolidado ---
    # (Tu lógica original de procesamiento de df_consolidado a df_final)
    # Esta parte se mantiene como en tu código original, ya que el objetivo era solo cambiar la autenticación
    # y la carga inicial de las hojas.
    
    df_final = df_consolidado.copy() # Renombrar a df_final para coincidir con tu código original
    
    # Asegurar que 'Fecha' sea datetime y eliminar filas sin fecha válida (importante después de concat)
    if "Fecha" in df_final.columns:
        df_final["Fecha"] = pd.to_datetime(df_final["Fecha"], errors='coerce')
        df_final.dropna(subset=["Fecha"], inplace=True)
    else:
        st.error("Columna 'Fecha' perdida después de la consolidación. No se puede continuar.")
        return df_final_structure # Retorna estructura vacía si no hay fecha

    if df_final.empty:
        st.warning("No hay sesiones con fechas válidas después de la consolidación y procesamiento.")
        return df_final_structure # Retorna estructura vacía

    df_final['Año'] = df_final['Fecha'].dt.year.astype('Int64')
    df_final['NumSemana'] = df_final['Fecha'].dt.isocalendar().week.astype('Int64')
    df_final['MesNombre'] = df_final['Fecha'].dt.month_name()
    df_final['AñoMes'] = df_final['Fecha'].dt.strftime('%Y-%m')

    if "SQL" not in df_final.columns: df_final["SQL"] = "" # Crear si no existe
    df_final["SQL"] = df_final["SQL"].fillna("") # Llenar NaNs antes de .astype(str)
    df_final['SQL_Estandarizado'] = df_final['SQL'].astype(str).str.strip().str.upper()
    known_sql_values = [s for s in SQL_ORDER_OF_IMPORTANCE if s != 'SIN CALIFICACIÓN SQL']
    mask_empty_sql = ~df_final['SQL_Estandarizado'].isin(known_sql_values) & \
                     (df_final['SQL_Estandarizado'].isin(['', 'NAN', 'NONE', 'NA']) | df_final['SQL_Estandarizado'].isna()) # NA por si acaso
    df_final.loc[mask_empty_sql, 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'
    df_final.loc[df_final['SQL_Estandarizado'] == '', 'SQL_Estandarizado'] = 'SIN CALIFICACIÓN SQL'

    for col_actor, default_actor_name in [("AE", "No Asignado AE"), ("LG", "No Asignado LG")]:
        if col_actor not in df_final.columns: df_final[col_actor] = default_actor_name
        df_final[col_actor] = df_final[col_actor].fillna(default_actor_name).astype(str).str.strip()
        df_final.loc[df_final[col_actor].isin(['', 'nan', 'none', 'NaN', 'None', 'NA', pd.NA]), col_actor] = default_actor_name

    for col_clean in ["Puesto", "Empresa", "País", "Nombre", "Apellido", "Siguientes Pasos", "Email", "RPA", "LinkedIn"]:
        default_clean_val = "No Especificado"
        if col_clean not in df_final.columns: df_final[col_clean] = default_clean_val
        df_final[col_clean] = df_final[col_clean].fillna(default_clean_val).astype(str).str.strip()
        df_final.loc[df_final[col_clean].isin(['', 'nan', 'none', 'NaN', 'None', 'NA', pd.NA]), col_clean] = default_clean_val
        if col_clean == "Puesto" and df_final[col_clean].str.strip().eq("").any():
            df_final.loc[df_final[col_clean].str.strip().eq(""), col_clean] = "No Especificado"

    # Recrear df_final con solo las columnas esperadas y derivadas finales
    # Esto es similar a tu bloque original "df_final = pd.DataFrame()" y el bucle para llenar all_final_cols
    # pero aplicado después de toda la consolidación y procesamiento.
    df_to_return = pd.DataFrame()
    for col in COLUMNAS_FINALES_UNIFICADAS:
        if col in df_final.columns:
            df_to_return[col] = df_final[col]
        else:
            # Si alguna columna de COLUMNAS_FINALES_UNIFICADAS no existe en df_final, créala vacía o con default
            # st.warning(f"Columna final '{col}' no generada, se creará vacía/default.")
            if col in ['Año', 'NumSemana']: df_to_return[col] = pd.Series(dtype='Int64')
            elif col == 'Fecha': df_to_return[col] = pd.Series(dtype='datetime64[ns]')
            elif col in COLUMNAS_ESPERADAS: df_to_return[col] = "No Especificado" # Default para columnas esperadas faltantes
            else: df_to_return[col] = pd.NA # Para columnas derivadas que no se pudieron calcular
            
    return df_to_return


# --- El resto de tus funciones (clear_ses_filters_callback, sidebar_filters_sesiones, etc.) y Flujo Principal se mantienen igual ---
# --- (Tu código original para estas funciones y el flujo principal) ---
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
    
    # Tu lógica de validación de selección para semanas, LG, AE, País, SQL se mantiene
    # Ejemplo para semanas (aplicar lógica similar de validación a los otros multiselects si es necesario)
    current_week_selection = st.session_state.get(SES_WEEK_FILTER_KEY, ["– Todas –"])
    valid_week_selection = [val for val in current_week_selection if val in weeks]
    if not valid_week_selection:
        valid_week_selection = ["– Todas –"] if "– Todas –" in weeks else ([weeks[0]] if weeks and weeks[0] != "– Todas –" else [])
    st.sidebar.multiselect("Semanas", weeks, key=SES_WEEK_FILTER_KEY, default=valid_week_selection)

    st.sidebar.markdown("---")
    st.sidebar.subheader("👥 Por Analistas, País y Calificación")
    
    lgs_options = ["– Todos –"] + (sorted(df_options["LG"].dropna().unique()) if "LG" in df_options and not df_options["LG"].dropna().empty else [])
    st.sidebar.multiselect("Analista LG", lgs_options, key=SES_LG_FILTER_KEY, default=st.session_state.get(SES_LG_FILTER_KEY, ["– Todos –"]))
    
    ae_options = ["– Todos –"] + (sorted(df_options["AE"].dropna().unique()) if "AE" in df_options and not df_options["AE"].dropna().empty else [])
    st.sidebar.multiselect("Account Executive (AE)", ae_options, key=SES_AE_FILTER_KEY, default=st.session_state.get(SES_AE_FILTER_KEY, ["– Todos –"]))
    
    paises_opts = ["– Todos –"] + (sorted(df_options["País"].dropna().unique()) if "País" in df_options and not df_options["País"].dropna().empty else [])
    st.sidebar.multiselect("País", paises_opts, key=SES_PAIS_FILTER_KEY, default=st.session_state.get(SES_PAIS_FILTER_KEY, ["– Todos –"]))
    
    sqls_opts = ["– Todos –"] + (sorted(df_options["SQL_Estandarizado"].dropna().unique(), key=lambda x: SQL_ORDER_OF_IMPORTANCE.index(x) if x in SQL_ORDER_OF_IMPORTANCE else len(SQL_ORDER_OF_IMPORTANCE)) if "SQL_Estandarizado" in df_options and not df_options["SQL_Estandarizado"].dropna().empty else [])
    st.sidebar.multiselect("Calificación SQL", sqls_opts, key=SES_SQL_FILTER_KEY, default=st.session_state.get(SES_SQL_FILTER_KEY, ["– Todos –"]))

    st.sidebar.markdown("---")
    st.sidebar.button("🧹 Limpiar Todos los Filtros", on_click=clear_ses_filters_callback, use_container_width=True, key=f"{FILTER_KEYS_PREFIX}btn_clear_sesiones_final")
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
    if ae_f and "– Todos –" not in ae_f and "AE" in df_f.columns: df_f = df_f[df_f["AE"].isin(ae_f)]
    if lg_f and "– Todos –" not in lg_f and "LG" in df_f.columns: df_f = df_f[df_f["LG"].isin(lg_f)]
    if pais_f and "– Todos –" not in pais_f and "País" in df_f.columns: df_f = df_f[df_f["País"].isin(pais_f)]
    if sql_f and "– Todos –" not in sql_f and "SQL_Estandarizado" in df_f.columns: df_f = df_f[df_f["SQL_Estandarizado"].isin(sql_f)]
    return df_f

def get_sql_category_order(df_column_or_list):
    present_sqls = pd.Series(df_column_or_list).unique()
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
    summary_dim_sql = df_filtered.groupby([dimension_col, 'SQL_Estandarizado'], as_index=False, observed=False)['Fecha'].count().rename(columns={'Fecha': 'Cantidad_SQL'}) # observed=False puede ser más seguro
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
        df_agg_evol['Año-Semana'] = df_agg_evol['Año'].astype(str) + '-S' + df_agg_evol['NumSemana'].astype(str).str.zfill(2) # Asegurar que Año sea string
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
            key=f"{FILTER_KEYS_PREFIX}btn_download_detalle_sesiones_final")

# --- Flujo Principal de la Página ---
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
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
