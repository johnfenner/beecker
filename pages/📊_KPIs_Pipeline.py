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
st.set_page_config(layout="wide", page_title="Pipeline Prospección v6") # Versión Final
st.title("📈 Pipeline de Prospección (Datos Validados)")
st.markdown("Análisis del embudo basado en la hoja 'Prospects'.")

PIPELINE_SHEET_URL_KEY = "pipeline_sheet_url_oct_2025"
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/1MYj_43IFIzrg8tQxG9LUfT6-V0O3lg8TuQUveWhEVAM/edit?gid=971436223#gid=971436223"
PIPELINE_SHEET_NAME = "Prospects"

COL_LEAD_GEN_DATE = "Lead Generated (Date)"
COL_FIRST_CONTACT_DATE = "First Contact Date"
COL_MEETING_DATE = "Meeting Date"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"
COL_CONTACTED = "Contacted?"

SES_PREFIX = "pipe_v6_"
SES_START_DATE_KEY = f"{SES_PREFIX}start_date"
SES_END_DATE_KEY = f"{SES_PREFIX}end_date"
SES_INDUSTRY_KEY = f"{SES_PREFIX}industry"
SES_MANAGEMENT_KEY = f"{SES_PREFIX}management"
SES_MEETING_KEY = f"{SES_PREFIX}meeting"

# --- Funciones de Utilidad (Mantenemos las versiones funcionales) ---

@st.cache_data(ttl=300)
def parse_date_optimized(date_input):
    if pd.isna(date_input): return pd.NaT
    if isinstance(date_input, (bool, np.bool_)): return pd.NaT
    if isinstance(date_input, (datetime.datetime, datetime.date)):
        try:
             dt = pd.to_datetime(date_input); dt = dt.tz_localize(None) if dt.tzinfo is not None else dt
             return dt.normalize()
        except Exception: pass
    date_str = str(date_input).strip();
    if not date_str or date_str.lower() in ['true', 'false']: return pd.NaT
    formats_to_try = ["%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y", "%m-%d-%Y", "%Y-%m-%d"]
    for fmt in formats_to_try:
        try: return pd.to_datetime(date_str.split(' ')[0], format=fmt, errors='raise').normalize()
        except (ValueError, TypeError): pass
    if re.fullmatch(r'\d+(\.\d+)?', date_str):
        try:
             excel_date_num = float(date_str);
             if 30000 < excel_date_num < 60000:
                 origin = pd.Timestamp('1899-12-30'); parsed_excel = origin + pd.to_timedelta(excel_date_num, unit='D')
                 if pd.Timestamp('1980-01-01') <= parsed_excel <= pd.Timestamp('2050-12-31'): return parsed_excel.normalize()
        except Exception: pass
    try:
        parsed_generic = pd.to_datetime(date_str, errors='coerce', dayfirst=True);
        if pd.notna(parsed_generic): return parsed_generic.normalize()
    except Exception: pass
    return pd.NaT

@st.cache_data
def clean_yes_no_optimized(val):
    if pd.isna(val): return "No"
    if isinstance(val, (bool, np.bool_)): return "Si" if val else "No"
    cleaned = str(val).strip().lower()
    if cleaned == 'true': return "Si"
    affirmative = ['yes', 'sí', 'si', '1', 'verdadero', 'agendada', 'ok', 'realizada']
    if cleaned in affirmative: return "Si"
    return "No"

# **REVISIÓN CRUCIAL: Función Calculate Rate**
# Asegurémonos de que devuelve un float estándar, no un tipo numpy.
@st.cache_data
def calculate_rate(numerator, denominator, round_to=1):
    num = pd.to_numeric(numerator, errors='coerce')
    den = pd.to_numeric(denominator, errors='coerce')
    if pd.isna(den) or den == 0 or pd.isna(num): return 0.0 # Devuelve float 0.0
    rate = (num / den) * 100
    if np.isinf(rate) or np.isnan(rate): return 0.0 # Devuelve float 0.0
    # Redondear y devolver como float estándar
    return float(round(rate, round_to))

@st.cache_data
def calculate_time_diff(date1, date2):
    d1 = pd.to_datetime(date1, errors='coerce'); d2 = pd.to_datetime(date2, errors='coerce')
    if pd.notna(d1) and pd.notna(d2) and d2 >= d1: return (d2 - d1).days
    return np.nan # Devolver NaN estándar

def make_unique_headers(headers_list):
    counts = Counter(); new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"; h_stripped = h_stripped if h_stripped else "Columna_Vacia"
        counts[h_stripped] += 1; new_headers.append(h_stripped if counts[h_stripped] == 1 else f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

# --- Carga y Procesamiento (Mantenemos la versión funcional) ---
@st.cache_data(ttl=300)
def load_and_process_data():
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL); processing_warnings = []; df = pd.DataFrame()
    try:
        creds = st.secrets["gcp_service_account"]; client = gspread.service_account_from_dict(creds)
        workbook = client.open_by_url(sheet_url); sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
        all_data_loaded = sheet.get_all_values(value_render_option='FORMATTED_VALUE') # Leer como texto formateado
        if not all_data_loaded or len(all_data_loaded) <= 1: raise ValueError(f"Hoja '{PIPELINE_SHEET_NAME}' vacía.")
        headers = make_unique_headers(all_data_loaded[0]); df = pd.DataFrame(all_data_loaded[1:], columns=headers)
    except gspread.exceptions.APIError as e:
         if "This operation is not supported" in str(e): st.error("❌ Error: Archivo es .xlsx."); st.warning("Solución: 'Archivo' -> 'Guardar como Hoja de Google'. Comparte la *nueva* hoja y actualiza URL."); st.stop()
         else: st.error(f"❌ Error API Google: {e}"); st.info(f"Verifica URL, nombre pestaña ('{PIPELINE_SHEET_NAME}') y permisos."); st.stop()
    except Exception as e: st.error(f"❌ Error crítico cargando: {e}"); st.info(f"Verifica URL ('{PIPELINE_SHEET_URL_KEY}'), nombre pestaña y permisos."); st.stop()
    if df.empty: st.error("DataFrame vacío post-carga."); st.stop()

    essential_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, COL_CONTACTED]; missing = [c for c in essential_cols if c not in df.columns]
    if missing: st.error(f"Faltan columnas: {', '.join(missing)}."); [df.update({c: pd.NA}) for c in missing] # Corrección: usar df.update o df[c] = pd.NA

    date_cols = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]; fail_counts = {c: 0 for c in date_cols}
    for col in date_cols:
        if col in df.columns:
            non_empty = df[col].apply(lambda x: pd.notna(x) and str(x).strip() != "" and str(x).lower() not in ['true', 'false'])
            df[col] = df[col].apply(parse_date_optimized); failed = df[col].isna() & non_empty; fail_counts[col] = failed.sum()
        else: df[col] = pd.NaT
    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True); initial_rows = len(df)
    df.dropna(subset=['Fecha_Principal'], inplace=True); dropped = initial_rows - len(df)
    if dropped > 0: processing_warnings.append(f"⚠️ **{dropped:,} filas eliminadas** por '{COL_LEAD_GEN_DATE}' inválida.")
    for col, count in fail_counts.items():
        if count > 0 : processing_warnings.append(f"⚠️ {count} valores en '{col}' no parseados como fecha.")
    st.session_state['data_load_warnings'] = processing_warnings

    status_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING]
    for col in status_cols: df[col] = df[col].apply(clean_yes_no_optimized) if col in df.columns else "No"
    df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No') if COL_FIRST_CONTACT_DATE in df.columns else 'No'

    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    na_strings = {'N/A': 'No Definido', 'Na': 'No Definido', 'N/D': 'No Definido', '-': 'No Definido', 'False': 'No Definido', 'True': 'No Definido'}
    for col in cat_cols:
        if col in df.columns: df[col] = df[col].fillna('No Definido').astype(str).str.strip().str.title().replace('', 'No Definido').replace(na_strings)
        else: df[col] = "No Definido"

    if not df.empty and 'Fecha_Principal' in df.columns and pd.api.types.is_datetime64_any_dtype(df['Fecha_Principal']):
        try: df['Año'] = df['Fecha_Principal'].dt.year.astype('Int64'); df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64'); df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
        except Exception as e: st.warning(f"Error columnas tiempo: {e}"); [df.update({c: pd.NA}) for c in ['Año', 'NumSemana', 'AñoMes']] # Corrección: usar df.update o df[c] = pd.NA
    else: [df.update({c: pd.NA}) for c in ['Año', 'NumSemana', 'AñoMes']] # Corrección: usar df.update o df[c] = pd.NA

    df['Dias_Gen_a_Contacto'] = df.apply(lambda r: calculate_time_diff(r.get('Fecha_Principal'), r.get(COL_FIRST_CONTACT_DATE)), axis=1)
    df['Dias_Contacto_a_Reunion'] = df.apply(lambda r: calculate_time_diff(r.get(COL_FIRST_CONTACT_DATE), r.get(COL_MEETING_DATE)), axis=1)
    df['Dias_Gen_a_Reunion'] = df.apply(lambda r: calculate_time_diff(r.get('Fecha_Principal'), r.get(COL_MEETING_DATE)), axis=1)
    return df

# --- Filtros (Sin cambios) ---
def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")
    defaults = {SES_START_DATE_KEY: None, SES_END_DATE_KEY: None, SES_INDUSTRY_KEY: ["– Todos –"], SES_MANAGEMENT_KEY: ["– Todos –"], SES_MEETING_KEY: "– Todos –"}
    for k, v in defaults.items(): st.session_state.setdefault(k, v)
    st.sidebar.subheader("🗓️ Por Fecha Lead Gen")
    min_d, max_d = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        try: min_d, max_d = df_options["Fecha_Principal"].min().date(), df_options["Fecha_Principal"].max().date()
        except Exception as e: st.sidebar.warning(f"Error fechas min/max: {e}")
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", value=st.session_state[SES_START_DATE_KEY], key=SES_START_DATE_KEY, min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
    c2.date_input("Hasta", value=st.session_state[SES_END_DATE_KEY], key=SES_END_DATE_KEY, min_value=min_d, max_value=max_d, format="DD/MM/YYYY")
    st.sidebar.subheader("👥 Por Atributo")
    def create_ms(col, lbl, key):
        opts = ["– Todos –"];
        if col in df_options.columns and not df_options[col].dropna().empty:
            unique = sorted([v for v in df_options[col].astype(str).unique() if v != 'No Definido']); opts.extend(unique)
            if 'No Definido' in df_options[col].astype(str).unique(): opts.append('No Definido')
        state = st.session_state.get(key, ["– Todos –"]); valid = [s for s in state if s in opts]
        if not valid or (len(valid)==1 and valid[0] not in opts): valid = ["– Todos –"]
        st.session_state[key] = valid # Actualizar estado
        st.sidebar.multiselect(lbl, opts, key=f"widget_{key}", default=valid) # Usar default
    create_ms(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY); create_ms(COL_MANAGEMENT, "Nivel Management", SES_MANAGEMENT_KEY)
    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)
    def clear_filters(): [st.session_state.update({k: v}) for k, v in defaults.items()]; st.toast("Filtros reiniciados ✅", icon="🧹") # Corrección: usar update
    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_filters, use_container_width=True)
    return (st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY], st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY], st.session_state[SES_MEETING_KEY])

# --- Aplicar Filtros (Sin cambios) ---
def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    df_f = df.copy();
    if df_f.empty: return df_f
    if "Fecha_Principal" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f['Fecha_Principal']):
        start = pd.to_datetime(start_dt).normalize() if start_dt else None; end = pd.to_datetime(end_dt).normalize() if end_dt else None
        mask = pd.Series(True, index=df_f.index); valid = df_f['Fecha_Principal'].notna()
        if start: mask &= (df_f['Fecha_Principal'] >= start) & valid
        if end: mask &= (df_f['Fecha_Principal'] <= end) & valid
        df_f = df_f[mask]
    if industries and "– Todos –" not in industries and COL_INDUSTRY in df_f.columns: df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
    if managements and "– Todos –" not in managements and COL_MANAGEMENT in df_f.columns: df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]
    if meeting_status != "– Todos –" and COL_MEETING in df_f.columns: df_f = df_f[df_f[COL_MEETING] == meeting_status]
    return df_f

# --- Componentes de Visualización (Ajustes en Tasas y Textos) ---

def display_enhanced_funnel(df_filtered):
    st.markdown("### 🏺 Embudo de Conversión Detallado") # Emoji cambiado
    st.caption("Muestra cuántos leads avanzan en cada etapa clave del proceso.")
    if df_filtered.empty: st.info("No hay datos filtrados para mostrar el embudo."); return

    total_leads = len(df_filtered)
    total_first_contact = (df_filtered['FirstContactStatus'] == "Si").sum()
    total_responded = (df_filtered[COL_RESPONDED] == "Si").sum()
    total_meetings = (df_filtered[COL_MEETING] == "Si").sum()

    funnel_stages = ["Leads Generados", "1er Contacto", "Respuesta Recibida", "Reunión Agendada"] # Nombres más cortos
    funnel_values = [total_leads, total_first_contact, total_responded, total_meetings]

    # **AJUSTE**: Calcular porcentajes explícitamente para textinfo
    percents_vs_previous = [100.0] # Primer etapa es 100% de sí misma
    percents_vs_initial = [100.0]
    for i in range(1, len(funnel_values)):
        p_prev = calculate_rate(funnel_values[i], funnel_values[i-1], 1) if funnel_values[i-1] > 0 else 0.0
        p_init = calculate_rate(funnel_values[i], funnel_values[0], 1) if funnel_values[0] > 0 else 0.0
        percents_vs_previous.append(p_prev)
        percents_vs_initial.append(p_init)

    # Crear textos personalizados para cada etapa
    funnel_texts = [f"{val:,}<br>{p_init:.1f}% Inicial" for val, p_init in zip(funnel_values, percents_vs_initial)]
    # Añadir % vs anterior a partir de la segunda etapa
    for i in range(1, len(funnel_texts)):
         funnel_texts[i] += f"<br>{percents_vs_previous[i]:.1f}% Anterior"


    fig = go.Figure(go.Funnel(
        y = funnel_stages, x = funnel_values,
        textposition = "inside",
        # **AJUSTE**: Usar textos personalizados en lugar de textinfo automático
        text = funnel_texts,
        hoverinfo = 'y+x', # Mostrar nombre etapa y valor al pasar el mouse
        opacity = 0.75, marker = {"color": ["#636EFA", "#FECB52", "#EF553B", "#00CC96"],
                  "line": {"width": [4, 2, 2, 1], "color": ["#4048A5", "#DDAA3F", "#C9452F", "#00A078"]}},
        connector = {"line": {"color": "grey", "dash": "dot", "width": 2}}))
    fig.update_layout(title_text="Embudo Detallado: Leads a Reuniones", title_x=0.5, margin=dict(t=50, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Tasas de Conversión por Etapa")
    # Usar los porcentajes ya calculados
    rate_lead_to_contact = percents_vs_previous[1] if len(percents_vs_previous) > 1 else 0.0
    rate_contact_to_response = percents_vs_previous[2] if len(percents_vs_previous) > 2 else 0.0
    rate_response_to_meeting = percents_vs_previous[3] if len(percents_vs_previous) > 3 else 0.0
    rate_global_lead_to_meeting = percents_vs_initial[3] if len(percents_vs_initial) > 3 else 0.0

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Lead → Contacto", f"{rate_lead_to_contact:.1f}%", help=f"{total_first_contact:,} / {total_leads:,} Leads")
    r2.metric("Contacto → Respuesta", f"{rate_contact_to_response:.1f}%", help=f"{total_responded:,} / {total_first_contact:,} Contactos")
    r3.metric("Respuesta → Reunión", f"{rate_response_to_meeting:.1f}%", help=f"{total_meetings:,} / {total_responded:,} Respuestas")
    r4.metric("Lead → Reunión (Global)", f"{rate_global_lead_to_meeting:.1f}%", help=f"{total_meetings:,} / {total_leads:,} Leads")

def display_time_lag_analysis(df_filtered):
    # (Sin cambios, parece correcto)
    st.markdown("---"); st.markdown("### ⏱️ Tiempos Promedio del Ciclo (días)"); st.caption("Tiempo promedio entre etapas para leads que las completaron.")
    if df_filtered.empty: st.info("No hay datos."); return
    avg_gen_c = df_filtered['Dias_Gen_a_Contacto'].mean(); cnt_gen_c = df_filtered['Dias_Gen_a_Contacto'].count()
    avg_c_m = df_filtered['Dias_Contacto_a_Reunion'].mean(); cnt_c_m = df_filtered['Dias_Contacto_a_Reunion'].count()
    avg_gen_m = df_filtered['Dias_Gen_a_Reunion'].mean(); cnt_gen_m = df_filtered['Dias_Gen_a_Reunion'].count()
    f_avg_gen_c = f"{avg_gen_c:.1f}" if pd.notna(avg_gen_c) else "N/A"
    f_avg_c_m = f"{avg_c_m:.1f}" if pd.notna(avg_c_m) else "N/A"
    f_avg_gen_m = f"{avg_gen_m:.1f}" if pd.notna(avg_gen_m) else "N/A"
    t1, t2, t3 = st.columns(3)
    t1.metric("Lead Gen → 1er Contacto", f_avg_gen_c, help=f"Promedio {cnt_gen_c:,} leads.")
    t2.metric("1er Contacto → Reunión", f_avg_c_m, help=f"Promedio {cnt_c_m:,} reuniones.")
    t3.metric("Lead Gen → Reunión", f_avg_gen_m, help=f"Promedio {cnt_gen_m:,} reuniones.")

def display_segmentation_analysis(df_filtered):
    # (Ajustar formato de texto en gráfico)
    st.markdown("---"); st.markdown("### 📊 Desempeño por Segmento"); st.caption("Tasa Global (Leads → Reuniones) por Industria y Nivel.")
    if df_filtered.empty: st.info("No hay datos."); return

    def create_segment_chart(group_col, title_suffix):
        if group_col not in df_filtered.columns or df_filtered[group_col].nunique() < 1: st.caption(f"No hay datos/variación en '{title_suffix}'."); return
        seg_sum = df_filtered.groupby(group_col).agg(Total_Leads=(group_col, 'count'), Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index()
        seg_sum['Tasa_Conv_Global (%)'] = seg_sum.apply(lambda r: calculate_rate(r['Total_Reuniones'], r['Total_Leads']), axis=1)
        min_leads = 3; seg_chart = seg_sum[seg_sum['Total_Leads'] >= min_leads].copy()

        if seg_chart.empty:
            st.caption(f"No hay grupos en '{title_suffix}' con ≥ {min_leads} leads para gráfico.")
            show_table = True
        else:
            seg_chart = seg_chart.sort_values('Tasa_Conv_Global (%)', ascending=False)
            fig = px.bar(seg_chart.head(10), x=group_col, y='Tasa_Conv_Global (%)', title=f"Top 10 {title_suffix} por Tasa",
                         # **AJUSTE**: Usar text auto y formato directo
                         text_auto='.1f', color='Tasa_Conv_Global (%)', color_continuous_scale=px.colors.sequential.YlGnBu)
            # **AJUSTE**: Añadir sufijo % al texto y eje Y
            fig.update_traces(texttemplate='%{y:.1f}%', textposition='outside')
            fig.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", xaxis_title=title_suffix, title_x=0.5,
                              yaxis_range=[0, max(10, seg_chart['Tasa_Conv_Global (%)'].max() * 1.1 + 5)])
            st.plotly_chart(fig, use_container_width=True)
            show_table = False # Ya mostramos gráfico

        if show_table: # Mostrar tabla si no hubo gráfico
             with st.expander(f"Ver datos por {title_suffix} (todos)"): st.dataframe(seg_sum.sort_values('Total_Leads', ascending=False).style.format({'Total_Leads': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Conv_Global (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)
        elif not show_table: # Ofrecer tabla en expander si sí hubo gráfico
             with st.expander(f"Ver tabla completa por {title_suffix}"): st.dataframe(seg_sum.sort_values('Total_Leads', ascending=False).style.format({'Total_Leads': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Conv_Global (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)


    col1, col2 = st.columns(2)
    with col1: create_segment_chart(COL_INDUSTRY, "Industria")
    with col2: create_segment_chart(COL_MANAGEMENT, "Nivel Management") # Texto más corto

def display_channel_analysis(df_filtered):
    # (Ajustar formato texto gráfico)
    st.markdown("---"); st.markdown(f"### 📣 Efectividad por Canal Respuesta"); st.caption("Volumen de respuestas y tasa Respuesta → Reunión.")
    if COL_CHANNEL not in df_filtered.columns or COL_RESPONDED not in df_filtered.columns: st.info(f"Faltan '{COL_CHANNEL}' o '{COL_RESPONDED}'."); return
    df_resp = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()
    if df_resp.empty: st.info("No hay leads con respuesta 'Si'."); return
    if df_resp[COL_CHANNEL].nunique() < 1: st.info(f"No hay datos/variación en '{COL_CHANNEL}'."); return

    chan_sum = df_resp.groupby(COL_CHANNEL).agg(Total_Respuestas=(COL_CHANNEL, 'count'), Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index()
    chan_sum['Tasa_Reunion_x_Resp (%)'] = chan_sum.apply(lambda r: calculate_rate(r['Total_Reuniones'], r['Total_Respuestas']), axis=1)
    chan_sum_vol = chan_sum.sort_values('Total_Respuestas', ascending=False)

    col1, col2 = st.columns(2)
    with col1:
        fig_vol = px.bar(chan_sum_vol, x=COL_CHANNEL, y='Total_Respuestas', title="Volumen Respuestas x Canal", text_auto=True);
        fig_vol.update_layout(yaxis_title="Nº Respuestas", title_x=0.5, xaxis_title="Canal"); st.plotly_chart(fig_vol, use_container_width=True)
    with col2:
        if chan_sum['Total_Reuniones'].sum() > 0:
            chan_sum_rate = chan_sum.sort_values('Tasa_Reunion_x_Resp (%)', ascending=False)
            fig_rate = px.bar(chan_sum_rate, x=COL_CHANNEL, y='Tasa_Reunion_x_Resp (%)', title="Tasa Respuesta → Reunión x Canal",
                              # **AJUSTE**: Usar text auto y formato
                              text_auto='.1f', color='Tasa_Reunion_x_Resp (%)', color_continuous_scale=px.colors.sequential.OrRd)
            # **AJUSTE**: Añadir sufijo % al texto y eje Y
            fig_rate.update_traces(texttemplate='%{y:.1f}%', textposition='outside');
            fig_rate.update_layout(yaxis_title="Tasa (%)", yaxis_ticksuffix="%", title_x=0.5, xaxis_title="Canal", yaxis_range=[0,max(10, chan_sum['Tasa_Reunion_x_Resp (%)'].max() * 1.1 + 5)]); st.plotly_chart(fig_rate, use_container_width=True)
        else: st.caption("No hay reuniones desde respuestas.")

    with st.expander("Ver datos por Canal"): st.dataframe(chan_sum_vol.style.format({'Total_Respuestas': '{:,}', 'Total_Reuniones': '{:,}', 'Tasa_Reunion_x_Resp (%)': '{:.1f}%'}), hide_index=True, use_container_width=True)

def display_enhanced_time_evolution(df_filtered):
    # (Sin cambios, parece correcto)
    st.markdown("---"); st.markdown("### 📈 Evolución Temporal Embudo (Mes)"); st.caption("Volumen en cada etapa mes a mes.")
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns or df_filtered['AñoMes'].nunique() < 1: st.info("No hay datos temporales (AñoMes)."); return
    time_sum = df_filtered.groupby('AñoMes').agg(Leads=('AñoMes', 'count'), Contacto=('FirstContactStatus', lambda x: (x == 'Si').sum()), Respuesta=(COL_RESPONDED, lambda x: (x == 'Si').sum()), Reunion=(COL_MEETING, lambda x: (x == 'Si').sum())).reset_index().sort_values('AñoMes')
    if not time_sum.empty:
        time_melt = time_sum.melt(id_vars=['AñoMes'], value_vars=['Leads', 'Contacto', 'Respuesta', 'Reunion'], var_name='Etapa', value_name='Cantidad')
        fig = px.line(time_melt, x='AñoMes', y='Cantidad', color='Etapa', title="Evolución Mensual del Embudo", markers=True, labels={"Cantidad": "Número", "AñoMes": "Mes"})
        fig.update_layout(legend_title_text='Etapa', title_x=0.5, yaxis_rangemode='tozero'); st.plotly_chart(fig, use_container_width=True)
        with st.expander("Ver datos mensuales"): st.dataframe(time_sum.set_index('AñoMes').style.format("{:,}"), use_container_width=True)
    else: st.caption("No se generaron datos agregados por mes.")

# --- Flujo Principal ---
# (Quitamos logs de depuración, mantenemos flujo)
df_pipeline_base = load_and_process_data()

processing_warnings = st.session_state.get('data_load_warnings', [])
if processing_warnings:
    with st.expander("⚠️ Avisos Carga/Procesamiento", expanded=True):
        for msg in processing_warnings: st.warning(msg)

if df_pipeline_base.empty:
    if not processing_warnings: st.error("Fallo: DataFrame vacío post-procesamiento.")
    st.stop()
else:
    start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base.copy())
    df_pipeline_filtered = apply_pipeline_filters(df_pipeline_base, start_date, end_date, industries, managements, meeting_status)

    # Mostrar visualizaciones solo si hay datos filtrados
    if not df_pipeline_filtered.empty:
        display_enhanced_funnel(df_pipeline_filtered)
        display_time_lag_analysis(df_pipeline_filtered)
        display_segmentation_analysis(df_pipeline_filtered)
        display_channel_analysis(df_pipeline_filtered)
        display_enhanced_time_evolution(df_pipeline_filtered)

        with st.expander("Ver tabla detallada de leads filtrados"):
            st.info(f"Mostrando {len(df_pipeline_filtered):,} leads filtrados.")
            cols_show = ["Company", "Full Name", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT, 'Fecha_Principal',
                           COL_FIRST_CONTACT_DATE, COL_CONTACTED, COL_RESPONDED, COL_MEETING, COL_MEETING_DATE,
                           COL_CHANNEL, "LinkedIn URL", 'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']
            cols_exist = [c for c in cols_show if c in df_pipeline_filtered.columns]; df_display = df_pipeline_filtered[cols_exist].copy()
            for dc in ['Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]:
                if dc in df_display.columns: df_display[dc] = pd.to_datetime(df_display[dc], errors='coerce').dt.strftime('%Y-%m-%d').fillna('N/A')
            for tc in ['Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion']:
                if tc in df_display.columns: df_display[tc] = df_display[tc].apply(lambda x: f"{x:.0f}" if pd.notna(x) else 'N/A')
            st.dataframe(df_display, hide_index=True)
            try:
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df_pipeline_filtered[cols_exist].to_excel(writer, index=False, sheet_name='Pipeline_Filtrado')
                st.download_button(label="⬇️ Descargar Vista Filtrada (Excel)", data=output.getvalue(), file_name="pipeline_filtrado.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            except Exception as e: st.error(f"Error generando Excel: {e}")
    else:
        st.info("ℹ️ No se encontraron datos que coincidan con los filtros seleccionados.")
