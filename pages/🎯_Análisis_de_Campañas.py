# pages/🎯_Análisis_de_Campañas.py

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
    "Análisis del potencial de campañas, prospección manual y prospección por email."
)

# --- Constants and Session State Keys ---
SHEET_URL_SECRET_KEY = "main_prostraction_sheet_url"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0" # Fallback

# Columns related to Campaign Potential
COL_CAMPAIGN = "Campaña"

# Columns for Manual Prospecting
COL_FECHA_INVITE = "Fecha de Invite"
COL_INVITE_ACEPTADA = "¿Invite Aceptada?"
COL_RESPUESTA_1ER_MSJ = "Respuesta Primer Mensaje"
COL_SESION_AGENDADA_MANUAL = "Sesion Agendada?"
COL_QUIEN_PROSPECTO = "¿Quién Prospecto?"
COL_AVATAR = "Avatar"
COL_FECHA_SESION_MANUAL = "Fecha Sesion"


# Columns for Email Prospecting
COL_CONTACTADOS_EMAIL = "Contactados por Campaña"
COL_RESPUESTA_EMAIL = "Respuesta Email"
COL_SESION_AGENDADA_EMAIL = "Sesion Agendada Email"
COL_FECHA_SESION_EMAIL = "Fecha de Sesion Email"

# Session State Keys for Filters
SES_CAMPAIGN_FILTER_KEY = "campaign_page_campaign_filter_v1"
SES_START_DATE_KEY = "campaign_page_start_date_v1"
SES_END_DATE_KEY = "campaign_page_end_date_v1"
SES_PROSPECTOR_FILTER_KEY = "campaign_page_prospector_filter_v1"
SES_AVATAR_FILTER_KEY = "campaign_page_avatar_filter_v1"

# --- Helper Functions (Self-Contained) ---

def clean_text_value(val, default="N/D"):
    """Cleans and standardizes text values."""
    if pd.isna(val) or str(val).strip() == "":
        return default
    return str(val).strip()

def clean_yes_no_value(val, true_val="si", false_val="no", default_val="no"):
    """Cleans yes/no type values and returns a standard representation."""
    if pd.isna(val):
        return default_val
    cleaned = str(val).strip().lower()
    if cleaned == true_val.lower():
        return true_val
    elif cleaned == false_val.lower():
        return false_val
    elif cleaned in ["", "nan"]: # Treat common empty/NaN strings as default_val
        return default_val
    return cleaned # Return original if not a clear yes/no and not empty/nan

def parse_date_robustly(date_val):
    """Robustly parses dates from various common formats."""
    if pd.isna(date_val) or str(date_val).strip() == "":
        return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)):
        return pd.to_datetime(date_val)
    
    date_str = str(date_val).strip()
    common_formats = [
        "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
        "%Y-%m-%d %H:%M:%S", "%Y-%m-%d",
        "%m/%d/%Y %H:%M:%S", "%m/%d/%Y",
    ]
    for fmt in common_formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except (ValueError, TypeError):
            continue
    # Fallback to pandas' general parser, coercing errors
    return pd.to_datetime(date_str, errors='coerce')


def make_unique_column_names(headers_list):
    """Ensures all column names are unique by appending suffixes if needed."""
    counts = Counter()
    new_headers = []
    for h in headers_list:
        h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
        if not h_stripped:
            h_stripped = "Columna_Vacia"
        counts[h_stripped] += 1
        if counts[h_stripped] == 1:
            new_headers.append(h_stripped)
        else:
            new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
    return new_headers

@st.cache_data(ttl=600) # Cache for 10 minutes
def load_and_prepare_campaign_data():
    """Loads and prepares data specifically for the campaign analysis page."""
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta [gcp_service_account] en Streamlit Secrets.")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al cargar credenciales de Google Sheets: {e}")
        return pd.DataFrame()

    try:
        sheet_url = st.secrets.get(SHEET_URL_SECRET_KEY, DEFAULT_SHEET_URL)
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.sheet1 # Assuming data is in the first sheet
        raw_data = sheet.get_all_values()

        if not raw_data or len(raw_data) < 1:
            st.warning("La hoja de Google Sheets está vacía o no se pudo leer.")
            return pd.DataFrame()

        headers = make_unique_column_names(raw_data[0])
        df = pd.DataFrame(raw_data[1:], columns=headers)

    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo en la URL proporcionada en secrets ('{SHEET_URL_SECRET_KEY}').")
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo: {e}")
        return pd.DataFrame()

    # --- Data Cleaning and Preparation ---
    # Campaign Column
    if COL_CAMPAIGN not in df.columns:
        st.warning(f"La columna '{COL_CAMPAIGN}' es esencial y no se encontró. Se creará vacía.")
        df[COL_CAMPAIGN] = "N/D"
    df[COL_CAMPAIGN] = df[COL_CAMPAIGN].apply(lambda x: clean_text_value(x, default="Sin Campaña Asignada"))

    # Manual Prospecting Columns
    date_cols_manual = [COL_FECHA_INVITE, COL_FECHA_SESION_MANUAL]
    for col in date_cols_manual:
        if col in df.columns:
            df[col] = df[col].apply(parse_date_robustly)
        else:
            df[col] = pd.NaT
            st.info(f"Columna '{col}' para prospección manual no encontrada. Se tratará como vacía.")
            
    yes_no_cols_manual = [COL_INVITE_ACEPTADA, COL_RESPUESTA_1ER_MSJ, COL_SESION_AGENDADA_MANUAL]
    for col in yes_no_cols_manual:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no_value)
        else:
            df[col] = "no" # Default to 'no' if column is missing
            st.info(f"Columna '{col}' para prospección manual no encontrada. Se tratará como 'no'.")

    text_cols_manual = [COL_QUIEN_PROSPECTO, COL_AVATAR]
    for col in text_cols_manual:
        if col in df.columns:
            df[col] = df[col].apply(clean_text_value)
        else:
            df[col] = "N/D"
            st.info(f"Columna '{col}' para prospección manual no encontrada. Se tratará como 'N/D'.")
            
    # Standardize Avatar (example from existing utils, adapted)
    if COL_AVATAR in df.columns:
        df[COL_AVATAR] = df[COL_AVATAR].astype(str).str.strip().str.title()
        equivalencias_avatar = {
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"
        }
        df[COL_AVATAR] = df[COL_AVATAR].replace(equivalencias_avatar)


    # Email Prospecting Columns
    if COL_CONTACTADOS_EMAIL in df.columns:
        df[COL_CONTACTADOS_EMAIL] = df[COL_CONTACTADOS_EMAIL].apply(lambda x: clean_yes_no_value(x, true_val="si", false_val="no", default_val="no"))
    else:
        df[COL_CONTACTADOS_EMAIL] = "no"
        st.info(f"Columna '{COL_CONTACTADOS_EMAIL}' para prospección por email no encontrada. Se tratará como 'no'.")

    if COL_RESPUESTA_EMAIL in df.columns:
        df[COL_RESPUESTA_EMAIL] = df[COL_RESPUESTA_EMAIL].apply(lambda x: clean_yes_no_value(x, true_val="si", false_val="no", default_val="no"))
    else:
        df[COL_RESPUESTA_EMAIL] = "no"
        st.info(f"Columna '{COL_RESPUESTA_EMAIL}' para prospección por email no encontrada. Se tratará como 'no'.")
        
    if COL_SESION_AGENDADA_EMAIL in df.columns:
        df[COL_SESION_AGENDADA_EMAIL] = df[COL_SESION_AGENDADA_EMAIL].apply(lambda x: clean_yes_no_value(x, true_val="si", false_val="no", default_val="no"))
    else:
        df[COL_SESION_AGENDADA_EMAIL] = "no"
        st.info(f"Columna '{COL_SESION_AGENDADA_EMAIL}' para prospección por email no encontrada. Se tratará como 'no'.")

    if COL_FECHA_SESION_EMAIL in df.columns:
        df[COL_FECHA_SESION_EMAIL] = df[COL_FECHA_SESION_EMAIL].apply(parse_date_robustly)
    else:
        df[COL_FECHA_SESION_EMAIL] = pd.NaT
        st.info(f"Columna '{COL_FECHA_SESION_EMAIL}' para prospección por email no encontrada. Se tratará como vacía.")
        
    # Create a general date column for filtering if Fecha de Invite exists, otherwise use a placeholder for calculations.
    # This will be used for the main date filter in the sidebar.
    # If you have a specific "Campaign Start Date" or "Email Sent Date" that should be primary, adjust here.
    if COL_FECHA_INVITE in df.columns and not df[COL_FECHA_INVITE].isnull().all():
         df["FechaFiltroPrincipal"] = df[COL_FECHA_INVITE]
    elif COL_FECHA_SESION_EMAIL in df.columns and not df[COL_FECHA_SESION_EMAIL].isnull().all(): # Fallback if no invite date
         df["FechaFiltroPrincipal"] = df[COL_FECHA_SESION_EMAIL]
    else: # If no relevant date column found for primary filtering
        df["FechaFiltroPrincipal"] = pd.NaT # No primary date to filter on
        st.warning("No se encontró una columna de fecha principal (como Fecha de Invite) para los filtros de fecha generales. Los filtros de fecha pueden no funcionar como se espera.")


    return df

# --- Sidebar Filters ---
def display_campaign_filters(df_options):
    st.sidebar.header("🎯 Filtros de Campaña")

    # Initialize session state for filters if not already present
    if SES_CAMPAIGN_FILTER_KEY not in st.session_state:
        st.session_state[SES_CAMPAIGN_FILTER_KEY] = ["– Todas –"]
    if SES_START_DATE_KEY not in st.session_state:
        st.session_state[SES_START_DATE_KEY] = None
    if SES_END_DATE_KEY not in st.session_state:
        st.session_state[SES_END_DATE_KEY] = None
    if SES_PROSPECTOR_FILTER_KEY not in st.session_state:
        st.session_state[SES_PROSPECTOR_FILTER_KEY] = ["– Todos –"]
    if SES_AVATAR_FILTER_KEY not in st.session_state:
        st.session_state[SES_AVATAR_FILTER_KEY] = ["– Todos –"]

    # Campaign Filter
    campaign_options = ["– Todas –"]
    if COL_CAMPAIGN in df_options.columns and not df_options[COL_CAMPAIGN].empty:
        campaign_options.extend(sorted(df_options[COL_CAMPAIGN].dropna().unique()))
    
    # Validate current selection against available options
    current_campaign_selection = st.session_state[SES_CAMPAIGN_FILTER_KEY]
    valid_campaign_selection = [c for c in current_campaign_selection if c in campaign_options]
    if not valid_campaign_selection: # If current selection is invalid (e.g. data changed)
        valid_campaign_selection = ["– Todas –"]
    st.session_state[SES_CAMPAIGN_FILTER_KEY] = valid_campaign_selection
    
    selected_campaigns = st.sidebar.multiselect(
        "Seleccionar Campaña(s)",
        options=campaign_options,
        key=SES_CAMPAIGN_FILTER_KEY # Uses validated value from session state as default
    )

    # Date Filter
    min_date, max_date = None, None
    if "FechaFiltroPrincipal" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["FechaFiltroPrincipal"]):
        valid_dates = df_options["FechaFiltroPrincipal"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()

    date_col1, date_col2 = st.sidebar.columns(2)
    start_date = date_col1.date_input("Fecha Desde", value=st.session_state[SES_START_DATE_KEY], min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    end_date = date_col2.date_input("Fecha Hasta", value=st.session_state[SES_END_DATE_KEY], min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_END_DATE_KEY)

    # Prospector Filter
    prospector_options = ["– Todos –"]
    if COL_QUIEN_PROSPECTO in df_options.columns and not df_options[COL_QUIEN_PROSPECTO].empty:
        prospector_options.extend(sorted(df_options[COL_QUIEN_PROSPECTO].dropna().unique()))
    
    current_prospector_selection = st.session_state[SES_PROSPECTOR_FILTER_KEY]
    valid_prospector_selection = [p for p in current_prospector_selection if p in prospector_options]
    if not valid_prospector_selection: valid_prospector_selection = ["– Todos –"]
    st.session_state[SES_PROSPECTOR_FILTER_KEY] = valid_prospector_selection

    selected_prospectors = st.sidebar.multiselect("¿Quién Prospectó?", prospector_options, key=SES_PROSPECTOR_FILTER_KEY)

    # Avatar Filter
    avatar_options = ["– Todos –"]
    if COL_AVATAR in df_options.columns and not df_options[COL_AVATAR].empty:
        avatar_options.extend(sorted(df_options[COL_AVATAR].dropna().unique()))

    current_avatar_selection = st.session_state[SES_AVATAR_FILTER_KEY]
    valid_avatar_selection = [a for a in current_avatar_selection if a in avatar_options]
    if not valid_avatar_selection: valid_avatar_selection = ["– Todos –"]
    st.session_state[SES_AVATAR_FILTER_KEY] = valid_avatar_selection

    selected_avatars = st.sidebar.multiselect("Avatar", avatar_options, key=SES_AVATAR_FILTER_KEY)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True):
        st.session_state[SES_CAMPAIGN_FILTER_KEY] = ["– Todas –"]
        st.session_state[SES_START_DATE_KEY] = None
        st.session_state[SES_END_DATE_KEY] = None
        st.session_state[SES_PROSPECTOR_FILTER_KEY] = ["– Todos –"]
        st.session_state[SES_AVATAR_FILTER_KEY] = ["– Todos –"]
        st.rerun()

    return selected_campaigns, start_date, end_date, selected_prospectors, selected_avatars

def apply_campaign_filters(df, campaigns, start_date, end_date, prospectors, avatars):
    """Applies selected filters to the DataFrame."""
    if df.empty:
        return df
    
    df_filtered = df.copy()

    # Campaign filter
    if campaigns and "– Todas –" not in campaigns:
        df_filtered = df_filtered[df_filtered[COL_CAMPAIGN].isin(campaigns)]

    # Date filter (using the general "FechaFiltroPrincipal" column)
    if "FechaFiltroPrincipal" in df_filtered.columns and pd.api.types.is_datetime64_any_dtype(df_filtered["FechaFiltroPrincipal"]):
        if start_date and end_date:
            df_filtered = df_filtered[(df_filtered["FechaFiltroPrincipal"].dt.date >= start_date) & (df_filtered["FechaFiltroPrincipal"].dt.date <= end_date)]
        elif start_date:
            df_filtered = df_filtered[df_filtered["FechaFiltroPrincipal"].dt.date >= start_date]
        elif end_date:
            df_filtered = df_filtered[df_filtered["FechaFiltroPrincipal"].dt.date <= end_date]
    
    # Prospector filter
    if prospectors and "– Todos –" not in prospectors:
        df_filtered = df_filtered[df_filtered[COL_QUIEN_PROSPECTO].isin(prospectors)]
    
    # Avatar filter
    if avatars and "– Todos –" not in avatars:
        df_filtered = df_filtered[df_filtered[COL_AVATAR].isin(avatars)]
        
    return df_filtered

# --- Analysis and Display Functions ---

def display_campaign_potential(df_all_data, df_filtered_for_potential):
    st.subheader("📊 Potencial de Prospección por Campaña")
    
    if COL_CAMPAIGN not in df_all_data.columns:
        st.warning(f"Columna '{COL_CAMPAIGN}' no encontrada. No se puede mostrar el potencial.")
        return

    # Calculate potential based on *all* data, before time/prospector filters for this specific metric
    # as potential is about total records per campaign category in the source.
    potential_counts = df_all_data[COL_CAMPAIGN].value_counts().reset_index()
    potential_counts.columns = [COL_CAMPAIGN, 'Total Prospectos Potenciales']

    if potential_counts.empty:
        st.info("No hay datos de campaña para analizar el potencial.")
        return

    fig = px.bar(
        potential_counts.sort_values(by='Total Prospectos Potenciales', ascending=False),
        x=COL_CAMPAIGN,
        y='Total Prospectos Potenciales',
        title='Total de Prospectos Potenciales por Campaña (Datos Base)',
        text_auto=True,
        color=COL_CAMPAIGN
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Ver tabla de potencial por campaña"):
        st.dataframe(potential_counts.style.format({'Total Prospectos Potenciales': "{:,}"}), use_container_width=True)

    # Info about current filter context for other analyses
    st.markdown("---")
    st.info(f"Los análisis de prospección (manual y email) a continuación se basan en los filtros de la barra lateral, incluyendo el rango de fechas y los prospectadores/avatares seleccionados, aplicados a las campañas elegidas.")


def display_manual_prospecting_analysis(df_manual):
    st.subheader("🛠️ Análisis de Prospección Manual")

    if df_manual.empty:
        st.info("No hay datos de prospección manual para las campañas y filtros seleccionados.")
        return

    # Filter for actual manual prospecting attempts (Fecha de Invite is filled)
    df_attempted_manual = df_manual[df_manual[COL_FECHA_INVITE].notna()].copy()
    
    total_manual_prospects_in_filter = len(df_attempted_manual)

    if total_manual_prospects_in_filter == 0:
        st.info("No se encontraron intentos de prospección manual (con Fecha de Invite) para los filtros actuales.")
        return
        
    st.metric("Total Prospectos (Manualmente, con Fecha Invite)", f"{total_manual_prospects_in_filter:,}")

    # KPIs Manual
    invites_aceptadas_manual = df_attempted_manual[df_attempted_manual[COL_INVITE_ACEPTADA] == "si"].shape[0]
    respuestas_1er_msj_manual = df_attempted_manual[df_attempted_manual[COL_RESPUESTA_1ER_MSJ] == "si"].shape[0] # Assuming 'si' means responded positively or at all
    sesiones_agendadas_manual = df_attempted_manual[df_attempted_manual[COL_SESION_AGENDADA_MANUAL] == "si"].shape[0]

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Invites Aceptadas (Manual)", f"{invites_aceptadas_manual:,}")
    m_col2.metric("Respuestas 1er Mensaje (Manual)", f"{respuestas_1er_msj_manual:,}")
    m_col3.metric("Sesiones Agendadas (Manual)", f"{sesiones_agendadas_manual:,}")

    # Funnel Manual
    funnel_data_manual = pd.DataFrame({
        "Etapa": ["Prospectos con Fecha Invite", "Invites Aceptadas", "Respuestas 1er Msj", "Sesiones Agendadas"],
        "Cantidad": [total_manual_prospects_in_filter, invites_aceptadas_manual, respuestas_1er_msj_manual, sesiones_agendadas_manual]
    })
    fig_funnel_manual = px.funnel(funnel_data_manual, x='Cantidad', y='Etapa', title="Embudo de Conversión (Prospección Manual)")
    st.plotly_chart(fig_funnel_manual, use_container_width=True)

    # Breakdown by Prospector (Manual)
    if COL_QUIEN_PROSPECTO in df_attempted_manual.columns:
        prospector_counts_manual = df_attempted_manual[COL_QUIEN_PROSPECTO].value_counts().reset_index()
        prospector_counts_manual.columns = ["Prospectador", "Total Prospectado (Manual)"]
        if not prospector_counts_manual.empty:
            fig_prospector_manual = px.bar(prospector_counts_manual, x="Prospectador", y="Total Prospectado (Manual)", title="Prospección Manual por Prospectador", text_auto=True, color="Prospectador")
            st.plotly_chart(fig_prospector_manual, use_container_width=True)
            with st.expander("Ver tabla de prospección manual por prospectador"):
                st.dataframe(prospector_counts_manual.style.format({'Total Prospectado (Manual)': "{:,}"}), use_container_width=True)


    # Breakdown by Avatar (Manual)
    if COL_AVATAR in df_attempted_manual.columns:
        avatar_counts_manual = df_attempted_manual[COL_AVATAR].value_counts().reset_index()
        avatar_counts_manual.columns = ["Avatar", "Total Prospectado (Manual)"]
        if not avatar_counts_manual.empty:
            fig_avatar_manual = px.bar(avatar_counts_manual, x="Avatar", y="Total Prospectado (Manual)", title="Prospección Manual por Avatar", text_auto=True, color="Avatar")
            st.plotly_chart(fig_avatar_manual, use_container_width=True)
            with st.expander("Ver tabla de prospección manual por avatar"):
                st.dataframe(avatar_counts_manual.style.format({'Total Prospectado (Manual)': "{:,}"}), use_container_width=True)

def display_email_prospecting_analysis(df_email):
    st.subheader("📧 Análisis de Prospección por Email")

    if df_email.empty:
        st.info("No hay datos de prospección por email para las campañas y filtros seleccionados.")
        return

    # Filter for actual email prospecting attempts
    df_attempted_email = df_email[df_email[COL_CONTACTADOS_EMAIL] == "si"].copy()
    total_email_prospects_in_filter = len(df_attempted_email)

    if total_email_prospects_in_filter == 0:
        st.info("No se encontraron intentos de prospección por email (Contactados por Campaña = 'si') para los filtros actuales.")
        return

    st.metric("Total Contactados por Email", f"{total_email_prospects_in_filter:,}")

    # KPIs Email
    respuestas_email = df_attempted_email[df_attempted_email[COL_RESPUESTA_EMAIL] == "si"].shape[0]
    sesiones_agendadas_email = df_attempted_email[df_attempted_email[COL_SESION_AGENDADA_EMAIL] == "si"].shape[0]

    e_col1, e_col2 = st.columns(2)
    e_col1.metric("Respuestas Email", f"{respuestas_email:,}")
    e_col2.metric("Sesiones Agendadas (Email)", f"{sesiones_agendadas_email:,}")

    # Funnel Email
    funnel_data_email = pd.DataFrame({
        "Etapa": ["Contactados por Email", "Respuestas Email", "Sesiones Agendadas (Email)"],
        "Cantidad": [total_email_prospects_in_filter, respuestas_email, sesiones_agendadas_email]
    })
    fig_funnel_email = px.funnel(funnel_data_email, x='Cantidad', y='Etapa', title="Embudo de Conversión (Prospección por Email)")
    st.plotly_chart(fig_funnel_email, use_container_width=True)
    
    # Note: Breakdowns by Prospector/Avatar for email campaigns might not be directly applicable
    # if the email sending process is automated or attributed differently.
    # If "Quién Prospectó" or "Avatar" is relevant for email campaigns, that logic can be added here similar to manual.


# --- Main Page Logic ---
df_base_campaigns = load_and_prepare_campaign_data()

if df_base_campaigns.empty:
    st.error("No se pudieron cargar o procesar los datos para el análisis de campañas. La página no puede continuar.")
    st.stop()

# Display filters in the sidebar
selected_campaigns, start_date_filter, end_date_filter, selected_prospectors, selected_avatars = display_campaign_filters(df_base_campaigns.copy())

# Apply filters to the base DataFrame
df_filtered_campaigns = apply_campaign_filters(
    df_base_campaigns.copy(),
    selected_campaigns,
    start_date_filter,
    end_date_filter,
    selected_prospectors,
    selected_avatars
)

# --- Display Sections ---
st.markdown("---")
# Section 1: Campaign Potential (uses df_base_campaigns for potential, and df_filtered_campaigns to show context)
display_campaign_potential(df_base_campaigns.copy(), df_filtered_campaigns.copy()) # Pass full base for potential calculation

st.markdown("---")
# Section 2: Manual Prospecting Analysis (uses df_filtered_campaigns)
display_manual_prospecting_analysis(df_filtered_campaigns.copy())

st.markdown("---")
# Section 3: Email Prospecting Analysis (uses df_filtered_campaigns)
display_email_prospecting_analysis(df_filtered_campaigns.copy())


st.markdown("---")
with st.expander("ℹ️ Columnas y Lógica Clave Utilizada"):
    st.markdown(f"""
    **Columna de Campaña Principal:** `{COL_CAMPAIGN}`
    
    **Prospección Manual:**
    - Identificador de intento: `{COL_FECHA_INVITE}` (debe tener una fecha)
    - Invite Aceptada: `{COL_INVITE_ACEPTADA}` (valor esperado: 'si')
    - Respuesta 1er Mensaje: `{COL_RESPUESTA_1ER_MSJ}` (valor esperado: 'si')
    - Sesión Agendada (Manual): `{COL_SESION_AGENDADA_MANUAL}` (valor esperado: 'si')
    - Fecha Sesión (Manual): `{COL_FECHA_SESION_MANUAL}`
    - Prospectador: `{COL_QUIEN_PROSPECTO}`
    - Avatar: `{COL_AVATAR}`
    
    **Prospección por Email:**
    - Identificador de contacto: `{COL_CONTACTADOS_EMAIL}` (valor esperado: 'si')
    - Respuesta Email: `{COL_RESPUESTA_EMAIL}` (valor esperado: 'si')
    - Sesión Agendada (Email): `{COL_SESION_AGENDADA_EMAIL}` (valor esperado: 'si')
    - Fecha Sesión (Email): `{COL_FECHA_SESION_EMAIL}`
    
    **Filtro de Fecha Principal (Sidebar):** Se basa en la columna `FechaFiltroPrincipal`, que se deriva de `{COL_FECHA_INVITE}` o, si esta está vacía, de `{COL_FECHA_SESION_EMAIL}`.
    """)


st.markdown("---")
st.info("Esta página de análisis de campañas ha sido desarrollada por Johnsito ✨")