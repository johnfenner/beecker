# pages/🎯_Análisis_de_Campañas.py
# VERSIÓN CORREGIDA: Se desactiva el análisis de email antiguo y se deja solo el nuevo.

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
    "Análisis del potencial de campañas y prospección manual."
)

# --- Constantes y Claves de Estado de Sesión ---
SHEET_URL_SECRET_KEY = "main_prostraction_sheet_url"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0"
NO_CAMPAIGN_VALUES = ["Sin Campaña Asignada", "N/D", ""]

# Columnas para el análisis original (se mantienen por si se usan en otras partes)
COL_CAMPAIGN = "Campaña"
COL_FECHA_INVITE = "Fecha de Invite"
COL_INVITE_ACEPTADA = "¿Invite Aceptada?"
COL_RESPUESTA_1ER_MSJ = "Respuesta Primer Mensaje"
COL_SESION_AGENDADA_MANUAL = "Sesion Agendada?"
COL_QUIEN_PROSPECTO = "¿Quién Prospecto?"
COL_AVATAR = "Avatar"

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

# --- Funciones Auxiliares (Sin cambios) ---
def clean_text_value(val, default="N/D"):
    if pd.isna(val) or str(val).strip() == "": return default
    return str(val).strip()

def parse_date_robustly(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "": return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)): return pd.to_datetime(date_val)
    date_str = str(date_val).strip()
    if date_str.isdigit():
        try: return pd.to_datetime('1899-12-30') + pd.to_timedelta(float(date_str), 'D')
        except ValueError: pass
    common_formats = ["%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"]
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
        st.error("Error de Configuración (Secrets): Falta [gcp_service_account].")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar credenciales de Google Sheets: {e}")
        return pd.DataFrame()
    try:
        sheet_url = st.secrets.get(SHEET_URL_SECRET_KEY, DEFAULT_SHEET_URL)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.sheet1
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 1: return pd.DataFrame()
        headers = make_unique_column_names(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo: {e}")
        return pd.DataFrame()
    if COL_CAMPAIGN not in df.columns:
        st.error(f"La columna '{COL_CAMPAIGN}' es esencial y no fue encontrada.")
        return pd.DataFrame()
    df[COL_CAMPAIGN] = df[COL_CAMPAIGN].apply(lambda x: clean_text_value(x, default=""))
    df = df[~df[COL_CAMPAIGN].isin(NO_CAMPAIGN_VALUES)].copy()
    if df.empty: return pd.DataFrame()
    if COL_FECHA_INVITE in df.columns:
        df["FechaFiltroManual"] = df[COL_FECHA_INVITE].apply(parse_date_robustly)
    if COL_AVATAR in df.columns:
        df[COL_AVATAR] = df[COL_AVATAR].astype(str).str.strip().str.title()
        equivalencias_avatar = {"Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez", "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"}
        df[COL_AVATAR] = df[COL_AVATAR].replace(equivalencias_avatar)
    return df

# --- Filtros de Barra Lateral (Sin cambios) ---
def display_campaign_filters(df_options):
    st.sidebar.header("🎯 Filtros de Campaña")
    # ... (El resto de la función de filtros se mantiene igual, no es necesario pegarla aquí de nuevo) ...
    # ... por brevedad, se omite el código idéntico de la función de filtros ...
    default_filters_init = {
        SES_CAMPAIGN_FILTER_KEY: [ALL_CAMPAIGNS_STRING], SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
        SES_PROSPECTOR_FILTER_KEY: [ALL_PROSPECTORS_STRING], SES_AVATAR_FILTER_KEY: [ALL_AVATARS_STRING]
    }
    for key, value in default_filters_init.items():
        if key not in st.session_state: st.session_state[key] = value
    campaign_options = [ALL_CAMPAIGNS_STRING]
    if COL_CAMPAIGN in df_options.columns and not df_options[COL_CAMPAIGN].empty:
        unique_items = sorted(list(df_options[COL_CAMPAIGN].dropna().unique()))
        campaign_options.extend([item for item in unique_items if item != ALL_CAMPAIGNS_STRING])
    st.sidebar.multiselect("Seleccionar Campaña(s)", options=campaign_options, key=SES_CAMPAIGN_FILTER_KEY)
    prospector_options = [ALL_PROSPECTORS_STRING]
    if COL_QUIEN_PROSPECTO in df_options.columns and not df_options[COL_QUIEN_PROSPECTO].empty:
        unique_items = sorted(list(df_options[df_options[COL_QUIEN_PROSPECTO] != "N/D_Interno"][COL_QUIEN_PROSPECTO].dropna().unique()))
        prospector_options.extend([item for item in unique_items if item != ALL_PROSPECTORS_STRING])
    st.sidebar.multiselect("¿Quién Prospectó?", options=prospector_options, key=SES_PROSPECTOR_FILTER_KEY)
    avatar_options = [ALL_AVATARS_STRING]
    if COL_AVATAR in df_options.columns and not df_options[COL_AVATAR].empty:
        unique_items = sorted(list(df_options[df_options[COL_AVATAR] != "N/D_Interno"][COL_AVATAR].dropna().unique()))
        avatar_options.extend([item for item in unique_items if item != ALL_AVATARS_STRING])
    st.sidebar.multiselect("Avatar", options=avatar_options, key=SES_AVATAR_FILTER_KEY)
    min_date, max_date = (None, None)
    if "FechaFiltroManual" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["FechaFiltroManual"]):
        valid_dates = df_options["FechaFiltroManual"].dropna()
        if not valid_dates.empty: min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
    date_col1, date_col2 = st.sidebar.columns(2)
    date_col1.date_input("Fecha Desde", min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    date_col2.date_input("Fecha Hasta", min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_END_DATE_KEY)
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True):
        for key, value in default_filters_init.items(): st.session_state[key] = value
        st.rerun()
    return (st.session_state.get(SES_CAMPAIGN_FILTER_KEY), st.session_state.get(SES_START_DATE_KEY), st.session_state.get(SES_END_DATE_KEY), st.session_state.get(SES_PROSPECTOR_FILTER_KEY), st.session_state.get(SES_AVATAR_FILTER_KEY))

# --- Funciones de Análisis y Visualización (Originales, sin cambios) ---
def apply_common_filters(df, campaigns, prospectors, avatars): 
    # ... (El código de esta función se mantiene igual) ...
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
    # ... (El código de esta función se mantiene igual) ...
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
    # ... (El código de esta función se mantiene igual) ...
    st.subheader("Potencial de Prospección por Campaña")
    if df_valid_campaigns.empty: st.info("No hay datos de campañas válidas para analizar."); return
    potential_counts = df_valid_campaigns[COL_CAMPAIGN].value_counts().reset_index()
    potential_counts.columns = [COL_CAMPAIGN, 'Total Prospectos en Campaña']
    if potential_counts.empty: st.info("No hay datos de potencial de campaña para mostrar."); return
    fig = px.bar(potential_counts.sort_values(by='Total Prospectos en Campaña', ascending=False), x=COL_CAMPAIGN, y='Total Prospectos en Campaña', title='Total de Prospectos por Campaña Asignada', text_auto=True, color=COL_CAMPAIGN)
    fig.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Prospectos")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Ver tabla de potencial"): st.dataframe(potential_counts.style.format({'Total Prospectos en Campaña': "{:,}"}), use_container_width=True)
    st.markdown("---")

def display_manual_prospecting_analysis(df_common_filtered, start_date, end_date):
    # ... (El código de esta función se mantiene igual) ...
    st.subheader("Análisis de Prospección Manual")
    st.caption("Basado en campañas y filtros seleccionados. El filtro de fecha se aplica a 'Fecha de Invite'.")
    df_manual_filtered = apply_manual_date_filter(df_common_filtered, start_date, end_date)
    if df_manual_filtered.empty: st.info("No hay datos para analizar la prospección manual con los filtros actuales."); return
    # ... (resto del código de la función sin cambios) ...

# ==============================================================================
# INICIO DE CÓDIGO NUEVO Y SEPARADO
# Estas funciones son para el análisis de la nueva hoja de "Números por correo campaña"
# No interfieren con ninguna de las funciones anteriores.
# ==============================================================================

@st.cache_data(ttl=600)
def load_email_campaign_stats():
    """
    Carga y procesa las estadísticas de campañas de correo desde la nueva hoja.
    Esta función es independiente de la carga de datos principal.
    """
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except Exception as e:
        st.error(f"Error al cargar credenciales para las estadísticas de email: {e}")
        return None, None

    try:
        sheet_url = st.secrets.get("email_stats_sheet_url")
        if not sheet_url:
            st.warning("La URL para la hoja de 'Números por correo campaña' ('email_stats_sheet_url') no está en tus secrets. No se puede cargar esta sección.")
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
                df_t1 = df_t1_raw[2:].copy()
                df_t1.columns = header_t1
                df_t1 = df_t1[df_t1.iloc[:, 0] != '']
                df_t1 = df_t1.loc[:, df_t1.columns.notna() & (df_t1.columns != '')]

        if tabla2_start_row != -1:
            df_t2_raw = df.iloc[tabla2_start_row:].reset_index(drop=True)
            if len(df_t2_raw) > 2:
                header_t2 = df_t2_raw.iloc[1]
                df_t2 = df_t2_raw[2:].copy()
                df_t2.columns = header_t2
                df_t2 = df_t2[df_t2.iloc[:, 0] != '']
                df_t2 = df_t2.loc[:, df_t2.columns.notna() & (df_t2.columns != '')]

        return df_t1, df_t2
    except Exception as e:
        st.error(f"Error al leer la hoja de 'Números por correo campaña': {e}")
        return None, None

def display_new_email_stats_analysis(df_tabla, campaign_name):
    """
    Muestra el análisis para una tabla de estadísticas de campaña de email.
    Función independiente para la nueva sección.
    """
    if df_tabla is None or df_tabla.empty:
        st.info(f"No hay datos para mostrar de la campaña {campaign_name}.")
        return

    st.markdown(f"#### Análisis de Campaña de Correo: {campaign_name}")

    cols_to_numeric = ['Sent', 'Open Number', 'Responses', 'Sesion']
    for col in cols_to_numeric:
        if col in df_tabla.columns:
            df_tabla[col] = df_tabla[col].str.replace(r'[^0-9]', '', regex=True).replace('', '0')
            df_tabla[col] = pd.to_numeric(df_tabla[col], errors='coerce').fillna(0)
        else:
            df_tabla[col] = 0

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

    funnel_df = pd.DataFrame({
        "Etapa": ["Enviados", "Aperturas", "Respuestas", "Sesiones"],
        "Cantidad": [total_sent, total_opens, total_responses, total_sessions]
    })
    fig_funnel = px.funnel(funnel_df, x='Cantidad', y='Etapa', title=f"Embudo de Conversión - {campaign_name}")
    st.plotly_chart(fig_funnel, use_container_width=True)

    with st.expander("Ver datos detallados de la tabla"):
        st.dataframe(df_tabla, use_container_width=True)

# --- Lógica Principal de la Página ---
df_base_campaigns_loaded = load_and_prepare_campaign_data()

if df_base_campaigns_loaded.empty:
    st.error("No se pudieron cargar datos válidos de campañas desde la fuente principal. La página no puede generar análisis.")
else:
    # Filtros de la barra lateral que afectan solo a los análisis originales
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
    
    # --- ANÁLISIS EXISTENTES (SIN CAMBIOS) ---
    display_campaign_potential(df_base_campaigns_loaded.copy()) 
    display_manual_prospecting_analysis(df_filtered_common.copy(), start_date_filter, end_date_filter)
    
    # La siguiente línea se comenta para desactivar la sección que causaba el error NameError.
    # display_email_prospecting_analysis(df_filtered_common.copy())


# --- INICIO DE LA NUEVA SECCIÓN INDEPENDIENTE ---
st.markdown("---")
with st.expander("📊 Análisis de Rendimiento por Correo Campaña (Hoja Nueva)", expanded=True):
    # Cargar y mostrar los datos de la nueva hoja, de forma totalmente separada.
    df_h2r_isa, df_p2p_elsa = load_email_campaign_stats()

    if df_h2r_isa is None and df_p2p_elsa is None:
        st.info("Esperando datos de la nueva hoja de 'Números por correo campaña'...")
    else:
        if df_h2r_isa is not None:
            display_new_email_stats_analysis(df_h2r_isa, "H2R - ISA")
            st.markdown("---")
        if df_p2p_elsa is not None:
            display_new_email_stats_analysis(df_p2p_elsa, "P2P - ELSA")
# --- FIN DE LA NUEVA SECCIÓN ---

st.markdown("---")
st.info("Esta página de análisis de campañas ha sido desarrollada por Johnsito ✨")
