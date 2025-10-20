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

st.set_page_config(layout="wide", page_title="Pipeline de Prospección Detallado")
st.title("📈 Pipeline de Prospección Detallado (Oct 2025)")
st.markdown("Análisis avanzado del embudo, tiempos de conversión y segmentación.")

# --- Constantes ---
PIPELINE_SHEET_URL_KEY = "pipeline_october_2025"
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/..."
PIPELINE_SHEET_NAME = "Prospects"

COL_LEAD_GEN_DATE = "Lead Generated (Date)"
COL_FIRST_CONTACT_DATE = "First Contact Date"
COL_MEETING_DATE = "Meeting Date"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_CONTACTED = "Contacted?"
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"

SES_START_DATE_KEY = "pipeline_page_start_date_v4" # Incrementar versión
SES_END_DATE_KEY = "pipeline_page_end_date_v4"
SES_INDUSTRY_KEY = "pipeline_page_industry_v4"
SES_MANAGEMENT_KEY = "pipeline_page_management_v4"
SES_MEETING_KEY = "pipeline_page_meeting_v4"

# --- Funciones de Utilidad ---
def parse_date_robustly(date_val):
    if pd.isna(date_val): return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)):
        try:
             # Intentar normalizar y quitar timezone si existe
             dt = pd.to_datetime(date_val)
             if dt.tzinfo is not None: dt = dt.tz_localize(None)
             return dt.normalize()
        except: return pd.to_datetime(date_val, errors='coerce') # Fallback

    date_str = str(date_val).strip()
    if not date_str: return pd.NaT

    # Priorizar D/M/YYYY y M/D/YYYY
    formats_to_try = [
        "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y",
        "%d/%m/%Y %H:%M", "%m/%d/%Y %H:%M",
        "%d/%m/%Y %H:%M:%S", "%m/%d/%Y %H:%M:%S",
        "%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S",
        "%d-%b-%Y", "%b %d, %Y", "%Y%m%d"
    ]
    for fmt in formats_to_try:
        try: return pd.to_datetime(date_str, format=fmt).normalize()
        except (ValueError, TypeError): continue

    # Intento genérico final, probando dayfirst=True y False
    try:
        parsed_date_dayfirst = pd.to_datetime(date_str, errors='coerce', dayfirst=True)
        if pd.notna(parsed_date_dayfirst): return parsed_date_dayfirst.normalize()

        parsed_date_monthfirst = pd.to_datetime(date_str, errors='coerce', dayfirst=False)
        if pd.notna(parsed_date_monthfirst): return parsed_date_monthfirst.normalize()

        # Manejo de números de Excel
        if re.fullmatch(r'\d+(\.\d+)?', date_str):
             excel_date_num = float(date_str)
             if 30000 < excel_date_num < 60000: # Rango razonable para fechas Excel
                 origin = pd.Timestamp('1899-12-30')
                 parsed_excel_date = origin + pd.to_timedelta(excel_date_num, unit='D')
                 if pd.Timestamp('1980-01-01') <= parsed_excel_date <= pd.Timestamp('2050-12-31'):
                      return parsed_excel_date.normalize()
        return pd.NaT
    except Exception:
        return pd.NaT


def clean_yes_no(val):
    original_cleaned = str(val).strip()
    if not original_cleaned: return "No"
    if original_cleaned.lower() in ['yes', 'sí', 'si', '1', 'true', 'agendada', 'ok', 'realizada', 'hecho', 'completo', 'listo', 'verdadero']:
        return "Si"
    return "No"

def calculate_rate(numerator, denominator, round_to=1):
    num = pd.to_numeric(numerator, errors='coerce')
    den = pd.to_numeric(denominator, errors='coerce')
    if pd.isna(den) or den == 0 or pd.isna(num): return 0.0
    rate = (num / den) * 100
    if np.isinf(rate) or np.isnan(rate): return 0.0
    return round(rate, round_to)

def calculate_time_diff(date1, date2):
    d1 = pd.to_datetime(date1, errors='coerce')
    d2 = pd.to_datetime(date2, errors='coerce')
    if pd.notna(d1) and pd.notna(d2) and d2 >= d1:
        return (d2 - d1).days
    return np.nan

def make_unique_headers(headers_list):
    counts = Counter(); new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped: h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1: new_headers.append(h_stripped)
        else: new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

@st.cache_data(ttl=300)
def load_pipeline_data():
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    df = pd.DataFrame()
    debug_messages = [] # Para acumular advertencias
    
    try:
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1: raise ValueError("Hoja vacía o sin encabezados.")
        
        headers = make_unique_headers(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)
        # Mensaje de éxito eliminado

    except Exception as e_gspread:
        st.error(f"❌ Error crítico al cargar datos desde Google Sheet: {e_gspread}")
        st.info(f"Verifica la URL ('{PIPELINE_SHEET_URL_KEY}'), nombre de pestaña ('{PIPELINE_SHEET_NAME}') y permisos de '{st.secrets.get('gcp_service_account',{}).get('client_email','EMAIL_NO_ENCONTRADO')}'.")
        st.stop()

    essential_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE, COL_RESPONDED, COL_MEETING, COL_INDUSTRY, COL_MANAGEMENT]
    missing_essentials = [col for col in essential_cols if col not in df.columns]
    if missing_essentials:
        st.error(f"Faltan columnas esenciales: {', '.join(missing_essentials)}. Verifica nombres.")
        for col in missing_essentials: df[col] = pd.NA

    date_cols_to_parse = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]
    parse_errors = {col: 0 for col in date_cols_to_parse}
    
    for col in date_cols_to_parse:
        if col in df.columns:
            original_dates = df[col].copy()
            df[col] = df[col].apply(parse_date_robustly)
            parse_errors[col] = df[col].isna().sum() - original_dates.isna().sum() # Contar nuevos NAs
        else:
             df[col] = pd.NaT

    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True)
    initial_rows = len(df)
    
    # Manejar NAs en Fecha_Principal ANTES de eliminar
    fecha_principal_na_count_before_drop = df['Fecha_Principal'].isna().sum()
    
    df.dropna(subset=['Fecha_Principal'], inplace=True)
    rows_dropped = initial_rows - len(df)
    
    # Solo mostrar advertencia si se eliminaron filas O si hubo errores de parseo iniciales
    if rows_dropped > 0 or any(v > 0 for v in parse_errors.values()):
         debug_messages.append(f"⚠️ Se eliminaron {rows_dropped} filas por fecha inválida en '{COL_LEAD_GEN_DATE}'.")
         for col, errors in parse_errors.items():
              if errors > 0 and col != COL_LEAD_GEN_DATE : # Evitar doble reporte para Lead Gen Date
                  debug_messages.append(f"⚠️ {errors} fechas no pudieron interpretarse en '{col}'.")
    
    # Guardar mensajes para mostrar en expander
    st.session_state['data_load_debug_messages'] = debug_messages

    status_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in status_cols:
        if col in df.columns: df[col] = df[col].apply(clean_yes_no)
        else: df[col] = "No"
            
    if COL_FIRST_CONTACT_DATE in df.columns:
        df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No')
    else: df['FirstContactStatus'] = 'No'

    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('No Definido')
            df[col] = df[col].astype(str).str.strip().replace('', 'No Definido').str.title()
            df[col] = df[col].replace({'N/D': 'No Definido', 'Na': 'No Definido'})
        else: df[col] = "No Definido"

    if not df.empty:
        df['Año'] = df['Fecha_Principal'].dt.year.astype('Int64', errors='ignore')
        df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64', errors='ignore')
        df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
    else:
        for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA

    df['Dias_Gen_a_Contacto'] = df.apply(lambda row: calculate_time_diff(row['Fecha_Principal'], row.get(COL_FIRST_CONTACT_DATE)), axis=1)
    df['Dias_Contacto_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get(COL_FIRST_CONTACT_DATE), row.get(COL_MEETING_DATE)), axis=1)
    df['Dias_Gen_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row['Fecha_Principal'], row.get(COL_MEETING_DATE)), axis=1)
            
    return df

# --- Filtros (Sin cambios) ---
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
        except: min_date, max_date = None, None
    
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

    st.sidebar.subheader("👥 Por Atributo de Lead")
    def create_multiselect(col_name, label, key):
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            unique_vals = sorted(df_options[col_name].astype(str).unique())
            options.extend([val for val in unique_vals if val != "No Definido"])
            if "No Definido" in unique_vals: options.append("No Definido")
        current_state = st.session_state.get(key, ["– Todos –"])
        valid_state = [s for s in current_state if s in options]
        if not valid_state or not options: valid_state = ["– Todos –"]
        st.session_state[key] = valid_state
        st.sidebar.multiselect(label, options, key=key)

    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)
    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)

    def clear_pipeline_filters():
        for key, val in default_filters.items(): st.session_state[key] = val
        st.toast("Filtros del Pipeline reiniciados ✅", icon="🧹")
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
        if start_dt_norm: mask &= (df_f['Fecha_Principal'] >= start_dt_norm)
        if end_dt_norm: mask &= (df_f['Fecha_Principal'] <= end_dt_norm)
        df_f = df_f[mask]
    if industries and "– Todos –" not in industries and COL_INDUSTRY in df_f.columns:
        df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
    if managements and "– Todos –" not in managements and COL_MANAGEMENT in df_f.columns:
        df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]
    if meeting_status != "– Todos –" and COL_MEETING in df_f.columns:
        df_f = df_f[df_f[COL_MEETING] == meeting_status]
    return df_f

# --- Componentes de Visualización (Sin cambios) ---
def display_enhanced_funnel(df_filtered):
    st.markdown("###  funnel Embudo de Conversión Detallado")
    st.caption("Muestra cuántos leads avanzan en cada etapa clave del proceso.")
    if df_filtered.empty: st.info("No hay datos filtrados para mostrar el embudo."); return
    total_leads = len(df_filtered)
    total_first_contact = len(df_filtered[df_filtered['FirstContactStatus'] == "Si"])
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])
    funnel_stages = ["Total Leads Generados", "Primer Contacto Realizado", "Respuesta Recibida", "Reunión Agendada"]
    funnel_values = [total_leads, total_first_contact, total_responded, total_meetings]
    fig = go.Figure(go.Funnel(y=funnel_stages, x=funnel_values, textposition="inside", textinfo="value+percent previous+percent initial", opacity=0.7, marker={"color": ["#8A2BE2", "#5A639C", "#7B8FA1", "#9BABB8"], "line": {"width": [4, 2, 2, 1], "color": ["#6A1B9A", "#4A528A", "#6B7F91", "#8B9AAA"]}}, connector={"line": {"color": "grey", "dash": "dot", "width": 2}}))
    fig.update_layout(title_text="Embudo Detallado: Leads a Reuniones", title_x=0.5, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("#### Tasas de Conversión por Etapa")
    rate_lead_to_contact = calculate_rate(total_first_contact, total_leads)
    rate_contact_to_response = calculate_rate(total_responded, total_first_contact)
    rate_response_to_meeting = calculate_rate(total_meetings, total_responded)
    rate_global_lead_to_meeting = calculate_rate(total_meetings, total_leads)
    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Lead → Contacto", f"{rate_lead_to_contact:.1f}%", help="Porcentaje de leads totales a los que se les registró un primer contacto.")
    r2.metric("Contacto → Respuesta", f"{rate_contact_to_response:.1f}%", help="De los leads contactados, porcentaje que respondieron.")
    r3.metric("Respuesta → Reunión", f"{rate_response_to_meeting:.1f}%", help="De los leads que respondieron, porcentaje que agendó reunión.")
    r4.metric("Lead → Reunión (Global)", f"{rate_global_lead_to_meeting:.1f}%", help="Porcentaje de leads totales que terminaron en una reunión agendada.")

def display_time_lag_analysis(df_filtered):
    st.markdown("---"); st.markdown("### ⏱️ Tiempos Promedio del Ciclo (en días)"); st.caption("Calcula el tiempo promedio entre etapas clave para los leads que completaron esas etapas.")
    if df_filtered.empty: st.info("No hay datos suficientes."); return
    avg_gen_to_contact = df_filtered['Dias_Gen_a_Contacto'].dropna().mean()
    avg_contact_to_meeting = df_filtered['Dias_Contacto_a_Reunion'].dropna().mean()
    avg_gen_to_meeting = df_filtered['Dias_Gen_a_Reunion'].dropna().mean()
    count_gen_contact = df_filtered['Dias_Gen_a_Contacto'].count(); count_contact_meeting = df_filtered['Dias_Contacto_a_Reunion'].count(); count_gen_meeting = df_filtered['Dias_Gen_a_Reunion'].count()
    f_avg_gen_contact = f"{avg_gen_to_contact:.1f}" if pd.notna(avg_gen_to_contact) else "N/A"
    f_avg_contact_meeting = f"{avg_contact_to_meeting:.1f}" if pd.notna(avg_contact_to_meeting) else "N/A"
    f_avg_gen_meeting = f"{avg_gen_to_meeting:.1f}" if pd.notna(avg_gen_to_meeting) else "N/A"
    t1, t2, t3 = st.columns(3)
    t1.metric("Lead Gen → 1er Contacto", f_avg_gen_contact, help=f"Promedio calculado sobre {count_gen_contact:,} leads.")
    t2.metric("1er Contacto → Reunión", f_avg_contact_meeting, help=f"Promedio calculado sobre {count_contact_meeting:,} reuniones.")
    t3.metric("Lead Gen → Reunión (Total)", f_avg_gen_meeting, help=f"Promedio calculado sobre {count_gen_meeting:,} reuniones.")

def display_segmentation_analysis(df_filtered):
    st.markdown("---"); st.markdown("### 📊 Desempeño por Segmento (Industria y Nivel)"); st.caption("Compara la Tasa de Conversión Global (Leads Generados a Reuniones Agendadas) entre los principales segmentos.")
    if df_filtered.empty: st.info("No hay datos para analizar por segmento."); return
    def create_segment_chart(group_col, title_suffix):
        if group_col not in df_filtered.columns or df_filtered[group_col].nunique() < 2: st.caption(f"No hay suficientes datos o variaciones en '{group_col}'."); return
        segment_summary = df_filtered.groupby(group_col).agg(Total_Leads=(group_col, 'count'), Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index()
        segment_summary['Tasa_Conversion_Global (%)'] = segment_summary.apply(lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Leads']), axis=1)
        min_leads_threshold = 3
        segment_summary_filtered = segment_summary[segment_summary['Total_Leads'] >= min_leads_threshold].copy()
        show_table = True # Mostrar tabla siempre
        if segment_summary_filtered.empty: st.caption(f"No hay grupos en '{group_col}' con al menos {min_leads_threshold} leads para mostrar gráfico.")
        else:
            segment_summary_filtered = segment_summary_filtered.sort_values('Tasa_Conversion_Global (%)', ascending=False)
            fig = px.bar(segment_summary_filtered.head(10), x=group_col, y='Tasa_Conversion_Global (%)', title=f"Top 10 {title_suffix} por Tasa Conversión", text='Tasa_Conversion_Global (%)', color='Tasa_Conversion_Global (%)', color_continuous_scale=px.colors.sequential.YlGnBu)
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside'); fig.update_layout(yaxis_title="Tasa Conversión (%)", yaxis_ticksuffix="%", xaxis_title=title_suffix, title_x=0.5, yaxis_range=[0,105])
            st.plotly_chart(fig, use_container_width=True)
        if show_table:
            with st.expander(f"Ver datos por {title_suffix} (todos)"):
                st.dataframe(segment_summary.sort_values('Total_Leads', ascending=False).style.format({'Total_Leads': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Conversion_Global (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)
    col1, col2 = st.columns(2)
    with col1: create_segment_chart(COL_INDUSTRY, "Industria")
    with col2: create_segment_chart(COL_MANAGEMENT, "Nivel de Management")

def display_channel_analysis(df_filtered):
    st.markdown("---"); st.markdown(f"### 📣 Efectividad por Canal de Respuesta ({COL_CHANNEL})"); st.caption("Analiza qué canales generan más respuestas y cuál convierte mejor esas respuestas en reuniones.")
    if COL_CHANNEL not in df_filtered.columns or COL_RESPONDED not in df_filtered.columns: st.info(f"Faltan '{COL_CHANNEL}' o '{COL_RESPONDED}'."); return
    df_responded = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()
    if df_responded.empty: st.info("No hay leads con respuesta registrada."); return
    if df_responded[COL_CHANNEL].nunique() < 1: st.info(f"No hay suficientes datos o variación en '{COL_CHANNEL}'."); return
    channel_summary = df_responded.groupby(COL_CHANNEL).agg(Total_Respuestas=(COL_CHANNEL, 'count'), Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index()
    channel_summary['Tasa_Reunion_por_Respuesta (%)'] = channel_summary.apply(lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Respuestas']), axis=1)
    channel_summary = channel_summary.sort_values('Total_Respuestas', ascending=False)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_volume = px.bar(channel_summary, x=COL_CHANNEL, y='Total_Respuestas', title="Volumen de Respuestas por Canal", text_auto=True); fig_volume.update_layout(yaxis_title="Número de Respuestas", title_x=0.5); st.plotly_chart(fig_volume, use_container_width=True)
    with col_chart2:
        if channel_summary['Total_Reuniones'].sum() > 0:
            fig_rate = px.bar(channel_summary.sort_values('Tasa_Reunion_por_Respuesta (%)', ascending=False), x=COL_CHANNEL, y='Tasa_Reunion_por_Respuesta (%)', title="Tasa Respuesta -> Reunión por Canal", text='Tasa_Reunion_por_Respuesta (%)', color='Tasa_Reunion_por_Respuesta (%)', color_continuous_scale=px.colors.sequential.OrRd)
            fig_rate.update_traces(texttemplate='%{text:.1f}%', textposition='outside'); fig_rate.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", title_x=0.5, yaxis_range=[0,105]); st.plotly_chart(fig_rate, use_container_width=True)
        else: st.caption("No hay reuniones para calcular tasa por canal.")
    with st.expander("Ver datos por Canal de Respuesta"): st.dataframe(channel_summary.style.format({'Total_Respuestas': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Reunion_por_Respuesta (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)

def display_enhanced_time_evolution(df_filtered):
    st.markdown("---"); st.markdown("### 📈 Evolución Temporal Detallada del Embudo (por Mes)"); st.caption("Compara la generación de leads con el avance en las etapas clave mes a mes.")
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns or df_filtered['AñoMes'].nunique() < 1: st.info("No hay datos suficientes."); return
    time_summary = df_filtered.groupby('AñoMes').agg(Leads_Generados=('AñoMes', 'count'), Primer_Contacto=('FirstContactStatus', lambda x: (x == 'Si').sum()), Respuestas=(COL_RESPONDED, lambda x: (x == 'Si').sum()), Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index().sort_values('AñoMes')
    if not time_summary.empty:
        time_summary_melted = time_summary.melt(id_vars=['AñoMes'], value_vars=['Leads_Generados', 'Primer_Contacto', 'Respuestas', 'Reuniones'], var_name='Etapa', value_name='Cantidad')
        fig = px.line(time_summary_melted, x='AñoMes', y='Cantidad', color='Etapa', title="Evolución Mensual del Embudo", markers=True, labels={"Cantidad": "Número", "AñoMes": "Mes"})
        fig.update_layout(legend_title_text='Etapa', title_x=0.5, yaxis_rangemode='tozero'); st.plotly_chart(fig, use_container_width=True)
        with st.expander("Ver datos de evolución mensual"): st.dataframe(time_summary.set_index('AñoMes').style.format("{:,}"), use_container_width=True)
    else: st.caption("No hay datos agregados por mes.")

# --- Flujo Principal ---
df_pipeline_base = load_pipeline_data()

# Mostrar mensajes de depuración acumulados
debug_msgs = st.session_state.get('data_load_debug_messages', [])
if debug_msgs:
    with st.expander("⚠️ Avisos durante la carga de datos"):
        for msg in debug_msgs: st.warning(msg)

if df_pipeline_base.empty:
    st.error("Fallo crítico: El DataFrame del Pipeline está vacío tras la carga.")
else:
    start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base.copy())
    df_pipeline_filtered = apply_pipeline_filters(df_pipeline_base, start_date, end_date, industries, managements, meeting_status)

    if not df_pipeline_filtered.empty:
        display_enhanced_funnel(df_pipeline_filtered)
        display_time_lag_analysis(df_pipeline_filtered)
        display_segmentation_analysis(df_pipeline_filtered)
        display_channel_analysis(df_pipeline_filtered)
        display_enhanced_time_evolution(df_pipeline_filtered)

        with st.expander("Ver tabla detallada de leads filtrados"):
            cols_to_show = ["Full Name", "Company", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT, 'Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, COL_MEETING_DATE, COL_CHANNEL, "LinkedIn URL", 'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']
            cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
            df_display = df_pipeline_filtered[cols_exist].copy()
            for date_col in ['Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]:
                if date_col in df_display.columns: df_display[date_col] = df_display[date_col].dt.strftime('%Y-%m-%d').fillna('N/A')
            for time_col in ['Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']:
                 if time_col in df_display.columns: df_display[time_col] = df_display[time_col].apply(lambda x: f"{x:.0f}" if pd.notna(x) else 'N/A')
            st.dataframe(df_display, hide_index=True)
    else:
        st.info("ℹ️ No se encontraron datos que coincidan con los filtros seleccionados.")

st.markdown("---")

