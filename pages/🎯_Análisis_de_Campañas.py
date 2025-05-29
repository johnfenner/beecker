# pages/🎯_Análisis_de_Campañas.py

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

    nombre_columna_fecha_invite = "Fecha de Invite" # Crucial para definir prospectos manuales
    # No pararemos si "Fecha de Invite" no existe, ya que campañas puede operar sin ella para métricas de email
    # Pero sí es necesaria para las métricas de prospección "manual".

    # Hacemos una copia antes de filtrar por Fecha de Invite para asegurar que todos los datos (incluyendo campañas sin fecha de invite) se procesen
    df_base = df.copy()

    # Limpieza de fechas principales y de campaña
    if nombre_columna_fecha_invite in df_base.columns:
        # Convertir a texto primero para manejar formatos mixtos antes de pd.to_datetime
        df_base[nombre_columna_fecha_invite] = df_base[nombre_columna_fecha_invite].astype(str).str.strip()
        df_base.loc[df_base[nombre_columna_fecha_invite] == '', nombre_columna_fecha_invite] = pd.NaT
        df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], format='%d/%m/%Y', errors="coerce")
        # No se hace dropna aquí para mantener todas las filas para el análisis de campaña general

    if "Fecha Sesion" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha Sesion"]):
        df_base["Fecha Sesion"] = pd.to_datetime(df_base["Fecha Sesion"], errors='coerce')
    
    # NUEVO: Procesar "Fecha de Sesion Email"
    if "Fecha de Sesion Email" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha de Sesion Email"]):
        df_base["Fecha de Sesion Email"] = pd.to_datetime(df_base["Fecha de Sesion Email"], errors='coerce')

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].astype(str).str.strip().str.title()
        df_base["Avatar"] = df_base["Avatar"].replace({
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"
        })

    columnas_texto_a_limpiar = [
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje",
        "Respuestas Subsecuentes", "Fuente de la Lista", "Proceso", "Pais", 
        "Industria", "¿Quién Prospecto?", "Nombre", "Apellido", "Empresa", "Puesto",
        "Campaña", # <--- NUEVA COLUMNA A LIMPIAR
        "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email" # <--- NUEVAS COLUMNAS A LIMPIAR
    ]
    common_empty_strings = ["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A", "NO", "no"] # "NO", "no" se convierten a "No" (Title)

    for col in columnas_texto_a_limpiar:
        if col in df_base.columns:
            df_base[col] = df_base[col].fillna("").astype(str).str.strip()
            # Reemplazar todos los vacíos comunes por "No" (Title Case) solo si la columna no es "Campaña" u otra que no sea binaria "si/no"
            # Para "Campaña", queremos mantener los nombres tal cual, solo limpiar espacios.
            # Para las nuevas columnas de email, asumimos que "si/no" es el comportamiento deseado para `limpiar_valor_kpi`
            if col not in ["Campaña", "Nombre", "Apellido", "Empresa", "Puesto", "Industria", "Pais", "Proceso", "Fuente de la Lista", "¿Quién Prospecto?"]: # Columnas que no deberían ser "No" por defecto si están vacías
                 df_base.loc[df_base[col].isin(common_empty_strings) | (df_base[col].str.lower() == 'no'), col] = 'No'
                 df_base.loc[df_base[col].str.lower() == 'si', col] = 'Si' # Estandarizar a "Si"
            elif col == "Campaña": # Solo limpiar y dejar vacíos como están, o reemplazar por "N/D" (No Definida)
                 df_base.loc[df_base[col].isin(common_empty_strings), col] = 'N/D' # O dejar como "" si se prefiere
            else: # Para otras columnas de texto como Nombre, Empresa, etc.
                 df_base.loc[df_base[col].isin(common_empty_strings), col] = '' # Dejar como string vacío si es un NA común

    # Asegurar que columnas clave para conteos existan, si no, crearlas vacías o con valor por defecto.
    # Esto es importante para que las agrupaciones y sumas no fallen más adelante.
    key_metric_cols = ["¿Invite Aceptada?", "Respuesta Primer Mensaje", "Sesion Agendada?",
                       "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email", "Campaña"]
    for kmc in key_metric_cols:
        if kmc not in df_base.columns:
            if kmc == "Campaña":
                df_base[kmc] = "N/D" # Default para agrupaciones
            else: # Columnas de "si/no"
                df_base[kmc] = "No" # Default para conteos booleanos
    
    # Convertir "Fecha de Invite" a datetime después de la limpieza inicial si aún no lo es (ya se hizo arriba, pero como reaseguro)
    if nombre_columna_fecha_invite in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base[nombre_columna_fecha_invite]):
        df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], errors='coerce')

    return df_base


def cargar_y_procesar_datos(df): 
    df_procesado = df.copy() 
    # Si 'calcular_dias_respuesta' es relevante para la nueva página, asegúrate que las columnas
    # de fecha que usa (ej. 'Fecha Primer Mensaje') estén disponibles o adapta la función.
    # Por ahora, la mantenemos como estaba.
    try:
        df_procesado = calcular_dias_respuesta(df_procesado)
    except Exception as e:
        st.warning(f"Error al ejecutar calcular_dias_respuesta: {e}")
    return df_procesado