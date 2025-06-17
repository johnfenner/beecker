# pages/📢_Campañas.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
from collections import Counter

# --- Configuración de Página ---
st.set_page_config(page_title="Análisis de Campañas", layout="wide")
st.title("📢 Análisis de Campañas")
st.markdown(
    "Análisis del potencial de campañas, prospección manual y prospección por email. "
    "Este análisis excluye prospectos sin una campaña asignada."
)

# --- Constantes y Claves de Estado de Sesión ---
SHEET_URL_SECRET_KEY = "main_prostraction_sheet_url"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0"
EMAIL_STATS_SHEET_URL_KEY = "email_stats_sheet_url" # Constante para la nueva hoja
NO_CAMPAIGN_VALUES = ["Sin Campaña Asignada", "N/D", ""]

# Columnas
COL_CAMPAIGN = "Campaña"
COL_FECHA_INVITE = "Fecha de Invite"
COL_INVITE_ACEPTADA = "¿Invite Aceptada?"
COL_RESPUESTA_1ER_MSJ = "Respuesta Primer Mensaje"
COL_SESION_AGENDADA_MANUAL = "Sesion Agendada?"
COL_QUIEN_PROSPECTO = "¿Quién Prospecto?"
COL_AVATAR = "Avatar"
COL_FECHA_SESION_MANUAL = "Fecha Sesion"
COL_CONTACTADOS_EMAIL = "Contactados por Campaña"
COL_RESPUESTA_EMAIL = "Respuesta Email"
COL_SESION_AGENDADA_EMAIL = "Sesion Agendada Email"
COL_FECHA_SESION_EMAIL = "Fecha de Sesion Email"

# Claves de Sesión para Filtros
SES_CAMPAIGN_FILTER_KEY = "campaign_page_campaign_filter_v5"
SES_START_DATE_KEY = "campaign_page_start_date_v5"
SES_END_DATE_KEY = "campaign_page_end_date_v5"
SES_PROSPECTOR_FILTER_KEY = "campaign_page_prospector_filter_v5"
SES_AVATAR_FILTER_KEY = "campaign_page_avatar_filter_v5"

# Cadenas Canónicas para "Mostrar Todo"
ALL_CAMPAIGNS_STRING = "– Todas –"
ALL_PROSPECTORS_STRING = "– Todos –"
ALL_AVATARS_STRING = "– Todos –"

# --- Funciones Auxiliares ---
def clean_text_value(val, default="N/D"):
    if pd.isna(val) or str(val).strip() == "": return default
    return str(val).strip()

def clean_yes_no_value(val, true_val="si", false_val="no", default_val="no"):
    if pd.isna(val): return default_val
    cleaned = str(val).strip().lower()
    if cleaned == true_val.lower(): return true_val
    elif cleaned == false_val.lower(): return false_val
    elif cleaned in ["", "nan", "na", "<na>"]: return default_val
    return cleaned

def parse_date_robustly(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "": return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)): return pd.to_datetime(date_val)
    date_str = str(date_val).strip()
    if date_str.isdigit():
        try: return pd.to_datetime('1899-12-30') + pd.to_timedelta(float(date_str), 'D')
        except ValueError: pass
    common_formats = [
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
    ]
    for fmt in common_formats:
        try: return pd.to_datetime(date_str, format=fmt)
        except (ValueError, TypeError): continue
    return pd.to_datetime(date_str, errors='coerce')

def make_unique_column_names(headers_list):
    counts = Counter(); new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped: h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1: new_headers.append(h_stripped)
        else: new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

@st.cache_data(ttl=600)
def load_and_prepare_campaign_data():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta [gcp_service_account]. Revisa los secrets de Streamlit.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar credenciales de Google Sheets: {e}")
        return pd.DataFrame()
    try:
        sheet_url = st.secrets.get(SHEET_URL_SECRET_KEY, DEFAULT_SHEET_URL)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.sheet1
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 1:
            st.warning("La hoja de Google Sheets está vacía o no se pudo leer.")
            return pd.DataFrame()
        headers = make_unique_column_names(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: Hoja no encontrada en la URL definida en secrets ('{SHEET_URL_SECRET_KEY}') o en la URL por defecto.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo: {e}")
        return pd.DataFrame()

    if COL_CAMPAIGN not in df.columns:
        st.error(f"La columna '{COL_CAMPAIGN}' es esencial y no fue encontrada. El análisis de campañas no puede continuar.")
        return pd.DataFrame()

    df[COL_CAMPAIGN] = df[COL_CAMPAIGN].apply(lambda x: clean_text_value(x, default=""))
    df = df[~df[COL_CAMPAIGN].isin(NO_CAMPAIGN_VALUES)].copy()
    if df.empty:
        st.warning("No se encontraron prospectos con campañas asignadas válidas después de la limpieza inicial.")
        return pd.DataFrame()

    date_cols_manual_processing = [COL_FECHA_INVITE, COL_FECHA_SESION_MANUAL]
    for col in date_cols_manual_processing:
        if col in df.columns: df[col] = df[col].apply(parse_date_robustly)
        else: df[col] = pd.NaT

    yes_no_cols_manual = [COL_INVITE_ACEPTADA, COL_RESPUESTA_1ER_MSJ, COL_SESION_AGENDADA_MANUAL]
    for col in yes_no_cols_manual:
        if col in df.columns: df[col] = df[col].apply(clean_yes_no_value)
        else: df[col] = "no"

    text_cols_manual = [COL_QUIEN_PROSPECTO, COL_AVATAR]
    for col in text_cols_manual:
        if col in df.columns: df[col] = df[col].apply(lambda x: clean_text_value(x, default="N/D_Interno"))
        else: df[col] = "N/D_Interno"

    if COL_AVATAR in df.columns:
        df[COL_AVATAR] = df[COL_AVATAR].astype(str).str.strip().str.title()
        equivalencias_avatar = {"Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez", "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"}
        df[COL_AVATAR] = df[COL_AVATAR].replace(equivalencias_avatar)

    email_yes_no_cols = [COL_CONTACTADOS_EMAIL, COL_RESPUESTA_EMAIL, COL_SESION_AGENDADA_EMAIL]
    for col in email_yes_no_cols:
        if col in df.columns: df[col] = df[col].apply(clean_yes_no_value)
        else: df[col] = "no"

    if COL_FECHA_SESION_EMAIL in df.columns: df[COL_FECHA_SESION_EMAIL] = df[COL_FECHA_SESION_EMAIL].apply(parse_date_robustly)
    else: df[COL_FECHA_SESION_EMAIL] = pd.NaT

    df["FechaFiltroManual"] = pd.NaT
    if COL_FECHA_INVITE in df.columns and not df[COL_FECHA_INVITE].isnull().all():
         df["FechaFiltroManual"] = df[COL_FECHA_INVITE]
    
    return df

# --- Filtros de Barra Lateral ---
def display_campaign_filters(df_options): # df_options is a copy of df_base_campaigns_loaded
    st.sidebar.header("🎯 Filtros de Campaña")

    default_filters_init = {
        SES_CAMPAIGN_FILTER_KEY: [ALL_CAMPAIGNS_STRING],
        SES_START_DATE_KEY: None,
        SES_END_DATE_KEY: None,
        SES_PROSPECTOR_FILTER_KEY: [ALL_PROSPECTORS_STRING],
        SES_AVATAR_FILTER_KEY: [ALL_AVATARS_STRING]
    }
    for key, value in default_filters_init.items():
        if key not in st.session_state:
            st.session_state[key] = value
    campaign_options = [ALL_CAMPAIGNS_STRING]
    if COL_CAMPAIGN in df_options.columns and not df_options[COL_CAMPAIGN].empty:
        unique_items = df_options[COL_CAMPAIGN].dropna().unique()
        for item in sorted(list(unique_items)):
            if item != ALL_CAMPAIGNS_STRING: campaign_options.append(item)
    st.sidebar.multiselect("Seleccionar Campaña(s)", options=campaign_options, key=SES_CAMPAIGN_FILTER_KEY)
    prospector_options = [ALL_PROSPECTORS_STRING]
    if COL_QUIEN_PROSPECTO in df_options.columns and not df_options[COL_QUIEN_PROSPECTO].empty:
        unique_items = df_options[df_options[COL_QUIEN_PROSPECTO] != "N/D_Interno"][COL_QUIEN_PROSPECTO].dropna().unique()
        for item in sorted(list(unique_items)):
            if item != ALL_PROSPECTORS_STRING: prospector_options.append(item)
    st.sidebar.multiselect("¿Quién Prospectó?", options=prospector_options, key=SES_PROSPECTOR_FILTER_KEY)
    avatar_options = [ALL_AVATARS_STRING]
    if COL_AVATAR in df_options.columns and not df_options[COL_AVATAR].empty:
        unique_items = df_options[df_options[COL_AVATAR] != "N/D_Interno"][COL_AVATAR].dropna().unique()
        for item in sorted(list(unique_items)):
            if item != ALL_AVATARS_STRING: avatar_options.append(item)
    st.sidebar.multiselect("Avatar", options=avatar_options, key=SES_AVATAR_FILTER_KEY)
    min_date, max_date = None, None
    if "FechaFiltroManual" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["FechaFiltroManual"]):
        valid_dates = df_options["FechaFiltroManual"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()
    date_col1, date_col2 = st.sidebar.columns(2)
    st.date_input("Fecha Desde", value=None, min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    st.date_input("Fecha Hasta", value=None, min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True):
        st.session_state[SES_CAMPAIGN_FILTER_KEY] = [ALL_CAMPAIGNS_STRING]
        st.session_state[SES_START_DATE_KEY] = None
        st.session_state[SES_END_DATE_KEY] = None
        st.session_state[SES_PROSPECTOR_FILTER_KEY] = [ALL_PROSPECTORS_STRING]
        st.session_state[SES_AVATAR_FILTER_KEY] = [ALL_AVATARS_STRING]
        st.rerun()
    return (st.session_state.get(SES_CAMPAIGN_FILTER_KEY), st.session_state.get(SES_START_DATE_KEY), st.session_state.get(SES_END_DATE_KEY), st.session_state.get(SES_PROSPECTOR_FILTER_KEY), st.session_state.get(SES_AVATAR_FILTER_KEY))

# --- Funciones de Análisis Originales ---
def apply_common_filters(df, campaigns, prospectors, avatars): 
    if df.empty: return df
    df_filtered = df.copy()
    if campaigns and ALL_CAMPAIGNS_STRING not in campaigns:
        df_filtered = df_filtered[df_filtered[COL_CAMPAIGN].isin(campaigns)]
    if prospectors and ALL_PROSPECTORS_STRING not in prospectors:
        df_filtered = df_filtered[df_filtered[COL_QUIEN_PROSPECTO].isin(prospectors)]
    if avatars and ALL_AVATARS_STRING not in avatars:
        df_filtered = df_filtered[df_filtered[COL_AVATAR].isin(avatars)]
    return df_filtered

def apply_manual_date_filter(df, start_date, end_date):
    if df.empty or (start_date is None and end_date is None): return df
    df_date_filtered = df.copy()
    if "FechaFiltroManual" in df_date_filtered.columns and pd.api.types.is_datetime64_any_dtype(df_date_filtered["FechaFiltroManual"]):
        s_date = pd.to_datetime(start_date).date() if start_date else None
        e_date = pd.to_datetime(end_date).date() if end_date else None
        date_series_for_filter = df_date_filtered["FechaFiltroManual"].dt.date
        if s_date and e_date: df_date_filtered = df_date_filtered[(date_series_for_filter >= s_date) & (date_series_for_filter <= e_date)]
        elif s_date: df_date_filtered = df_date_filtered[date_series_for_filter >= s_date]
        elif e_date: df_date_filtered = df_date_filtered[date_series_for_filter <= e_date]
    return df_date_filtered

def display_campaign_potential(df_valid_campaigns):
    st.subheader("Potencial de Prospección por Campaña")
    if df_valid_campaigns.empty:
        st.info("No hay datos de campañas válidas para analizar el potencial.")
        return
    potential_counts = df_valid_campaigns[COL_CAMPAIGN].value_counts().reset_index()
    potential_counts.columns = [COL_CAMPAIGN, 'Total Prospectos en Campaña']
    if potential_counts.empty:
        st.info("No hay datos de potencial de campaña para mostrar.")
        return
    fig = px.bar(potential_counts.sort_values(by='Total Prospectos en Campaña', ascending=False),
        x=COL_CAMPAIGN, y='Total Prospectos en Campaña', title='Total de Prospectos por Campaña Asignada', text_auto=True, color=COL_CAMPAIGN)
    fig.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Prospectos")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Ver tabla de potencial"):
        st.dataframe(potential_counts.style.format({'Total Prospectos en Campaña': "{:,}"}), use_container_width=True)
    st.markdown("---")

def display_manual_prospecting_analysis(df_common_filtered, start_date, end_date):
    st.subheader("Análisis de Prospección Manual")
    st.caption("Basado en campañas y filtros seleccionados. El filtro de fecha se aplica a 'Fecha de Invite'. Muestra prospectos asignados, cuántos fueron contactados manualmente y su progreso en el embudo.")
    df_manual_filtered = apply_manual_date_filter(df_common_filtered, start_date, end_date)
    if df_manual_filtered.empty:
        st.info("No hay datos para analizar la prospección manual con los filtros actuales (incluyendo el rango de fechas).")
        return
    total_in_current_filter = len(df_manual_filtered) 
    if COL_FECHA_INVITE not in df_manual_filtered.columns:
        st.warning(f"Columna '{COL_FECHA_INVITE}' no encontrada. No se puede calcular 'Contactos Manuales Iniciados'.")
        df_contactos_iniciados = pd.DataFrame()
    else:
        df_contactos_iniciados = df_manual_filtered[df_manual_filtered[COL_FECHA_INVITE].notna()].copy()
    total_contactos_iniciados_manual = len(df_contactos_iniciados)
    col_metric1, col_metric2 = st.columns(2)
    col_metric1.metric("Prospectos en Selección Actual (Asignados, filtrados por fecha)", f"{total_in_current_filter:,}")
    col_metric2.metric("De estos, con Contacto Manual Iniciado (tienen Fecha Invite)", f"{total_contactos_iniciados_manual:,}")
    if total_contactos_iniciados_manual == 0:
        if total_in_current_filter > 0:
            st.warning("De los prospectos en la selección actual (filtrada por fecha), ninguno tiene un contacto manual iniciado (Fecha de Invite registrada).")
        st.markdown("---")
        return 
    st.markdown("#### Trazabilidad Detallada: Asignados vs. Contactados y Embudo por Prospectador")
    group_cols_trace = [COL_CAMPAIGN, COL_QUIEN_PROSPECTO]
    if not all(col in df_manual_filtered.columns for col in group_cols_trace):
        st.warning(f"Faltan columnas para la trazabilidad: {', '.join(col for col in group_cols_trace if col not in df_manual_filtered)}. No se puede generar la tabla.")
        st.markdown("---")
        return
    assigned_counts = df_manual_filtered.groupby(group_cols_trace, as_index=False).size().rename(columns={'size': 'Prospectos Asignados'})
    if df_contactos_iniciados.empty or not all(col in df_contactos_iniciados.columns for col in group_cols_trace) :
         contactos_iniciados_counts = pd.DataFrame(columns=group_cols_trace + ['Contactos Manuales Iniciados'])
         if not assigned_counts.empty:
            contactos_iniciados_counts = assigned_counts[group_cols_trace].copy()
            contactos_iniciados_counts['Contactos Manuales Iniciados'] = 0
    else:
        contactos_iniciados_counts = df_contactos_iniciados.groupby(group_cols_trace, as_index=False).size().rename(columns={'size': 'Contactos Manuales Iniciados'})
    funnel_metrics = pd.DataFrame() 
    if not df_contactos_iniciados.empty and all(col in df_contactos_iniciados.columns for col in group_cols_trace):
        agg_ops_dict = {}
        if COL_INVITE_ACEPTADA in df_contactos_iniciados.columns: agg_ops_dict['Invites_Aceptadas'] = (COL_INVITE_ACEPTADA, lambda x: (x == "si").sum())
        if COL_RESPUESTA_1ER_MSJ in df_contactos_iniciados.columns: agg_ops_dict['Respuestas_1er_Msj'] = (COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum())
        if COL_SESION_AGENDADA_MANUAL in df_contactos_iniciados.columns: agg_ops_dict['Sesiones_Agendadas'] = (COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
        if agg_ops_dict:
            funnel_metrics = df_contactos_iniciados.groupby(group_cols_trace, as_index=False).agg(**agg_ops_dict)
    trace_df = pd.merge(assigned_counts, contactos_iniciados_counts, on=group_cols_trace, how='left')
    if not funnel_metrics.empty:
        trace_df = pd.merge(trace_df, funnel_metrics, on=group_cols_trace, how='left')
    count_cols_fill = ['Contactos Manuales Iniciados', 'Invites_Aceptadas', 'Respuestas_1er_Msj', 'Sesiones_Agendadas']
    for col in count_cols_fill:
        if col not in trace_df.columns: trace_df[col] = 0
        trace_df[col] = trace_df[col].fillna(0).astype(int)
    trace_df['Tasa Inicio Prospección (%)'] = (trace_df['Contactos Manuales Iniciados'].astype(float) / trace_df['Prospectos Asignados'].astype(float) * 100).where(trace_df['Prospectos Asignados'] > 0, 0).fillna(0).round(1)
    base_rates_embudo = trace_df['Contactos Manuales Iniciados'].astype(float)
    if 'Invites_Aceptadas' in trace_df.columns: 
        trace_df['Tasa Aceptación vs Contactos (%)'] = (trace_df['Invites_Aceptadas'].astype(float) / base_rates_embudo * 100).where(base_rates_embudo > 0, 0).fillna(0).round(1)
    else: trace_df['Tasa Aceptación vs Contactos (%)'] = 0.0
    if 'Respuestas_1er_Msj' in trace_df.columns and 'Invites_Aceptadas' in trace_df.columns:
        trace_df['Tasa Respuesta vs Aceptadas (%)'] = (trace_df['Respuestas_1er_Msj'].astype(float) / trace_df['Invites_Aceptadas'].astype(float) * 100).where(trace_df['Invites_Aceptadas'] > 0, 0).fillna(0).round(1)
    else: trace_df['Tasa Respuesta vs Aceptadas (%)'] = 0.0
    if 'Sesiones_Agendadas' in trace_df.columns and 'Respuestas_1er_Msj' in trace_df.columns:
        trace_df['Tasa Sesión vs Respuestas (%)'] = (trace_df['Sesiones_Agendadas'].astype(float) / trace_df['Respuestas_1er_Msj'].astype(float) * 100).where(trace_df['Respuestas_1er_Msj'] > 0, 0).fillna(0).round(1)
    else: trace_df['Tasa Sesión vs Respuestas (%)'] = 0.0
    if 'Sesiones_Agendadas' in trace_df.columns:
        trace_df['Tasa Sesión Global vs Contactos (%)'] = (trace_df['Sesiones_Agendadas'].astype(float) / base_rates_embudo * 100).where(base_rates_embudo > 0, 0).fillna(0).round(1)
    else: trace_df['Tasa Sesión Global vs Contactos (%)'] = 0.0
    trace_df_display = trace_df[trace_df[COL_QUIEN_PROSPECTO] != "N/D_Interno"].copy()
    if not trace_df_display.empty:
        column_order = [
            COL_CAMPAIGN, COL_QUIEN_PROSPECTO, 'Prospectos Asignados', 'Contactos Manuales Iniciados', 'Tasa Inicio Prospección (%)',
            'Invites_Aceptadas', 'Tasa Aceptación vs Contactos (%)', 'Respuestas_1er_Msj', 'Tasa Respuesta vs Aceptadas (%)',
            'Sesiones_Agendadas', 'Tasa Sesión vs Respuestas (%)', 'Tasa Sesión Global vs Contactos (%)'
        ]
        column_order_existing = [col for col in column_order if col in trace_df_display.columns]
        st.dataframe(trace_df_display[column_order_existing].style.format({col: "{:,}" for col in ['Prospectos Asignados', 'Contactos Manuales Iniciados', 'Invites_Aceptadas', 'Respuestas_1er_Msj', 'Sesiones_Agendadas'] if col in column_order_existing} | {tasa_col: "{:.1f}%" for tasa_col in ['Tasa Inicio Prospección (%)', 'Tasa Aceptación vs Contactos (%)', 'Tasa Respuesta vs Aceptadas (%)', 'Tasa Sesión vs Respuestas (%)', 'Tasa Sesión Global vs Contactos (%)'] if tasa_col in column_order_existing}), use_container_width=True)
    else: 
        st.info("No hay datos para la tabla de trazabilidad detallada.")
    st.markdown("#### Embudo de Conversión Agregado (para Contactos Manuales Iniciados)")
    invites_aceptadas_agg = df_contactos_iniciados[df_contactos_iniciados[COL_INVITE_ACEPTADA] == "si"].shape[0] if COL_INVITE_ACEPTADA in df_contactos_iniciados else 0
    respuestas_1er_msj_agg = df_contactos_iniciados[df_contactos_iniciados[COL_RESPUESTA_1ER_MSJ] == "si"].shape[0] if COL_RESPUESTA_1ER_MSJ in df_contactos_iniciados else 0
    sesiones_agendadas_agg = df_contactos_iniciados[df_contactos_iniciados[COL_SESION_AGENDADA_MANUAL] == "si"].shape[0] if COL_SESION_AGENDADA_MANUAL in df_contactos_iniciados else 0
    funnel_data_manual_agg = pd.DataFrame({"Etapa": ["Contactos Manuales Iniciados", "Invites Aceptadas", "Respuestas 1er Msj", "Sesiones Agendadas"], "Cantidad": [total_contactos_iniciados_manual, invites_aceptadas_agg, respuestas_1er_msj_agg, sesiones_agendadas_agg]})
    fig_funnel_manual_agg = px.funnel(funnel_data_manual_agg, x='Cantidad', y='Etapa', title="Embudo Agregado Prospección Manual")
    st.plotly_chart(fig_funnel_manual_agg, use_container_width=True)
    st.markdown("---")

def display_global_manual_prospecting_deep_dive(df_common_filtered, start_date, end_date):
    st.header("Desglose General de Prospección Manual en Campañas Seleccionadas")
    st.caption("Este análisis se basa en la selección actual de campañas y filtros de la barra lateral, incluyendo el filtro de fecha para 'Fecha de Invite'.")
    df_manual_filtered = apply_manual_date_filter(df_common_filtered, start_date, end_date)
    if df_manual_filtered.empty:
        st.info("No hay datos para este desglose con los filtros actuales (incluyendo el rango de fechas).")
        return
    if COL_FECHA_INVITE not in df_manual_filtered.columns:
        st.warning(f"Columna '{COL_FECHA_INVITE}' no encontrada. No se puede generar el desglose detallado.")
        df_contactos_iniciados = pd.DataFrame()
    else:
        df_contactos_iniciados = df_manual_filtered[df_manual_filtered[COL_FECHA_INVITE].notna()].copy()
    if df_contactos_iniciados.empty:
        st.info("No hay prospectos con contacto manual iniciado en la selección actual (filtrada por fecha) para este desglose detallado.")
        return
    st.markdown("#### Métricas Globales (sobre Contactos Manuales Iniciados)")
    # ... (código de esta función se mantiene igual)
    pass

def display_email_prospecting_analysis(df_common_filtered): 
    st.subheader("Análisis de Prospección por Email")
    st.caption("Basado en campañas y filtros seleccionados en la barra lateral. El filtro de fecha NO se aplica a esta sección.")
    if df_common_filtered.empty: 
        st.info("No hay datos para analizar la prospección por email con los filtros de campaña/prospector/avatar actuales.")
        return
    if COL_CONTACTADOS_EMAIL not in df_common_filtered.columns:
        st.warning(f"Columna '{COL_CONTACTADOS_EMAIL}' no encontrada. No se puede analizar la prospección por email.")
        return
    df_contactados_email = df_common_filtered[df_common_filtered[COL_CONTACTADOS_EMAIL] == "si"].copy()
    total_contactados_email_seleccion = len(df_contactos_email)
    if total_contactados_email_seleccion == 0:
        st.info("No se encontraron contactos por email (Contactados por Campaña = 'si') para la selección actual de campaña/prospector/avatar.")
        return
    st.metric("Total Contactados por Email en Selección", f"{total_contactados_email_seleccion:,}")
    respuestas_email = df_contactados_email[df_contactados_email[COL_RESPUESTA_EMAIL] == "si"].shape[0] if COL_RESPUESTA_EMAIL in df_contactos_email.columns else 0
    sesiones_agendadas_email = df_contactados_email[df_contactados_email[COL_SESION_AGENDADA_EMAIL] == "si"].shape[0] if COL_SESION_AGENDADA_EMAIL in df_contactos_email.columns else 0
    e_col1, e_col2 = st.columns(2)
    e_col1.metric("Respuestas Email", f"{respuestas_email:,}")
    e_col2.metric("Sesiones Agendadas vía Email", f"{sesiones_agendadas_email:,}")
    funnel_data_email = pd.DataFrame({"Etapa": ["Contactados por Email", "Respuestas Email", "Sesiones Agendadas por Email"], "Cantidad": [total_contactados_email_seleccion, respuestas_email, sesiones_agendadas_email]})
    fig_funnel_email = px.funnel(funnel_data_email, x='Cantidad', y='Etapa', title="Embudo Conversión Prospección por Email")
    st.plotly_chart(fig_funnel_email, use_container_width=True)
    st.markdown("---")

# --- Lógica Principal de la Página ---
df_base_campaigns_loaded = load_and_prepare_campaign_data()

if df_base_campaigns_loaded.empty:
    st.error("No se pudieron cargar datos válidos de campañas desde la fuente. La página no puede generar análisis.")
else:
    (selected_campaigns, 
     start_date_filter, 
     end_date_filter, 
     selected_prospectors, 
     selected_avatars) = display_campaign_filters(df_base_campaigns_loaded.copy()) 

    df_filtered_common = apply_common_filters(
        df_base_campaigns_loaded.copy(), 
        selected_campaigns, 
        selected_prospectors, 
        selected_avatars
    )
    
    display_campaign_potential(df_base_campaigns_loaded.copy()) 
    display_manual_prospecting_analysis(df_filtered_common.copy(), start_date_filter, end_date_filter)
    display_global_manual_prospecting_deep_dive(df_common_filtered.copy(), start_date_filter, end_date_filter)
    display_email_prospecting_analysis(df_filtered_common.copy())

# ==============================================================================
# INICIO DE CÓDIGO NUEVO Y SEPARADO
# ==============================================================================

@st.cache_data(ttl=600)
def load_email_stats_from_new_sheet():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Error al cargar credenciales para la hoja de estadísticas: {e}")
        return None, None
    try:
        sheet_url = st.secrets.get(EMAIL_STATS_SHEET_URL_KEY)
        if not sheet_url:
            return None, None
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.sheet1
        all_data = sheet.get_all_values()
        df = pd.DataFrame(all_data)
        tabla1_start_row, tabla2_start_row = -1, -1
        for i, row in enumerate(df[0]):
            if str(row).strip() == "Tabla_1": tabla1_start_row = i
            elif str(row).strip() == "Tabla_2": tabla2_start_row = i
        df_t1, df_t2 = None, None
        if tabla1_start_row != -1:
            end_t1 = tabla2_start_row if tabla2_start_row != -1 else len(df)
            df_t1_raw = df.iloc[tabla1_start_row:end_t1].reset_index(drop=True)
            if len(df_t1_raw) > 2:
                header_t1 = df_t1_raw.iloc[1]
                df_t1 = df_t1_raw[2:].copy(); df_t1.columns = header_t1
                df_t1 = df_t1[df_t1.iloc[:, 0].astype(str).str.strip() != '']
                df_t1 = df_t1.loc[:, df_t1.columns.notna() & (df_t1.columns != '')]
        if tabla2_start_row != -1:
            df_t2_raw = df.iloc[tabla2_start_row:].reset_index(drop=True)
            if len(df_t2_raw) > 2:
                header_t2 = df_t2_raw.iloc[1]
                df_t2 = df_t2_raw[2:].copy(); df_t2.columns = header_t2
                df_t2 = df_t2[df_t2.iloc[:, 0].astype(str).str.strip() != '']
                df_t2 = df_t2.loc[:, df_t2.columns.notna() & (df_t2.columns != '')]
        return df_t1, df_t2
    except gspread.exceptions.SpreadsheetNotFound:
         st.error(f"Error: No se encontró el nuevo archivo de 'Números por correo'. Verifica la URL en el secret '{EMAIL_STATS_SHEET_URL_KEY}' y que el archivo esté compartido.")
         return None, None
    except Exception as e:
        st.error(f"Error al procesar el nuevo archivo de 'Números por correo': {e}")
        return None, None

def display_new_email_stats_analysis(df_tabla, campaign_name):
    st.markdown(f"### Análisis de Rendimiento: {campaign_name}")
    if df_tabla is None or df_tabla.empty:
        st.info(f"No se encontraron datos para la campaña {campaign_name} en la hoja.")
        return
    cols_to_numeric = ['Sent', 'Open Number', 'Responses', 'Sesion']
    for col in cols_to_numeric:
        if col in df_tabla.columns:
            df_tabla[col] = df_tabla[col].str.replace(r'[^0-9]', '', regex=True).replace('', '0')
            df_tabla[col] = pd.to_numeric(df_tabla[col], errors='coerce').fillna(0)
        else: df_tabla[col] = 0
    total_sent = df_tabla['Sent'].sum()
    total_opens = df_tabla['Open Number'].sum()
    total_responses = df_tabla['Responses'].sum()
    total_sessions = df_tabla['Sesion'].sum()
    open_rate = (total_opens / total_sent * 100) if total_sent > 0 else 0
    response_rate_vs_opens = (total_responses / total_opens * 100) if total_opens > 0 else 0
    session_rate_vs_responses = (total_sessions / total_responses * 100) if total_responses > 0 else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Enviados 📤", f"{total_sent:,.0f}")
    col2.metric("Total Aperturas 📬", f"{total_opens:,.0f}", f"{open_rate:.1f}% Tasa Apertura")
    col3.metric("Total Respuestas 💬", f"{total_responses:,.0f}", f"{response_rate_vs_opens:.1f}% vs Aperturas")
    col4.metric("Total Sesiones 🗓️", f"{total_sessions:,.0f}", f"{session_rate_vs_responses:.1f}% vs Respuestas")
    funnel_df = pd.DataFrame({"Etapa": ["Enviados", "Aperturas", "Respuestas", "Sesiones"], "Cantidad": [total_sent, total_opens, total_responses, total_sessions]})
    fig_funnel = px.funnel(funnel_df, x='Cantidad', y='Etapa', title=f"Embudo de Conversión - {campaign_name}")
    st.plotly_chart(fig_funnel, use_container_width=True)
    with st.expander("Ver datos detallados de la tabla"):
        st.dataframe(df_tabla, use_container_width=True)

st.markdown("---")
st.header("Análisis de Rendimiento por Correo Campaña")
st.caption("Esta sección carga los datos desde la hoja de 'Números por correo campaña' de forma independiente.")
df_h2r_isa, df_p2p_elsa = load_email_stats_from_new_sheet()
if df_h2r_isa is None and df_p2p_elsa is None:
    st.info("Para ver este análisis, asegúrate de haber configurado la clave 'email_stats_sheet_url' en tus secretos de Streamlit.")
else:
    if df_h2r_isa is not None:
        display_new_email_stats_analysis(df_h2r_isa, "H2R - ISA")
        st.markdown("---")
    if df_p2p_elsa is not None:
        display_new_email_stats_analysis(df_p2p_elsa, "P2P - ELSA")

st.markdown("---")
st.info("Esta página de análisis de campañas ha sido desarrollada por Johnsito ✨")
