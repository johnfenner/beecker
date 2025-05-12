import pandas as pd
import gspread
import streamlit as st # Importar streamlit para st.secrets, st.error, st.stop
from oauth2client.service_account import ServiceAccountCredentials
from collections import Counter
# Asegúrate de que estas funciones de limpieza estén disponibles en utils.limpieza
# Es posible que necesites importar st en utils/limpieza.py si esas funciones lo usan.
from utils.limpieza import calcular_dias_respuesta, estandarizar_avatar # Asumo que estas siguen siendo relevantes

def cargar_y_limpiar_datos():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    # --- Cargar credenciales desde Streamlit Secrets ---
    try:
        creds_dict = {
            "type": st.secrets["google_sheets_credentials"]["type"],
            "project_id": st.secrets["google_sheets_credentials"]["project_id"],
            "private_key_id": st.secrets["google_sheets_credentials"]["private_key_id"],
            "private_key": st.secrets["google_sheets_credentials"]["private_key"], # Asume comillas triples en TOML para private_key
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

    except KeyError as e: # Específicamente para claves faltantes en los secrets
        st.error(f"Error: Falta la clave '{e}' en los 'Secrets' de Streamlit. Verifica la configuración de secrets en Streamlit Cloud.")
        st.info("Asegúrate de haber configurado una sección [google_sheets_credentials] con todas las claves necesarias como se muestra en la documentación o ejemplos.")
        st.stop()
    except Exception as e: # Para cualquier otro error al cargar credenciales
        st.error(f"Error al autenticar con Google Sheets usando Streamlit Secrets: {e}")
        st.info("Verifica la configuración de tus 'Secrets' en Streamlit Community Cloud y los permisos de tu cuenta de servicio.")
        st.stop()
    # --- Fin de la carga de credenciales ---

    # Abrir hoja por URL
    # Opcional: Leer la URL de la hoja desde secrets también para mayor flexibilidad
    main_sheet_url = st.secrets.get(
        "MAIN_SHEET_URL", # Nombre del secret si lo defines
        "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0" # Valor por defecto
    )

    try:
        sheet = client.open_by_url(main_sheet_url).sheet1
        raw_data = sheet.get_all_values()
        if not raw_data: # Verificar si raw_data está vacío
            st.error("No se encontraron datos en la hoja de Google Sheets. La hoja podría estar completamente vacía.")
            return pd.DataFrame() # Retornar DataFrame vacío para evitar más errores
        
        headers_list = raw_data[0]
        rows = raw_data[1:]

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo en la URL proporcionada: {main_sheet_url}")
        st.info("Verifica que la URL es correcta y que la cuenta de servicio tiene permisos para acceder a ella.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo '{main_sheet_url}': {e}")
        st.info("Verifica la URL, los permisos de la cuenta de servicio y la conexión a internet.")
        st.stop()

    def make_unique(headers_input): # Renombrada la variable para evitar conflicto
        counts = Counter()
        new_headers = []
        for h_item in headers_input: # Renombrada la variable para evitar conflicto
            h_stripped = h_item.strip()
            counts[h_stripped] += 1
            if counts[h_stripped] == 1:
                new_headers.append(h_stripped)
            else:
                new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
        return new_headers

    headers = make_unique(headers_list) # Usar la variable correcta
    df = pd.DataFrame(rows, columns=headers)

    nombre_columna_fecha_invite = "Fecha de Invite"
    if nombre_columna_fecha_invite not in df.columns:
        st.error(f"¡ERROR! La columna '{nombre_columna_fecha_invite}' no se encontró. Columnas disponibles: {df.columns.tolist()}")
        st.info("Por favor, verifica el nombre de la columna de la fecha de invitación en tu Google Sheet.")
        return pd.DataFrame() # Retornar DataFrame vacío

    df_base = df[df[nombre_columna_fecha_invite].astype(str).str.strip() != ""].copy()

    if df_base.empty:
        st.warning(f"El DataFrame base está vacío después de filtrar por '{nombre_columna_fecha_invite}' no vacía. Verifica los datos en esa columna.")
        # No necesariamente detener, podría no haber datos que cumplan el criterio.
        # Se retornará un df_base vacío que las funciones posteriores deben manejar.

    df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], format='%d/%m/%Y', errors="coerce")
    # df_base.dropna(subset=[nombre_columna_fecha_invite], inplace=True) # Opcional: eliminar filas donde la fecha no se pudo convertir

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title()
        df_base["Avatar"] = df_base["Avatar"].replace({
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"
        })

    columnas_a_limpiar = [
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje",
        "Respuestas Subsecuentes", "Fecha Sesion",
    ]
    columnas_a_limpiar_filtrada = [col for col in columnas_a_limpiar if col != nombre_columna_fecha_invite]

    for col in columnas_a_limpiar_filtrada:
        if col in df_base.columns:
            df_base[col] = df_base[col].fillna("No").replace(r'^\s*$', "No", regex=True)

    return df_base


def cargar_y_procesar_datos(df): # df aquí es df_base
    if df.empty: # Si df_base estaba vacío, no hay nada que procesar
        return df
    try:
        # La función calcular_dias_respuesta no se usa activamente en el dashboard principal según los últimos cambios
        # Si la necesitas para otras páginas o análisis, asegúrate que esté bien implementada.
        # df = calcular_dias_respuesta(df) 
        pass # Por ahora, esta función no hace mucho más si calcular_dias_respuesta no se usa.
    except Exception as e:
        st.warning(f"Error al ejecutar procesamiento adicional de datos: {e}")
    return df
