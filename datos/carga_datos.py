# Prospe/datos/carga_datos.py
import pandas as pd
import gspread
import streamlit as st
from collections import Counter
from utils.limpieza import calcular_dias_respuesta

def make_unique(headers_list):
    """Crea encabezados únicos para un DataFrame para evitar columnas duplicadas."""
    counts = Counter()
    new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped: h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1:
            new_headers.append(h_stripped)
        else:
            new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

def limpiar_y_estandarizar_df(df, fuente_analista, mapeo_columnas):
    """
    Limpia y estandariza un DataFrame individual antes de la unificación.
    """
    if df.empty:
        return pd.DataFrame()

    # 1. Renombrar columnas según el mapeo
    df_renombrado = df.rename(columns=mapeo_columnas)

    # 2. Filtrar por fecha de invite y convertir a datetime
    col_fecha_invite = "Fecha de Invite"
    if col_fecha_invite not in df_renombrado.columns:
        st.error(f"¡ERROR Crítico! La columna '{col_fecha_invite}' no se encontró en la hoja de '{fuente_analista}' después del mapeo.")
        return pd.DataFrame()

    df_base = df_renombrado[df_renombrado[col_fecha_invite].astype(str).str.strip() != ""].copy()
    if df_base.empty:
        return pd.DataFrame()

    df_base[col_fecha_invite] = pd.to_datetime(df_base[col_fecha_invite], format='%d/%m/%Y', errors="coerce")
    df_base.dropna(subset=[col_fecha_invite], inplace=True)

    # 3. Añadir columna de fuente y estandarizar Prospectador/Avatar
    df_base['Fuente_Analista'] = fuente_analista
    
    if '¿Quién Prospecto?' not in df_base.columns or df_base['¿Quién Prospecto?'].isnull().all():
        df_base['¿Quién Prospecto?'] = fuente_analista
    
    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title()
        df_base["Avatar"] = df_base["Avatar"].replace({
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez",
            # Añade aquí mapeos para la nueva analista si es necesario
            "Evelyn": "Evelyn" 
        })
    else:
        df_base['Avatar'] = fuente_analista # Asignar por defecto si no existe

    return df_base


@st.cache_data(ttl=600)
def cargar_y_unificar_sheets():
    """
    Carga datos de la hoja principal y de la hoja de la nueva analista (Evelyn),
    las limpia, estandariza columnas y las unifica en un solo DataFrame.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets desde st.secrets: {e}")
        st.stop()

    dataframes = []

    # --- Definición de Mapeos de Columnas ---
    # No es necesario un mapeo para la hoja principal si sus nombres ya son el estándar
    mapeo_principal = {} 

    # Mapeo para la hoja de la nueva analista.
    # La clave es el nombre de la columna en la hoja de Evelyn,
    # el valor es el nombre estándar que usa el resto de tu app.
    mapeo_evelyn = {
        # 'Sesion Agendada?_1': 'Sesion Agendada? (Alterna 1)', # Ejemplo de cómo manejar duplicados si fuera necesario
        # 'Sesion Agendada?_2': 'Sesion Agendada? (Alterna 2)',
    }
    
    # 1. Cargar Hoja Principal
    try:
        sheet_url_main = st.secrets.get("main_prostraction_sheet_url")
        if sheet_url_main:
            sheet_main = client.open_by_url(sheet_url_main).sheet1
            raw_data_main = sheet_main.get_all_values()
            if raw_data_main:
                unique_headers_main = make_unique(raw_data_main[0])
                df_main = pd.DataFrame(raw_data_main[1:], columns=unique_headers_main)
                df_main_cleaned = limpiar_y_estandarizar_df(df_main, "Equipo Principal", mapeo_principal)
                dataframes.append(df_main_cleaned)
    except Exception as e:
        st.warning(f"No se pudo cargar o procesar la hoja de Prospección Principal. Error: {e}")

    # 2. Cargar Hoja de la Nueva Analista (Evelyn)
    try:
        sheet_url_analyst = st.secrets.get("analyst_sheet_url")
        if sheet_url_analyst:
            sheet_analyst = client.open_by_url(sheet_url_analyst).sheet1
            raw_data_analyst = sheet_analyst.get_all_values()
            if raw_data_analyst:
                unique_headers_analyst = make_unique(raw_data_analyst[0])
                df_analyst = pd.DataFrame(raw_data_analyst[1:], columns=unique_headers_analyst)
                df_analyst_cleaned = limpiar_y_estandarizar_df(df_analyst, "Evelyn", mapeo_evelyn)
                dataframes.append(df_analyst_cleaned)
    except Exception as e:
        st.warning(f"No se pudo cargar o procesar la hoja de la analista Evelyn. Error: {e}")

    if not dataframes:
        st.error("No se pudo cargar ningún dato de ninguna hoja de Google Sheets. El dashboard no puede continuar.")
        st.stop()
        
    # 3. Unificar DataFrames
    df_consolidado = pd.concat(dataframes, ignore_index=True, sort=False)
    
    # 4. Limpieza Final y Procesamiento
    # Asegurarse de que todas las columnas importantes existan
    columnas_finales_estandar = [
        "Fuente de la Lista", "Proceso", "Campaña", "Pais", "Empresa", "Industria",
        "Nombre", "Apellido", "Puesto", "Category", "LinkedIn", "¿Quién Prospecto?",
        "Avatar", "Fecha de Invite", "¿Invite Aceptada?", "Fecha Primer Mensaje",
        "Respuesta Primer Mensaje", "Respuestas Subsecuentes", "Sesion Agendada?",
        "Fecha Sesion", "Email", "Notas"
    ]
    for col in columnas_finales_estandar:
        if col not in df_consolidado.columns:
            df_consolidado[col] = pd.NA

    # Limpieza final de strings
    for col in df_consolidado.select_dtypes(include=['object']).columns:
        df_consolidado[col] = df_consolidado[col].fillna("").astype(str).str.strip()

    # Procesamientos adicionales
    df_final = calcular_dias_respuesta(df_consolidado)

    return df_final


# --- Funciones Legacy (se mantienen por compatibilidad) ---
def cargar_y_limpiar_datos():
    """Wrapper para mantener la compatibilidad con el dashboard principal."""
    return cargar_y_unificar_sheets()
    
def cargar_y_procesar_datos(df): 
    """Esta función ahora solo es un paso a través."""
    return df
