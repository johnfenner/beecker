# Prospe/datos/carga_datos.py
import pandas as pd
import gspread
import streamlit as st
from collections import Counter
from utils.limpieza import calcular_dias_respuesta 

def cargar_y_limpiar_datos():
    # --- CONEXIÓN A GOOGLE SHEETS (sin cambios) ---
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account]...")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets: {e}")
        st.stop()

    # --- INICIO DE MODIFICACIONES ---

    lista_dataframes = [] # Usaremos una lista para guardar los DataFrames antes de unirlos

    # --- 1. Carga de la Hoja de Prospección Principal (código existente adaptado) ---
    try:
        sheet_url_principal = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        sheet_principal = client.open_by_url(sheet_url_principal).sheet1
        raw_data_principal = sheet_principal.get_all_values()
        
        if raw_data_principal:
            headers_principal = make_unique(raw_data_principal[0])
            df_principal = pd.DataFrame(raw_data_principal[1:], columns=headers_principal)
            lista_dataframes.append(df_principal)
        else:
            st.warning("La hoja de prospección principal está vacía.")

    except Exception as e:
        st.warning(f"No se pudo cargar la hoja de prospección principal: {e}")

    # --- 2. Carga de la Nueva Hoja de la Analista ---
    try:
        # Usamos la nueva clave del archivo de secrets
        sheet_url_analista = st.secrets.get("analista_extra_sheet_url")
        if sheet_url_analista:
            sheet_analista = client.open_by_url(sheet_url_analista).sheet1
            raw_data_analista = sheet_analista.get_all_values()

            if raw_data_analista:
                headers_analista = make_unique(raw_data_analista[0])
                df_analista = pd.DataFrame(raw_data_analista[1:], columns=headers_analista)
                
                # --- 3. NORMALIZACIÓN DE COLUMNAS (El paso más importante) ---
                # Aquí mapeamos los nombres de las columnas de la hoja de la analista
                # a los nombres de columna estándar que usa el dashboard.
                #
                # ¡¡DEBES AJUSTAR ESTE DICCIONARIO!!
                # "Nombre Columna en Hoja Analista": "Nombre Columna Estándar del Dashboard"
                mapa_columnas_analista = {
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
                    # ... añade aquí todas las columnas que correspondan
                }

                df_analista_renamed = df_analista.rename(columns=mapa_columnas_analista)

                # Asignar el nombre de la analista a la columna estándar "¿Quién Prospecto?"
                # ¡¡IMPORTANTE!! Cambia "Nombre De La Analista" por su nombre real.
                df_analista_renamed["¿Quién Prospecto?"] = "Nombre De La Analista" 

                lista_dataframes.append(df_analista_renamed)
            else:
                st.warning("La hoja de la analista extra está vacía.")
    
    except KeyError: # Ocurre si 'analista_extra_sheet_url' no está en los secrets
        st.info("No se encontró URL para la hoja de la analista extra en los secrets. Se omitirá.")
    except Exception as e:
        st.warning(f"No se pudo cargar o procesar la hoja de la analista extra: {e}")

    # --- 4. Consolidación y Limpieza Final (Sobre el DataFrame Unificado) ---
    if not lista_dataframes:
        st.error("No se pudo cargar ninguna fuente de datos. El dashboard no puede continuar.")
        st.stop()

    # Combinamos todos los dataframes (el principal y el de la analista) en uno solo
    df_consolidado = pd.concat(lista_dataframes, ignore_index=True, sort=False)

    if df_consolidado.empty:
        st.warning("El DataFrame consolidado está vacío después de la carga inicial.")
        return pd.DataFrame()

    # El resto del código de limpieza se aplica ahora al DataFrame UNIFICADO,
    # asegurando que ambas fuentes de datos se procesen de la misma manera.
    nombre_columna_fecha_invite = "Fecha de Invite"
    if nombre_columna_fecha_invite not in df_consolidado.columns:
        st.error(f"¡ERROR! La columna '{nombre_columna_fecha_invite}' no se encontró en los datos consolidados.")
        st.info(f"Columnas disponibles: {df_consolidado.columns.tolist()}")
        st.stop()

    df_base = df_consolidado[df_consolidado[nombre_columna_fecha_invite].astype(str).str.strip() != ""].copy()

    if df_base.empty:
        st.warning(f"El DataFrame está vacío después de filtrar por '{nombre_columna_fecha_invite}' no vacía.")
        return pd.DataFrame()

    # Conversión de fechas y limpieza (ahora se aplica a todos los datos)
    df_base[nombre_columna_fecha_invite] = pd.to_datetime(df_base[nombre_columna_fecha_invite], format='%d/%m/%Y', errors="coerce")
    df_base.dropna(subset=[nombre_columna_fecha_invite], inplace=True)
    
    if "Fecha Sesion" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha Sesion"]):
        df_base["Fecha Sesion"] = pd.to_datetime(df_base["Fecha Sesion"], errors='coerce')
    
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
    common_empty_strings = ["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A"]

    for col in columnas_texto_a_limpiar:
        if col in df_base.columns:
            df_base[col] = df_base[col].fillna("").astype(str).str.strip()
            df_base.loc[df_base[col].isin(common_empty_strings) | (df_base[col].str.lower() == 'no'), col] = 'No'

    return df_base

# Función de ayuda para crear cabeceras únicas (sin cambios)
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

def cargar_y_procesar_datos(df): 
    df_procesado = df.copy() 
    try:
        df_procesado = calcular_dias_respuesta(df_procesado)
    except Exception as e:
        st.warning(f"Error al ejecutar calcular_dias_respuesta: {e}")
    return df_procesado
