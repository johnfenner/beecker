# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import re
import numpy as np
import io

# --- Configuración y Constantes ---
st.set_page_config(layout="wide", page_title="Pipeline Prospección")
st.title("📈 Pipeline de Prospección (Datos Validados)")
st.markdown("Análisis del embudo basado en la hoja 'Prospects'.")

# Clave del secret de Streamlit donde guardaste la URL
# Asegúrate de tener esta clave en tus secrets de Streamlit
PIPELINE_SHEET_URL_KEY = "pipeline_sheet_url_oct_2025"
# URL por defecto (la que me diste) si el secret no se encuentra
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/1MYj_43IFIzrg8tQxG9LUfT6-V0O3lg8TuQUveWhEVAM/edit?gid=971436223#gid=971436223"
PIPELINE_SHEET_NAME = "Prospects" # Nombre exacto de la pestaña

# Nombres EXACTOS de columnas clave de tu hoja
COL_LEAD_GEN_DATE = "Lead Generated (Date)"
COL_FIRST_CONTACT_DATE = "First Contact Date"
COL_MEETING_DATE = "Meeting Date"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"
COL_CONTACTED = "Contacted?" # Columna de tu muestra

# Claves de Sesión (prefijo único para esta página)
SES_PREFIX = "pipe_v3_" # Incrementamos versión por si acaso
SES_START_DATE_KEY = f"{SES_PREFIX}start_date"
SES_END_DATE_KEY = f"{SES_PREFIX}end_date"
SES_INDUSTRY_KEY = f"{SES_PREFIX}industry"
SES_MANAGEMENT_KEY = f"{SES_PREFIX}management"
SES_MEETING_KEY = f"{SES_PREFIX}meeting"

# --- Funciones de Utilidad (Ajustadas) ---

@st.cache_data(ttl=300)
def parse_date_optimized(date_input):
    """
    Parsea fechas de forma robusta, priorizando D/M/YYYY y DD/M/YYYY.
    También maneja números de serie de Excel y otros formatos comunes.
    Ignora valores booleanos (TRUE/FALSE) que no son fechas.
    """
    if pd.isna(date_input): return pd.NaT
    # Ignorar si es directamente un booleano
    if isinstance(date_input, (bool, np.bool_)): return pd.NaT

    # Si ya es fecha/hora, normalizarla
    if isinstance(date_input, (datetime.datetime, datetime.date)):
        try:
             dt = pd.to_datetime(date_input)
             # Quitar información de zona horaria si existe
             if dt.tzinfo is not None: dt = dt.tz_localize(None)
             # Devolver solo la fecha (sin hora)
             return dt.normalize()
        except Exception:
             # Si falla la conversión directa (raro), intentar parsear como string
             pass

    date_str = str(date_input).strip()
    if not date_str: return pd.NaT
    # Ignorar si el string es 'true' o 'false' (case-insensitive)
    if date_str.lower() in ['true', 'false']: return pd.NaT

    # *** PRIORIDAD: Formatos D/M/YYYY y DD/M/YYYY ***
    formats_to_try = ["%d/%m/%Y", "%m/%d/%Y", # Más comunes primero
                      "%d-%m-%Y", "%m-%d-%Y",
                      "%Y-%m-%d", # ISO format
                      # Formatos con hora (tomará solo la fecha)
                      "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M",
                      "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M",
                      "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"]

    for fmt in formats_to_try:
        try:
            # Intentar parsear solo la parte de la fecha si hay hora
            date_part = date_str.split(' ')[0]
            parsed = pd.to_datetime(date_part, format=fmt, errors='raise')
            if pd.notna(parsed): return parsed.normalize()
        except (ValueError, TypeError):
            continue # Probar el siguiente formato

    # Intentar con número de serie de Excel (si es un número)
    if re.fullmatch(r'\d+(\.\d+)?', date_str):
        try:
             excel_date_num = float(date_str)
             # Rango típico para fechas en Excel
             if 30000 < excel_date_num < 60000:
                 origin = pd.Timestamp('1899-12-30')
                 parsed_excel = origin + pd.to_timedelta(excel_date_num, unit='D')
                 # Validar que la fecha resultante sea razonable
                 if pd.Timestamp('1980-01-01') <= parsed_excel <= pd.Timestamp('2050-12-31'):
                      return parsed_excel.normalize()
        except Exception:
            pass # Ignorar si la conversión falla

    # Último recurso: Dejar que Pandas intente adivinar (menos fiable)
    try:
        # Probar día primero
        parsed_generic_d = pd.to_datetime(date_str, errors='coerce', dayfirst=True)
        if pd.notna(parsed_generic_d): return parsed_generic_d.normalize()
        # Probar mes primero
        parsed_generic_m = pd.to_datetime(date_str, errors='coerce', dayfirst=False)
        if pd.notna(parsed_generic_m): return parsed_generic_m.normalize()
    except Exception:
        return pd.NaT # Falló todo

    return pd.NaT # No se pudo parsear

@st.cache_data
def clean_yes_no_optimized(val):
    """
    Limpia valores booleanos y strings (TRUE/FALSE, Yes/No, etc.) a 'Si' o 'No'.
    Maneja específicamente 'TRUE' y 'FALSE' como strings.
    """
    # Manejar booleanos nativos de Python/Numpy
    if isinstance(val, (bool, np.bool_)):
        return "Si" if val else "No"

    # Convertir a string y limpiar
    cleaned = str(val).strip().lower()

    # Mapear valores afirmativos
    affirmative_values = ['yes', 'sí', 'si', '1', 'true', 'verdadero', 'agendada', 'ok', 'realizada']
    if cleaned in affirmative_values:
        return "Si"

    # Mapear valores negativos explícitos (aunque el default es 'No')
    # negative_values = ['no', '0', 'false', 'falso']
    # if cleaned in negative_values:
    #    return "No"

    # Cualquier otra cosa (incluyendo '', 'nan', '0', 'false', etc.) se considera "No"
    return "No"

@st.cache_data
def calculate_rate(numerator, denominator, round_to=1):
    """Calcula una tasa como porcentaje, manejando ceros y NaNs."""
    # Convertir a numérico, forzando errores a NaN
    num = pd.to_numeric(numerator, errors='coerce')
    den = pd.to_numeric(denominator, errors='coerce')

    # Si denominador es NaN, 0, o numerador es NaN, la tasa es 0
    if pd.isna(den) or den == 0 or pd.isna(num):
        return 0.0

    rate = (num / den) * 100

    # Manejar casos de infinito o NaN resultantes de la división
    if np.isinf(rate) or np.isnan(rate):
        return 0.0

    return round(rate, round_to)

@st.cache_data
def calculate_time_diff(date1, date2):
    """Calcula la diferencia en días entre dos fechas."""
    d1 = pd.to_datetime(date1, errors='coerce')
    d2 = pd.to_datetime(date2, errors='coerce')
    # Solo calcular si ambas fechas son válidas y d2 es igual o posterior a d1
    if pd.notna(d1) and pd.notna(d2) and d2 >= d1:
        return (d2 - d1).days
    return np.nan # Devolver NaN si no se puede calcular

def make_unique_headers(headers_list):
    """Asegura que los nombres de las columnas sean únicos."""
    counts = Counter(); new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped: h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1: new_headers.append(h_stripped)
        else: new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

# --- Carga y Procesamiento de Datos ---
@st.cache_data(ttl=300) # Cachear por 5 minutos
def load_and_process_data():
    """
    Carga datos desde Google Sheets usando gspread y los procesa.
    Utiliza parseo optimizado de fechas y limpieza de booleanos.
    """
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    processing_warnings = []

    try:
        # Usar las credenciales de la cuenta de servicio desde secrets
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
        # Usar 'UNFORMATTED_VALUE' es importante para fechas como números
        # Usar 'FORMATTED_VALUE' puede ser mejor si las fechas SIEMPRE están como texto D/M/YYYY
        # Probemos con FORMATED_VALUE primero, dado tu formato D/M/YYYY
        all_data_loaded = sheet.get_all_values(value_render_option='FORMATTED_VALUE')

        if not all_data_loaded or len(all_data_loaded) <= 1:
            raise ValueError(f"La hoja '{PIPELINE_SHEET_NAME}' está vacía o solo contiene encabezados.")

        headers = make_unique_headers(all_data_loaded[0])
        df = pd.DataFrame(all_data_loaded[1:], columns=headers)

    except gspread.exceptions.APIError as e:
         # Manejar error específico si la hoja sigue siendo .xlsx
         if "This operation is not supported for this document" in str(e):
             st.error("❌ Error: El archivo en la URL parece ser un archivo Excel (.xlsx).")
             st.warning("Debes 'Guardar como Hoja de Google' en Google Drive, compartir esa *nueva* hoja y actualizar la URL en los secrets de Streamlit.")
             st.stop()
         else:
             st.error(f"❌ Error de API de Google al acceder a la hoja: {e}")
             st.info(f"Verifica la URL, el nombre de la pestaña ('{PIPELINE_SHEET_NAME}') y asegúrate de que la cuenta de servicio ({creds.get('client_email', 'No encontrado')}) tenga permisos de LECTOR en la Hoja de Google.")
             st.stop()
    except Exception as e:
        st.error(f"❌ Error crítico al cargar datos desde Google Sheets: {e}")
        st.info(f"Verifica la URL en secrets ('{PIPELINE_SHEET_URL_KEY}'), el nombre de la pestaña ('{PIPELINE_SHEET_NAME}') y los permisos.")
        st.stop()

    # --- Procesamiento Post-Carga ---

    # Verificar columnas esenciales para el embudo
    essential_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, COL_CONTACTED]
    missing_essentials = [col for col in essential_cols if col not in df.columns]
    if missing_essentials:
        st.error(f"Faltan columnas esenciales para el análisis del embudo: {', '.join(missing_essentials)}. Verifica los nombres exactos en la hoja '{PIPELINE_SHEET_NAME}'.")
        # Crear columnas faltantes con Nulos para evitar errores posteriores
        for col in missing_essentials: df[col] = pd.NA

    # --- Parseo de Fechas (MUY IMPORTANTE) ---
    date_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]
    date_parse_fail_counts = {col: 0 for col in date_cols}
    for col in date_cols:
        if col in df.columns:
            # Contar cuántos no eran nulos/vacíos antes de parsear
            original_non_empty = df[col].apply(lambda x: pd.notna(x) and str(x).strip() != "" and str(x).lower() not in ['true', 'false'])
            count_before = original_non_empty.sum()

            # Aplicar el parseo optimizado
            df[col] = df[col].apply(parse_date_optimized)

            # Contar cuántos son NaT *después* de parsear, pero *eran* no vacíos antes
            failed_to_parse = df[col].isna() & original_non_empty
            date_parse_fail_counts[col] = failed_to_parse.sum()
        else:
            df[col] = pd.NaT # Asegurar que la columna exista como tipo fecha si no estaba

    # Usar COL_LEAD_GEN_DATE como la fecha principal para filtros y agregaciones
    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True)
    initial_rows = len(df)
    # Eliminar filas donde la fecha principal no se pudo parsear (crítico)
    df.dropna(subset=['Fecha_Principal'], inplace=True)
    rows_dropped_no_lead_date = initial_rows - len(df)

    # Añadir advertencias sobre el parseo de fechas
    if rows_dropped_no_lead_date > 0:
        processing_warnings.append(f"⚠️ **{rows_dropped_no_lead_date:,} filas eliminadas** porque la columna '{COL_LEAD_GEN_DATE}' estaba vacía o no se pudo interpretar como fecha.")
    for col, count in date_parse_fail_counts.items():
        if count > 0 :
             processing_warnings.append(f"⚠️ {count} valores en la columna '{col}' no pudieron ser interpretados como fecha y ahora son Nulos.")

    # Guardar advertencias para mostrarlas después
    st.session_state['data_load_warnings'] = processing_warnings

    # --- Limpieza de Columnas de Estado (Booleanas/Texto como TRUE/FALSE) ---
    status_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in status_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no_optimized)
        else:
            df[col] = "No" # Asumir 'No' si la columna falta

    # --- Creación de KPI derivado: 'FirstContactStatus' ---
    # Usamos la FECHA de primer contacto como indicador de si se contactó
    if COL_FIRST_CONTACT_DATE in df.columns:
        df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No')
    else:
        # Si no existe la columna de fecha de contacto, no podemos saberlo
        df['FirstContactStatus'] = 'No' # O podríamos poner 'Desconocido'

    # --- Limpieza de Columnas Categóricas (Dimensiones) ---
    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('No Definido') # Rellenar nulos
            # Convertir a string, quitar espacios, poner Título y reemplazar vacíos
            df[col] = df[col].astype(str).str.strip().str.title().replace('', 'No Definido')
            # Limpiar valores comunes que significan "no definido"
            common_na_strings = {'N/A': 'No Definido', 'Na': 'No Definido', 'N/D': 'No Definido',
                                 '-': 'No Definido', 'False': 'No Definido', 'True': 'No Definido'}
            df[col] = df[col].replace(common_na_strings)
        else:
            df[col] = "No Definido" # Crear columna si no existe

    # --- Creación de Columnas de Tiempo para Agregación Temporal ---
    # Solo si hay datos y la 'Fecha_Principal' es de tipo datetime
    if not df.empty and 'Fecha_Principal' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Fecha_Principal']):
        try:
            df['Año'] = df['Fecha_Principal'].dt.year.astype('Int64') # Usar Int64 para permitir nulos
            # Usar isocalendar() para semana ISO
            df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64')
            df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m') # Formato AAAA-MM
        except Exception as e:
            st.warning(f"Error al crear columnas de tiempo (Año, Semana, AñoMes): {e}")
            for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA
    else:
        # Crear columnas como NA si no se pueden calcular
        for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA

    # --- Cálculo de KPIs de Tiempo (Lags en días) ---
    df['Dias_Gen_a_Contacto'] = df.apply(
        lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_FIRST_CONTACT_DATE)), axis=1
    )
    df['Dias_Contacto_a_Reunion'] = df.apply(
        lambda row: calculate_time_diff(row.get(COL_FIRST_CONTACT_DATE), row.get(COL_MEETING_DATE)), axis=1
    )
    df['Dias_Gen_a_Reunion'] = df.apply(
        lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_MEETING_DATE)), axis=1
    )

    return df

# --- Filtros (Sin cambios grandes, solo ajustes menores) ---
def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")

    default_filters = {
        SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
        SES_INDUSTRY_KEY: ["– Todos –"], SES_MANAGEMENT_KEY: ["– Todos –"],
        SES_MEETING_KEY: "– Todos –"
    }
    for key, val in default_filters.items():
        if key not in st.session_state: st.session_state[key] = val

    st.sidebar.subheader("🗓️ Por Fecha de Lead Generado")
    min_date, max_date = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        try:
            min_date = df_options["Fecha_Principal"].min().date()
            max_date = df_options["Fecha_Principal"].max().date()
        except Exception as e:
            st.sidebar.warning(f"No se pudieron determinar las fechas min/max: {e}")

    c1, c2 = st.sidebar.columns(2)
    # Usar el valor del session_state como default para los date_input
    c1.date_input("Desde", value=st.session_state[SES_START_DATE_KEY], key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", value=st.session_state[SES_END_DATE_KEY], key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

    st.sidebar.subheader("👥 Por Atributo de Lead")

    def create_multiselect(col_name, label, key):
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            # Ordenar valores únicos, asegurando que "No Definido" vaya al final
            unique_vals = sorted([v for v in df_options[col_name].astype(str).unique() if v != 'No Definido'])
            options.extend(unique_vals)
            if 'No Definido' in df_options[col_name].astype(str).unique():
                options.append('No Definido')

        current_state = st.session_state.get(key, ["– Todos –"])
        # Filtrar el estado actual para mantener solo opciones válidas
        valid_state = [s for s in current_state if s in options]
        # Si el estado filtrado está vacío o no contenía nada válido, resetear a Todos
        if not valid_state or (len(valid_state) == 1 and valid_state[0] not in options):
             valid_state = ["– Todos –"]

        # Actualizar el estado de sesión ANTES de renderizar el widget
        st.session_state[key] = valid_state

        # Renderizar usando el estado de sesión actualizado como default
        st.sidebar.multiselect(label, options, key=f"widget_{key}", default=valid_state) # Usar una key diferente para el widget si da problemas

    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)

    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)

    def clear_pipeline_filters():
        for key, val in default_filters.items(): st.session_state[key] = val
        st.toast("Filtros reiniciados ✅", icon="🧹")

    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_pipeline_filters, use_container_width=True)

    # Devolver los valores directamente del estado de sesión
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY],
            st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY],
            st.session_state[SES_MEETING_KEY])


# --- Aplicar Filtros (Sin cambios) ---
def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    df_f = df.copy()
    if df_f.empty: return df_f

    # Fecha
    if "Fecha_Principal" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f['Fecha_Principal']):
        start_dt_norm = pd.to_datetime(start_dt).normalize() if start_dt else None
        end_dt_norm = pd.to_datetime(end_dt).normalize() if end_dt else None

        mask = pd.Series(True, index=df_f.index)
        valid_dates_mask = df_f['Fecha_Principal'].notna()

        if start_dt_norm: mask &= (df_f['Fecha_Principal'] >= start_dt_norm) & valid_dates_mask
        if end_dt_norm: mask &= (df_f['Fecha_Principal'] <= end_dt_norm) & valid_dates_mask
        df_f = df_f[mask]

    # Categóricos
    if industries and "– Todos –" not in industries and COL_INDUSTRY in df_f.columns:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
    if managements and "– Todos –" not in managements and COL_MANAGEMENT in df_f.columns:
        df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]
    if meeting_status != "– Todos –" and COL_MEETING in df_f.columns:
        df_f = df_f[df_f[COL_MEETING] == meeting_status]

    return df_f

# --- Componentes de Visualización (Sin cambios estructurales) ---
# ... (Las funciones display_enhanced_funnel, display_time_lag_analysis,
#      display_segmentation_analysis, display_channel_analysis,
#      display_enhanced_time_evolution permanecen igual que en el código anterior)

# --- Pegar aquí las 5 funciones de visualización del código anterior ---
# display_enhanced_funnel(df_filtered)
# display_time_lag_analysis(df_filtered)
# display_segmentation_analysis(df_filtered)
# display_channel_analysis(df_filtered)
# display_enhanced_time_evolution(df_filtered)

def display_enhanced_funnel(df_filtered):
    """Muestra un embudo de conversión detallado."""
    st.markdown("###  funnel Embudo de Conversión Detallado")
    st.caption("Muestra cuántos leads avanzan en cada etapa clave del proceso.")

    if df_filtered.empty:
        st.info("No hay datos filtrados para mostrar el embudo.")
        return

    # Definición de las etapas del embudo
    total_leads = len(df_filtered)
    # Etapa 2: Primer Contacto (basado en 'FirstContactStatus' derivado de la fecha)
    total_first_contact = len(df_filtered[df_filtered['FirstContactStatus'] == "Si"])
    # Etapa 3: Respuesta Recibida
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    # Etapa 4: Reunión Agendada
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])

    funnel_stages = ["Total Leads Generados", "Primer Contacto Realizado", "Respuesta Recibida", "Reunión Agendada"]
    funnel_values = [total_leads, total_first_contact, total_responded, total_meetings]

    # Usar Plotly Graph Objects para un embudo más personalizable
    fig = go.Figure(go.Funnel(
        y = funnel_stages,
        x = funnel_values,
        textposition = "inside",
        textinfo = "value+percent previous+percent initial", # Muestra valor, % vs anterior, % vs inicial
        opacity = 0.75,
        marker = {"color": ["#636EFA", "#FECB52", "#EF553B", "#00CC96"], # Colores por etapa
                  "line": {"width": [4, 2, 2, 1], "color": ["#4048A5", "#DDAA3F", "#C9452F", "#00A078"]}}, # Bordes
        connector = {"line": {"color": "grey", "dash": "dot", "width": 2}} # Líneas conectoras
    ))
    fig.update_layout(title_text="Embudo Detallado: Leads a Reuniones", title_x=0.5, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Mostrar Tasas de Conversión Clave debajo del embudo
    st.markdown("#### Tasas de Conversión por Etapa")
    rate_lead_to_contact = calculate_rate(total_first_contact, total_leads)
    rate_contact_to_response = calculate_rate(total_responded, total_first_contact)
    rate_response_to_meeting = calculate_rate(total_meetings, total_responded)
    rate_global_lead_to_meeting = calculate_rate(total_meetings, total_leads)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Lead → Contacto", f"{rate_lead_to_contact:.1f}%", help="Leads con fecha de primer contacto / Total Leads")
    r2.metric("Contacto → Respuesta", f"{rate_contact_to_response:.1f}%", help="Leads con respuesta 'Si' / Leads con fecha de primer contacto")
    r3.metric("Respuesta → Reunión", f"{rate_response_to_meeting:.1f}%", help="Leads con reunión 'Si' / Leads con respuesta 'Si'")
    r4.metric("Lead → Reunión (Global)", f"{rate_global_lead_to_meeting:.1f}%", help="Leads con reunión 'Si' / Total Leads")

def display_time_lag_analysis(df_filtered):
    """Muestra los KPIs de tiempo promedio del ciclo."""
    st.markdown("---")
    st.markdown("### ⏱️ Tiempos Promedio del Ciclo (en días)")
    st.caption("Calcula el tiempo promedio entre etapas clave para los leads que completaron dichas etapas.")

    if df_filtered.empty:
        st.info("No hay datos suficientes para calcular los tiempos del ciclo.")
        return

    # Calcular promedios para las columnas de días (ignorando NaN)
    avg_gen_to_contact = df_filtered['Dias_Gen_a_Contacto'].mean()
    avg_contact_to_meeting = df_filtered['Dias_Contacto_a_Reunion'].mean()
    avg_gen_to_meeting = df_filtered['Dias_Gen_a_Reunion'].mean()

    # Contar cuántos registros válidos se usaron para cada promedio
    count_gen_contact = df_filtered['Dias_Gen_a_Contacto'].count()
    count_contact_meeting = df_filtered['Dias_Contacto_a_Reunion'].count()
    count_gen_meeting = df_filtered['Dias_Gen_a_Reunion'].count()

    # Formatear para visualización, mostrando N/A si no hay datos
    f_avg_gen_contact = f"{avg_gen_to_contact:.1f}" if pd.notna(avg_gen_to_contact) else "N/A"
    f_avg_contact_meeting = f"{avg_contact_to_meeting:.1f}" if pd.notna(avg_contact_to_meeting) else "N/A"
    f_avg_gen_meeting = f"{avg_gen_to_meeting:.1f}" if pd.notna(avg_gen_to_meeting) else "N/A"

    t1, t2, t3 = st.columns(3)
    t1.metric("Lead Gen → 1er Contacto", f_avg_gen_contact, help=f"Promedio sobre {count_gen_contact:,} leads contactados.")
    t2.metric("1er Contacto → Reunión", f_avg_contact_meeting, help=f"Promedio sobre {count_contact_meeting:,} reuniones con fecha de contacto.")
    t3.metric("Lead Gen → Reunión (Total)", f_avg_gen_meeting, help=f"Promedio sobre {count_gen_meeting:,} reuniones.")

def display_segmentation_analysis(df_filtered):
    """Muestra el rendimiento por Industria y Nivel de Management."""
    st.markdown("---")
    st.markdown("### 📊 Desempeño por Segmento (Industria y Nivel)")
    st.caption("Compara la Tasa de Conversión Global (Leads a Reuniones) entre los diferentes segmentos.")

    if df_filtered.empty:
        st.info("No hay datos para el análisis de segmentación.")
        return

    def create_segment_chart(group_col, title_suffix):
        """Función helper para generar gráfico y tabla por segmento."""
        if group_col not in df_filtered.columns or df_filtered[group_col].nunique() < 2:
            st.caption(f"No hay suficientes datos o variación en '{title_suffix}' para un desglose significativo.")
            return

        # Calcular totales y tasa global por segmento
        segment_summary = df_filtered.groupby(group_col).agg(
            Total_Leads=(group_col, 'count'),
            Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum()) # Contar solo donde Meeting es 'Si'
        ).reset_index()

        segment_summary['Tasa_Conversion_Global (%)'] = segment_summary.apply(
            lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Leads']),
            axis=1
        )

        # Filtrar para gráfico: exigir un número mínimo de leads para que la tasa sea significativa
        # Umbral dinámico: 1% del total filtrado, pero mínimo 3 leads
        min_leads_threshold = max(3, int(len(df_filtered) * 0.01))
        segment_summary_for_chart = segment_summary[segment_summary['Total_Leads'] >= min_leads_threshold].copy()

        if segment_summary_for_chart.empty:
            st.caption(f"No hay grupos en '{title_suffix}' con al menos {min_leads_threshold} leads para mostrar gráficamente la tasa de conversión.")
            # Mostrar tabla completa si no hay gráfico
            with st.expander(f"Ver datos por {title_suffix} (todos)"):
                st.dataframe(
                    segment_summary.sort_values('Total_Leads', ascending=False).style.format({
                        'Total_Leads': '{:,}',
                        'Total_Reuniones': '{:,}',
                        'Tasa_Conversion_Global (%)': '{:.1f}%'
                    }),
                    hide_index=True, use_container_width=True
                )
        else:
            # Gráfico de Tasa de Conversión (Top 10)
            segment_summary_for_chart = segment_summary_for_chart.sort_values('Tasa_Conversion_Global (%)', ascending=False)
            fig = px.bar(
                segment_summary_for_chart.head(10), # Mostrar solo los top 10 por tasa
                x=group_col,
                y='Tasa_Conversion_Global (%)',
                title=f"Top 10 {title_suffix} por Tasa Conversión",
                text='Tasa_Conversion_Global (%)', # Mostrar el valor de la tasa en la barra
                color='Tasa_Conversion_Global (%)', # Colorear por la tasa
                color_continuous_scale=px.colors.sequential.YlGnBu # Esquema de color
            )
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside') # Formato del texto
            fig.update_layout(
                yaxis_title="Tasa (%)",
                yaxis_ticksuffix="%",
                xaxis_title=title_suffix,
                title_x=0.5, # Centrar título
                # Ajustar rango del eje Y para mejor visualización
                yaxis_range=[0, max(10, segment_summary_for_chart['Tasa_Conversion_Global (%)'].max() * 1.1 + 5)]
            )
            st.plotly_chart(fig, use_container_width=True)

            # Ofrecer ver la tabla completa en un expander
            with st.expander(f"Ver tabla completa de datos por {title_suffix}"):
                st.dataframe(
                    segment_summary.sort_values('Total_Leads', ascending=False).style.format({
                        'Total_Leads': '{:,}',
                        'Total_Reuniones': '{:,}',
                        'Tasa_Conversion_Global (%)': '{:.1f}%'
                    }),
                    hide_index=True, use_container_width=True
                )

    # Crear los dos gráficos/tablas de segmentación en columnas
    col1, col2 = st.columns(2)
    with col1:
        create_segment_chart(COL_INDUSTRY, "Industria")
    with col2:
        create_segment_chart(COL_MANAGEMENT, "Nivel de Management")

def display_channel_analysis(df_filtered):
    """Analiza la efectividad por canal de respuesta."""
    st.markdown("---")
    st.markdown(f"### 📣 Efectividad por Canal de Respuesta ({COL_CHANNEL})")
    st.caption("Analiza qué canales generan más respuestas y cuál convierte mejor esas respuestas en reuniones.")

    # Verificar si las columnas necesarias existen
    if COL_CHANNEL not in df_filtered.columns or COL_RESPONDED not in df_filtered.columns:
        st.info(f"No se pueden analizar los canales. Faltan las columnas '{COL_CHANNEL}' o '{COL_RESPONDED}'.")
        return

    # Filtrar solo por leads que han respondido ("Si")
    df_responded = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()

    if df_responded.empty:
        st.info("No hay leads con respuesta 'Si' en el conjunto filtrado para analizar canales.")
        return

    # Verificar si hay variación en los canales
    if df_responded[COL_CHANNEL].nunique() < 1:
        st.info(f"No hay datos o variación en la columna '{COL_CHANNEL}' para los leads que respondieron.")
        return

    # Calcular KPIs por canal
    channel_summary = df_responded.groupby(COL_CHANNEL).agg(
        Total_Respuestas=(COL_CHANNEL, 'count'),
        Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum()) # Contar reuniones 'Si'
    ).reset_index()

    # Calcular Tasa de Conversión: Reuniones / Respuestas
    channel_summary['Tasa_Reunion_por_Respuesta (%)'] = channel_summary.apply(
        lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Respuestas']),
        axis=1
    )

    # Ordenar por volumen de respuestas para la tabla y gráfico 1
    channel_summary_sorted_volume = channel_summary.sort_values('Total_Respuestas', ascending=False)

    col_chart1, col_chart2 = st.columns(2)

    # Gráfico 1: Volumen de Respuestas
    with col_chart1:
        fig_volume = px.bar(
            channel_summary_sorted_volume,
            x=COL_CHANNEL,
            y='Total_Respuestas',
            title="Volumen de Respuestas por Canal",
            text_auto=True # Mostrar valor en las barras
        )
        fig_volume.update_layout(yaxis_title="Nº Respuestas", title_x=0.5, xaxis_title="Canal")
        st.plotly_chart(fig_volume, use_container_width=True)

    # Gráfico 2: Tasa de Conversión (Respuesta -> Reunión)
    with col_chart2:
        # Solo mostrar si hay alguna reunión para calcular tasas
        if channel_summary['Total_Reuniones'].sum() > 0:
            # Ordenar por tasa para este gráfico
            channel_summary_sorted_rate = channel_summary.sort_values('Tasa_Reunion_por_Respuesta (%)', ascending=False)
            fig_rate = px.bar(
                channel_summary_sorted_rate,
                x=COL_CHANNEL,
                y='Tasa_Reunion_por_Respuesta (%)',
                title="Tasa Respuesta -> Reunión por Canal",
                text='Tasa_Reunion_por_Respuesta (%)', # Mostrar valor de la tasa
                color='Tasa_Reunion_por_Respuesta (%)', # Colorear por tasa
                color_continuous_scale=px.colors.sequential.OrRd # Esquema de color
            )
            fig_rate.update_traces(texttemplate='%{text:.1f}%', textposition='outside') # Formato y posición del texto
            fig_rate.update_layout(
                yaxis_title="Tasa (%)",
                yaxis_ticksuffix="%",
                title_x=0.5,
                xaxis_title="Canal",
                # Rango dinámico del eje Y
                yaxis_range=[0, max(10, channel_summary['Tasa_Reunion_por_Respuesta (%)'].max() * 1.1 + 5)]
            )
            st.plotly_chart(fig_rate, use_container_width=True)
        else:
            st.caption("No hay reuniones agendadas desde respuestas para calcular la tasa de conversión por canal.")

    # Tabla detallada en un expander
    with st.expander("Ver datos detallados por Canal"):
        st.dataframe(
            channel_summary_sorted_volume.style.format({ # Usar el ordenado por volumen aquí
                'Total_Respuestas': '{:,}',
                'Total_Reuniones': '{:,}',
                'Tasa_Reunion_por_Respuesta (%)': '{:.1f}%'
            }),
            hide_index=True, use_container_width=True
        )

def display_enhanced_time_evolution(df_filtered):
    """Muestra la evolución temporal del embudo mes a mes."""
    st.markdown("---")
    st.markdown("### 📈 Evolución Temporal Detallada del Embudo (por Mes)")
    st.caption("Compara el volumen de leads generados, contactos, respuestas y reuniones mes a mes.")

    # Verificar si hay datos y la columna AñoMes
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns or df_filtered['AñoMes'].nunique() < 1:
        st.info("No hay suficientes datos temporales (AñoMes) válidos para mostrar la evolución.")
        return

    # Agrupar por mes y sumar las etapas clave del embudo
    time_summary = df_filtered.groupby('AñoMes').agg(
        Leads_Generados=('AñoMes', 'count'), # Total de filas en ese mes
        Primer_Contacto=('FirstContactStatus', lambda x: (x == 'Si').sum()), # Contar 'Si'
        Respuestas=(COL_RESPONDED, lambda x: (x == 'Si').sum()), # Contar 'Si'
        Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum()) # Contar 'Si'
    ).reset_index().sort_values('AñoMes') # Ordenar por mes

    # Solo proceder si la agregación resultó en datos
    if not time_summary.empty:
        # Reestructurar (melt) el DataFrame para Plotly: una fila por mes y etapa
        time_summary_melted = time_summary.melt(
            id_vars=['AñoMes'], # Columna identificadora
            value_vars=['Leads_Generados', 'Primer_Contacto', 'Respuestas', 'Reuniones'], # Columnas a convertir en filas
            var_name='Etapa', # Nueva columna con el nombre de la etapa
            value_name='Cantidad' # Nueva columna con el valor numérico
        )

        # Crear el gráfico de líneas
        fig = px.line(
            time_summary_melted,
            x='AñoMes',          # Eje X: Mes
            y='Cantidad',        # Eje Y: Número de leads/eventos
            color='Etapa',       # Una línea por cada etapa del embudo
            title="Evolución Mensual del Embudo",
            markers=True,        # Mostrar puntos en cada dato mensual
            labels={"Cantidad": "Número", "AñoMes": "Mes"} # Etiquetas de ejes
        )
        # Ajustes de layout
        fig.update_layout(legend_title_text='Etapa', title_x=0.5, yaxis_rangemode='tozero') # Empezar eje Y en 0
        st.plotly_chart(fig, use_container_width=True)

        # Mostrar tabla de datos en un expander
        with st.expander("Ver datos de evolución mensual"):
            # Usar AñoMes como índice y formatear números
            st.dataframe(time_summary.set_index('AñoMes').style.format("{:,}"), use_container_width=True)
    else:
        st.caption("No se generaron datos agregados por mes para mostrar la evolución.")


# --- Flujo Principal de la Página ---

# 1. Cargar y procesar datos (con manejo de errores)
df_pipeline_base = load_and_process_data()

# Mostrar advertencias acumuladas durante la carga/procesamiento
processing_warnings = st.session_state.get('data_load_warnings', [])
if processing_warnings:
    with st.expander("⚠️ Avisos durante la carga/procesamiento de datos", expanded=True): # Expandido por defecto si hay warnings
        for msg in processing_warnings:
            st.warning(msg) # Usar st.warning para mensajes importantes

# Detener si la carga/procesamiento inicial falló críticamente
if df_pipeline_base.empty:
    # El error específico ya se mostró en load_and_process_data
    if not processing_warnings: # Si no hubo error, pero quedó vacío (ej. 0 filas válidas)
        st.error("Fallo: El DataFrame está vacío después del procesamiento inicial. Verifica los datos de origen o los criterios de filtrado inicial (ej. fechas).")
    st.stop() # Detener la ejecución si no hay datos base

# 2. Mostrar filtros en la barra lateral y obtener las selecciones del usuario
start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base.copy()) # Pasar copia para evitar modificar el original

# 3. Aplicar los filtros seleccionados al DataFrame base
df_pipeline_filtered = apply_pipeline_filters(df_pipeline_base, start_date, end_date, industries, managements, meeting_status)

# 4. Mostrar los componentes de visualización si hay datos filtrados
if not df_pipeline_filtered.empty:
    display_enhanced_funnel(df_pipeline_filtered)
    display_time_lag_analysis(df_pipeline_filtered)
    display_segmentation_analysis(df_pipeline_filtered)
    display_channel_analysis(df_pipeline_filtered)
    display_enhanced_time_evolution(df_pipeline_filtered)

    # 5. Mostrar tabla detallada de leads filtrados (opcionalmente en expander)
    with st.expander("Ver tabla detallada de leads filtrados"):
        st.info(f"Mostrando {len(df_pipeline_filtered):,} leads que coinciden con los filtros.")
        # Definir columnas relevantes para mostrar en la tabla (ajusta según necesidad)
        cols_to_show = [
            "Company", "Full Name", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT,
            'Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_CONTACTED, COL_RESPONDED, COL_MEETING,
            COL_MEETING_DATE, COL_CHANNEL, "LinkedIn URL",
            'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion'
        ]
        # Filtrar solo las columnas que existen en el DataFrame
        cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
        df_display = df_pipeline_filtered[cols_exist].copy()

        # Formatear columnas de fecha y días para mejor lectura
        for date_col in ['Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]:
            if date_col in df_display.columns:
                # Formato AAAA-MM-DD, N/A si es nulo
                df_display[date_col] = pd.to_datetime(df_display[date_col], errors='coerce').dt.strftime('%Y-%m-%d').fillna('N/A')
        for time_col in ['Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']:
             if time_col in df_display.columns:
                 # Mostrar como número entero, N/A si es nulo
                 df_display[time_col] = df_display[time_col].apply(lambda x: f"{x:.0f}" if pd.notna(x) else 'N/A')

        st.dataframe(df_display, hide_index=True)

        # Botón de descarga para la vista filtrada
        try:
            output = io.BytesIO()
            # Escribir a Excel en memoria
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Usar el DataFrame original filtrado para no perder tipos de datos
                df_pipeline_filtered[cols_exist].to_excel(writer, index=False, sheet_name='Pipeline_Filtrado')

            st.download_button(
                label="⬇️ Descargar Vista Filtrada (Excel)",
                data=output.getvalue(),
                file_name="pipeline_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            st.error(f"Error al generar el archivo Excel para descarga: {e}")

else:
    # Mensaje si no hay datos después de aplicar filtros
    st.info("ℹ️ No se encontraron datos que coincidan con los filtros seleccionados.")


