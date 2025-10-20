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
PIPELINE_SHEET_URL_KEY = "pipeline_sheet_url_oct_2025" 
# URL por defecto (la que me diste) si el secret no se encuentra
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/1MYj_43IFIzrg8tQxG9LUfT6-V0O3lg8TuQUveWhEVAM/edit?gid=971436223#gid=971436223"
PIPELINE_SHEET_NAME = "Prospects"

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
SES_PREFIX = "pipe_v2_"
SES_START_DATE_KEY = f"{SES_PREFIX}start_date"
SES_END_DATE_KEY = f"{SES_PREFIX}end_date"
SES_INDUSTRY_KEY = f"{SES_PREFIX}industry"
SES_MANAGEMENT_KEY = f"{SES_PREFIX}management"
SES_MEETING_KEY = f"{SES_PREFIX}meeting"

# --- Funciones de Utilidad ---

@st.cache_data(ttl=300)
def parse_date_optimized(date_input):
    """
    Parsea fechas de forma robusta, manejando strings, números de Excel y booleanos.
    Prioriza formatos D/M/YYYY y DD/M/YYYY.
    """
    if pd.isna(date_input): return pd.NaT
    if isinstance(date_input, (datetime.datetime, datetime.date)):
        try:
             dt = pd.to_datetime(date_input)
             if dt.tzinfo is not None: dt = dt.tz_localize(None)
             return dt.normalize()
        except: return pd.to_datetime(date_input, errors='coerce')
    
    if isinstance(date_input, (bool, np.bool_)): return pd.NaT # Ignorar TRUE/FALSE

    date_str = str(date_input).strip()
    if not date_str: return pd.NaT

    # Prioridad 1: Formatos con / (D/M/YYYY o M/D/YYYY)
    if '/' in date_str:
        try:
            # Probar D/M/YYYY (común en tus datos)
            parsed = pd.to_datetime(date_str, format="%d/%m/%Y", errors='raise')
            if pd.notna(parsed): return parsed.normalize()
        except (ValueError, TypeError): pass
        
        try:
            # Probar D/M/YY
            parsed = pd.to_datetime(date_str, format="%d/%m/%y", errors='raise')
            if pd.notna(parsed): return parsed.normalize()
        except (ValueError, TypeError): pass

        try:
            # Probar M/D/YYYY
            parsed = pd.to_datetime(date_str, format="%m/%d/%Y", errors='raise')
            if pd.notna(parsed): return parsed.normalize()
        except (ValueError, TypeError): pass

    # Prioridad 2: Formato AAAA-MM-DD
    if '-' in date_str:
        try:
            parsed = pd.to_datetime(date_str, format="%Y-%m-%d", errors='coerce')
            if pd.notna(parsed): return parsed.normalize()
        except (ValueError, TypeError): pass

    # Prioridad 3: Número de serie de Excel (común en get_all_values no formateado)
    if re.fullmatch(r'\d+(\.\d+)?', date_str):
        try:
             excel_date_num = float(date_str)
             if 30000 < excel_date_num < 60000: # Rango razonable para fechas de Excel
                 origin = pd.Timestamp('1899-12-30')
                 parsed_excel = origin + pd.to_timedelta(excel_date_num, unit='D')
                 if pd.Timestamp('1980-01-01') <= parsed_excel <= pd.Timestamp('2050-12-31'):
                      return parsed_excel.normalize()
        except Exception: pass # Ignorar si la conversión numérica falla

    # Último recurso: Dejar que Pandas intente adivinar
    try:
        parsed_generic = pd.to_datetime(date_str, errors='coerce', dayfirst=True)
        if pd.notna(parsed_generic): return parsed_generic.normalize()
    except Exception:
        return pd.NaT
    
    return pd.NaT

@st.cache_data
def clean_yes_no_optimized(val):
    """Limpia valores booleanos, strings (TRUE/FALSE, Yes/No, etc.) a 'Si' o 'No'."""
    if isinstance(val, bool) or isinstance(val, np.bool_):
        return "Si" if val else "No"
    
    cleaned = str(val).strip().lower()
    
    if cleaned in ['yes', 'sí', 'si', '1', 'true', 'verdadero', 'agendada', 'ok', 'realizada', 'hecho', 'completo', 'listo']:
        return "Si"
    
    # El resto (incluyendo 'no', 'false', '', 'nan', '0', etc.) se considera "No"
    return "No"

@st.cache_data
def calculate_rate(numerator, denominator, round_to=1):
    """Calcula una tasa como porcentaje, manejando ceros y NaNs."""
    num = pd.to_numeric(numerator, errors='coerce')
    den = pd.to_numeric(denominator, errors='coerce')
    if pd.isna(den) or den == 0 or pd.isna(num): return 0.0
    rate = (num / den) * 100
    if np.isinf(rate) or np.isnan(rate): return 0.0
    return round(rate, round_to)

@st.cache_data
def calculate_time_diff(date1, date2):
    """Calcula la diferencia en días entre dos fechas."""
    d1 = pd.to_datetime(date1, errors='coerce')
    d2 = pd.to_datetime(date2, errors='coerce')
    if pd.notna(d1) and pd.notna(d2) and d2 >= d1:
        return (d2 - d1).days
    return np.nan

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
@st.cache_data(ttl=300)
def load_and_process_data():
    """
    Carga datos desde Google Sheets usando gspread y los procesa.
    """
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    processing_warnings = []

    try:
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
        # Usar 'UNFORMATTED_VALUE' es crucial para obtener números de fecha de Excel
        all_data_loaded = sheet.get_all_values(value_render_option='UNFORMATTED_VALUE') 
        
        if not all_data_loaded or len(all_data_loaded) <= 1:
            raise ValueError(f"La hoja '{PIPELINE_SHEET_NAME}' está vacía o no tiene encabezados.")

        headers = make_unique_headers(all_data_loaded[0])
        df = pd.DataFrame(all_data_loaded[1:], columns=headers)

    except gspread.exceptions.APIError as e:
         if "This operation is not supported for this document" in str(e):
             st.error("❌ Error: El archivo en la URL sigue siendo formato Excel (.xlsx).")
             st.warning("Debes 'Guardar como Hoja de Google', compartir la *nueva* hoja y actualizar la URL en secrets.toml.")
             st.stop()
         else:
             st.error(f"❌ Error de API Google: {e}")
             st.info(f"Verifica la URL, el nombre de la pestaña ('{PIPELINE_SHEET_NAME}') y los permisos de la cuenta de servicio.")
             st.stop()
    except Exception as e:
        st.error(f"❌ Error crítico al cargar datos: {e}")
        st.info(f"Verifica URL ('{PIPELINE_SHEET_URL_KEY}'), nombre pestaña ('{PIPELINE_SHEET_NAME}') y permisos.")
        st.stop()

    # --- Procesamiento Post-Carga ---
    essential_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, COL_CONTACTED]
    missing_essentials = [col for col in essential_cols if col not in df.columns]
    if missing_essentials:
        st.error(f"Faltan columnas esenciales para el análisis: {', '.join(missing_essentials)}. Verifica los nombres en la hoja.")
        # Crear columnas faltantes con Nulos para evitar que el script falle
        for col in missing_essentials: df[col] = pd.NA

    # Parseo de Fechas
    date_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]
    date_parse_fail_counts = {col: 0 for col in date_cols}
    for col in date_cols:
        if col in df.columns:
            original_nas = df[col].isna() | (df[col] == '')
            df[col] = df[col].apply(parse_date_optimized) # Usar la función optimizada
            new_nas = df[col].isna()
            # Contar solo las filas que NO eran NaT/vacías pero fallaron al parsear
            date_parse_fail_counts[col] = (new_nas & ~original_nas).sum()
        else: df[col] = pd.NaT # Asegurarse que la columna exista como tipo fecha

    # Renombrar la fecha principal para filtros
    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True)
    initial_rows = len(df)
    df.dropna(subset=['Fecha_Principal'], inplace=True) # Pilar del dashboard
    rows_dropped_no_lead_date = initial_rows - len(df)

    if rows_dropped_no_lead_date > 0:
        processing_warnings.append(f"⚠️ {rows_dropped_no_lead_date:,} filas eliminadas por fecha inválida/vacía en '{COL_LEAD_GEN_DATE}'.")
    for col, count in date_parse_fail_counts.items():
        if count > 0 : processing_warnings.append(f"⚠️ {count} fechas no se pudieron interpretar en la columna '{col}'.")
    
    # Almacenar advertencias para mostrarlas en la UI
    st.session_state['data_load_warnings'] = processing_warnings

    # Limpieza de Columnas de Estado (Booleanas/Texto)
    status_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in status_cols:
        if col in df.columns: df[col] = df[col].apply(clean_yes_no_optimized)
        else: df[col] = "No" # Si la columna no existe, asumir "No"

    # Creación de KPI derivado: 'FirstContactStatus'
    # Usamos la fecha de primer contacto como la fuente de verdad
    if COL_FIRST_CONTACT_DATE in df.columns:
        df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No')
    else: df['FirstContactStatus'] = 'No'

    # Limpieza de Columnas Categóricas (Dimensiones)
    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('No Definido')
            df[col] = df[col].astype(str).str.strip().replace('', 'No Definido').str.title()
            # Limpiar valores comunes de "vacío"
            df[col] = df[col].replace({'N/D': 'No Definido', 'Na': 'No Definido', '-':'No Definido', 'False':'No Definido', 'True':'No Definido'})
        else: df[col] = "No Definido" # Si la columna no existe

    # Creación de Columnas de Tiempo para Agregación
    if not df.empty and 'Fecha_Principal' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Fecha_Principal']):
        df['Año'] = df['Fecha_Principal'].dt.year.astype('Int64', errors='ignore')
        df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64', errors='ignore')
        df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
    else:
        for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA

    # Cálculo de KPIs de Tiempo (Lags)
    df['Dias_Gen_a_Contacto'] = df.apply(lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_FIRST_CONTACT_DATE)), axis=1)
    df['Dias_Contacto_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get(COL_FIRST_CONTACT_DATE), row.get(COL_MEETING_DATE)), axis=1)
    df['Dias_Gen_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_MEETING_DATE)), axis=1)

    return df

# --- Filtros de la Barra Lateral ---
def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")
    
    # Valores por defecto para los filtros
    default_filters = {
        SES_START_DATE_KEY: None, 
        SES_END_DATE_KEY: None, 
        SES_INDUSTRY_KEY: ["– Todos –"], 
        SES_MANAGEMENT_KEY: ["– Todos –"], 
        SES_MEETING_KEY: "– Todos –"
    }
    # Inicializar estado de sesión si no existe
    for key, val in default_filters.items():
        if key not in st.session_state: st.session_state[key] = val

    # Filtro de Fecha (basado en Fecha_Principal)
    st.sidebar.subheader("🗓️ Por Fecha de Lead Generado")
    min_date, max_date = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        try: 
            min_date = df_options["Fecha_Principal"].min().date()
            max_date = df_options["Fecha_Principal"].max().date()
        except: pass # Ignorar si hay fechas inválidas
    
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

    # Filtros Categóricos
    st.sidebar.subheader("👥 Por Atributo de Lead")
    
    def create_multiselect(col_name, label, key):
        """Función helper para crear un multiselect."""
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            unique_vals = sorted(df_options[col_name].astype(str).unique())
            # Mover "No Definido" al final si existe
            if "No Definido" in unique_vals:
                unique_vals.remove("No Definido")
                options.extend(unique_vals)
                options.append("No Definido")
            else:
                options.extend(unique_vals)
                
        current_state = st.session_state.get(key, ["– Todos –"])
        # Asegurar que el estado actual solo contenga opciones válidas
        valid_state = [s for s in current_state if s in options]
        if not valid_state or not options: valid_state = ["– Todos –"]
        st.session_state[key] = valid_state # Actualizar estado antes de renderizar
        st.sidebar.multiselect(label, options, key=key)

    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)

    # Filtro de Estado
    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)

    # Botón de Limpiar
    def clear_pipeline_filters():
        """Callback para resetear todos los filtros a su valor por defecto."""
        for key, val in default_filters.items(): st.session_state[key] = val
        st.toast("Filtros reiniciados ✅", icon="🧹")
    
    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_pipeline_filters, use_container_width=True)

    # Retornar los valores actuales del estado de sesión
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], 
            st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY], 
            st.session_state[SES_MEETING_KEY])

# --- Lógica para Aplicar Filtros ---
def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    df_f = df.copy()
    if df_f.empty: return df_f

    # Aplicar filtro de fecha
    if "Fecha_Principal" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f['Fecha_Principal']):
        start_dt_norm = pd.to_datetime(start_dt).normalize() if start_dt else None
        end_dt_norm = pd.to_datetime(end_dt).normalize() if end_dt else None
        
        mask = pd.Series(True, index=df_f.index)
        valid_dates_mask = df_f['Fecha_Principal'].notna() # Trabajar solo con fechas válidas
        
        if start_dt_norm: mask &= (df_f['Fecha_Principal'] >= start_dt_norm) & valid_dates_mask
        if end_dt_norm: mask &= (df_f['Fecha_Principal'] <= end_dt_norm) & valid_dates_mask
        df_f = df_f[mask]

    # Aplicar filtros categóricos
    if industries and "– Todos –" not in industries and COL_INDUSTRY in df_f.columns:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
    
    if managements and "– Todos –" not in managements and COL_MANAGEMENT in df_f.columns:
        df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]
    
    if meeting_status != "– Todos –" and COL_MEETING in df_f.columns:
        df_f = df_f[df_f[COL_MEETING] == meeting_status]
        
    return df_f

# --- Componentes de Visualización ---

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
        textinfo = "value+percent previous+percent initial",
        opacity = 0.7,
        marker = {"color": ["#636EFA", "#FECB52", "#EF553B", "#00CC96"],
                  "line": {"width": [4, 2, 2, 1], "color": ["#4048A5", "#DDAA3F", "#C9452F", "#00A078"]}},
        connector = {"line": {"color": "grey", "dash": "dot", "width": 2}}
    ))
    fig.update_layout(title_text="Embudo Detallado: Leads a Reuniones", title_x=0.5, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # Mostrar Tasas de Conversión Clave
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

    # Calcular promedios
    avg_gen_to_contact = df_filtered['Dias_Gen_a_Contacto'].dropna().mean()
    avg_contact_to_meeting = df_filtered['Dias_Contacto_a_Reunion'].dropna().mean()
    avg_gen_to_meeting = df_filtered['Dias_Gen_a_Reunion'].dropna().mean()

    # Contar cuántos registros se usaron para cada promedio
    count_gen_contact = df_filtered['Dias_Gen_a_Contacto'].count()
    count_contact_meeting = df_filtered['Dias_Contacto_a_Reunion'].count()
    count_gen_meeting = df_filtered['Dias_Gen_a_Reunion'].count()

    # Formatear para visualización
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
            st.caption(f"No hay suficientes datos de '{title_suffix}' para un desglose.")
            return

        # Calcular totales y tasa global
        segment_summary = df_filtered.groupby(group_col).agg(
            Total_Leads=(group_col, 'count'),
            Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
        ).reset_index()
        
        segment_summary['Tasa_Conversion_Global (%)'] = segment_summary.apply(
            lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Leads']), 
            axis=1
        )
        
        # Filtrar para gráfico (evitar grupos con muy pocos datos)
        min_leads_threshold = max(3, int(len(df_filtered) * 0.01)) # Umbral dinámico, mínimo 3
        segment_summary_filtered = segment_summary[segment_summary['Total_Leads'] >= min_leads_threshold].copy()
        
        show_table = True
        if segment_summary_filtered.empty:
            st.caption(f"No hay grupos en '{title_suffix}' con ≥ {min_leads_threshold} leads para mostrar en el gráfico.")
        else:
            # Gráfico de Tasa de Conversión
            segment_summary_filtered = segment_summary_filtered.sort_values('Tasa_Conversion_Global (%)', ascending=False)
            fig = px.bar(
                segment_summary_filtered.head(10), # Top 10
                x=group_col, 
                y='Tasa_Conversion_Global (%)', 
                title=f"Top 10 {title_suffix} por Tasa Conversión",
                text='Tasa_Conversion_Global (%)',
                color='Tasa_Conversion_Global (%)',
                color_continuous_scale=px.colors.sequential.YlGnBu
            )
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(
                yaxis_title="Tasa (%)", 
                yaxis_ticksuffix="%", 
                xaxis_title=title_suffix, 
                title_x=0.5,
                yaxis_range=[0, max(10, segment_summary_filtered['Tasa_Conversion_Global (%)'].max() * 1.1 + 5)] # Rango dinámico
            )
            st.plotly_chart(fig, use_container_width=True)
            show_table = False # No mostrar la tabla si ya mostramos el gráfico

        if show_table: # Mostrar tabla si el gráfico no se mostró
            with st.expander(f"Ver datos por {title_suffix} (todos)"):
                st.dataframe(
                    segment_summary.sort_values('Total_Leads', ascending=False).style.format({
                        'Total_Leads': '{:,}', 
                        'Total_Reuniones': '{:,}', 
                        'Tasa_Conversion_Global (%)': '{:.1f}%'
                    }), 
                    hide_index=True, use_container_width=True
                )

    # Crear los dos gráficos de segmentación
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

    if COL_CHANNEL not in df_filtered.columns or COL_RESPONDED not in df_filtered.columns:
        st.info(f"No se pueden analizar los canales. Faltan las columnas '{COL_CHANNEL}' o '{COL_RESPONDED}'.")
        return

    # Filtrar solo por leads que han respondido
    df_responded = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()
    
    if df_responded.empty:
        st.info("No hay leads con respuesta 'Si' en el conjunto filtrado para analizar canales.")
        return
    
    if df_responded[COL_CHANNEL].nunique() < 1:
        st.info(f"No hay datos o variación en la columna '{COL_CHANNEL}' para los leads que respondieron.")
        return

    # Calcular KPIs por canal
    channel_summary = df_responded.groupby(COL_CHANNEL).agg(
        Total_Respuestas=(COL_CHANNEL, 'count'),
        Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index()
    
    channel_summary['Tasa_Reunion_por_Respuesta (%)'] = channel_summary.apply(
        lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Respuestas']), 
        axis=1
    )
    
    channel_summary = channel_summary.sort_values('Total_Respuestas', ascending=False)

    col_chart1, col_chart2 = st.columns(2)
    
    # Gráfico 1: Volumen de Respuestas
    with col_chart1:
        fig_volume = px.bar(
            channel_summary, 
            x=COL_CHANNEL, 
            y='Total_Respuestas', 
            title="Volumen de Respuestas por Canal", 
            text_auto=True
        )
        fig_volume.update_layout(yaxis_title="Nº Respuestas", title_x=0.5, xaxis_title="Canal")
        st.plotly_chart(fig_volume, use_container_width=True)
    
    # Gráfico 2: Tasa de Conversión (Respuesta -> Reunión)
    with col_chart2:
        if channel_summary['Total_Reuniones'].sum() > 0:
            fig_rate = px.bar(
                channel_summary.sort_values('Tasa_Reunion_por_Respuesta (%)', ascending=False), 
                x=COL_CHANNEL, 
                y='Tasa_Reunion_por_Respuesta (%)', 
                title="Tasa Respuesta -> Reunión por Canal", 
                text='Tasa_Reunion_por_Respuesta (%)',
                color='Tasa_Reunion_por_Respuesta (%)',
                color_continuous_scale=px.colors.sequential.OrRd
            )
            fig_rate.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_rate.update_layout(
                yaxis_title="Tasa (%)", 
                yaxis_ticksuffix="%", 
                title_x=0.5, 
                xaxis_title="Canal",
                yaxis_range=[0, max(10, channel_summary['Tasa_Reunion_por_Respuesta (%)'].max() * 1.1 + 5)]
            )
            st.plotly_chart(fig_rate, use_container_width=True)
        else:
            st.caption("No hay reuniones agendadas desde respuestas para calcular la tasa de conversión por canal.")

    with st.expander("Ver datos detallados por Canal"):
        st.dataframe(
            channel_summary.style.format({
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

    if df_filtered.empty or 'AñoMes' not in df_filtered.columns or df_filtered['AñoMes'].nunique() < 1:
        st.info("No hay suficientes datos temporales (AñoMes) para mostrar la evolución.")
        return

    # Agrupar por mes y sumar las etapas del embudo
    time_summary = df_filtered.groupby('AñoMes').agg(
        Leads_Generados=('AñoMes', 'count'),
        Primer_Contacto=('FirstContactStatus', lambda x: (x == 'Si').sum()),
        Respuestas=(COL_RESPONDED, lambda x: (x == 'Si').sum()),
        Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index().sort_values('AñoMes')

    if not time_summary.empty:
        # "Derretir" (melt) el DataFrame para que Plotly pueda usar 'Etapa' como color
        time_summary_melted = time_summary.melt(
            id_vars=['AñoMes'], 
            value_vars=['Leads_Generados', 'Primer_Contacto', 'Respuestas', 'Reuniones'], 
            var_name='Etapa', 
            value_name='Cantidad'
        )
        
        fig = px.line(
            time_summary_melted, 
            x='AñoMes', 
            y='Cantidad', 
            color='Etapa', 
            title="Evolución Mensual del Embudo", 
            markers=True,
            labels={"Cantidad": "Número", "AñoMes": "Mes"}
        )
        fig.update_layout(legend_title_text='Etapa', title_x=0.5, yaxis_rangemode='tozero')
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Ver datos de evolución mensual"):
            st.dataframe(time_summary.set_index('AñoMes').style.format("{:,}"), use_container_width=True)
    else:
        st.caption("No hay datos agregados por mes para mostrar.")

# --- Flujo Principal de la Página ---

# 1. Cargar y procesar datos
df_pipeline_base = load_and_process_data()

# Mostrar advertencias de carga si existen
processing_warnings = st.session_state.get('data_load_warnings', [])
if processing_warnings:
    with st.expander("⚠️ Avisos durante la carga/procesamiento de datos"):
        for msg in processing_warnings: st.warning(msg)

# Si la carga falla, df_pipeline_base estará vacío y se detendrá aquí
if df_pipeline_base.empty:
    if not processing_warnings: # Si no hubo error de carga pero sí de procesamiento
        st.error("Fallo: El DataFrame está vacío tras el procesamiento inicial (posiblemente por fechas inválidas).")
else:
    # 2. Mostrar filtros y obtener selecciones
    start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base.copy())
    
    # 3. Aplicar filtros
    df_pipeline_filtered = apply_pipeline_filters(df_pipeline_base, start_date, end_date, industries, managements, meeting_status)

    # 4. Mostrar visualizaciones
    if not df_pipeline_filtered.empty:
        display_enhanced_funnel(df_pipeline_filtered)
        display_time_lag_analysis(df_pipeline_filtered)
        display_segmentation_analysis(df_pipeline_filtered)
        display_channel_analysis(df_pipeline_filtered)
        display_enhanced_time_evolution(df_pipeline_filtered)

        # 5. Mostrar tabla de datos detallados
        with st.expander("Ver tabla detallada de leads filtrados"):
            st.info(f"Mostrando {len(df_pipeline_filtered):,} leads filtrados.")
            # Definir columnas de interés para la tabla
            cols_to_show = [
                "Company", "Full Name", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT, 
                'Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, 
                COL_MEETING_DATE, COL_CHANNEL, "LinkedIn URL", 
                'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion'
            ]
            cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
            df_display = df_pipeline_filtered[cols_exist].copy()
            
            # Formatear fechas y días para legibilidad
            for date_col in ['Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]:
                if date_col in df_display.columns: 
                    df_display[date_col] = df_display[date_col].dt.strftime('%Y-%m-%d').fillna('N/A')
            for time_col in ['Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']:
                 if time_col in df_display.columns: 
                     df_display[time_col] = df_display[time_col].apply(lambda x: f"{x:.0f}" if pd.notna(x) else 'N/A')
            
            st.dataframe(df_display, hide_index=True)
            
            # Botón de descarga
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_pipeline_filtered.to_excel(writer, index=False, sheet_name='Pipeline_Filtrado')
            
            st.download_button(
                label="⬇️ Descargar Vista (Excel)",
                data=output.getvalue(),
                file_name="pipeline_filtrado.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
    else:
        st.info("ℹ️ No se encontraron datos que coincidan con los filtros seleccionados.")

