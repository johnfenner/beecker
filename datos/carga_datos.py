# Prospe/datos/carga_datos.py
import pandas as pd
import gspread
import streamlit as st
from collections import Counter
from utils.limpieza import calcular_dias_respuesta 

# =================================================================
# === TU FUNCIÓN ORIGINAL - ESTA NO SE TOCA ===
# =================================================================
def cargar_y_limpiar_datos():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account]...")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets desde st.secrets (Carga Principal): {e}")
        st.stop()

    try:
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        sheet = client.open_by_url(sheet_url).sheet1
        raw_data = sheet.get_all_values()
        if not raw_data:
            st.error(f"La hoja de Google Sheets en '{sheet_url}' (Prospección Principal) está vacía o no se pudo leer.")
            st.stop()
        headers = raw_data[0]
        rows = raw_data[1:]
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo de Prospección Principal ('{sheet_url}'): {e}")
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
        return pd.DataFrame()

    df_base = df[df["Fecha de Invite"].astype(str).str.strip() != ""].copy()

    if df_base.empty:
        return pd.DataFrame()

    df_base["Fecha de Invite"] = pd.to_datetime(df_base["Fecha de Invite"], format='%d/%m/%Y', errors="coerce")
    df_base.dropna(subset=["Fecha de Invite"], inplace=True)

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title()
        df_base["Avatar"] = df_base["Avatar"].replace({"Jonh Fenner": "John Bermúdez", "Jonh": "John Bermúdez"})

    columnas_texto_a_limpiar = [
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje",
        "Respuestas Subsecuentes", "Fuente de la Lista", "Proceso", "Pais", 
        "Industria", "¿Quién Prospecto?", "Nombre", "Apellido", "Empresa", "Puesto"
    ]
    for col in columnas_texto_a_limpiar:
        if col in df_base.columns:
            df_base.loc[df_base[col].isin(["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A", "NO", "no"]), col] = 'No'

    if "Fecha Sesion" in df_base.columns:
        df_base["Fecha Sesion"] = pd.to_datetime(df_base["Fecha Sesion"], errors='coerce')

    return df_base


def cargar_y_procesar_datos(df): 
    df_procesado = df.copy() 
    try:
        df_procesado = calcular_dias_respuesta(df_procesado)
    except Exception as e:
        st.warning(f"Error al ejecutar calcular_dias_respuesta: {e}")
    return df_procesado

# =================================================================
# === NUEVA FUNCIÓN PARA EVELYN - AÑADIR ESTO AL FINAL DEL ARCHIVO ===
# =================================================================
@st.cache_data
def cargar_y_limpiar_datos_evelyn():
    """Carga y normaliza los datos específicamente de la hoja de Evelyn."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Error de credenciales al cargar hoja de Evelyn: {e}")
        return pd.DataFrame()

    try:
        sheet_url_analista = st.secrets["analista_extra_sheet_url"]
        sheet_analista = client.open_by_url(sheet_url_analista).sheet1
        raw_data_analista = sheet_analista.get_all_values()

        if len(raw_data_analista) > 1:
            headers_analista = make_unique_evelyn(raw_data_analista[0])
            df_analista = pd.DataFrame(raw_data_analista[1:], columns=headers_analista)
            
            # --- ¡¡AJUSTA ESTE MAPEO DE COLUMNAS!! ---
            mapa_columnas = {
                "Fecha de Contacto": "Fecha de Invite",
                "Empresa Contactada": "Empresa",
                "País": "Pais",
                "Nombre del Prospecto": "Nombre",
                "Apellido del Prospecto": "Apellido",
                "Cargo": "Puesto",
                "Invitación Aceptada (Si/No)": "¿Invite Aceptada?",
                "Respondió Mensaje (Si/No)": "Respuesta Primer Mensaje",
                "Agendó Sesión (Si/No)": "Sesion Agendada?",
                "Fecha de la Sesión Agendada": "Fecha Sesion",
                "Link a Perfil": "LinkedIn",
                "Fuente": "Fuente de la Lista",
                "Tipo de Proceso": "Proceso",
                "Avatar Usado": "Avatar"
            }
            df_analista_renamed = df_analista.rename(columns=mapa_columnas)
            
            # Asignar valores por defecto para columnas que puedan faltar
            if "¿Quién Prospecto?" not in df_analista_renamed.columns:
                df_analista_renamed["¿Quién Prospecto?"] = "Evelyn"

            # Limpieza similar a la función original
            df_analista_renamed = df_analista_renamed[pd.to_datetime(df_analista_renamed["Fecha de Invite"], errors='coerce').notna()].copy()
            df_analista_renamed["Fecha de Invite"] = pd.to_datetime(df_analista_renamed["Fecha de Invite"], errors='coerce')

            return df_analista_renamed
        else:
            return pd.DataFrame()
            
    except Exception as e:
        st.warning(f"No se pudo cargar o procesar la hoja de Evelyn. Error: {e}")
        return pd.DataFrame()

def make_unique_evelyn(headers_list): # Una versión de make_unique para esta función
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
