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
    "Análisis del potencial de campañas, prospección manual y prospección por email. "
    "Este análisis excluye prospectos sin una campaña asignada."
)

# --- Constants and Session State Keys ---
SHEET_URL_SECRET_KEY = "main_prostraction_sheet_url"
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0" # Fallback
NO_CAMPAIGN_VALUES = ["Sin Campaña Asignada", "N/D", ""] # Values indicating no campaign

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
SES_CAMPAIGN_FILTER_KEY = "campaign_page_campaign_filter_v2" # Incremented version
SES_START_DATE_KEY = "campaign_page_start_date_v2"
SES_END_DATE_KEY = "campaign_page_end_date_v2"
SES_PROSPECTOR_FILTER_KEY = "campaign_page_prospector_filter_v2"
SES_AVATAR_FILTER_KEY = "campaign_page_avatar_filter_v2"

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
    elif cleaned == false_val.lower(): # Includes "no"
        return false_val
    elif cleaned in ["", "nan", "na", "<na>"]: # Treat common empty/NaN strings as default_val
        return default_val
    return cleaned # Return original if not a clear yes/no and not empty/nan

def parse_date_robustly(date_val):
    """Robustly parses dates from various common formats."""
    if pd.isna(date_val) or str(date_val).strip() == "":
        return pd.NaT
    if isinstance(date_val, (datetime.datetime, datetime.date)):
        return pd.to_datetime(date_val)
    
    date_str = str(date_val).strip()
    # Handle potential numeric representations of dates (Excel dates)
    if date_str.isdigit():
        try:
            # Assuming it might be an Excel serial date (days since 1900-01-00)
            return pd.to_datetime('1899-12-30') + pd.to_timedelta(float(date_str), 'D')
        except ValueError:
            pass # If conversion fails, proceed to other formats

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

@st.cache_data(ttl=600)
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
        sheet = workbook.sheet1
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
    if COL_CAMPAIGN not in df.columns:
        st.error(f"La columna '{COL_CAMPAIGN}' es esencial y no se encontró. No se puede continuar con el análisis de campañas.")
        return pd.DataFrame()
        
    df[COL_CAMPAIGN] = df[COL_CAMPAIGN].apply(lambda x: clean_text_value(x, default="")) # Keep empty for now
    # **CRITICAL FILTER**: Exclude rows without a valid campaign assignment early on.
    df = df[~df[COL_CAMPAIGN].isin(NO_CAMPAIGN_VALUES)].copy()
    if df.empty:
        st.warning("No se encontraron prospectos con campañas asignadas válidas después del filtrado inicial.")
        return pd.DataFrame()

    # Manual Prospecting Columns
    date_cols_manual = [COL_FECHA_INVITE, COL_FECHA_SESION_MANUAL]
    for col in date_cols_manual:
        if col in df.columns:
            df[col] = df[col].apply(parse_date_robustly)
        else:
            df[col] = pd.NaT
    
    yes_no_cols_manual = [COL_INVITE_ACEPTADA, COL_RESPUESTA_1ER_MSJ, COL_SESION_AGENDADA_MANUAL]
    for col in yes_no_cols_manual:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no_value)
        else:
            df[col] = "no" 
            
    text_cols_manual = [COL_QUIEN_PROSPECTO, COL_AVATAR]
    for col in text_cols_manual:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: clean_text_value(x, default="N/D_Prospector_Avatar"))
        else:
            df[col] = "N/D_Prospector_Avatar"
            
    if COL_AVATAR in df.columns:
        df[COL_AVATAR] = df[COL_AVATAR].astype(str).str.strip().str.title()
        equivalencias_avatar = {
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez",
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez"
        }
        df[COL_AVATAR] = df[COL_AVATAR].replace(equivalencias_avatar)

    # Email Prospecting Columns
    email_yes_no_cols = [COL_CONTACTADOS_EMAIL, COL_RESPUESTA_EMAIL, COL_SESION_AGENDADA_EMAIL]
    for col in email_yes_no_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no_value)
        else:
            df[col] = "no"
            
    if COL_FECHA_SESION_EMAIL in df.columns:
        df[COL_FECHA_SESION_EMAIL] = df[COL_FECHA_SESION_EMAIL].apply(parse_date_robustly)
    else:
        df[COL_FECHA_SESION_EMAIL] = pd.NaT
        
    if COL_FECHA_INVITE in df.columns and not df[COL_FECHA_INVITE].isnull().all():
         df["FechaFiltroPrincipal"] = df[COL_FECHA_INVITE]
    elif COL_FECHA_SESION_EMAIL in df.columns and not df[COL_FECHA_SESION_EMAIL].isnull().all():
         df["FechaFiltroPrincipal"] = df[COL_FECHA_SESION_EMAIL]
    else:
        df["FechaFiltroPrincipal"] = pd.NaT

    return df

# --- Sidebar Filters ---
def display_campaign_filters(df_options):
    st.sidebar.header("🎯 Filtros de Campaña")

    # Initialize session state
    default_filters = {
        SES_CAMPAIGN_FILTER_KEY: ["– Todas –"],
        SES_START_DATE_KEY: None,
        SES_END_DATE_KEY: None,
        SES_PROSPECTOR_FILTER_KEY: ["– Todos –"],
        SES_AVATAR_FILTER_KEY: ["– Todos –"]
    }
    for key, value in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # Campaign Filter
    campaign_options = ["– Todas –"]
    if COL_CAMPAIGN in df_options.columns and not df_options[COL_CAMPAIGN].empty:
        # Options should only be actual campaign names now
        campaign_options.extend(sorted(df_options[COL_CAMPAIGN].dropna().unique())) 
    
    current_campaign_selection = st.session_state[SES_CAMPAIGN_FILTER_KEY]
    valid_campaign_selection = [c for c in current_campaign_selection if c in campaign_options]
    if not valid_campaign_selection: valid_campaign_selection = ["– Todas –"]
    st.session_state[SES_CAMPAIGN_FILTER_KEY] = valid_campaign_selection
    
    selected_campaigns = st.sidebar.multiselect(
        "Seleccionar Campaña(s)", options=campaign_options, key=SES_CAMPAIGN_FILTER_KEY
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
        prospector_options.extend(sorted(df_options[df_options[COL_QUIEN_PROSPECTO] != "N/D_Prospector_Avatar"][COL_QUIEN_PROSPECTO].dropna().unique()))

    current_prospector_selection = st.session_state[SES_PROSPECTOR_FILTER_KEY]
    valid_prospector_selection = [p for p in current_prospector_selection if p in prospector_options]
    if not valid_prospector_selection: valid_prospector_selection = ["– Todos –"]
    st.session_state[SES_PROSPECTOR_FILTER_KEY] = valid_prospector_selection
    selected_prospectors = st.sidebar.multiselect("¿Quién Prospectó?", prospector_options, key=SES_PROSPECTOR_FILTER_KEY)

    # Avatar Filter
    avatar_options = ["– Todos –"]
    if COL_AVATAR in df_options.columns and not df_options[COL_AVATAR].empty:
        avatar_options.extend(sorted(df_options[df_options[COL_AVATAR] != "N/D_Prospector_Avatar"][COL_AVATAR].dropna().unique()))
    
    current_avatar_selection = st.session_state[SES_AVATAR_FILTER_KEY]
    valid_avatar_selection = [a for a in current_avatar_selection if a in avatar_options]
    if not valid_avatar_selection: valid_avatar_selection = ["– Todos –"]
    st.session_state[SES_AVATAR_FILTER_KEY] = valid_avatar_selection
    selected_avatars = st.sidebar.multiselect("Avatar", avatar_options, key=SES_AVATAR_FILTER_KEY)
    
    st.sidebar.markdown("---")
    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True):
        for key, value in default_filters.items():
            st.session_state[key] = value
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
        elif start_date:
            df_filtered = df_filtered[df_filtered["FechaFiltroPrincipal"].dt.date >= start_date]
        elif end_date:
            df_filtered = df_filtered[df_filtered["FechaFiltroPrincipal"].dt.date <= end_date]
    if prospectors and "– Todos –" not in prospectors:
        df_filtered = df_filtered[df_filtered[COL_QUIEN_PROSPECTO].isin(prospectors)]
    if avatars and "– Todos –" not in avatars:
        df_filtered = df_filtered[df_filtered[COL_AVATAR].isin(avatars)]
    return df_filtered

# --- Analysis and Display Functions ---

def display_campaign_potential(df_valid_campaigns):
    st.subheader("📊 Potencial de Prospección por Campaña")
    
    if df_valid_campaigns.empty:
        st.info("No hay datos de campañas válidas para analizar el potencial.")
        return

    potential_counts = df_valid_campaigns[COL_CAMPAIGN].value_counts().reset_index()
    potential_counts.columns = [COL_CAMPAIGN, 'Total Prospectos Potenciales']

    fig = px.bar(
        potential_counts.sort_values(by='Total Prospectos Potenciales', ascending=False),
        x=COL_CAMPAIGN, y='Total Prospectos Potenciales',
        title='Total de Prospectos con Campaña Asignada', text_auto=True, color=COL_CAMPAIGN
    )
    fig.update_layout(xaxis_tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)
    
    with st.expander("Ver tabla de potencial por campaña"):
        st.dataframe(potential_counts.style.format({'Total Prospectos Potenciales': "{:,}"}), use_container_width=True)
    st.markdown("---")

def display_manual_prospecting_analysis(df_filtered_campaigns):
    st.subheader("🛠️ Análisis de Prospección Manual (Dentro de Campañas Seleccionadas)")

    if df_filtered_campaigns.empty:
        st.info("No hay datos para las campañas y filtros seleccionados.")
        return

    # This df_filtered_campaigns already has campaign, date, prospector, avatar filters from sidebar applied.
    # It also only contains rows with valid campaigns.

    # Calculate overall metrics for the current filtered view
    total_in_current_filter = len(df_filtered_campaigns)
    
    # Metrics for actual manual prospecting attempts (Fecha de Invite is filled)
    df_attempted_manual_overall = df_filtered_campaigns[df_filtered_campaigns[COL_FECHA_INVITE].notna()].copy()
    total_manually_prospected_overall = len(df_attempted_manual_overall)

    st.metric("Prospectos en Campaña(s) y Filtros Seleccionados", f"{total_in_current_filter:,}")
    st.metric("De estos, Prospectados Manualmente (con Fecha de Invite)", f"{total_manually_prospected_overall:,}")
    
    if total_manually_prospected_overall == 0:
        st.info("No se encontraron intentos de prospección manual (con Fecha de Invite) para los filtros actuales.")
        return

    # --- Detailed Traceability Table ---
    st.markdown("#### Trazabilidad Detallada de Prospección Manual")
    
    # Group by Campaign and Prospector
    # 1. Total Assigned to Prospector in Campaign (from df_filtered_campaigns)
    assigned_counts = df_filtered_campaigns.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO]).size().reset_index(name='Total Asignado en Campaña')
    
    # 2. Total Manually Prospected by Prospector (Fecha Invite) (from df_attempted_manual_overall)
    manually_prospected_counts = df_attempted_manual_overall.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO]).size().reset_index(name='Prospectado Manualmente (con Fecha Invite)')
    
    # 3. Funnel metrics (from df_attempted_manual_overall)
    funnel_metrics = df_attempted_manual_overall.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO]).agg(
        Invites_Aceptadas_Manual=(COL_INVITE_ACEPTADA, lambda x: (x == "si").sum()),
        Respuestas_1er_Msj_Manual=(COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum()),
        Sesiones_Agendadas_Manual=(COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
    ).reset_index()

    # Merge the dataframes
    trace_df = pd.merge(assigned_counts, manually_prospected_counts, on=[COL_CAMPAIGN, COL_QUIEN_PROSPECTO], how='left')
    trace_df = pd.merge(trace_df, funnel_metrics, on=[COL_CAMPAIGN, COL_QUIEN_PROSPECTO], how='left')
    
    # Fill NaNs for counts where no manual prospecting occurred after assignment, or no funnel activity
    count_cols_to_fill = ['Prospectado Manualmente (con Fecha Invite)', 'Invites_Aceptadas_Manual', 'Respuestas_1er_Msj_Manual', 'Sesiones_Agendadas_Manual']
    for col in count_cols_to_fill:
        trace_df[col] = trace_df[col].fillna(0).astype(int)

    # Calculate conversion rates
    base_for_rates = trace_df['Prospectado Manualmente (con Fecha Invite)']
    trace_df['Tasa Aceptación (vs Prospectado)'] = ((trace_df['Invites_Aceptadas_Manual'] / base_for_rates) * 100).fillna(0).round(1)
    trace_df['Tasa Respuesta (vs Aceptadas)'] = ((trace_df['Respuestas_1er_Msj_Manual'] / trace_df['Invites_Aceptadas_Manual']) * 100).fillna(0).round(1)
    trace_df['Tasa Sesión (vs Respuestas)'] = ((trace_df['Sesiones_Agendadas_Manual'] / trace_df['Respuestas_1er_Msj_Manual']) * 100).fillna(0).round(1)
    trace_df['Tasa Sesión Global (vs Prospectado)'] = ((trace_df['Sesiones_Agendadas_Manual'] / base_for_rates) * 100).fillna(0).round(1)
    
    # Handle division by zero again for rates if base_for_rates was 0 for some rows but Invites_Aceptadas > 0 etc. (edge case)
    rate_cols = ['Tasa Aceptación (vs Prospectado)', 'Tasa Respuesta (vs Aceptadas)', 'Tasa Sesión (vs Respuestas)', 'Tasa Sesión Global (vs Prospectado)']
    for r_col in rate_cols:
        trace_df[r_col] = trace_df[r_col].apply(lambda x: 0 if pd.isna(x) or x == float('inf') or x == float('-inf') else x)


    if not trace_df.empty:
        st.dataframe(trace_df.style.format({
            'Total Asignado en Campaña': "{:,}",
            'Prospectado Manualmente (con Fecha Invite)': "{:,}",
            'Invites_Aceptadas_Manual': "{:,}",
            'Respuestas_1er_Msj_Manual': "{:,}",
            'Sesiones_Agendadas_Manual': "{:,}",
            'Tasa Aceptación (vs Prospectado)': "{:.1f}%",
            'Tasa Respuesta (vs Aceptadas)': "{:.1f}%",
            'Tasa Sesión (vs Respuestas)': "{:.1f}%",
            'Tasa Sesión Global (vs Prospectado)': "{:.1f}%"
        }), use_container_width=True)
    else:
        st.info("No hay datos suficientes para la tabla de trazabilidad detallada.")

    # --- Aggregated Funnel for current selection ---
    st.markdown("#### Embudo de Conversión Agregado (Prospección Manual para Selección Actual)")
    invites_aceptadas_agg = df_attempted_manual_overall[df_attempted_manual_overall[COL_INVITE_ACEPTADA] == "si"].shape[0]
    respuestas_1er_msj_agg = df_attempted_manual_overall[df_attempted_manual_overall[COL_RESPUESTA_1ER_MSJ] == "si"].shape[0]
    sesiones_agendadas_agg = df_attempted_manual_overall[df_attempted_manual_overall[COL_SESION_AGENDADA_MANUAL] == "si"].shape[0]

    funnel_data_manual_agg = pd.DataFrame({
        "Etapa": ["Prospectados Manualmente (con Fecha Invite)", "Invites Aceptadas", "Respuestas 1er Msj", "Sesiones Agendadas"],
        "Cantidad": [total_manually_prospected_overall, invites_aceptadas_agg, respuestas_1er_msj_agg, sesiones_agendadas_agg]
    })
    fig_funnel_manual_agg = px.funnel(funnel_data_manual_agg, x='Cantidad', y='Etapa', title="Embudo Agregado (Prospección Manual)")
    st.plotly_chart(fig_funnel_manual_agg, use_container_width=True)

    # Optional: Breakdowns by Prospector/Avatar for 'Prospectado Manualmente (con Fecha Invite)'
    if COL_QUIEN_PROSPECTO in df_attempted_manual_overall.columns:
        prospector_counts_actual = df_attempted_manual_overall[COL_QUIEN_PROSPECTO].value_counts().reset_index()
        prospector_counts_actual.columns = ["Prospectador", "Nº Prospectado Manualmente (con Fecha Invite)"]
        if not prospector_counts_actual.empty:
            fig_prospector_actual = px.bar(prospector_counts_actual, x="Prospectador", y="Nº Prospectado Manualmente (con Fecha Invite)", title="Nº Prospectado Manualmente por Prospectador", text_auto=True, color="Prospectador")
            st.plotly_chart(fig_prospector_actual, use_container_width=True)
    st.markdown("---")


def display_email_prospecting_analysis(df_filtered_campaigns):
    st.subheader("📧 Análisis de Prospección por Email (Dentro de Campañas Seleccionadas)")

    if df_filtered_campaigns.empty:
        st.info("No hay datos para las campañas y filtros seleccionados.")
        return

    df_attempted_email = df_filtered_campaigns[df_filtered_campaigns[COL_CONTACTADOS_EMAIL] == "si"].copy()
    total_email_prospects_in_filter = len(df_attempted_email)

    if total_email_prospects_in_filter == 0:
        st.info("No se encontraron intentos de prospección por email (Contactados por Campaña = 'si') para los filtros actuales.")
        return

    st.metric("Total Contactados por Email (en selección)", f"{total_email_prospects_in_filter:,}")

    respuestas_email = df_attempted_email[df_attempted_email[COL_RESPUESTA_EMAIL] == "si"].shape[0]
    sesiones_agendadas_email = df_attempted_email[df_attempted_email[COL_SESION_AGENDADA_EMAIL] == "si"].shape[0]

    e_col1, e_col2 = st.columns(2)
    e_col1.metric("Respuestas Email", f"{respuestas_email:,}")
    e_col2.metric("Sesiones Agendadas (Email)", f"{sesiones_agendadas_email:,}")

    funnel_data_email = pd.DataFrame({
        "Etapa": ["Contactados por Email", "Respuestas Email", "Sesiones Agendadas (Email)"],
        "Cantidad": [total_email_prospects_in_filter, respuestas_email, sesiones_agendadas_email]
    })
    fig_funnel_email = px.funnel(funnel_data_email, x='Cantidad', y='Etapa', title="Embudo de Conversión (Prospección por Email)")
    st.plotly_chart(fig_funnel_email, use_container_width=True)
    st.markdown("---")

# --- Main Page Logic ---
df_base_campaigns_loaded = load_and_prepare_campaign_data()

if df_base_campaigns_loaded.empty:
    st.error("No se pudieron cargar o procesar los datos para el análisis de campañas con campañas asignadas. La página no puede continuar.")
    st.stop()

selected_campaigns, start_date_filter, end_date_filter, selected_prospectors, selected_avatars = display_campaign_filters(df_base_campaigns_loaded.copy())

df_filtered_by_sidebar = apply_campaign_filters(
    df_base_campaigns_loaded.copy(),
    selected_campaigns,
    start_date_filter,
    end_date_filter,
    selected_prospectors,
    selected_avatars
)

# --- Display Sections ---
# Section 1: Campaign Potential (uses df_base_campaigns_loaded as it represents all valid campaign data)
display_campaign_potential(df_base_campaigns_loaded.copy())

# Section 2: Manual Prospecting Analysis (uses df_filtered_by_sidebar)
display_manual_prospecting_analysis(df_filtered_by_sidebar.copy())

# Section 3: Email Prospecting Analysis (uses df_filtered_by_sidebar)
display_email_prospecting_analysis(df_filtered_by_sidebar.copy())

st.markdown("---")
with st.expander("ℹ️ Columnas y Lógica Clave Utilizada (Excluye prospectos sin campaña asignada)"):
    st.markdown(f"""
    **Filtro Inicial:** Solo se consideran prospectos con un valor en la columna `{COL_CAMPAIGN}` que no esté en `{", ".join(NO_CAMPAIGN_VALUES)}`.
    
    **Columna de Campaña Principal:** `{COL_CAMPAIGN}`
    
    **Prospección Manual:**
    - Trazabilidad: Campaña -> `{COL_QUIEN_PROSPECTO}` -> Prospectos Asignados -> Prospectados Manualmente (con `{COL_FECHA_INVITE}`) -> Embudo.
    - Invite Aceptada: `{COL_INVITE_ACEPTADA}` (valor esperado: 'si')
    - Respuesta 1er Mensaje: `{COL_RESPUESTA_1ER_MSJ}` (valor esperado: 'si' o no 'no')
    - Sesión Agendada (Manual): `{COL_SESION_AGENDADA_MANUAL}` (valor esperado: 'si')
    
    **Prospección por Email:**
    - Identificador de contacto: `{COL_CONTACTADOS_EMAIL}` (valor esperado: 'si')
    - Respuesta Email: `{COL_RESPUESTA_EMAIL}` (valor esperado: 'si' o no 'no')
    - Sesión Agendada (Email): `{COL_SESION_AGENDADA_EMAIL}` (valor esperado: 'si')
    
    **Filtro de Fecha Principal (Sidebar):** Se basa en la columna `FechaFiltroPrincipal`.
    """)

st.markdown("---")
st.info("Esta página de análisis de campañas ha sido desarrollada por Johnsito ✨")
