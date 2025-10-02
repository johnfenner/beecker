# Archivo: datos/carga_datos.py

import pandas as pd
import gspread
import streamlit as st
from collections import Counter
from utils.limpieza import calcular_dias_respuesta

# -----------------------------------------------------------------------------
# ESTA ES LA NUEVA FUNCIÓN "MAESTRA" QUE CARGARÁ TODO
# -----------------------------------------------------------------------------
@st.cache_data(ttl=600)  # Guarda los datos en caché por 10 minutos
def cargar_todas_las_fuentes():
    """
    Carga todas las hojas de Google Sheets necesarias para la aplicación una sola vez.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Error fatal al autenticar con Google Sheets: {e}")
        return None # Devuelve None si falla la autenticación

    # Un diccionario para guardar todos nuestros DataFrames
    fuentes_de_datos = {
        "principal": cargar_y_limpiar_datos(client), # Llama a tu función original
        "kpis_semanales": cargar_hoja_individual(client, st.secrets["kpis_sheet_url"]),
        "kpis_sdr": cargar_hoja_individual(client, st.secrets["main_prostraction_sheet_url"], "KPI´s SDR"),
        "sesiones_principal": cargar_hoja_individual(client, "https://docs.google.com/spreadsheets/d/1Cejc7xfxd62qqsbzBOMRSI9HiJjHe_JSFnjf3lrXai4/edit?gid=1354854902#gid=1354854902", "Sesiones 2024-2025"),
        "sesiones_suramerica": cargar_hoja_individual(client, "https://docs.google.com/spreadsheets/d/1MoTUg0sZ76168k4VNajzyrxAa5hUHdWNtGNu9t0Nqnc/edit?gid=278542854#gid=278542854", "SesionesSA 2024-2025"),
        "email_stats": cargar_hoja_individual(client, st.secrets["email_stats_sheet_url"])
    }

    return fuentes_de_datos

# -----------------------------------------------------------------------------
# FUNCIÓN AUXILIAR PARA NO REPETIR CÓDIGO (NO LA TIENES QUE USAR DIRECTAMENTE)
# -----------------------------------------------------------------------------
def cargar_hoja_individual(client, url, nombre_hoja=None):
    try:
        workbook = client.open_by_url(url)
        sheet = workbook.worksheet(nombre_hoja) if nombre_hoja else workbook.sheet1
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 2:
            st.warning(f"Hoja en {url} está vacía o no tiene datos.")
            return pd.DataFrame()

        headers = make_unique(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)
        return df
    except Exception as e:
        st.warning(f"No se pudo cargar la hoja desde {url}. Error: {e}")
        return pd.DataFrame()

# -----------------------------------------------------------------------------
# TU FUNCIÓN ORIGINAL (MODIFICADA LIGERAMENTE PARA QUE ACEPTE EL "CLIENTE")
# -----------------------------------------------------------------------------
def cargar_y_limpiar_datos(client): # Añadimos "client" como argumento
    """
    Función que carga y unifica datos de la hoja principal del equipo.
    """
    # La autenticación ya no se hace aquí, se recibe el cliente ya autenticado.

    df_main = cargar_hoja_individual(client, st.secrets["main_prostraction_sheet_url"]) # Usamos la nueva función auxiliar

    if df_main.empty:
        st.error("No se pudo cargar la hoja principal. El dashboard no puede continuar.")
        st.stop()
    
    # El resto de tu lógica de limpieza es idéntico
    df_unificado = df_main # Como ya no cargas la de Evelyn, solo hay una.
    df_unificado['Fuente_Analista'] = 'Equipo Principal'

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
