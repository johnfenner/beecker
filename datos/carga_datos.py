# Prospe/datos/carga_datos.py
import pandas as pd
import gspread
import streamlit as st
from collections import Counter
from utils.limpieza import calcular_dias_respuesta

def cargar_y_limpiar_datos():
    """
    Función principal que carga y unifica datos de la hoja del equipo y de Evelyn.
    Mantenemos el nombre original por compatibilidad con el dashboard.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta [gcp_service_account].")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets: {e}")
        st.stop()

    def make_unique(headers_list):
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

    dataframes = []

    # 1. Cargar Hoja Principal (Equipo)
    try:
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        sheet = client.open_by_url(sheet_url).sheet1
        raw_data = sheet.get_all_values()
        if raw_data:
            headers = make_unique(raw_data[0])
            df_main = pd.DataFrame(raw_data[1:], columns=headers)
            df_main['Fuente_Analista'] = 'Equipo Principal'
            dataframes.append(df_main)
    except Exception as e:
        st.warning(f"No se pudo cargar la hoja principal. Error: {e}")

    # 2. Cargar Hoja de Evelyn
    try:
        sheet_url_evelyn = "https://docs.google.com/spreadsheets/d/1eV-wLbzbVRa68Kb-H8UvIvN7VEo5B5ONCOaIQ66mT9Y/edit?gid=0#gid=0"
        sheet_evelyn = client.open_by_url(sheet_url_evelyn).sheet1
        raw_data_evelyn = sheet_evelyn.get_all_values()
        if raw_data_evelyn:
            headers_evelyn = make_unique(raw_data_evelyn[0])
            df_evelyn = pd.DataFrame(raw_data_evelyn[1:], columns=headers_evelyn)
            df_evelyn['Fuente_Analista'] = 'Evelyn'
            if '¿Quién Prospecto?' not in df_evelyn.columns or df_evelyn['¿Quién Prospecto?'].isnull().all():
                 df_evelyn['¿Quién Prospecto?'] = 'Evelyn'
            else:
                 df_evelyn['¿Quién Prospecto?'].fillna('Evelyn', inplace=True)
            dataframes.append(df_evelyn)
    except Exception as e:
        st.warning(f"No se pudo cargar la hoja de Evelyn. Error: {e}")

    if not dataframes:
        st.error("No se pudieron cargar datos de ninguna fuente. El dashboard no puede continuar.")
        st.stop()
    
    df_unificado = pd.concat(dataframes, ignore_index=True, sort=False)

    nombre_columna_fecha_invite = "Fecha de Invite"
    if nombre_columna_fecha_invite not in df_unificado.columns:
        st.error(f"¡ERROR CRÍTICO! La columna '{nombre_columna_fecha_invite}' es esencial y no se encontró.")
        st.stop()

    df_base = df_unificado[df_unificado[nombre_columna_fecha_invite].astype(str).str.strip() != ""].copy()
    if df_base.empty:
        st.warning("El DataFrame está vacío después de filtrar por fechas de invite válidas.")
        return pd.DataFrame()

    df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], format='%d/%m/%Y', errors="coerce")
    df_base.dropna(subset=[nombre_columna_fecha_invite], inplace=True)

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title()
        df_base["Avatar"] = df_base["Avatar"].replace({
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"
        })

    columnas_texto_a_limpiar = [
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje",
        "Respuestas Subsecuentes", "Fuente de la Lista", "Proceso", "Pais",
        "Industria", "¿Quién Prospecto?", "Nombre", "Apellido", "Empresa", "Puesto"
    ]
    common_empty_strings = ["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A", "NO", "no"]

    for col in columnas_texto_a_limpiar:
        if col in df_base.columns:
            df_base[col] = df_base[col].fillna("").astype(str).str.strip()
            df_base.loc[df_base[col].isin(common_empty_strings) | (df_base[col].str.lower() == 'no'), col] = 'No'

    if "Fecha Sesion" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha Sesion"]):
        df_base["Fecha Sesion"] = pd.to_datetime(df_base["Fecha Sesion"], errors='coerce')

    return df_base


def cargar_y_procesar_datos(df): 
    df_procesado = df.copy() 
    try:
        df_procesado = calcular_dias_respuesta(df_procesado)
    except Exception as e:
        st.warning(f"Error al ejecutar calcular_dias_respuesta: {e}")
    return df_procesado
