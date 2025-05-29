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
DEFAULT_SHEET_URL = "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0"
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

SES_CAMPAIGN_FILTER_KEY = "campaign_page_campaign_filter_v4" # Incremented version
SES_START_DATE_KEY = "campaign_page_start_date_v4"
SES_END_DATE_KEY = "campaign_page_end_date_v4"
SES_PROSPECTOR_FILTER_KEY = "campaign_page_prospector_filter_v4"
SES_AVATAR_FILTER_KEY = "campaign_page_avatar_filter_v4"

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
    # ... (resto de la función load_and_prepare_campaign_data sin cambios)...
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
    elif COL_FECHA_SESION_EMAIL in df.columns and not df[COL_FECHA_SESION_EMAIL].isnull().all():
         df["FechaFiltroPrincipal"] = df[COL_FECHA_SESION_EMAIL]
    else: df["FechaFiltroPrincipal"] = pd.NaT
    return df


# --- Sidebar Filters ---
def display_campaign_filters(df_options):
    st.sidebar.header("🎯 Filtros de Campaña")

    # Ensure consistent use of the "All" string, e.g., "– Todas –" (with en-dash)
    all_campaigns_value = ["– Todas –"]
    all_prospectors_value = ["– Todas –"] # Changed from "– Todos –" if you intended singular agreement with "Prospector"
                                         # Or keep as "– Todos –" if that's the canonical string you want.
                                         # The key is *consistency* with the options list.
                                         # For this example, I'll assume "– Todas –" is universal for simplicity here.
    all_avatars_value = ["– Todas –"]

    default_filters_init = {
        SES_CAMPAIGN_FILTER_KEY: all_campaigns_value,
        SES_START_DATE_KEY: None,
        SES_END_DATE_KEY: None,
        SES_PROSPECTOR_FILTER_KEY: all_prospectors_value, # Use the consistent string
        SES_AVATAR_FILTER_KEY: all_avatars_value          # Use the consistent string
    }
    for key, value in default_filters_init.items():
        if key not in st.session_state:
            st.session_state[key] = value

    # --- Campaign Filter ---
    campaign_options = list(all_campaigns_value) # Start with the "All" value
    if COL_CAMPAIGN in df_options.columns and not df_options[COL_CAMPAIGN].empty:
        campaign_options.extend(sorted(df_options[COL_CAMPAIGN].dropna().unique()))
    # Ensure no duplicates if "– Todas –" could come from data; typically, it shouldn't.
    # If necessary, convert to set and back to list to ensure uniqueness while preserving "– Todas –" at the start.
    # A simpler way if "– Todas –" is special:
    # unique_data_options = sorted(df_options[COL_CAMPAIGN].dropna().unique())
    # campaign_options = list(all_campaigns_value) + [opt for opt in unique_data_options if opt != all_campaigns_value[0]]


    current_campaign_selection_in_state = st.session_state[SES_CAMPAIGN_FILTER_KEY]
    validated_campaign_selection = [c for c in current_campaign_selection_in_state if c in campaign_options]

    if not validated_campaign_selection:
        st.session_state[SES_CAMPAIGN_FILTER_KEY] = default_filters_init[SES_CAMPAIGN_FILTER_KEY]
    elif len(validated_campaign_selection) != len(current_campaign_selection_in_state):
        st.session_state[SES_CAMPAIGN_FILTER_KEY] = validated_campaign_selection

    selected_campaigns = st.sidebar.multiselect(
        "Seleccionar Campaña(s)",
        options=campaign_options,
        default=default_filters_init[SES_CAMPAIGN_FILTER_KEY],
        key=SES_CAMPAIGN_FILTER_KEY
    )

    # --- Date Filter ---
    min_date, max_date = None, None
    if "FechaFiltroPrincipal" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["FechaFiltroPrincipal"]):
        valid_dates = df_options["FechaFiltroPrincipal"].dropna()
        if not valid_dates.empty:
            min_date = valid_dates.min().date()
            max_date = valid_dates.max().date()

    date_col1, date_col2 = st.sidebar.columns(2)
    start_date = date_col1.date_input("Fecha Desde", value=st.session_state[SES_START_DATE_KEY], min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_START_DATE_KEY)
    end_date = date_col2.date_input("Fecha Hasta", value=st.session_state[SES_END_DATE_KEY], min_value=min_date, max_value=max_date, format="DD/MM/YYYY", key=SES_END_DATE_KEY)

    # --- Prospector Filter (Line 215 is the multiselect below) ---
    prospector_options = list(all_prospectors_value) # Start with the "All" value
    if COL_QUIEN_PROSPECTO in df_options.columns and not df_options[COL_QUIEN_PROSPECTO].empty:
        unique_prospectors = df_options[df_options[COL_QUIEN_PROSPECTO] != "N/D_Interno"][COL_QUIEN_PROSPECTO].dropna().unique()
        # Add only those not matching the "All" string to avoid duplicates if data contains it
        prospector_options.extend(sorted([p for p in unique_prospectors if p != all_prospectors_value[0]]))


    current_prospector_selection_in_state = st.session_state[SES_PROSPECTOR_FILTER_KEY]
    validated_prospector_selection = [p for p in current_prospector_selection_in_state if p in prospector_options]

    if not validated_prospector_selection:
        st.session_state[SES_PROSPECTOR_FILTER_KEY] = default_filters_init[SES_PROSPECTOR_FILTER_KEY]
    elif len(validated_prospector_selection) != len(current_prospector_selection_in_state):
        st.session_state[SES_PROSPECTOR_FILTER_KEY] = validated_prospector_selection

    # For debugging, add these lines just before the failing multiselect:
    # st.sidebar.write(f"DEBUG: Default for prospector: `{default_filters_init[SES_PROSPECTOR_FILTER_KEY]}`")
    # st.sidebar.write(f"DEBUG: Prospector options: `{prospector_options}`")
    # st.sidebar.write(f"DEBUG: Is default in options? `{default_filters_init[SES_PROSPECTOR_FILTER_KEY][0] in prospector_options}`")

    selected_prospectors = st.sidebar.multiselect( # This is approximately line 215
        "¿Quién Prospectó?",
        options=prospector_options,
        default=default_filters_init[SES_PROSPECTOR_FILTER_KEY],
        key=SES_PROSPECTOR_FILTER_KEY
    )

    # --- Avatar Filter ---
    avatar_options = list(all_avatars_value) # Start with the "All" value
    if COL_AVATAR in df_options.columns and not df_options[COL_AVATAR].empty:
        unique_avatars = df_options[df_options[COL_AVATAR] != "N/D_Interno"][COL_AVATAR].dropna().unique()
        avatar_options.extend(sorted([a for a in unique_avatars if a != all_avatars_value[0]]))


    current_avatar_selection_in_state = st.session_state[SES_AVATAR_FILTER_KEY]
    validated_avatar_selection = [a for a in current_avatar_selection_in_state if a in avatar_options]

    if not validated_avatar_selection:
        st.session_state[SES_AVATAR_FILTER_KEY] = default_filters_init[SES_AVATAR_FILTER_KEY]
    elif len(validated_avatar_selection) != len(current_avatar_selection_in_state):
        st.session_state[SES_AVATAR_FILTER_KEY] = validated_avatar_selection

    selected_avatars = st.sidebar.multiselect(
        "Avatar",
        options=avatar_options,
        default=default_filters_init[SES_AVATAR_FILTER_KEY],
        key=SES_AVATAR_FILTER_KEY
    )

    st.sidebar.markdown("---")
    # Ensure the button key is unique if you've had issues with it before
    if st.sidebar.button("🧹 Limpiar Filtros", use_container_width=True, key=f"{SES_CAMPAIGN_FILTER_KEY}_clear_button_v3"):
        st.session_state[SES_CAMPAIGN_FILTER_KEY] = default_filters_init[SES_CAMPAIGN_FILTER_KEY]
        st.session_state[SES_START_DATE_KEY] = default_filters_init[SES_START_DATE_KEY]
        st.session_state[SES_END_DATE_KEY] = default_filters_init[SES_END_DATE_KEY]
        st.session_state[SES_PROSPECTOR_FILTER_KEY] = default_filters_init[SES_PROSPECTOR_FILTER_KEY]
        st.session_state[SES_AVATAR_FILTER_KEY] = default_filters_init[SES_AVATAR_FILTER_KEY]
        st.rerun()

    return st.session_state[SES_CAMPAIGN_FILTER_KEY], \
           st.session_state[SES_START_DATE_KEY], \
           st.session_state[SES_END_DATE_KEY], \
           st.session_state[SES_PROSPECTOR_FILTER_KEY], \
           st.session_state[SES_AVATAR_FILTER_KEY]
    # The selected_... variables will reflect st.session_state[KEY] due to the key argument
    return st.session_state[SES_CAMPAIGN_FILTER_KEY], \
           st.session_state[SES_START_DATE_KEY], \
           st.session_state[SES_END_DATE_KEY], \
           st.session_state[SES_PROSPECTOR_FILTER_KEY], \
           st.session_state[SES_AVATAR_FILTER_KEY]

# --- Apply Filters ---
# ... (la función apply_campaign_filters permanece igual que en la versión anterior)...
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

# ... (la función display_campaign_potential permanece igual)...
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

# ... (la función display_manual_prospecting_analysis con la lógica de trazabilidad que ya hicimos permanece igual)...
def display_manual_prospecting_analysis(df_filtered_campaigns):
    st.subheader("Análisis de Prospección Manual")
    st.caption("Basado en campañas y filtros seleccionados en la barra lateral. Muestra prospectos asignados, cuántos fueron contactados manualmente y su progreso en el embudo.")

    if df_filtered_campaigns.empty:
        st.info("No hay datos para analizar la prospección manual con los filtros actuales.")
        return

    total_in_current_filter = len(df_filtered_campaigns)
    df_contactos_iniciados = df_filtered_campaigns[df_filtered_campaigns[COL_FECHA_INVITE].notna()].copy()
    total_contactos_iniciados_manual = len(df_contactos_iniciados)

    col_metric1, col_metric2 = st.columns(2)
    col_metric1.metric("Prospectos en Selección Actual (Asignados en Campaña)", f"{total_in_current_filter:,}")
    col_metric2.metric("De estos, con Contacto Manual Iniciado (tienen Fecha Invite)", f"{total_contactos_iniciados_manual:,}")

    if total_contactos_iniciados_manual == 0 and total_in_current_filter > 0:
        st.warning("De los prospectos en la selección actual, ninguno tiene un contacto manual iniciado (Fecha de Invite registrada).")
    elif total_contactos_iniciados_manual == 0 and total_in_current_filter == 0:
        st.info("No se encontraron prospectos asignados ni contactos manuales iniciados para la selección actual.")
        return

    st.markdown("#### Trazabilidad Detallada: Asignados vs. Contactados y Embudo por Prospectador")
    assigned_counts = df_filtered_campaigns.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO], as_index=False).size().rename(columns={'size': 'Prospectos Asignados'})
    contactos_iniciados_counts = df_contactos_iniciados.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO], as_index=False).size().rename(columns={'size': 'Contactos Manuales Iniciados'})

    funnel_metrics = pd.DataFrame()
    if not df_contactos_iniciados.empty:
        funnel_metrics = df_contactos_iniciados.groupby([COL_CAMPAIGN, COL_QUIEN_PROSPECTO], as_index=False).agg(
            Invites_Aceptadas=(COL_INVITE_ACEPTADA, lambda x: (x == "si").sum()),
            Respuestas_1er_Msj=(COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum()),
            Sesiones_Agendadas=(COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
        )

    trace_df = pd.merge(assigned_counts, contactos_iniciados_counts, on=[COL_CAMPAIGN, COL_QUIEN_PROSPECTO], how='left')
    if not funnel_metrics.empty:
        trace_df = pd.merge(trace_df, funnel_metrics, on=[COL_CAMPAIGN, COL_QUIEN_PROSPECTO], how='left')
    else:
        trace_df['Invites_Aceptadas'] = 0
        trace_df['Respuestas_1er_Msj'] = 0
        trace_df['Sesiones_Agendadas'] = 0

    count_cols_fill = ['Contactos Manuales Iniciados', 'Invites_Aceptadas', 'Respuestas_1er_Msj', 'Sesiones_Agendadas']
    for col in count_cols_fill:
        if col not in trace_df.columns:
            trace_df[col] = 0
        trace_df[col] = trace_df[col].fillna(0).astype(int)

    trace_df['Tasa Inicio Prospección (%)'] = ((trace_df['Contactos Manuales Iniciados'] / trace_df['Prospectos Asignados']) * 100).fillna(0).round(1)
    base_rates_embudo = trace_df['Contactos Manuales Iniciados']
    trace_df['Tasa Aceptación vs Contactos (%)'] = ((trace_df['Invites_Aceptadas'] / base_rates_embudo) * 100).fillna(0).round(1)
    trace_df['Tasa Respuesta vs Aceptadas (%)'] = ((trace_df['Respuestas_1er_Msj'] / trace_df['Invites_Aceptadas']) * 100).fillna(0).round(1)
    trace_df['Tasa Sesión vs Respuestas (%)'] = ((trace_df['Sesiones_Agendadas'] / trace_df['Respuestas_1er_Msj']) * 100).fillna(0).round(1)
    trace_df['Tasa Sesión Global vs Contactos (%)'] = ((trace_df['Sesiones_Agendadas'] / base_rates_embudo) * 100).fillna(0).round(1)

    rate_cols = ['Tasa Inicio Prospección (%)', 'Tasa Aceptación vs Contactos (%)', 'Tasa Respuesta vs Aceptadas (%)', 'Tasa Sesión vs Respuestas (%)', 'Tasa Sesión Global vs Contactos (%)']
    for r_col in rate_cols:
        trace_df[r_col] = trace_df[r_col].apply(lambda x: 0 if pd.isna(x) or x == float('inf') or x == float('-inf') else x)

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
        column_order_existing = [col for col in column_order if col in trace_df_display.columns]
        st.dataframe(trace_df_display[column_order_existing].style.format({
            'Prospectos Asignados': "{:,}", 'Contactos Manuales Iniciados': "{:,}",
            'Invites_Aceptadas': "{:,}", 'Respuestas_1er_Msj': "{:,}", 'Sesiones_Agendadas': "{:,}",
            'Tasa Inicio Prospección (%)': "{:.1f}%", 'Tasa Aceptación vs Contactos (%)': "{:.1f}%",
            'Tasa Respuesta vs Aceptadas (%)': "{:.1f}%", 'Tasa Sesión vs Respuestas (%)': "{:.1f}%",
            'Tasa Sesión Global vs Contactos (%)': "{:.1f}%"
        }), use_container_width=True)
    else:
        st.info("No hay datos para la tabla de trazabilidad detallada después de filtrar N/D_Interno o no hay prospectadores asignados.")

    if total_contactos_iniciados_manual > 0:
        st.markdown("#### Embudo de Conversión Agregado (para Contactos Manuales Iniciados)")
        # ... (lógica del embudo agregado permanece igual) ...
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


# Debes reemplazar la función display_global_manual_prospecting_deep_dive
# en tu archivo pages/📢_Campañas.py con esta versión completa.

# Debes reemplazar la función display_global_manual_prospecting_deep_dive
# en tu archivo .py con esta versión completa.

def display_global_manual_prospecting_deep_dive(df_filtered_selection):
    st.header("Desglose General de Prospección Manual en Campañas Seleccionadas")
    st.caption("Este análisis se basa en la selección actual de campañas y filtros de la barra lateral.")

    if df_filtered_selection.empty:
        st.info("No hay datos para este desglose con los filtros actuales.")
        return

    df_contactos_iniciados = df_filtered_selection[df_filtered_selection[COL_FECHA_INVITE].notna()].copy()

    if df_contactos_iniciados.empty:
        st.info("No hay prospectos con contacto manual iniciado en la selección actual para este desglose detallado.")
        return

    st.markdown("#### Métricas Globales (sobre Contactos Manuales Iniciados)")
    total_contactos_iniciados = len(df_contactos_iniciados)
    total_invites_aceptadas = df_contactos_iniciados[df_contactos_iniciados[COL_INVITE_ACEPTADA] == "si"].shape[0]
    total_respuestas_1er_msj = df_contactos_iniciados[df_contactos_iniciados[COL_RESPUESTA_1ER_MSJ] == "si"].shape[0]
    total_sesiones_agendadas = df_contactos_iniciados[df_contactos_iniciados[COL_SESION_AGENDADA_MANUAL] == "si"].shape[0]
    total_asignados_seleccion = len(df_filtered_selection)
    tasa_inicio_general = (total_contactos_iniciados / total_asignados_seleccion * 100) if total_asignados_seleccion > 0 else 0
    tasa_aceptacion_general = (total_invites_aceptadas / total_contactos_iniciados * 100) if total_contactos_iniciados > 0 else 0
    tasa_sesion_global_general = (total_sesiones_agendadas / total_contactos_iniciados * 100) if total_contactos_iniciados > 0 else 0

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Total Contactos Manuales Iniciados", f"{total_contactos_iniciados:,}")
    m_col2.metric("Total Invites Aceptadas", f"{total_invites_aceptadas:,} ({tasa_aceptacion_general:.1f}%)")
    m_col3.metric("Total Sesiones Agendadas", f"{total_sesiones_agendadas:,} ({tasa_sesion_global_general:.1f}%)")
    st.caption(f"Tasa Inicio Prospección General (sobre {total_asignados_seleccion:,} asignados): {tasa_inicio_general:.1f}%")

    st.markdown("---")
    st.markdown("#### Desglose por Prospectador (sobre Contactos Manuales Iniciados)")
    asignados_por_prospectador = df_filtered_selection.groupby(COL_QUIEN_PROSPECTO, as_index=False).size().rename(columns={'size': 'Total Asignados'})
    asignados_por_prospectador = asignados_por_prospectador[asignados_por_prospectador[COL_QUIEN_PROSPECTO] != "N/D_Interno"]

    if not df_contactos_iniciados.empty:
        # CORRECCIÓN: Nombrar columnas directamente con espacios en la agregación
        desglose_prospectador_agg_spec = {
            'Contactos Manuales Iniciados': (COL_FECHA_INVITE, 'count'),
            'Invites Aceptadas': (COL_INVITE_ACEPTADA, lambda x: (x == "si").sum()),
            'Respuestas 1er Msj': (COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum()),
            'Sesiones Agendadas': (COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
        }
        desglose_prospectador = df_contactos_iniciados.groupby(COL_QUIEN_PROSPECTO, as_index=False).agg(**desglose_prospectador_agg_spec)
        desglose_prospectador = desglose_prospectador[desglose_prospectador[COL_QUIEN_PROSPECTO] != "N/D_Interno"]
        desglose_prospectador_final = pd.merge(asignados_por_prospectador, desglose_prospectador, on=COL_QUIEN_PROSPECTO, how='left').fillna(0)

        cols_to_ensure_numeric = ['Contactos Manuales Iniciados', 'Invites Aceptadas', 'Respuestas 1er Msj', 'Sesiones Agendadas', 'Total Asignados']
        for col in cols_to_ensure_numeric:
            if col not in desglose_prospectador_final.columns: desglose_prospectador_final[col] = 0
            desglose_prospectador_final[col] = pd.to_numeric(desglose_prospectador_final[col], errors='coerce').fillna(0).astype(int)

        desglose_prospectador_final['Tasa Inicio (%)'] = ((desglose_prospectador_final['Contactos Manuales Iniciados'] / desglose_prospectador_final['Total Asignados']) * 100).fillna(0).round(1)
        base_embudo_prosp = desglose_prospectador_final['Contactos Manuales Iniciados']
        desglose_prospectador_final['Tasa Aceptación (%)'] = ((desglose_prospectador_final['Invites Aceptadas'] / base_embudo_prosp) * 100).fillna(0).round(1)
        desglose_prospectador_final['Tasa Respuesta (%)'] = ((desglose_prospectador_final['Respuestas 1er Msj'] / desglose_prospectador_final['Invites Aceptadas']) * 100).fillna(0).round(1)
        desglose_prospectador_final['Tasa Sesión vs Resp. (%)'] = ((desglose_prospectador_final['Sesiones Agendadas'] / desglose_prospectador_final['Respuestas 1er Msj']) * 100).fillna(0).round(1)
        desglose_prospectador_final['Tasa Sesión Global (%)'] = ((desglose_prospectador_final['Sesiones Agendadas'] / base_embudo_prosp) * 100).fillna(0).round(1)
        rate_cols_prosp = ['Tasa Inicio (%)', 'Tasa Aceptación (%)', 'Tasa Respuesta (%)', 'Tasa Sesión vs Resp. (%)', 'Tasa Sesión Global (%)']
        for r_col in rate_cols_prosp: desglose_prospectador_final[r_col] = desglose_prospectador_final[r_col].apply(lambda x: 0 if pd.isna(x) or x == float('inf') or x == float('-inf') else x)

        st.dataframe(desglose_prospectador_final.style.format(
            {'Total Asignados': "{:,}", 'Contactos Manuales Iniciados': "{:,}", 'Invites Aceptadas': "{:,}", 'Respuestas 1er Msj': "{:,}", 'Sesiones Agendadas': "{:,}",
             'Tasa Inicio (%)': "{:.1f}%", 'Tasa Aceptación (%)': "{:.1f}%", 'Tasa Respuesta (%)': "{:.1f}%",
             'Tasa Sesión vs Resp. (%)': "{:.1f}%", 'Tasa Sesión Global (%)': "{:.1f}%"}
        ), use_container_width=True)
        # ... (resto de los gráficos por prospectador sin cambios)
        p_chart1, p_chart2 = st.columns(2)
        with p_chart1:
            if not desglose_prospectador_final.empty:
                fig_contactos_prosp = px.bar(desglose_prospectador_final.sort_values(by='Contactos Manuales Iniciados', ascending=False),
                    x=COL_QUIEN_PROSPECTO, y='Contactos Manuales Iniciados', color=COL_QUIEN_PROSPECTO,
                    title='Contactos Manuales Iniciados por Prospectador', text_auto=True)
                st.plotly_chart(fig_contactos_prosp, use_container_width=True)
        with p_chart2:
            df_for_chart_p2 = desglose_prospectador_final[desglose_prospectador_final['Contactos Manuales Iniciados']>0].copy()
            if not df_for_chart_p2.empty:
                fig_sesion_prosp = px.bar(df_for_chart_p2.sort_values(by='Tasa Sesión Global (%)', ascending=False),
                    x=COL_QUIEN_PROSPECTO, y='Tasa Sesión Global (%)', color=COL_QUIEN_PROSPECTO,
                    title='Tasa Sesión Global por Prospectador', text='Tasa Sesión Global (%)')
                fig_sesion_prosp.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_sesion_prosp.update_layout(yaxis_range=[0,105])
                st.plotly_chart(fig_sesion_prosp, use_container_width=True)

    else:
        st.info("No hay contactos manuales iniciados para mostrar desglose por prospectador.")

    st.markdown("---")
    st.markdown("#### Desglose por Avatar (sobre Contactos Manuales Iniciados)")
    if not df_contactos_iniciados.empty and COL_AVATAR in df_contactos_iniciados.columns:
        # CORRECCIÓN: Nombrar columnas directamente con espacios en la agregación
        desglose_avatar_agg_spec = {
            'Contactos Manuales Iniciados': (COL_FECHA_INVITE, 'count'),
            'Invites Aceptadas': (COL_INVITE_ACEPTADA, lambda x: (x == "si").sum()),
            'Respuestas 1er Msj': (COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum()),
            'Sesiones Agendadas': (COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
        }
        desglose_avatar = df_contactos_iniciados.groupby(COL_AVATAR, as_index=False).agg(**desglose_avatar_agg_spec)
        desglose_avatar = desglose_avatar[desglose_avatar[COL_AVATAR] != "N/D_Interno"]

        base_embudo_avatar = desglose_avatar['Contactos Manuales Iniciados'] # Ahora debería funcionar
        desglose_avatar['Tasa Aceptación (%)'] = ((desglose_avatar['Invites Aceptadas'] / base_embudo_avatar) * 100).fillna(0).round(1)
        desglose_avatar['Tasa Respuesta (%)'] = ((desglose_avatar['Respuestas 1er Msj'] / desglose_avatar['Invites Aceptadas']) * 100).fillna(0).round(1)
        desglose_avatar['Tasa Sesión Global (%)'] = ((desglose_avatar['Sesiones Agendadas'] / base_embudo_avatar) * 100).fillna(0).round(1)
        rate_cols_avatar = ['Tasa Aceptación (%)', 'Tasa Respuesta (%)', 'Tasa Sesión Global (%)']
        for r_col in rate_cols_avatar: desglose_avatar[r_col] = desglose_avatar[r_col].apply(lambda x: 0 if pd.isna(x) or x == float('inf') or x == float('-inf') else x)

        st.dataframe(desglose_avatar.style.format(
            {'Contactos Manuales Iniciados': "{:,}", 'Invites Aceptadas': "{:,}", 'Respuestas 1er Msj': "{:,}", 'Sesiones Agendadas': "{:,}",
             'Tasa Aceptación (%)': "{:.1f}%", 'Tasa Respuesta (%)': "{:.1f}%", 'Tasa Sesión Global (%)': "{:.1f}%"}
        ), use_container_width=True)
        # ... (resto de los gráficos por avatar sin cambios)
        a_chart1, a_chart2 = st.columns(2)
        with a_chart1:
            if not desglose_avatar.empty:
                fig_contactos_avatar = px.bar(desglose_avatar.sort_values(by='Contactos Manuales Iniciados', ascending=False),
                    x=COL_AVATAR, y='Contactos Manuales Iniciados', color=COL_AVATAR,
                    title='Contactos Manuales Iniciados por Avatar', text_auto=True)
                st.plotly_chart(fig_contactos_avatar, use_container_width=True)
        with a_chart2:
            df_for_chart_a2 = desglose_avatar[desglose_avatar['Contactos Manuales Iniciados']>0].copy()
            if not df_for_chart_a2.empty:
                fig_sesion_avatar = px.bar(df_for_chart_a2.sort_values(by='Tasa Sesión Global (%)', ascending=False),
                    x=COL_AVATAR, y='Tasa Sesión Global (%)', color=COL_AVATAR,
                    title='Tasa Sesión Global por Avatar', text='Tasa Sesión Global (%)')
                fig_sesion_avatar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_sesion_avatar.update_layout(yaxis_range=[0,105])
                st.plotly_chart(fig_sesion_avatar, use_container_width=True)
    else:
        st.info("No hay contactos manuales iniciados o columna Avatar no disponible para mostrar desglose por avatar.")

    st.markdown("---")
    st.markdown("#### Desglose por Campaña (sobre Contactos Manuales Iniciados)")
    campaign_filter_active = st.session_state.get(SES_CAMPAIGN_FILTER_KEY, ["– Todas –"])
    show_campaign_breakdown = False
    if ("– Todas –" in campaign_filter_active and df_contactos_iniciados[COL_CAMPAIGN].nunique() > 1) or \
       (len(campaign_filter_active) > 1 and "– Todas –" not in campaign_filter_active):
        show_campaign_breakdown = True

    if not df_contactos_iniciados.empty and COL_CAMPAIGN in df_contactos_iniciados.columns and show_campaign_breakdown:
        # CORRECCIÓN: Nombrar columnas directamente con espacios en la agregación
        desglose_campana_agg_spec = {
            'Contactos Manuales Iniciados': (COL_FECHA_INVITE, 'count'),
            'Invites Aceptadas': (COL_INVITE_ACEPTADA, lambda x: (x == "si").sum()),
            'Respuestas 1er Msj': (COL_RESPUESTA_1ER_MSJ, lambda x: (x == "si").sum()),
            'Sesiones Agendadas': (COL_SESION_AGENDADA_MANUAL, lambda x: (x == "si").sum())
        }
        desglose_campana = df_contactos_iniciados.groupby(COL_CAMPAIGN, as_index=False).agg(**desglose_campana_agg_spec)

        base_embudo_camp = desglose_campana['Contactos Manuales Iniciados'] # Ahora debería funcionar
        desglose_campana['Tasa Aceptación (%)'] = ((desglose_campana['Invites Aceptadas'] / base_embudo_camp) * 100).fillna(0).round(1)
        desglose_campana['Tasa Respuesta (%)'] = ((desglose_campana['Respuestas 1er Msj'] / desglose_campana['Invites Aceptadas']) * 100).fillna(0).round(1)
        desglose_campana['Tasa Sesión Global (%)'] = ((desglose_campana['Sesiones Agendadas'] / base_embudo_camp) * 100).fillna(0).round(1)
        rate_cols_camp = ['Tasa Aceptación (%)', 'Tasa Respuesta (%)', 'Tasa Sesión Global (%)']
        for r_col in rate_cols_camp: desglose_campana[r_col] = desglose_campana[r_col].apply(lambda x: 0 if pd.isna(x) or x == float('inf') or x == float('-inf') else x)

        st.dataframe(desglose_campana.style.format(
            {'Contactos Manuales Iniciados': "{:,}", 'Invites Aceptadas': "{:,}", 'Respuestas 1er Msj': "{:,}", 'Sesiones Agendadas': "{:,}",
             'Tasa Aceptación (%)': "{:.1f}%", 'Tasa Respuesta (%)': "{:.1f}%", 'Tasa Sesión Global (%)': "{:.1f}%"}
        ), use_container_width=True)
        # ... (resto de los gráficos por campaña sin cambios)
        c_chart1, c_chart2 = st.columns(2)
        with c_chart1:
            if not desglose_campana.empty:
                fig_contactos_camp = px.bar(desglose_campana.sort_values(by='Contactos Manuales Iniciados', ascending=False),
                    x=COL_CAMPAIGN, y='Contactos Manuales Iniciados', color=COL_CAMPAIGN,
                    title='Contactos Manuales Iniciados por Campaña', text_auto=True)
                st.plotly_chart(fig_contactos_camp, use_container_width=True)
        with c_chart2:
            df_for_chart_c2 = desglose_campana[desglose_campana['Contactos Manuales Iniciados']>0].copy()
            if not df_for_chart_c2.empty:
                fig_sesion_camp = px.bar(df_for_chart_c2.sort_values(by='Tasa Sesión Global (%)', ascending=False),
                    x=COL_CAMPAIGN, y='Tasa Sesión Global (%)', color=COL_CAMPAIGN,
                    title='Tasa Sesión Global por Campaña', text='Tasa Sesión Global (%)')
                fig_sesion_camp.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_sesion_camp.update_layout(yaxis_range=[0,105])
                st.plotly_chart(fig_sesion_camp, use_container_width=True)

    elif not show_campaign_breakdown:
         st.info("Selecciona '– Todas las Campañas –' o múltiples campañas en la barra lateral para ver este desglose comparativo.")
    else:
        st.info("No hay contactos manuales iniciados para mostrar desglose por campaña.")
    st.markdown("---")

# ... (la función display_email_prospecting_analysis permanece igual)...
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

# Sección 1: Potencial de Campaña
display_campaign_potential(df_base_campaigns_loaded.copy())

# Sección 2: Trazabilidad Detallada (Campaña -> Prospectador -> Embudo)
display_manual_prospecting_analysis(df_filtered_by_sidebar.copy())

# NUEVA Sección 3: Desglose General de Prospección Manual
display_global_manual_prospecting_deep_dive(df_filtered_by_sidebar.copy()) # Usar el mismo df filtrado

# Sección 4: Análisis de Prospección por Email
display_email_prospecting_analysis(df_filtered_by_sidebar.copy())

st.markdown("---")
st.info("Esta página de análisis de campañas ha sido desarrollada por Johnsito ✨")
