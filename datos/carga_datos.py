# Prospe/datos/carga_datos.py
import pandas as pd
import gspread
import streamlit as st
from collections import Counter
from utils.limpieza import calcular_dias_respuesta # Asegúrate que esta función esté definida en utils/limpieza.py

def cargar_y_limpiar_datos():
    try:
        # CORRECCIÓN: Usar la sección [gcp_service_account] de tus secretos
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError: # Este error ocurrirá si [gcp_service_account] no está en tus secretos
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account] o alguna de sus claves en los 'Secrets' de Streamlit (Carga Principal).")
        st.error("Asegúrate de haber configurado correctamente tus secretos en Streamlit Cloud con la sección [gcp_service_account] y todos sus campos (type, project_id, private_key, client_email, etc.). Revisa tu archivo TOML de secretos.")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets desde st.secrets (Carga Principal): {e}")
        st.stop()

    try:
        # Usar la clave específica para la URL de esta hoja desde tus secretos
        # Coincide con "main_prostraction_sheet_url" de tu secrets.toml
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        
        sheet = client.open_by_url(sheet_url).sheet1
        raw_data = sheet.get_all_values()
        if not raw_data:
            st.error(f"La hoja de Google Sheets en '{sheet_url}' (Prospección Principal) está vacía o no se pudo leer.")
            st.stop()
        headers = raw_data[0]
        rows = raw_data[1:]
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo de Prospección Principal en la URL: {sheet_url}")
        st.error("Verifica que la URL es correcta y que la cuenta de servicio tiene permisos de acceso.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo de Prospección Principal ('{sheet_url}'): {e}")
        st.info("Verifica la URL de la hoja, los permisos de la cuenta de servicio y la conexión a internet.")
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

    unique_headers = make_unique(headers)
    df = pd.DataFrame(rows, columns=unique_headers)

    if df.empty:
        st.warning("El DataFrame de Prospección Principal está vacío después de la carga inicial.")
        return pd.DataFrame()

    nombre_columna_fecha_invite = "Fecha de Invite"
    if nombre_columna_fecha_invite not in df.columns:
        st.error(f"¡ERROR! La columna '{nombre_columna_fecha_invite}' no se encontró en la hoja de Prospección Principal.")
        st.info(f"Columnas disponibles: {df.columns.tolist()}")
        st.stop()

    df_base = df[df[nombre_columna_fecha_invite].astype(str).str.strip() != ""].copy()

    if df_base.empty:
        st.warning(f"El DataFrame de Prospección Principal está vacío después de filtrar por '{nombre_columna_fecha_invite}' no vacía (versión texto).")
        return pd.DataFrame()

    df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], format='%d/%m/%Y', errors="coerce")
    df_base.dropna(subset=[nombre_columna_fecha_invite], inplace=True)

    if df_base.empty:
        st.warning(f"El DataFrame de Prospección Principal está vacío después de convertir '{nombre_columna_fecha_invite}' a fecha y eliminar NaTs.")
        return pd.DataFrame()

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title() #
        df_base["Avatar"] = df_base["Avatar"].replace({ #
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez", #
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez" #
        })

    columnas_texto_a_limpiar = [ #
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje", #
        "Respuestas Subsecuentes", "Fuente de la Lista", "Proceso", "Pais",  #
        "Industria", "¿Quién Prospecto?", "Nombre", "Apellido", "Empresa", "Puesto" #
    ]
    common_empty_strings = ["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A", "NO", "no"] #

    for col in columnas_texto_a_limpiar: #
        if col in df_base.columns: #
            df_base[col] = df_base[col].fillna("").astype(str).str.strip() #
            # Reemplazar todos los vacíos comunes Y 'no' (minúscula) por "No" (Title Case)
            df_base.loc[df_base[col].isin(common_empty_strings) | (df_base[col].str.lower() == 'no'), col] = 'No' #

    if "Fecha Sesion" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha Sesion"]):
        df_base["Fecha Sesion"] = pd.to_datetime(df_base["Fecha Sesion"], errors='coerce')

    return df_base


def cargar_y_procesar_datos(df): 
    df_procesado = df.copy() 
    try:
        df_procesado = calcular_dias_respuesta(df_procesado) #
    except Exception as e:
        st.warning(f"Error al ejecutar calcular_dias_respuesta: {e}") #
    return df_procesado

