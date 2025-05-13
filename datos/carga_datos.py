# Prospe/datos/carga_datos.py
import pandas as pd
import gspread
import streamlit as st
# from oauth2client.service_account import ServiceAccountCredentials # Ya no es necesario con st.secrets y gspread >= 5.0
from collections import Counter
from utils.limpieza import calcular_dias_respuesta

def cargar_y_limpiar_datos():
    try:
        # Usar st.secrets para las credenciales de Google Sheets
        # gspread >= 5.0.0 usa service_account_from_dict
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error: No se encontró la configuración 'gcp_service_account' en los secretos de Streamlit.")
        st.error("Asegúrate de haber configurado correctamente tus secretos en Streamlit Cloud con la sección [gcp_service_account] y todos sus campos.")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets desde st.secrets: {e}")
        st.stop()

    # Abrir hoja. Puedes poner la URL en st.secrets también si lo deseas.
    try:
        # Para usar una URL desde los secretos (recomendado para producción):
        # sheet_url = st.secrets.get("google_sheets_url", "URL_POR_DEFECTO_SI_NO_LA_ENCUENTRA_EN_SECRETS")
        # Si no está en secretos, usa la URL hardcodeada como fallback o principal:
        sheet_url = st.secrets.get("google_sheets_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")

        sheet = client.open_by_url(sheet_url).sheet1
        raw_data = sheet.get_all_values()
        if not raw_data:
            st.error(f"La hoja de Google Sheets en '{sheet_url}' está vacía o no se pudo leer.")
            st.stop()
        headers = raw_data[0]
        rows = raw_data[1:]
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo en la URL: {sheet_url}")
        st.error("Verifica que la URL es correcta y que la cuenta de servicio tiene permisos de acceso.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo de Google Sheets ('{sheet_url}'): {e}")
        st.info("Verifica la URL de la hoja, los permisos de la cuenta de servicio y la conexión a internet.")
        st.stop()

    def make_unique(headers_list):
        counts = Counter()
        new_headers = []
        for h in headers_list:
            h_stripped = h.strip() if isinstance(h, str) else str(h)
            counts[h_stripped] += 1
            if counts[h_stripped] == 1:
                new_headers.append(h_stripped)
            else:
                new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
        return new_headers

    unique_headers = make_unique(headers)
    df = pd.DataFrame(rows, columns=unique_headers)

    if df.empty:
        st.warning("El DataFrame está vacío después de la carga inicial desde Google Sheets.")
        return pd.DataFrame()

    nombre_columna_fecha_invite = "Fecha de Invite"
    if nombre_columna_fecha_invite not in df.columns:
        st.error(f"¡ERROR! La columna '{nombre_columna_fecha_invite}' no se encontró.")
        st.info(f"Columnas disponibles: {df.columns.tolist()}")
        st.stop()

    df_base = df[df[nombre_columna_fecha_invite].astype(str).str.strip() != ""].copy()

    if df_base.empty:
        st.warning(f"El DataFrame está vacío después de filtrar por '{nombre_columna_fecha_invite}' no vacía (versión texto).")
        return pd.DataFrame()

    df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], format='%d/%m/%Y', errors="coerce")
    df_base.dropna(subset=[nombre_columna_fecha_invite], inplace=True)

    if df_base.empty:
        st.warning(f"El DataFrame está vacío después de convertir '{nombre_columna_fecha_invite}' a fecha y eliminar NaTs.")
        return pd.DataFrame()

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title()
        # La estandarización más detallada de Avatar se hará después con la función estandarizar_avatar
        df_base["Avatar"] = df_base["Avatar"].replace({
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"
        })


    columnas_texto_a_limpiar = [
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje",
        "Respuestas Subsecuentes",
        "Fuente de la Lista", "Proceso", "Pais", "Industria", "¿Quién Prospecto?",
        "Nombre", "Apellido", "Empresa", "Puesto"
    ]
    common_empty_strings = ["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A", "NO", "no"]

    for col in columnas_texto_a_limpiar:
        if col in df_base.columns:
            df_base[col] = df_base[col].fillna("").astype(str).str.strip()
            # Reemplazar todos los vacíos comunes por "No" (Title Case)
            df_base.loc[df_base[col].isin(common_empty_strings) | (df_base[col].str.lower() == 'no'), col] = 'No'


    # Limpieza final para asegurar que "No" sea consistente si algunos eran "no"
    # for col in ["¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje"]:
    #    if col in df_base.columns:
    #        df_base.loc[df_base[col].str.lower() == 'no', col] = 'No'

    # Aquí no forzamos 'category' o 'string[pyarrow]' para mantenerlo como lo tenías antes de las optimizaciones de velocidad.
    # Si alguna conversión específica a 'category' funcionaba bien y la quieres, puedes añadirla aquí.
    # Ejemplo:
    # if "¿Invite Aceptada?" in df_base.columns:
    #     df_base["¿Invite Aceptada?"] = df_base["¿Invite Aceptada?"].astype('category')


    if "Fecha Sesion" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha Sesion"]):
        df_base["Fecha Sesion"] = pd.to_datetime(df_base["Fecha Sesion"], errors='coerce')

    return df_base


def cargar_y_procesar_datos(df): # df es df_base
    df_procesado = df.copy() # Trabajar con una copia
    try:
        df_procesado = calcular_dias_respuesta(df_procesado)
    except Exception as e:
        st.warning(f"Error al ejecutar calcular_dias_respuesta: {e}")
    return df_procesado
