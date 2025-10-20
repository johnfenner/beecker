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

# --- Configuración y Constantes ---
st.set_page_config(layout="wide", page_title="Pipeline Prospección Válido")
st.title("📈 Pipeline de Prospección (Datos Validados)")
st.markdown("Análisis del embudo basado en la hoja 'Prospects'.")

PIPELINE_SHEET_URL_KEY = "pipeline_october_2025"
PIPELINE_SHEET_NAME = "Prospects"

# Nombres EXACTOS de columnas clave
COL_LEAD_GEN_DATE = "Lead Generated (Date)"
COL_FIRST_CONTACT_DATE = "First Contact Date"
COL_MEETING_DATE = "Meeting Date"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
# COL_CONTACTED = "Contacted?" # No la usaremos directamente, derivaremos de fecha
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"

# Claves de Sesión (usar nombres únicos para evitar conflictos)
SES_PREFIX = "pipe_valido_v1_"
SES_START_DATE_KEY = f"{SES_PREFIX}start_date"
SES_END_DATE_KEY = f"{SES_PREFIX}end_date"
SES_INDUSTRY_KEY = f"{SES_PREFIX}industry"
SES_MANAGEMENT_KEY = f"{SES_PREFIX}management"
SES_MEETING_KEY = f"{SES_PREFIX}meeting"

# --- Funciones de Utilidad ---
@st.cache_data # Cachear la función de parseo
def parse_date_optimized(date_input):
    if pd.isna(date_input): return pd.NaT
    if isinstance(date_input, (datetime.datetime, datetime.date)):
        # Si ya es fecha/datetime, solo normalizar (quitar hora)
        try:
            dt = pd.to_datetime(date_input)
            # Quitar timezone si existe para evitar problemas de comparación
            if dt.tzinfo is not None: dt = dt.tz_localize(None)
            return dt.normalize()
        except Exception:
            return pd.NaT # Si falla, marcar como inválida

    date_str = str(date_input).strip()
    if not date_str: return pd.NaT

    # Intentar formatos específicos primero (más rápido)
    # Prioridad AAAA-MM-DD y DD/MM/AAAA
    formats_to_try = ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats_to_try:
        try:
            # Añadir manejo explícito de hora si existe
            if ' ' in date_str:
                 return pd.to_datetime(date_str.split(' ')[0], format=fmt).normalize()
            else:
                 return pd.to_datetime(date_str, format=fmt).normalize()
        except (ValueError, TypeError):
            continue

    # Si formatos específicos fallan, intentar conversión genérica (más lenta)
    try:
        # errors='coerce' devuelve NaT si no puede parsear
        parsed_date = pd.to_datetime(date_str, errors='coerce', dayfirst=True) # Asumir día primero si ambiguo
        if pd.notna(parsed_date):
            return parsed_date.normalize()
        else: # Probar monthfirst si dayfirst falló
            parsed_date_mf = pd.to_datetime(date_str, errors='coerce', dayfirst=False)
            if pd.notna(parsed_date_mf):
                return parsed_date_mf.normalize()
            else: # Intentar como número de serie Excel como último recurso
                 if re.fullmatch(r'\d+(\.\d+)?', date_str):
                     excel_date_num = float(date_str)
                     if 30000 < excel_date_num < 60000: # Rango típico
                         origin = pd.Timestamp('1899-12-30')
                         parsed_excel = origin + pd.to_timedelta(excel_date_num, unit='D')
                         if pd.Timestamp('1980-01-01') <= parsed_excel <= pd.Timestamp('2050-12-31'):
                             return parsed_excel.normalize()
                 return pd.NaT # Si todo falla
    except Exception:
        return pd.NaT

def clean_yes_no_optimized(val):
    # Manejar directamente booleanos si pandas los interpreta así
    if isinstance(val, bool):
        return "Si" if val else "No"
    # Convertir a string y limpiar para el resto
    cleaned = str(val).strip().lower()
    if cleaned in ['yes', 'sí', 'si', '1', 'true', 'verdadero', 'agendada', 'ok', 'realizada', 'hecho', 'completo', 'listo']:
        return "Si"
    # Todo lo demás (incluyendo '', 'no', 'false', '0', 'nan', etc.) es No
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

# --- Carga y Procesamiento de Datos ---
@st.cache_data(ttl=300)
def load_and_process_data():
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    all_data_loaded = [] # Para depuración
    processing_warnings = []

    try:
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
        # Fetch all values as strings initially to prevent type guessing issues
        all_data_loaded = sheet.get_all_values(value_render_option='UNFORMATTED_VALUE') # Leer valores crudos
        
        if not all_data_loaded or len(all_data_loaded) <= 1:
            raise ValueError("La hoja está vacía o no tiene encabezados.")

        headers = make_unique_headers(all_data_loaded[0])
        df = pd.DataFrame(all_data_loaded[1:], columns=headers)
        
        # Guardar columnas originales para depuración si es necesario
        # st.session_state['original_columns'] = df.columns.tolist()

    except Exception as e:
        st.error(f"❌ Error crítico al cargar datos desde Google Sheet: {e}")
        st.info(f"Verifica URL ('{PIPELINE_SHEET_URL_KEY}'), nombre pestaña ('{PIPELINE_SHEET_NAME}') y permisos.")
        st.stop()

    # --- Procesamiento Post-Carga ---
    
    # Verificar columnas clave
    essential_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING]
    missing_essentials = [col for col in essential_cols if col not in df.columns]
    if missing_essentials:
        st.error(f"Faltan columnas esenciales: {', '.join(missing_essentials)}. Verifica nombres exactos.")
        # Rellenar con N/A para intentar continuar
        for col in missing_essentials: df[col] = pd.NA

    # Convertir fechas (más robusto)
    date_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]
    date_parse_fail_counts = {col: 0 for col in date_cols}
    for col in date_cols:
        if col in df.columns:
            # Guardar NAs originales para comparar
            original_nas = df[col].isna() | (df[col] == '')
            df[col] = df[col].apply(parse_date_optimized)
            new_nas = df[col].isna()
            # Contar solo los que NO eran NA antes pero AHORA sí lo son
            date_parse_fail_counts[col] = (new_nas & ~original_nas).sum()
        else:
            df[col] = pd.NaT # Crear columna NaT si falta

    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True)
    initial_rows = len(df)
    df.dropna(subset=['Fecha_Principal'], inplace=True) # Eliminar filas sin fecha principal válida
    rows_dropped_no_lead_date = initial_rows - len(df)

    if rows_dropped_no_lead_date > 0:
        processing_warnings.append(f"⚠️ {rows_dropped_no_lead_date} filas eliminadas por fecha inválida/vacía en '{COL_LEAD_GEN_DATE}'.")
    for col, count in date_parse_fail_counts.items():
        if count > 0 and col != COL_LEAD_GEN_DATE:
            processing_warnings.append(f"⚠️ {count} fechas no pudieron interpretarse en '{col}'.")
            
    # Limpiar Sí/No
    status_cols = [COL_RESPONDED, COL_MEETING] # Añadir COL_CONTACTED si existe y lo necesitas
    for col in status_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no_optimized)
        else:
            df[col] = "No" # Asumir No si la columna falta

    # Derivar estado de contacto desde la fecha
    if COL_FIRST_CONTACT_DATE in df.columns:
        df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No')
    else:
        df['FirstContactStatus'] = 'No'

    # Limpiar categóricas
    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('No Definido')
            # Asegurar que sea string antes de limpiar
            df[col] = df[col].astype(str).str.strip().replace('', 'No Definido').str.title()
            df[col] = df[col].replace({'N/D': 'No Definido', 'Na': 'No Definido', '-':'No Definido'}) # Limpiar más
        else:
            df[col] = "No Definido"

    # Crear columnas de tiempo
    if not df.empty and 'Fecha_Principal' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Fecha_Principal']):
        df['Año'] = df['Fecha_Principal'].dt.year.astype('Int64', errors='ignore')
        df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64', errors='ignore')
        df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
    else:
        for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA

    # Calcular diferencias de tiempo
    df['Dias_Gen_a_Contacto'] = df.apply(lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_FIRST_CONTACT_DATE)), axis=1)
    df['Dias_Contacto_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get(COL_FIRST_CONTACT_DATE), row.get(COL_MEETING_DATE)), axis=1)
    df['Dias_Gen_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row.get('Fecha_Principal'), row.get(COL_MEETING_DATE)), axis=1)

    # Guardar advertencias para mostrar después
    st.session_state['data_load_warnings'] = processing_warnings

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
        except: pass
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
        st.toast("Filtros reiniciados ✅", icon="🧹")
    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_pipeline_filters, use_container_width=True)
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY], st.session_state[SES_MEETING_KEY])

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

# --- Componentes de Visualización (Sin cambios, deberían funcionar mejor ahora) ---
def display_enhanced_funnel(df_filtered):
    st.markdown("###  funnel Embudo de Conversión Detallado")
    st.caption("Muestra cuántos leads avanzan en cada etapa clave.")
    if df_filtered.empty: st.info("No hay datos filtrados."); return
    total_leads = len(df_filtered)
    total_first_contact = len(df_filtered[df_filtered['FirstContactStatus'] == "Si"])
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])
    funnel_stages = ["Total Leads Generados", "Primer Contacto Realizado", "Respuesta Recibida", "Reunión Agendada"]
    funnel_values = [total_leads, total_first_contact, total_responded, total_meetings]
    fig = go.Figure(go.Funnel(y=funnel_stages, x=funnel_values, textposition="inside", textinfo="value+percent previous+percent initial", opacity=0.7, marker={"color": ["#636EFA", "#FECB52", "#EF553B", "#00CC96"], "line": {"width": [4, 2, 2, 1], "color": ["#4048A5", "#DDAA3F", "#C9452F", "#00A078"]}}, connector={"line": {"color": "grey", "dash": "dot", "width": 2}}))
    fig.update_layout(title_text="Embudo Detallado: Leads a Reuniones", title_x=0.5, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)
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
    st.markdown("---"); st.markdown("### ⏱️ Tiempos Promedio del Ciclo (en días)"); st.caption("Calcula el tiempo promedio entre etapas clave.")
    if df_filtered.empty: st.info("No hay datos suficientes."); return
    avg_gen_to_contact = df_filtered['Dias_Gen_a_Contacto'].dropna().mean()
    avg_contact_to_meeting = df_filtered['Dias_Contacto_a_Reunion'].dropna().mean()
    avg_gen_to_meeting = df_filtered['Dias_Gen_a_Reunion'].dropna().mean()
    count_gen_contact = df_filtered['Dias_Gen_a_Contacto'].count(); count_contact_meeting = df_filtered['Dias_Contacto_a_Reunion'].count(); count_gen_meeting = df_filtered['Dias_Gen_a_Reunion'].count()
    f_avg_gen_contact = f"{avg_gen_to_contact:.1f}" if pd.notna(avg_gen_to_contact) else "N/A"
    f_avg_contact_meeting = f"{avg_contact_to_meeting:.1f}" if pd.notna(avg_contact_to_meeting) else "N/A"
    f_avg_gen_meeting = f"{avg_gen_to_meeting:.1f}" if pd.notna(avg_gen_to_meeting) else "N/A"
    t1, t2, t3 = st.columns(3)
    t1.metric("Lead Gen → 1er Contacto", f_avg_gen_contact, help=f"Promedio sobre {count_gen_contact:,} leads.")
    t2.metric("1er Contacto → Reunión", f_avg_contact_meeting, help=f"Promedio sobre {count_contact_meeting:,} reuniones.")
    t3.metric("Lead Gen → Reunión (Total)", f_avg_gen_meeting, help=f"Promedio sobre {count_gen_meeting:,} reuniones.")

def display_segmentation_analysis(df_filtered):
    st.markdown("---"); st.markdown("### 📊 Desempeño por Segmento (Industria y Nivel)"); st.caption("Compara la Tasa de Conversión Global (Leads a Reuniones) entre segmentos.")
    if df_filtered.empty: st.info("No hay datos."); return
    def create_segment_chart(group_col, title_suffix):
        if group_col not in df_filtered.columns or df_filtered[group_col].nunique() < 2: st.caption(f"No hay suficientes datos en '{group_col}'."); return
        segment_summary = df_filtered.groupby(group_col).agg(Total_Leads=(group_col, 'count'), Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index()
        segment_summary['Tasa_Conversion_Global (%)'] = segment_summary.apply(lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Leads']), axis=1)
        min_leads_threshold = 3
        segment_summary_filtered = segment_summary[segment_summary['Total_Leads'] >= min_leads_threshold].copy()
        show_table = True
        if segment_summary_filtered.empty: st.caption(f"No hay grupos en '{group_col}' con ≥ {min_leads_threshold} leads para gráfico.")
        else:
            segment_summary_filtered = segment_summary_filtered.sort_values('Tasa_Conversion_Global (%)', ascending=False)
            fig = px.bar(segment_summary_filtered.head(10), x=group_col, y='Tasa_Conversion_Global (%)', title=f"Top 10 {title_suffix} por Tasa Conversión", text='Tasa_Conversion_Global (%)', color='Tasa_Conversion_Global (%)', color_continuous_scale=px.colors.sequential.YlGnBu)
            fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside'); fig.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", xaxis_title=title_suffix, title_x=0.5, yaxis_range=[0,max(10, segment_summary_filtered['Tasa_Conversion_Global (%)'].max() * 1.1 + 5)]) # Añadir +5 para espacio
            st.plotly_chart(fig, use_container_width=True)
        if show_table:
            with st.expander(f"Ver datos por {title_suffix} (todos)"): st.dataframe(segment_summary.sort_values('Total_Leads', ascending=False).style.format({'Total_Leads': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Conversion_Global (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)
    col1, col2 = st.columns(2)
    with col1: create_segment_chart(COL_INDUSTRY, "Industria")
    with col2: create_segment_chart(COL_MANAGEMENT, "Nivel de Management")

def display_channel_analysis(df_filtered):
    st.markdown("---"); st.markdown(f"### 📣 Efectividad por Canal de Respuesta ({COL_CHANNEL})"); st.caption("Analiza qué canales generan más respuestas y cuál convierte mejor.")
    if COL_CHANNEL not in df_filtered.columns or COL_RESPONDED not in df_filtered.columns: st.info(f"Faltan '{COL_CHANNEL}' o '{COL_RESPONDED}'."); return
    df_responded = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()
    if df_responded.empty: st.info("No hay leads con respuesta."); return
    if df_responded[COL_CHANNEL].nunique() < 1: st.info(f"No hay datos o variación en '{COL_CHANNEL}'."); return
    channel_summary = df_responded.groupby(COL_CHANNEL).agg(Total_Respuestas=(COL_CHANNEL, 'count'), Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index()
    channel_summary['Tasa_Reunion_por_Respuesta (%)'] = channel_summary.apply(lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Respuestas']), axis=1)
    channel_summary = channel_summary.sort_values('Total_Respuestas', ascending=False)
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        fig_volume = px.bar(channel_summary, x=COL_CHANNEL, y='Total_Respuestas', title="Volumen Respuestas por Canal", text_auto=True); fig_volume.update_layout(yaxis_title="Nº Respuestas", title_x=0.5); st.plotly_chart(fig_volume, use_container_width=True)
    with col_chart2:
        if channel_summary['Total_Reuniones'].sum() > 0:
            fig_rate = px.bar(channel_summary.sort_values('Tasa_Reunion_por_Respuesta (%)', ascending=False), x=COL_CHANNEL, y='Tasa_Reunion_por_Respuesta (%)', title="Tasa Respuesta -> Reunión por Canal", text='Tasa_Reunion_por_Respuesta (%)', color='Tasa_Reunion_por_Respuesta (%)', color_continuous_scale=px.colors.sequential.OrRd)
            fig_rate.update_traces(texttemplate='%{text:.1f}%', textposition='outside'); fig_rate.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", title_x=0.5, yaxis_range=[0,max(10, channel_summary['Tasa_Reunion_por_Respuesta (%)'].max() * 1.1 + 5)]); st.plotly_chart(fig_rate, use_container_width=True)
        else: st.caption("No hay reuniones para calcular tasa por canal.")
    with st.expander("Ver datos por Canal"): st.dataframe(channel_summary.style.format({'Total_Respuestas': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Reunion_por_Respuesta (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)

def display_enhanced_time_evolution(df_filtered):
    st.markdown("---"); st.markdown("### 📈 Evolución Temporal Detallada del Embudo (por Mes)"); st.caption("Compara el volumen en cada etapa mes a mes.")
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns or df_filtered['AñoMes'].nunique() < 1: st.info("No hay datos."); return
    time_summary = df_filtered.groupby('AñoMes').agg(Leads_Generados=('AñoMes', 'count'), Primer_Contacto=('FirstContactStatus', lambda x: (x == 'Si').sum()), Respuestas=(COL_RESPONDED, lambda x: (x == 'Si').sum()), Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index().sort_values('AñoMes')
    if not time_summary.empty:
        time_summary_melted = time_summary.melt(id_vars=['AñoMes'], value_vars=['Leads_Generados', 'Primer_Contacto', 'Respuestas', 'Reuniones'], var_name='Etapa', value_name='Cantidad')
        fig = px.line(time_summary_melted, x='AñoMes', y='Cantidad', color='Etapa', title="Evolución Mensual del Embudo", markers=True, labels={"Cantidad": "Número", "AñoMes": "Mes"})
        fig.update_layout(legend_title_text='Etapa', title_x=0.5, yaxis_rangemode='tozero'); st.plotly_chart(fig, use_container_width=True)
        with st.expander("Ver datos mensuales"): st.dataframe(time_summary.set_index('AñoMes').style.format("{:,}"), use_container_width=True)
    else: st.caption("No hay datos agregados por mes.")

# --- Flujo Principal ---
df_pipeline_base = load_and_process_data()

# Mostrar advertencias de procesamiento si existen
processing_warnings = st.session_state.get('data_load_warnings', [])
if processing_warnings:
    with st.expander("⚠️ Avisos durante la carga/procesamiento"):
        for msg in processing_warnings: st.warning(msg)

if df_pipeline_base.empty:
    st.error("Fallo: El DataFrame está vacío tras la carga.")
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
