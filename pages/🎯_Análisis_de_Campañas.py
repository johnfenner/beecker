# pages/📢_Campañas.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
from collections import Counter

# --- Page Configuration ---
st.set_page_config(page_title="Análisis de Campañas", layout="wide")
st.title("📢 Análisis de Campañas")
st.markdown(
    "Análisis del potencial de campañas, prospección manual y prospección por email. "
    "Este análisis excluye prospectos sin una campaña asignada."
)

# --- Constants and Session State Keys ---
SHEET_URL_SECRET_KEY = "main_prostraction_sheet_url"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0" # Fallback
NO_CAMPAIGN_VALUES = ["Sin Campaña Asignada", "N/D", ""] 

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

SES_CAMPAIGN_FILTER_KEY = "campaign_page_campaign_filter_v3"
SES_START_DATE_KEY = "campaign_page_start_date_v3"
SES_END_DATE_KEY = "campaign_page_end_date_v3"
SES_PROSPECTOR_FILTER_KEY = "campaign_page_prospector_filter_v3"
SES_AVATAR_FILTER_KEY = "campaign_page_avatar_filter_v3"

# --- Helper Functions (Self-Contained) ---

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
        st.error("Error de Configuración (Secrets): Falta [gcp_service_account].")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar credenciales de Google Sheets: {e}")
        return pd.DataFrame()
    try:
        sheet_url = st.secrets.get(SHEET_URL_SECRET_KEY, DEFAULT_SHEET_URL)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.sheet1; raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) < 1:
            st.warning("Hoja de Google Sheets vacía o ilegible.")
            return pd.DataFrame()
        headers = make_unique_column_names(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: Hoja no encontrada en URL de secrets ('{SHEET_URL_SECRET_KEY}').")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo: {e}")
        return pd.DataFrame()

    if COL_CAMPAIGN not in df.columns:
        st.error(f"Columna '{COL_CAMPAIGN}' no encontrada. Análisis de campañas no puede continuar.")
        return pd.DataFrame()
    df[COL_CAMPAIGN] = df[COL_CAMPAIGN].apply(lambda x: clean_text_value(x, default=""))
    df = df[~df[COL_CAMPAIGN].isin(NO_CAMPAIGN_VALUES)].copy()
    if df.empty:
        st.warning("No se encontraron prospectos con campañas asignadas válidas.")
        return pd.DataFrame()

    date_cols_manual = [COL_FECHA_INVITE, COL_FECHA_SESION_MANUAL]
    for col in date_cols_manual:
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
        
    if COL_FECHA_INVITE in df.columns and not df[COL_FECHA_INVITE].isnull().all():
         df["FechaFiltroPrincipal"] = df[COL_FECHA_INVITE]
    elif COL_FECHA_SESION_EMAIL in df.columns and not df[COL_FECHA_SESION_EMAIL].isnull().all(): # Fallback
         df["FechaFiltroPrincipal"] = df[COL_FECHA_SESION_EMAIL]
    else: df["FechaFiltroPrincipal"] = pd.NaT
    return df

# --- Sidebar Filters ---
def display_campaign_filters(df_options):
    st.sidebar.header("🎯 Filtros de Campaña")
    default_filters = {
        SES_CAMPAIGN_FILTER_KEY: ["– Todas –"], SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
        SES_PROSPECTOR_FILTER_KEY: ["– Todos –"], SES_AVATAR_FILTER_KEY: ["– Todos –"]
    }
    for key, value in default_filters.items():
        if key not in st.session_state: st.session_state[key] = value

    campaign_options = ["– Todas –"]
    if COL_CAMPAIGN in df_options.columns and not df_options[COL_CAMPAIGN].empty:
        campaign_options.extend(sorted(df_options[COL_CAMPAIGN].dropna().unique())) 
    current_campaign_selection = st.session_state[SES_CAMPAIGN_FILTER_KEY]
    valid_campaign_selection = [c for c in current_campaign_selection if c in campaign_options]
    if not valid_campaign_selection: valid_campaign_selection = ["– Todas –"]
    st.session_state[SES_CAMPAIGN_FILTER_KEY] = valid_campaign_selection
    selected_campaigns = st.sidebar.multiselect("Seleccionar Campaña(s)", options=campaign_options, key=SES_CAMPAIGN_FILTER_KEY)

    min_date, max_date = None, None
    if "FechaFiltroPrincipal" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["FechaFiltroPrincipal"]):
        valid_dates = df_options["FechaFiltroPrincipal"].dropna()
        if not valid_dates.empty: min_date, max_date = valid_dates.min().date(), valid_dates.max().date()
    date_col1, date_col2 = st.sidebar.columns(2)
    start_date = date_col1.date_input("Fecha Desde", value=st.session_state[SES_START_DATE_KEY], min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    end_date = date_col2.date_input("Fecha Hasta", value=st.session_state[SES_END_DATE_KEY], min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_END_DATE_KEY)

    prospector_options = ["– Todos –"]
    if COL_QUIEN_PROSPECTO in df_options.columns and not df_options[COL_QUIEN_PROSPECTO].empty:
        prospector_options.extend(sorted(df_options[df_options[COL_QUIEN_PROSPECTO] != "N/D_Interno"][COL_QUIEN_PROSPECTO].dropna().unique()))
    current_prospector_selection = st.session_state[SES_PROSPECTOR_FILTER_KEY]
    valid_prospector_selection = [p for p in current_prospector_selection if p in prospector_options]
    if not valid_prospector_selection: valid_prospector_selection = ["– Todos –"]
    st.session_state[SES_PROSPECTOR_FILTER_KEY] = valid_prospector_selection
    selected_prospectors = st.sidebar.multiselect("¿Quién Prospectó?", prospector_options, key=SES_PROSPECTOR_FILTER_KEY)

    avatar_options = ["– Todos –"]
    if COL_AVATAR in df_options.columns and not df_options[COL_AVATAR].empty:
        avatar_options.extend(sorted(df_options[df_options[COL_AVATAR] != "N/D_Interno"][COL_AVATAR].dropna().unique()))
    current_avatar_selection = st.session_state[SES_AVATAR_FILTER_KEY]
    valid_avatar_selection = [a for a in current_avatar_selection if a in avatar_options]
    if not valid_avatar_selection: valid_avatar_selection = ["– Todos –"]
    st.session_state[SES_AVATAR_FILTER_KEY] = valid_avatar_selection
    selected_avatars = st.sidebar.multiselect("Avatar", avatar_options, key=SES_AVATAR_FILTER_KEY)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True):
        for key, value in default_filters.items(): st.session_state[key] = value
        st.rerun()
    return selected_campaigns, start_date, end_date, selected_prospectors, selected_avatars

def apply_campaign_filters(df, campaigns, start_date, end_date, prospectors, avatars):
    if df.empty: return df
    df_filtered = df.copy()
    if campaigns and "– Todas –" not in campaigns:
        df_filtered = df_filtered[df_filtered[COL_CAMPAIGN].isin(campaigns)]
    if "FechaFiltroPrincipal" in df_filtered.columns and pd.api.types.is_datetime64_any_dtype(df_filtered["FechaFiltroPrincipal"]):
        if start_date and end_date:
            df_filtered = df_filtered[(df_filtered["FechaFiltroPrincipal"].dt.date >= start_date) & (df_filtered["FechaFiltroPrincipal"].dt.date <= end_date)]
        elif start_date: df_filtered = df_filtered[df_filtered["FechaFiltroPrincipal"].dt.date >= start_date]
        elif end_date: df_filtered = df_filtered[df_filtered["FechaFiltroPrincipal"].dt.date <= end_date]
    if prospectors and "– Todos –" not in prospectors:
        df_filtered = df_filtered[df_filtered[COL_QUIEN_PROSPECTO].isin(prospectors)]
    if avatars and "– Todos –" not in avatars:
        df_filtered = df_filtered[df_filtered[COL_AVATAR].isin(avatars)]
    return df_filtered

# --- Analysis and Display Functions ---

def display_campaign_potential(df_valid_campaigns):
    st.subheader("Potencial de Prospección por Campaña")
    if df_valid_campaigns.empty:
        st.info("No hay datos de campañas válidas para analizar el potencial.")
        return
    potential_counts = df_valid_campaigns[COL_CAMPAIGN].value_counts().reset_index()
    potential_counts.columns = [COL_CAMPAIGN, 'Total Prospectos en Campaña']
    fig = px.bar(potential_counts.sort_values(by='Total Prospectos en Campaña', ascending=False),
        x=COL_CAMPAIGN, y='Total Prospectos en Campaña', title='Total de Prospectos por Campaña Asignada', text_auto=True, color=COL_CAMPAIGN)
    fig.update_layout(xaxis_tickangle=-45, yaxis_title="Número de Prospectos")
    st.plotly_chart(fig, use_container_width=True)
    with st.expander("Ver tabla de potencial"):
        st.dataframe(potential_counts.style.format({'Total Prospectos en Campaña': "{:,}"}), use_container_width=True)
    st.markdown("---")

# Debes reemplazar la función display_manual_prospecting_analysis existente
# en tu archivo pages/📢_Campañas.py con esta versión completa.

def display_manual_prospecting_analysis(df_filtered_campaigns):
    st.subheader("Análisis de Prospección Manual")
    st.caption("Basado en campañas y filtros seleccionados en la barra lateral. Muestra prospectos asignados, cuántos fueron contactados manualmente y su progreso en el embudo.")

    if df_filtered_campaigns.empty:
        st.info("No hay datos para analizar la prospección manual con los filtros actuales.")
        return

    total_in_current_filter = len(df_filtered_campaigns)
    # Contactos Manuales Iniciados son aquellos con Fecha de Invite
    df_contactos_iniciados = df_filtered_campaigns[df_filtered_campaigns[COL_FECHA_INVITE].notna()].copy()
    total_contactos_iniciados_manual = len(df_contactos_iniciados)

    col_metric1, col_metric2 = st.columns(2)
    col_metric1.metric("Prospectos en Selección Actual (Asignados en Campaña)", f"{total_in_current_filter:,}")
    col_metric2.metric("De estos, con Contacto Manual Iniciado (tienen Fecha Invite)", f"{total_contactos_iniciados_manual:,}")
    
    if total_contactos_iniciados_manual == 0 and total_in_current_filter > 0:
        st.warning("De los prospectos en la selección actual, ninguno tiene un contacto manual iniciado (Fecha de Invite registrada).")
        # Aún así, mostraremos la tabla de asignados si hay prospectos en el filtro.
    elif total_contactos_iniciados_manual == 0 and total_in_current_filter == 0:
        st.info("No se encontraron prospectos asignados ni contactos manuales iniciados para la selección actual.")
        return


    st.markdown("#### Trazabilidad Detallada: Asignados vs. Contactados y Embudo por Prospectador")
    # Prospectos Asignados en la selección actual (cumplen filtros de sidebar)
    assigned_counts = df_filtered_campaigns.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO], as_index=False).size().rename(columns={'size': 'Prospectos Asignados'})
    
    # Contactos Manuales Iniciados (tienen Fecha de Invite)
    contactos_iniciados_counts = df_contactos_iniciados.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO], as_index=False).size().rename(columns={'size': 'Contactos Manuales Iniciados'})
    
    # Métricas del embudo para aquellos con Contacto Manual Iniciado
    funnel_metrics = pd.DataFrame() # Inicializar vacío
    if not df_contactos_iniciados.empty:
        funnel_metrics = df_contactos_iniciados.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO], as_index=False).agg(
            Invites_Aceptadas=(COL_INVITE_ACEPTADA, lambda x: (x == "si").sum()),
            Respuestas_1er_Msj=(COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum()), 
            Sesiones_Agendadas=(COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
        )

    # Unir la información
    # Empezar con assigned_counts para asegurar que todos los asignados aparezcan
    trace_df = pd.merge(assigned_counts, contactos_iniciados_counts, on=[COL_CAMPAIGN, COL_QUIEN_PROSPECTO], how='left')
    if not funnel_metrics.empty:
        trace_df = pd.merge(trace_df, funnel_metrics, on=[COL_CAMPAIGN, COL_QUIEN_PROSPECTO], how='left')
    else: # Si no hay contactos iniciados, las columnas del funnel no existirán en funnel_metrics
        trace_df['Invites_Aceptadas'] = 0
        trace_df['Respuestas_1er_Msj'] = 0
        trace_df['Sesiones_Agendadas'] = 0

    
    # Rellenar NaNs para las cuentas (si un prospectador tiene asignados pero 0 contactados, o 0 en etapas del embudo)
    count_cols_fill = ['Contactos Manuales Iniciados', 'Invites_Aceptadas', 'Respuestas_1er_Msj', 'Sesiones_Agendadas']
    for col in count_cols_fill:
        if col not in trace_df.columns: # Añadir columna si no existe por un merge vacío
            trace_df[col] = 0
        trace_df[col] = trace_df[col].fillna(0).astype(int)

    # Calcular tasas
    trace_df['Tasa Inicio Prospección (%)'] = ((trace_df['Contactos Manuales Iniciados'] / trace_df['Prospectos Asignados']) * 100).fillna(0).round(1)
    
    base_rates_embudo = trace_df['Contactos Manuales Iniciados'] # El embudo se calcula sobre los contactados
    trace_df['Tasa Aceptación vs Contactos (%)'] = ((trace_df['Invites_Aceptadas'] / base_rates_embudo) * 100).fillna(0).round(1)
    trace_df['Tasa Respuesta vs Aceptadas (%)'] = ((trace_df['Respuestas_1er_Msj'] / trace_df['Invites_Aceptadas']) * 100).fillna(0).round(1)
    trace_df['Tasa Sesión vs Respuestas (%)'] = ((trace_df['Sesiones_Agendadas'] / trace_df['Respuestas_1er_Msj']) * 100).fillna(0).round(1)
    trace_df['Tasa Sesión Global vs Contactos (%)'] = ((trace_df['Sesiones_Agendadas'] / base_rates_embudo) * 100).fillna(0).round(1)
    
    rate_cols = ['Tasa Inicio Prospección (%)', 'Tasa Aceptación vs Contactos (%)', 'Tasa Respuesta vs Aceptadas (%)', 'Tasa Sesión vs Respuestas (%)', 'Tasa Sesión Global vs Contactos (%)']
    for r_col in rate_cols:
        trace_df[r_col] = trace_df[r_col].apply(lambda x: 0 if pd.isna(x) or x == float('inf') or x == float('-inf') else x)

    # Excluir "N/D_Interno" de la tabla final si existe como prospectador
    trace_df_display = trace_df[trace_df[COL_QUIEN_PROSPECTO] != "N/D_Interno"].copy()

    if not trace_df_display.empty:
        column_order = [
            COL_CAMPAIGN, COL_QUIEN_PROSPECTO, 
            'Prospectos Asignados', 'Contactos Manuales Iniciados', 'Tasa Inicio Prospección (%)',
            'Invites_Aceptadas', 'Tasa Aceptación vs Contactos (%)',
            'Respuestas_1er_Msj', 'Tasa Respuesta vs Aceptadas (%)',
            'Sesiones_Agendadas', 'Tasa Sesión vs Respuestas (%)',
            'Tasa Sesión Global vs Contactos (%)'
        ]
        # Asegurar que solo se seleccionan columnas que existen en trace_df_display
        column_order_existing = [col for col in column_order if col in trace_df_display.columns]

        st.dataframe(trace_df_display[column_order_existing].style.format({
            'Prospectos Asignados': "{:,}", 'Contactos Manuales Iniciados': "{:,}", 
            'Invites_Aceptadas': "{:,}", 'Respuestas_1er_Msj': "{:,}", 'Sesiones_Agendadas': "{:,}",
            'Tasa Inicio Prospección (%)': "{:.1f}%", 
            'Tasa Aceptación vs Contactos (%)': "{:.1f}%",
            'Tasa Respuesta vs Aceptadas (%)': "{:.1f}%", 
            'Tasa Sesión vs Respuestas (%)': "{:.1f}%",
            'Tasa Sesión Global vs Contactos (%)': "{:.1f}%"
        }), use_container_width=True, height=400) # Aumenté un poco la altura
    else: 
        st.info("No hay datos para la tabla de trazabilidad detallada después de filtrar N/D_Interno o no hay prospectadores asignados.")

    # Embudo Agregado (solo si hay contactos manuales iniciados)
    if total_contactos_iniciados_manual > 0:
        st.markdown("#### Embudo de Conversión Agregado (para Contactos Manuales Iniciados)")
        invites_aceptadas_agg = df_contactos_iniciados[df_contactos_iniciados[COL_INVITE_ACEPTADA] == "si"].shape[0]
        respuestas_1er_msj_agg = df_contactos_iniciados[df_contactos_iniciados[COL_RESPUESTA_1ER_MSJ] == "si"].shape[0]
        sesiones_agendadas_agg = df_contactos_iniciados[df_contactos_iniciados[COL_SESION_AGENDADA_MANUAL] == "si"].shape[0]

        funnel_data_manual_agg = pd.DataFrame({
            "Etapa": ["Contactos Manuales Iniciados", "Invites Aceptadas", "Respuestas 1er Msj", "Sesiones Agendadas"],
            "Cantidad": [total_contactos_iniciados_manual, invites_aceptadas_agg, respuestas_1er_msj_agg, sesiones_agendadas_agg]
        })
        fig_funnel_manual_agg = px.funnel(funnel_data_manual_agg, x='Cantidad', y='Etapa', title="Embudo Agregado Prospección Manual")
        st.plotly_chart(fig_funnel_manual_agg, use_container_width=True)
    
    st.markdown("---")


def display_email_prospecting_analysis(df_filtered_campaigns):
    st.subheader("Análisis de Prospección por Email")
    st.caption("Basado en campañas y filtros seleccionados en la barra lateral.")

    if df_filtered_campaigns.empty:
        st.info("No hay datos para analizar la prospección por email con los filtros actuales.")
        return

    df_contactados_email = df_filtered_campaigns[df_filtered_campaigns[COL_CONTACTADOS_EMAIL] == "si"].copy()
    total_contactados_email_seleccion = len(df_contactados_email)

    if total_contactados_email_seleccion == 0:
        st.info("No se encontraron contactos por email (Contactados por Campaña = 'si') para la selección actual.")
        return

    st.metric("Total Contactados por Email en Selección", f"{total_contactados_email_seleccion:,}")
    respuestas_email = df_contactados_email[df_contactados_email[COL_RESPUESTA_EMAIL] == "si"].shape[0]
    sesiones_agendadas_email = df_contactados_email[df_contactados_email[COL_SESION_AGENDADA_EMAIL] == "si"].shape[0]

    e_col1, e_col2 = st.columns(2)
    e_col1.metric("Respuestas Email", f"{respuestas_email:,}")
    e_col2.metric("Sesiones Agendadas vía Email", f"{sesiones_agendadas_email:,}")

    funnel_data_email = pd.DataFrame({
        "Etapa": ["Contactados por Email", "Respuestas Email", "Sesiones Agendadas por Email"],
        "Cantidad": [total_contactados_email_seleccion, respuestas_email, sesiones_agendadas_email]
    })
    fig_funnel_email = px.funnel(funnel_data_email, x='Cantidad', y='Etapa', title="Embudo Conversión Prospección por Email")
    st.plotly_chart(fig_funnel_email, use_container_width=True)
    st.markdown("---")

# --- Main Page Logic ---
df_base_campaigns_loaded = load_and_prepare_campaign_data()

if df_base_campaigns_loaded.empty:
    st.error("No se pudieron cargar datos de campañas válidas. La página no puede continuar.")
    st.stop()

selected_campaigns, start_date_filter, end_date_filter, selected_prospectors, selected_avatars = display_campaign_filters(df_base_campaigns_loaded.copy())
df_filtered_by_sidebar = apply_campaign_filters(df_base_campaigns_loaded.copy(), selected_campaigns, start_date_filter, end_date_filter, selected_prospectors, selected_avatars)

display_campaign_potential(df_base_campaigns_loaded.copy())
display_manual_prospecting_analysis(df_filtered_by_sidebar.copy())
display_email_prospecting_analysis(df_filtered_by_sidebar.copy())

st.markdown("---")
st.info("Esta página de análisis de campañas ha sido desarrollada por Johnsito ✨")
