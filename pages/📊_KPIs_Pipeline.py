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
st.set_page_config(layout="wide", page_title="Pipeline Prospección v5") # Incrementamos versión
st.title("📈 Pipeline de Prospección (Datos Validados)")
st.markdown("Análisis del embudo basado en la hoja 'Prospects'.")

# Clave del secret (asegúrate que exista en tus secrets de Streamlit)
PIPELINE_SHEET_URL_KEY = "pipeline_sheet_url_oct_2025"
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/1MYj_43IFIzrg8tQxG9LUfT6-V0O3lg8TuQUveWhEVAM/edit?gid=971436223#gid=971436223"
PIPELINE_SHEET_NAME = "Prospects" # Nombre exacto de la pestaña

# Nombres EXACTOS de columnas clave (verificados con tu ejemplo)
COL_LEAD_GEN_DATE = "Lead Generated (Date)"
COL_FIRST_CONTACT_DATE = "First Contact Date"
COL_MEETING_DATE = "Meeting Date"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_RESPONDED = "Responded?" # Tiene 'TRUE'/'FALSE' -> Se limpia a 'Si'/'No'
COL_MEETING = "Meeting?"     # Parece tener 'No' o vacío -> Se limpia a 'Si'/'No'
COL_CONTACTED = "Contacted?" # Tiene 'TRUE'/'FALSE' -> Se limpia a 'Si'/'No'

# Claves de Sesión (prefijo único)
SES_PREFIX = "pipe_v5_" # Incrementamos versión
SES_START_DATE_KEY = f"{SES_PREFIX}start_date"
SES_END_DATE_KEY = f"{SES_PREFIX}end_date"
SES_INDUSTRY_KEY = f"{SES_PREFIX}industry"
SES_MANAGEMENT_KEY = f"{SES_PREFIX}management"
SES_MEETING_KEY = f"{SES_PREFIX}meeting"

# --- Funciones de Utilidad (Mantenemos las que funcionaron) ---

@st.cache_data(ttl=300)
def parse_date_optimized(date_input):
    # (Mantenemos la versión anterior que parseó correctamente según tus logs)
    if pd.isna(date_input): return pd.NaT
    if isinstance(date_input, (bool, np.bool_)): return pd.NaT
    if isinstance(date_input, (datetime.datetime, datetime.date)):
        try:
             dt = pd.to_datetime(date_input)
             if dt.tzinfo is not None: dt = dt.tz_localize(None)
             return dt.normalize()
        except Exception: pass

    date_str = str(date_input).strip()
    if not date_str: return pd.NaT
    if date_str.lower() in ['true', 'false']: return pd.NaT

    formats_to_try_first = ["%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats_to_try_first:
        try:
            parsed = pd.to_datetime(date_str, format=fmt, errors='raise')
            if pd.notna(parsed): return parsed.normalize()
        except (ValueError, TypeError): pass

    formats_to_try_secondary = ["%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d"]
    for fmt in formats_to_try_secondary:
         try:
            parsed = pd.to_datetime(date_str, format=fmt, errors='raise')
            if pd.notna(parsed): return parsed.normalize()
         except (ValueError, TypeError): continue

    if re.fullmatch(r'\d+(\.\d+)?', date_str):
        try:
             excel_date_num = float(date_str)
             if 30000 < excel_date_num < 60000:
                 origin = pd.Timestamp('1899-12-30')
                 parsed_excel = origin + pd.to_timedelta(excel_date_num, unit='D')
                 if pd.Timestamp('1980-01-01') <= parsed_excel <= pd.Timestamp('2050-12-31'):
                      return parsed_excel.normalize()
        except Exception: pass

    try:
        parsed_generic = pd.to_datetime(date_str, errors='coerce', dayfirst=True)
        if pd.notna(parsed_generic): return parsed_generic.normalize()
    except Exception: pass

    return pd.NaT

@st.cache_data
def clean_yes_no_optimized(val):
    # (Mantenemos la versión anterior que limpió TRUE/FALSE correctamente)
    if pd.isna(val): return "No"
    if isinstance(val, (bool, np.bool_)): return "Si" if val else "No"
    cleaned = str(val).strip().lower()
    if cleaned == 'true': return "Si"
    affirmative_values = ['yes', 'sí', 'si', '1', 'verdadero', 'agendada', 'ok', 'realizada']
    if cleaned in affirmative_values: return "Si"
    return "No"

@st.cache_data
def calculate_rate(numerator, denominator, round_to=1):
    # (Mantenemos la versión robusta anterior)
    num = pd.to_numeric(numerator, errors='coerce')
    den = pd.to_numeric(denominator, errors='coerce')
    if pd.isna(den) or den == 0 or pd.isna(num): return 0.0
    rate = (num / den) * 100
    if np.isinf(rate) or np.isnan(rate): return 0.0
    return round(rate, round_to)

@st.cache_data
def calculate_time_diff(date1, date2):
    # (Mantenemos la versión anterior)
    d1 = pd.to_datetime(date1, errors='coerce')
    d2 = pd.to_datetime(date2, errors='coerce')
    if pd.notna(d1) and pd.notna(d2) and d2 >= d1:
        return (d2 - d1).days
    return np.nan

def make_unique_headers(headers_list):
    # (Mantenemos la versión anterior)
    counts = Counter(); new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped: h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1: new_headers.append(h_stripped)
        else: new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

# --- Carga y Procesamiento de Datos (Mantenemos la lógica anterior) ---
@st.cache_data(ttl=300)
def load_and_process_data():
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    processing_warnings = []
    df = pd.DataFrame()

    try:
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
        # *** Usar FORMATTED_VALUE ***
        all_data_loaded = sheet.get_all_values(value_render_option='FORMATTED_VALUE')

        if not all_data_loaded or len(all_data_loaded) <= 1:
            raise ValueError(f"Hoja '{PIPELINE_SHEET_NAME}' vacía o solo encabezados.")

        headers = make_unique_headers(all_data_loaded[0])
        df = pd.DataFrame(all_data_loaded[1:], columns=headers)

    except gspread.exceptions.APIError as e:
         if "This operation is not supported for this document" in str(e):
             st.error("❌ Error: El archivo en la URL es .xlsx.")
             st.warning("Solución: 'Archivo' -> 'Guardar como Hoja de cálculo de Google'. Comparte la *nueva* hoja y actualiza la URL.")
             st.stop()
         else:
             st.error(f"❌ Error API Google: {e}")
             st.info(f"Verifica URL, nombre pestaña ('{PIPELINE_SHEET_NAME}') y permisos.")
             st.stop()
    except Exception as e:
        st.error(f"❌ Error crítico cargando datos: {e}")
        st.info(f"Verifica URL ('{PIPELINE_SHEET_URL_KEY}'), nombre pestaña ('{PIPELINE_SHEET_NAME}') y permisos.")
        st.stop()

    if df.empty:
        st.error("DataFrame vacío después de carga.")
        st.stop()

    essential_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, COL_CONTACTED]
    missing_essentials = [col for col in essential_cols if col not in df.columns]
    if missing_essentials:
        st.error(f"Faltan columnas esenciales: {', '.join(missing_essentials)}.")
        for col in missing_essentials: df[col] = pd.NA

    # --- Parseo Fechas ---
    date_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]
    date_parse_fail_counts = {col: 0 for col in date_cols}
    for col in date_cols:
        if col in df.columns:
            original_non_empty = df[col].apply(lambda x: pd.notna(x) and str(x).strip() != "" and str(x).lower() not in ['true', 'false'])
            df[col] = df[col].apply(parse_date_optimized)
            failed_to_parse = df[col].isna() & original_non_empty
            date_parse_fail_counts[col] = failed_to_parse.sum()
        else: df[col] = pd.NaT

    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True)
    initial_rows = len(df)
    df.dropna(subset=['Fecha_Principal'], inplace=True)
    rows_dropped_no_lead_date = initial_rows - len(df)

    if rows_dropped_no_lead_date > 0:
        processing_warnings.append(f"⚠️ **{rows_dropped_no_lead_date:,} filas eliminadas** por '{COL_LEAD_GEN_DATE}' vacía/inválida.")
    for col, count in date_parse_fail_counts.items():
        if count > 0 : processing_warnings.append(f"⚠️ {count} valores en '{col}' no se pudieron parsear como fecha.")
    st.session_state['data_load_warnings'] = processing_warnings

    # --- Limpieza Estado (TRUE/FALSE) ---
    status_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in status_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no_optimized)
        else: df[col] = "No"

    # --- KPI Derivado: FirstContactStatus ---
    if COL_FIRST_CONTACT_DATE in df.columns:
        df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No')
    else: df['FirstContactStatus'] = 'No'

    # --- Limpieza Categóricas ---
    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('No Definido').astype(str).str.strip().str.title().replace('', 'No Definido')
            common_na_strings = {'N/A': 'No Definido', 'Na': 'No Definido', 'N/D': 'No Definido',
                                 '-': 'No Definido', 'False': 'No Definido', 'True': 'No Definido'}
            df[col] = df[col].replace(common_na_strings)
        else: df[col] = "No Definido"

    # --- Columnas Tiempo ---
    if not df.empty and 'Fecha_Principal' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Fecha_Principal']):
        try:
            df['Año'] = df['Fecha_Principal'].dt.year.astype('Int64')
            df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64')
            df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
        except Exception as e:
            st.warning(f"Error creando columnas de tiempo: {e}")
            for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA
    else:
        for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA

    # --- KPIs Tiempo (Lags) ---
    df['Dias_Gen_a_Contacto'] = df.apply(lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_FIRST_CONTACT_DATE)), axis=1)
    df['Dias_Contacto_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get(COL_FIRST_CONTACT_DATE), row.get(COL_MEETING_DATE)), axis=1)
    df['Dias_Gen_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_MEETING_DATE)), axis=1)

    return df

# --- Filtros (Sin cambios) ---
def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")
    default_filters = {SES_START_DATE_KEY: None, SES_END_DATE_KEY: None, SES_INDUSTRY_KEY: ["– Todos –"], SES_MANAGEMENT_KEY: ["– Todos –"], SES_MEETING_KEY: "– Todos –"}
    for key, val in default_filters.items():
        if key not in st.session_state: st.session_state[key] = val
    st.sidebar.subheader("🗓️ Por Fecha de Lead Generado")
    min_date, max_date = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        try: min_date, max_date = df_options["Fecha_Principal"].min().date(), df_options["Fecha_Principal"].max().date()
        except Exception as e: st.sidebar.warning(f"Error fechas min/max: {e}")
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", value=st.session_state[SES_START_DATE_KEY], key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", value=st.session_state[SES_END_DATE_KEY], key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    st.sidebar.subheader("👥 Por Atributo de Lead")
    def create_multiselect(col_name, label, key):
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            unique_vals = sorted([v for v in df_options[col_name].astype(str).unique() if v != 'No Definido'])
            options.extend(unique_vals)
            if 'No Definido' in df_options[col_name].astype(str).unique(): options.append('No Definido')
        current_state = st.session_state.get(key, ["– Todos –"])
        valid_state = [s for s in current_state if s in options]
        if not valid_state or (len(valid_state) == 1 and valid_state[0] not in options): valid_state = ["– Todos –"]
        st.session_state[key] = valid_state
        st.sidebar.multiselect(label, options, key=f"widget_{key}", default=valid_state)
    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)
    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)
    def clear_pipeline_filters():
        for key, val in default_filters.items(): st.session_state[key] = val
        st.toast("Filtros reiniciados ✅", icon="🧹")
    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_pipeline_filters, use_container_width=True)
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY],
            st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY],
            st.session_state[SES_MEETING_KEY])

# --- Aplicar Filtros (Sin cambios) ---
def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    df_f = df.copy()
    if df_f.empty: return df_f
    if "Fecha_Principal" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f['Fecha_Principal']):
        start_dt_norm = pd.to_datetime(start_dt).normalize() if start_dt else None
        end_dt_norm = pd.to_datetime(end_dt).normalize() if end_dt else None
        mask = pd.Series(True, index=df_f.index)
        valid_dates_mask = df_f['Fecha_Principal'].notna()
        if start_dt_norm: mask &= (df_f['Fecha_Principal'] >= start_dt_norm) & valid_dates_mask
        if end_dt_norm: mask &= (df_f['Fecha_Principal'] <= end_dt_norm) & valid_dates_mask
        df_f = df_f[mask]
    if industries and "– Todos –" not in industries and COL_INDUSTRY in df_f.columns:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
    if managements and "– Todos –" not in managements and COL_MANAGEMENT in df_f.columns:
        df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]
    if meeting_status != "– Todos –" and COL_MEETING in df_f.columns:
        df_f = df_f[df_f[COL_MEETING] == meeting_status]
    return df_f

# --- Componentes de Visualización (Revisión Lógica Embudo/Tasas) ---

def display_enhanced_funnel(df_filtered):
    st.markdown("###  funnel Embudo de Conversión Detallado")
    st.caption("Muestra cuántos leads avanzan en cada etapa clave del proceso.")
    if df_filtered.empty: st.info("No hay datos filtrados para mostrar el embudo."); return

    total_leads = len(df_filtered)
    # **REVISIÓN**: Asegurarse que se usan los conteos correctos ('Si')
    total_first_contact = (df_filtered['FirstContactStatus'] == "Si").sum()
    total_responded = (df_filtered[COL_RESPONDED] == "Si").sum()
    total_meetings = (df_filtered[COL_MEETING] == "Si").sum()

    funnel_stages = ["Total Leads Generados", "Primer Contacto Realizado", "Respuesta Recibida", "Reunión Agendada"]
    funnel_values = [total_leads, total_first_contact, total_responded, total_meetings]

    # **DEBUG**: Imprimir valores del embudo
    # st.write("Valores del Embudo:", dict(zip(funnel_stages, funnel_values)))

    fig = go.Figure(go.Funnel(
        y = funnel_stages, x = funnel_values,
        textposition = "inside", textinfo = "value+percent previous+percent initial",
        opacity = 0.75, marker = {"color": ["#636EFA", "#FECB52", "#EF553B", "#00CC96"],
                  "line": {"width": [4, 2, 2, 1], "color": ["#4048A5", "#DDAA3F", "#C9452F", "#00A078"]}},
        connector = {"line": {"color": "grey", "dash": "dot", "width": 2}}))
    fig.update_layout(title_text="Embudo Detallado: Leads a Reuniones", title_x=0.5, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Tasas de Conversión por Etapa")
    # **REVISIÓN**: Calcular tasas usando los mismos conteos verificados
    rate_lead_to_contact = calculate_rate(total_first_contact, total_leads)
    rate_contact_to_response = calculate_rate(total_responded, total_first_contact) # Tasa sobre contactados
    rate_response_to_meeting = calculate_rate(total_meetings, total_responded)     # Tasa sobre respondidos
    rate_global_lead_to_meeting = calculate_rate(total_meetings, total_leads)      # Tasa global

    # **DEBUG**: Imprimir tasas calculadas
    # st.write(f"Tasas: Lead->Contacto={rate_lead_to_contact}%, Contacto->Resp={rate_contact_to_response}%, Resp->Reunión={rate_response_to_meeting}%, Global={rate_global_lead_to_meeting}%")

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Lead → Contacto", f"{rate_lead_to_contact:.1f}%", help="Leads con fecha de primer contacto / Total Leads")
    r2.metric("Contacto → Respuesta", f"{rate_contact_to_response:.1f}%", help="Leads con respuesta 'Si' / Leads con fecha de primer contacto")
    r3.metric("Respuesta → Reunión", f"{rate_response_to_meeting:.1f}%", help="Leads con reunión 'Si' / Leads con respuesta 'Si'")
    r4.metric("Lead → Reunión (Global)", f"{rate_global_lead_to_meeting:.1f}%", help="Leads con reunión 'Si' / Total Leads")

def display_time_lag_analysis(df_filtered):
    # (Sin cambios, depende de las columnas Dias_*)
    st.markdown("---"); st.markdown("### ⏱️ Tiempos Promedio del Ciclo (en días)"); st.caption("Calcula el tiempo promedio entre etapas clave.")
    if df_filtered.empty: st.info("No hay datos suficientes."); return
    avg_gen_to_contact = df_filtered['Dias_Gen_a_Contacto'].mean()
    avg_contact_to_meeting = df_filtered['Dias_Contacto_a_Reunion'].mean()
    avg_gen_to_meeting = df_filtered['Dias_Gen_a_Reunion'].mean()
    count_gen_contact = df_filtered['Dias_Gen_a_Contacto'].count(); count_contact_meeting = df_filtered['Dias_Contacto_a_Reunion'].count(); count_gen_meeting = df_filtered['Dias_Gen_a_Reunion'].count()
    f_avg_gen_contact = f"{avg_gen_to_contact:.1f}" if pd.notna(avg_gen_to_contact) else "N/A"
    f_avg_contact_meeting = f"{avg_contact_to_meeting:.1f}" if pd.notna(avg_contact_to_meeting) else "N/A"
    f_avg_gen_meeting = f"{avg_gen_to_meeting:.1f}" if pd.notna(avg_gen_to_meeting) else "N/A"
    t1, t2, t3 = st.columns(3)
    t1.metric("Lead Gen → 1er Contacto", f_avg_gen_contact, help=f"Promedio sobre {count_gen_contact:,} leads.")
    t2.metric("1er Contacto → Reunión", f_avg_contact_meeting, help=f"Promedio sobre {count_contact_meeting:,} reuniones.")
    t3.metric("Lead Gen → Reunión (Total)", f_avg_gen_meeting, help=f"Promedio sobre {count_gen_meeting:,} reuniones.")

def display_segmentation_analysis(df_filtered):
    # (Revisar cálculo de Total_Reuniones)
    st.markdown("---"); st.markdown("### 📊 Desempeño por Segmento (Industria y Nivel)"); st.caption("Compara la Tasa de Conversión Global (Leads a Reuniones) entre segmentos.")
    if df_filtered.empty: st.info("No hay datos."); return

    def create_segment_chart(group_col, title_suffix):
        if group_col not in df_filtered.columns or df_filtered[group_col].nunique() < 1:
            st.caption(f"No hay suficientes datos/variación en '{title_suffix}'."); return

        segment_summary = df_filtered.groupby(group_col).agg(
            Total_Leads=(group_col, 'count'),
            # **REVISIÓN**: Asegurar que cuenta solo 'Si'
            Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
        ).reset_index()
        segment_summary['Tasa_Conversion_Global (%)'] = segment_summary.apply(lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Leads']), axis=1)

        min_leads_threshold = 3
        segment_summary_for_chart = segment_summary[segment_summary['Total_Leads'] >= min_leads_threshold].copy()

        if segment_summary_for_chart.empty:
            st.caption(f"No hay grupos en '{title_suffix}' con ≥ {min_leads_threshold} leads para gráfico.")
            # Mostrar tabla si no hay gráfico
            with st.expander(f"Ver datos por {title_suffix} (todos)"):
                st.dataframe(segment_summary.sort_values('Total_Leads', ascending=False).style.format({'Total_Leads': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Conversion_Global (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)

        else:
            segment_summary_for_chart = segment_summary_for_chart.sort_values('Tasa_Conversion_Global (%)', ascending=False)
            fig = px.bar(segment_summary_for_chart.head(10), x=group_col, y='Tasa_Conversion_Global (%)',
                         title=f"Top 10 {title_suffix} por Tasa Conversión", text='Tasa_Conversion_Global (%)',
                         color='Tasa_Conversion_Global (%)', color_continuous_scale=px.colors.sequential.YlGnBu)
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", xaxis_title=title_suffix, title_x=0.5,
                              yaxis_range=[0, max(10, segment_summary_for_chart['Tasa_Conversion_Global (%)'].max() * 1.1 + 5)])
            st.plotly_chart(fig, use_container_width=True)
            with st.expander(f"Ver tabla completa de datos por {title_suffix}"):
                 st.dataframe(segment_summary.sort_values('Total_Leads', ascending=False).style.format({'Total_Leads': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Conversion_Global (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)

    col1, col2 = st.columns(2)
    with col1: create_segment_chart(COL_INDUSTRY, "Industria")
    with col2: create_segment_chart(COL_MANAGEMENT, "Nivel de Management")

def display_channel_analysis(df_filtered):
    # (Revisar conteos 'Si')
    st.markdown("---"); st.markdown(f"### 📣 Efectividad por Canal de Respuesta ({COL_CHANNEL})"); st.caption("Analiza qué canales generan más respuestas y cuál convierte mejor.")
    if COL_CHANNEL not in df_filtered.columns or COL_RESPONDED not in df_filtered.columns:
        st.info(f"Faltan '{COL_CHANNEL}' o '{COL_RESPONDED}'."); return

    # **REVISIÓN**: Filtrar por Responded == 'Si'
    df_responded = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()
    if df_responded.empty: st.info("No hay leads con respuesta 'Si'."); return
    if df_responded[COL_CHANNEL].nunique() < 1: st.info(f"No hay datos o variación en '{COL_CHANNEL}'."); return

    channel_summary = df_responded.groupby(COL_CHANNEL).agg(
        Total_Respuestas=(COL_CHANNEL, 'count'),
        # **REVISIÓN**: Contar Meeting == 'Si'
        Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index()
    channel_summary['Tasa_Reunion_por_Respuesta (%)'] = channel_summary.apply(lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Respuestas']), axis=1)
    channel_summary_sorted_volume = channel_summary.sort_values('Total_Respuestas', ascending=False)

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_volume = px.bar(channel_summary_sorted_volume, x=COL_CHANNEL, y='Total_Respuestas', title="Volumen Respuestas por Canal", text_auto=True);
        fig_volume.update_layout(yaxis_title="Nº Respuestas", title_x=0.5, xaxis_title="Canal"); st.plotly_chart(fig_volume, use_container_width=True)
    with col_chart2:
        if channel_summary['Total_Reuniones'].sum() > 0:
            channel_summary_sorted_rate = channel_summary.sort_values('Tasa_Reunion_por_Respuesta (%)', ascending=False)
            fig_rate = px.bar(channel_summary_sorted_rate, x=COL_CHANNEL, y='Tasa_Reunion_por_Respuesta (%)', title="Tasa Respuesta -> Reunión por Canal", text='Tasa_Reunion_por_Respuesta (%)', color='Tasa_Reunion_por_Respuesta (%)', color_continuous_scale=px.colors.sequential.OrRd)
            fig_rate.update_traces(texttemplate='%{text:.1f}%', textposition='outside');
            fig_rate.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", title_x=0.5, xaxis_title="Canal", yaxis_range=[0,max(10, channel_summary['Tasa_Reunion_por_Respuesta (%)'].max() * 1.1 + 5)]); st.plotly_chart(fig_rate, use_container_width=True)
        else: st.caption("No hay reuniones desde respuestas para calcular tasa por canal.")

    with st.expander("Ver datos detallados por Canal"):
        st.dataframe(channel_summary_sorted_volume.style.format({'Total_Respuestas': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Reunion_por_Respuesta (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)

def display_enhanced_time_evolution(df_filtered):
    # (Revisar conteos 'Si')
    st.markdown("---"); st.markdown("### 📈 Evolución Temporal Detallada del Embudo (por Mes)"); st.caption("Compara el volumen en cada etapa mes a mes.")
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns or df_filtered['AñoMes'].nunique() < 1:
        st.info("No hay suficientes datos temporales (AñoMes) válidos."); return

    time_summary = df_filtered.groupby('AñoMes').agg(
        Leads_Generados=('AñoMes', 'count'),
        # **REVISIÓN**: Contar 'Si' en cada etapa
        Primer_Contacto=('FirstContactStatus', lambda x: (x == 'Si').sum()),
        Respuestas=(COL_RESPONDED, lambda x: (x == 'Si').sum()),
        Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index().sort_values('AñoMes')

    if not time_summary.empty:
        time_summary_melted = time_summary.melt(id_vars=['AñoMes'], value_vars=['Leads_Generados', 'Primer_Contacto', 'Respuestas', 'Reuniones'], var_name='Etapa', value_name='Cantidad')
        fig = px.line(time_summary_melted, x='AñoMes', y='Cantidad', color='Etapa', title="Evolución Mensual del Embudo", markers=True, labels={"Cantidad": "Número", "AñoMes": "Mes"})
        fig.update_layout(legend_title_text='Etapa', title_x=0.5, yaxis_rangemode='tozero'); st.plotly_chart(fig, use_container_width=True)
        with st.expander("Ver datos de evolución mensual"):
            st.dataframe(time_summary.set_index('AñoMes').style.format("{:,}"), use_container_width=True)
    else: st.caption("No se generaron datos agregados por mes.")

# --- Flujo Principal ---
# (Sin cambios, la lógica de carga, filtro y llamada a display debe funcionar)
# --- Añadir logs ---
# st.write("Iniciando carga y procesamiento...") # Ya estaba
df_pipeline_base = load_and_process_data()

processing_warnings = st.session_state.get('data_load_warnings', [])
if processing_warnings:
    with st.expander("⚠️ Avisos durante la carga/procesamiento", expanded=True):
        for msg in processing_warnings: st.warning(msg)

if df_pipeline_base.empty:
    if not processing_warnings: st.error("Fallo: DataFrame vacío post-procesamiento.")
    st.stop()
else:
    # st.write(f"Datos base: {len(df_pipeline_base)} filas.") # Ya estaba
    start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base.copy())
    df_pipeline_filtered = apply_pipeline_filters(df_pipeline_base, start_date, end_date, industries, managements, meeting_status)
    # st.write(f"Datos filtrados: {len(df_pipeline_filtered)} filas.") # Ya estaba

    # --- Debug Conteos ---
    if not df_pipeline_filtered.empty:
        st.markdown("---")
        st.subheader("DEBUG: Conteos Clave Post-Filtro")
        debug_counts = {
            "Total Filtrado": len(df_pipeline_filtered),
            f"{COL_CONTACTED}='Si'": (df_pipeline_filtered[COL_CONTACTED] == 'Si').sum() if COL_CONTACTED in df_pipeline_filtered else 'N/A',
            "FirstContactStatus='Si'": (df_pipeline_filtered['FirstContactStatus'] == 'Si').sum(),
            f"{COL_RESPONDED}='Si'": (df_pipeline_filtered[COL_RESPONDED] == 'Si').sum() if COL_RESPONDED in df_pipeline_filtered else 'N/A',
            f"{COL_MEETING}='Si'": (df_pipeline_filtered[COL_MEETING] == 'Si').sum() if COL_MEETING in df_pipeline_filtered else 'N/A',
        }
        st.json(debug_counts)
        st.markdown("---")
    # --- Fin Debug ---


    if not df_pipeline_filtered.empty:
        display_enhanced_funnel(df_pipeline_filtered)
        display_time_lag_analysis(df_pipeline_filtered)
        display_segmentation_analysis(df_pipeline_filtered)
        display_channel_analysis(df_pipeline_filtered)
        display_enhanced_time_evolution(df_pipeline_filtered)

        with st.expander("Ver tabla detallada de leads filtrados"):
            st.info(f"Mostrando {len(df_pipeline_filtered):,} leads filtrados.")
            cols_to_show = ["Company", "Full Name", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT, 'Fecha_Principal',
                           COL_FIRST_CONTACT_DATE, COL_CONTACTED, COL_RESPONDED, COL_MEETING, COL_MEETING_DATE,
                           COL_CHANNEL, "LinkedIn URL", 'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']
            cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
            df_display = df_pipeline_filtered[cols_exist].copy()
            for date_col in ['Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]:
                if date_col in df_display.columns:
                     if pd.api.types.is_datetime64_any_dtype(df_display[date_col]):
                         df_display[date_col] = df_display[date_col].dt.strftime('%Y-%m-%d').fillna('N/A')
                     else: df_display[date_col] = df_display[date_col].astype(str).fillna('N/A')
            for time_col in ['Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']:
                 if time_col in df_display.columns:
                     df_display[time_col] = df_display[time_col].apply(lambda x: f"{x:.0f}" if pd.notna(x) else 'N/A')
            st.dataframe(df_display, hide_index=True)
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_pipeline_filtered[cols_exist].to_excel(writer, index=False, sheet_name='Pipeline_Filtrado')
                st.download_button(label="⬇️ Descargar Vista Filtrada (Excel)", data=output.getvalue(),
                                   file_name="pipeline_filtrado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e: st.error(f"Error al generar Excel: {e}")
    else:
        st.info("ℹ️ No se encontraron datos que coincidan con los filtros seleccionados.")




