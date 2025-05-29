# pages/🎯_Análisis_de_Campañas.py
import streamlit as st
import pandas as pd
import sys
import os
import datetime
import plotly.express as px
import gspread # Para la carga de datos independiente
from collections import Counter # Para la carga de datos independiente

# Añadir la raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importaciones de tu proyecto (si son necesarias y no conflictivas)
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Análisis de Campañas", layout="wide")
st.title("🚀 Análisis de Desempeño por Campaña")
st.markdown("Evaluación de prospectos y efectividad de campañas manuales y por correo electrónico.")

# --- LÓGICA DE CARGA DE DATOS ESPECÍFICA PARA ESTA PÁGINA ---
@st.cache_data(ttl=300) # Cachear los datos para mejorar rendimiento
def cargar_datos_completos_para_campanas():
    try:
        creds_dict = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_dict)
    except KeyError:
        st.error("Error de Configuración (Secrets): Falta la sección [gcp_service_account] en los 'Secrets' de Streamlit para esta página.")
        st.stop()
    except Exception as e:
        st.error(f"Error al cargar las credenciales de Google Sheets desde st.secrets: {e}")
        st.stop()

    try:
        sheet_url = st.secrets.get("main_prostraction_sheet_url", "https://docs.google.com/spreadsheets/d/1h-hNu0cH0W_CnGx4qd3JvF-Fg9Z18ZyI9lQ7wVhROkE/edit#gid=0")
        sheet = client.open_by_url(sheet_url).sheet1
        raw_data = sheet.get_all_values()
        if not raw_data:
            st.error(f"La hoja de Google Sheets en '{sheet_url}' está vacía o no se pudo leer.")
            st.stop()
        headers = raw_data[0]
        rows = raw_data[1:]
    except gspread.exceptions.SpreadsheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo en la URL: {sheet_url}")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja de cálculo ('{sheet_url}'): {e}")
        st.stop()

    def make_unique(headers_list):
        counts = Counter()
        new_headers = []
        for h in headers_list:
            h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
            if not h_stripped: h_stripped = "Columna_Vacia"
            counts[h_stripped] += 1
            if counts[h_stripped] == 1:
                new_headers.append(h_stripped)
            else:
                new_headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
        return new_headers

    unique_headers = make_unique(headers)
    df = pd.DataFrame(rows, columns=unique_headers)

    if df.empty:
        st.warning("El DataFrame está vacío después de la carga inicial desde Google Sheets.")
        return pd.DataFrame()

    # Procesamiento de columnas existentes y NUEVAS
    columnas_fechas_a_parsear = {
        "Fecha de Invite": '%d/%m/%Y',
        "Fecha Sesion": '%d/%m/%Y', # Asumiendo formato, ajustar si es necesario
        "Fecha Primer Mensaje": '%d/%m/%Y', # Asumiendo formato, ajustar si es necesario
        "Fecha de Sesion Email": '%d/%m/%Y' # NUEVA
    }

    for col, fmt in columnas_fechas_a_parsear.items():
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            df.loc[df[col] == '', col] = pd.NaT
            df[col] = pd.to_datetime(df[col], format=fmt, errors="coerce")

    if "Avatar" in df.columns: #
        df["Avatar"] = df["Avatar"].astype(str).str.strip().str.title() #
        df["Avatar"] = df["Avatar"].replace({ #
            "Jonh Fenner": "John Bermúdez", "Jonh Bermúdez": "John Bermúdez", #
            "Jonh": "John Bermúdez", "John Fenner": "John Bermúdez" #
        })

    columnas_texto_a_limpiar = [
        "¿Invite Aceptada?", "Sesion Agendada?", "Respuesta Primer Mensaje",
        "Respuestas Subsecuentes", "Fuente de la Lista", "Proceso", "Pais",
        "Industria", "¿Quién Prospecto?", "Nombre", "Apellido", "Empresa", "Puesto",
        "Campaña", # NUEVA
        "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email" # NUEVAS
    ]
    common_empty_strings = ["", "Nan", "None", "Na", "<NA>", "#N/A", "N/A", "NO", "no"] #

    for col in columnas_texto_a_limpiar:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str).str.strip()
            
            non_binary_text_cols = ["Campaña", "Nombre", "Apellido", "Empresa", "Puesto", "Industria", "Pais", "Proceso", "Fuente de la Lista", "¿Quién Prospecto?"]
            if col not in non_binary_text_cols: # Para columnas tipo Si/No
                 df.loc[df[col].isin(common_empty_strings) | (df[col].str.lower() == 'no'), col] = 'No' #
                 df.loc[df[col].str.lower() == 'si', col] = 'Si'
            elif col == "Campaña": # Para Campaña, los vacíos son N/D
                 df.loc[df[col].isin(common_empty_strings), col] = 'N/D'
            else: # Para otras de texto libre, los vacíos son string vacío
                 df.loc[df[col].isin(common_empty_strings), col] = ''
    
    # Asegurar que las columnas clave para métricas existan, incluso si no vienen de la hoja
    key_metric_cols_default_no = ["¿Invite Aceptada?", "Respuesta Primer Mensaje", "Sesion Agendada?",
                                  "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email"]
    for kmc in key_metric_cols_default_no:
        if kmc not in df.columns:
            df[kmc] = "No"
            
    if "Campaña" not in df.columns:
        df["Campaña"] = "N/D"
    else: # Asegurar que los N/D estén bien para 'Campaña' si la columna ya existe
        df["Campaña"] = df["Campaña"].fillna("N/D")
        df.loc[df["Campaña"].astype(str).str.strip() == "", "Campaña"] = "N/D"

    if "¿Quién Prospecto?" not in df.columns:
        df["¿Quién Prospecto?"] = "N/D"
    else:
        df["¿Quién Prospecto?"] = df["¿Quién Prospecto?"].fillna("N/D")
        df.loc[df["¿Quién Prospecto?"].astype(str).str.strip() == "", "¿Quién Prospecto?"] = "N/D"
        
    if "Avatar" not in df.columns:
        df["Avatar"] = "N/D"
    else: # Asegurar que los N/D estén bien para 'Avatar' si la columna ya existe
        df["Avatar"] = df["Avatar"].fillna("N/D")
        df.loc[df["Avatar"].astype(str).str.strip() == "", "Avatar"] = "N/D"
        # Re-aplicar estandarización por si algún N/D se coló antes
        df["Avatar"] = df["Avatar"].apply(estandarizar_avatar)


    return df

# --- FIN LÓGICA DE CARGA DE DATOS ESPECÍFICA ---

# --- ESTADO DE SESIÓN PARA FILTROS DE ESTA PÁGINA ---
CAMPANAS_PREFIX = "campanas_page_v3_"
FILTRO_CAMPANA_KEY = f"{CAMPANAS_PREFIX}filtro_campana"
FILTRO_PROSPECTADOR_KEY = f"{CAMPANAS_PREFIX}filtro_prospectador"
FILTRO_AVATAR_KEY = f"{CAMPANAS_PREFIX}filtro_avatar"
FILTRO_FECHA_INI_KEY = f"{CAMPANAS_PREFIX}fecha_ini_manual"
FILTRO_FECHA_FIN_KEY = f"{CAMPANAS_PREFIX}fecha_fin_manual"
# Podrías añadir claves para fechas de email si el filtro se extiende

default_filters_campanas = {
    FILTRO_CAMPANA_KEY: ["– Todas –"],
    FILTRO_PROSPECTADOR_KEY: ["– Todos –"],
    FILTRO_AVATAR_KEY: ["– Todos –"],
    FILTRO_FECHA_INI_KEY: None,
    FILTRO_FECHA_FIN_KEY: None,
}

for key, default_val in default_filters_campanas.items():
    if key not in st.session_state:
        st.session_state[key] = default_val

def reset_campanas_filters_state():
    for key, default_val in default_filters_campanas.items():
        st.session_state[key] = default_val
    st.toast("Filtros de campañas reiniciados ✅")

df_base_campanas_page = cargar_datos_completos_para_campanas()

if df_base_campanas_page.empty:
    st.error("No se pudieron cargar datos para el análisis de campañas. La página no puede continuar.")
    st.stop()

# --- FILTROS EN EL SIDEBAR ---
def mostrar_filtros_sidebar_campanas(df_options):
    st.sidebar.header("🎯 Filtros de Campañas")
    st.sidebar.button("🧹 Limpiar Filtros de Campañas", on_click=reset_campanas_filters_state, use_container_width=True)
    st.sidebar.markdown("---")

    opciones_campana = ["– Todas –"]
    if "Campaña" in df_options.columns:
        campanas_validas = sorted([c for c in df_options["Campaña"].unique() if c and str(c).strip() != 'N/D' and str(c).strip() != ''])
        opciones_campana.extend(campanas_validas)
        if 'N/D' in df_options["Campaña"].unique() and 'N/D' not in opciones_campana :
             opciones_campana.append('N/D')

    current_campana_selection = st.session_state.get(FILTRO_CAMPANA_KEY, ["– Todas –"])
    valid_campana_selection = [sel for sel in current_campana_selection if sel in opciones_campana]
    if not valid_campana_selection:
        valid_campana_selection = ["– Todas –"] if "– Todas –" in opciones_campana else ([opciones_campana[0]] if opciones_campana else [])
    st.session_state[FILTRO_CAMPANA_KEY] = valid_campana_selection

    st.sidebar.multiselect(
        "Seleccionar Campaña(s):",
        options=opciones_campana,
        key=FILTRO_CAMPANA_KEY
    )

    opciones_prospectador = ["– Todos –"]
    if "¿Quién Prospecto?" in df_options.columns:
        prospectadores_unicos = df_options["¿Quién Prospecto?"].unique()
        prospectadores_validos = sorted([p for p in prospectadores_unicos if p and str(p).strip() != 'N/D' and str(p).strip() != ''])
        opciones_prospectador.extend(prospectadores_validos)
        if 'N/D' in prospectadores_unicos and 'N/D' not in opciones_prospectador:
            opciones_prospectador.append('N/D')
    
    current_prospectador_selection = st.session_state.get(FILTRO_PROSPECTADOR_KEY, ["– Todos –"])
    valid_prospectador_selection = [sel for sel in current_prospectador_selection if sel in opciones_prospectador]
    if not valid_prospectador_selection:
        valid_prospectador_selection = ["– Todos –"] if "– Todos –" in opciones_prospectador else ([opciones_prospectador[0]] if opciones_prospectador else [])
    st.session_state[FILTRO_PROSPECTADOR_KEY] = valid_prospectador_selection
    
    st.sidebar.multiselect(
        "¿Quién Prospectó?:",
        options=opciones_prospectador,
        key=FILTRO_PROSPECTADOR_KEY
    )

    opciones_avatar = ["– Todos –"]
    if "Avatar" in df_options.columns:
        avatares_unicos = df_options["Avatar"].unique()
        avatares_validos = sorted([a for a in avatares_unicos if a and str(a).strip() != 'N/D' and str(a).strip() != ''])
        opciones_avatar.extend(avatares_validos)
        if 'N/D' in avatares_unicos and 'N/D' not in opciones_avatar:
            opciones_avatar.append('N/D')

    current_avatar_selection = st.session_state.get(FILTRO_AVATAR_KEY, ["– Todos –"])
    valid_avatar_selection = [sel for sel in current_avatar_selection if sel in opciones_avatar]
    if not valid_avatar_selection:
        valid_avatar_selection = ["– Todos –"] if "– Todos –" in opciones_avatar else ([opciones_avatar[0]] if opciones_avatar else [])
    st.session_state[FILTRO_AVATAR_KEY] = valid_avatar_selection

    st.sidebar.multiselect(
        "Avatar:",
        options=opciones_avatar,
        key=FILTRO_AVATAR_KEY
    )
    
    st.sidebar.markdown("---")
    st.sidebar.subheader("🗓️ Filtro de Fechas (Prosp. Manual)")
    min_fecha_data_manual = None
    max_fecha_data_manual = None

    if "Fecha de Invite" in df_options.columns and pd.api.types.is_datetime64_any_dtype(df_options["Fecha de Invite"]):
        fechas_relevantes_manual = df_options["Fecha de Invite"].dropna()
        if not fechas_relevantes_manual.empty:
            min_fecha_data_manual = fechas_relevantes_manual.min().date()
            max_fecha_data_manual = fechas_relevantes_manual.max().date()

    cf1, cf2 = st.sidebar.columns(2)
    with cf1:
        st.date_input("Desde (Fecha Invite)", value=st.session_state.get(FILTRO_FECHA_INI_KEY), format="DD/MM/YYYY", key=FILTRO_FECHA_INI_KEY, min_value=min_fecha_data_manual, max_value=max_fecha_data_manual)
    with cf2:
        st.date_input("Hasta (Fecha Invite)", value=st.session_state.get(FILTRO_FECHA_FIN_KEY), format="DD/MM/YYYY", key=FILTRO_FECHA_FIN_KEY, min_value=min_fecha_data_manual, max_value=max_fecha_data_manual)

    return (
        st.session_state[FILTRO_CAMPANA_KEY],
        st.session_state[FILTRO_PROSPECTADOR_KEY],
        st.session_state[FILTRO_AVATAR_KEY],
        st.session_state[FILTRO_FECHA_INI_KEY],
        st.session_state[FILTRO_FECHA_FIN_KEY]
    )

(
    selected_campanas,
    selected_prospectadores,
    selected_avatars,
    selected_fecha_ini_manual,
    selected_fecha_fin_manual,
) = mostrar_filtros_sidebar_campanas(df_base_campanas_page)


# --- APLICACIÓN DE FILTROS ---
def aplicar_filtros_campanas_page(df_original, campanas_sel, prospectadores_sel, avatars_sel, fecha_ini_m, fecha_fin_m):
    df_filtrado_general = df_original.copy() # Empezamos con todos los datos cargados para la página

    # 1. Filtro por Campaña (Aplica a todo lo que se mostrará en la página)
    if campanas_sel and "– Todos –" not in campanas_sel:
        df_filtrado_general = df_filtrado_general[df_filtrado_general["Campaña"].isin(campanas_sel)]
    
    # Estos filtros (prospectador, avatar) se aplican después del de campaña, al DataFrame que ya tiene las campañas seleccionadas
    # Estos se usarán como base para los dos contextos (manual y email)
    
    df_para_contextos = df_filtrado_general.copy()
    if prospectadores_sel and "– Todos –" not in prospectadores_sel:
        if "¿Quién Prospecto?" in df_para_contextos.columns:
            df_para_contextos = df_para_contextos[df_para_contextos["¿Quién Prospecto?"].isin(prospectadores_sel)]
    
    if avatars_sel and "– Todos –" not in avatars_sel:
        if "Avatar" in df_para_contextos.columns:
            df_para_contextos = df_para_contextos[df_para_contextos["Avatar"].isin(avatars_sel)]

    # 2. Preparar DataFrame para Prospección Manual (aplicando filtro de fecha manual)
    df_manual_ctx = df_para_contextos.copy()
    if "Fecha de Invite" in df_manual_ctx.columns and pd.api.types.is_datetime64_any_dtype(df_manual_ctx["Fecha de Invite"]):
        if fecha_ini_m and fecha_fin_m:
            df_manual_ctx = df_manual_ctx[
                (df_manual_ctx["Fecha de Invite"].dt.normalize() >= pd.to_datetime(fecha_ini_m).normalize()) &
                (df_manual_ctx["Fecha de Invite"].dt.normalize() <= pd.to_datetime(fecha_fin_m).normalize())
            ]
        elif fecha_ini_m:
            df_manual_ctx = df_manual_ctx[df_manual_ctx["Fecha de Invite"].dt.normalize() >= pd.to_datetime(fecha_ini_m).normalize()]
        elif fecha_fin_m:
            df_manual_ctx = df_manual_ctx[df_manual_ctx["Fecha de Invite"].dt.normalize() <= pd.to_datetime(fecha_fin_m).normalize()]
    
    # 3. DataFrame para Prospección por Email (no se aplica filtro de fecha manual aquí, podría tener su propio filtro de fecha de email si se implementa)
    df_email_ctx = df_para_contextos.copy()
            
    return df_filtrado_general, df_manual_ctx, df_email_ctx

df_general_filtrado_campana, df_filtrado_manual_final, df_filtrado_email_final = aplicar_filtros_campanas_page(
    df_base_campanas_page, selected_campanas, selected_prospectadores, selected_avatars, selected_fecha_ini_manual, selected_fecha_fin_manual
)

# --- LÓGICA PRINCIPAL DE LA PÁGINA ---

st.header("Información General de Campañas Seleccionadas")

# Usamos df_general_filtrado_campana para los totales de prospectable POR CAMPAÑA
# (ya que este df tiene aplicados los filtros de Campaña, Prospectador y Avatar del sidebar)
if not df_general_filtrado_campana.empty:
    total_prospectable_filtrado = df_general_filtrado_campana.groupby("Campaña").size().reset_index(name="Prospectos en Campaña (con filtros aplicados)")
    total_prospectable_filtrado = total_prospectable_filtrado.sort_values(by="Prospectos en Campaña (con filtros aplicados)", ascending=False)

    if not total_prospectable_filtrado.empty:
        col_summary1, col_summary2 = st.columns([2,3])
        with col_summary1:
            st.metric("Total Campañas Únicas (filtradas)", df_general_filtrado_campana["Campaña"].nunique())
            st.metric("Total Prospectos (en campañas filtradas)", f"{df_general_filtrado_campana.shape[0]:,}")

        with col_summary2:
            st.markdown("##### Prospectos por Campaña (con filtros aplicados):")
            fig_potenciales = px.bar(
                total_prospectable_filtrado.head(15),
                x="Campaña",
                y="Prospectos en Campaña (con filtros aplicados)",
                title="Top 15 Campañas por # Prospectos (Filtros Aplicados)",
                text_auto=True
            )
            fig_potenciales.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_potenciales, use_container_width=True)

        with st.expander("Ver tabla completa de Prospectos por Campaña (con filtros aplicados)"):
            st.dataframe(total_prospectable_filtrado, use_container_width=True)
    else:
        st.info("No hay prospectos que coincidan con los filtros de Campaña, Prospectador y/o Avatar para el resumen general.")

else:
    st.info("No hay datos base que coincidan con los filtros seleccionados para el resumen general de campañas.")


st.markdown("---")
st.header("📈 Análisis de Prospección dentro de Campañas Seleccionadas")

# --- Sub-sección: Prospección Manual ---
st.subheader("🛠️ Prospección Manual")
# Usamos df_filtrado_manual_final, que ya tiene todos los filtros aplicados, incluyendo fecha manual
df_manual_accion = df_filtrado_manual_final[df_filtrado_manual_final["Fecha de Invite"].notna()].copy() #

if df_manual_accion.empty:
    st.info("No hay datos de prospección manual para las campañas y filtros seleccionados (incluyendo filtro de fecha manual).")
else:
    st.metric("Prospectos con Interacción Manual Registrada (Fecha Invite)", f"{len(df_manual_accion):,}")
    
    manual_invites_aceptadas = df_manual_accion[df_manual_accion["¿Invite Aceptada?"].apply(limpiar_valor_kpi) == "si"].shape[0] #
    manual_respuestas_1er_msj = df_manual_accion[df_manual_accion["Respuesta Primer Mensaje"].apply(lambda x: limpiar_valor_kpi(x) not in ["no", "", "nan"])].shape[0] #
    manual_sesiones_agendadas = df_manual_accion[df_manual_accion["Sesion Agendada?"].apply(limpiar_valor_kpi) == "si"].shape[0] #

    m_col1, m_col2, m_col3 = st.columns(3)
    m_col1.metric("Invites Aceptadas (Manual)", f"{manual_invites_aceptadas:,}")
    m_col2.metric("Respuestas 1er Msj (Manual)", f"{manual_respuestas_1er_msj:,}")
    m_col3.metric("Sesiones Agendadas (Manual)", f"{manual_sesiones_agendadas:,}")

    tasa_acept_manual = (manual_invites_aceptadas / len(df_manual_accion) * 100) if len(df_manual_accion) > 0 else 0
    tasa_resp_manual = (manual_respuestas_1er_msj / manual_invites_aceptadas * 100) if manual_invites_aceptadas > 0 else 0
    tasa_sesion_manual = (manual_sesiones_agendadas / manual_respuestas_1er_msj * 100) if manual_respuestas_1er_msj > 0 else 0
    
    tm_col1, tm_col2, tm_col3 = st.columns(3)
    tm_col1.metric("Tasa Aceptación (Manual)", f"{tasa_acept_manual:.1f}%", help="Invites Aceptadas / Prospectos con Interacción Manual Registrada")
    tm_col2.metric("Tasa Respuesta / Acept. (Manual)", f"{tasa_resp_manual:.1f}%")
    tm_col3.metric("Tasa Sesión / Resp. (Manual)", f"{tasa_sesion_manual:.1f}%")

    st.markdown("##### Desempeño Manual por Campaña")
    if not df_manual_accion.empty:
        resumen_manual_campana = df_manual_accion.groupby("Campaña").agg(
            Con_Fecha_Invite_Manual=("Campaña", "count"),
            Invites_Aceptadas_Manual=("¿Invite Aceptada?", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum()), #
            Respuestas_1er_Msj_Manual=("Respuesta Primer Mensaje", lambda col: (col.apply(lambda x: limpiar_valor_kpi(x) not in ["no", "", "nan"])).sum()), #
            Sesiones_Agendadas_Manual=("Sesion Agendada?", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum()) #
        ).reset_index()
        resumen_manual_campana["Tasa Sesión Global (Manual %)"] = (
            resumen_manual_campana["Sesiones_Agendadas_Manual"] / resumen_manual_campana["Con_Fecha_Invite_Manual"] * 100
        ).round(1).fillna(0)
        
        if not resumen_manual_campana.empty:
            fig_manual_camp_ses = px.bar(
                resumen_manual_campana.sort_values(by="Tasa Sesión Global (Manual %)", ascending=False).head(10),
                x="Campaña", y="Tasa Sesión Global (Manual %)",
                title="Top 10 Campañas por Tasa de Sesión Global (Manual)", text_auto=".1f"
            )
            st.plotly_chart(fig_manual_camp_ses, use_container_width=True)
            with st.expander("Ver tabla de desempeño manual por campaña"):
                st.dataframe(resumen_manual_campana, use_container_width=True)
        else:
            st.info("No hay datos suficientes para el desglose manual por campaña.")
    else:
        st.info("No hay acciones manuales registradas (Fecha Invite) para los filtros aplicados.")

st.markdown("---")
# --- Sub-sección: Prospección por Correo ---
st.subheader("📧 Prospección por Correo Electrónico")
# Usamos df_filtrado_email_final, que tiene filtros de Campaña, Prospectador y Avatar
df_email_accion = df_filtrado_email_final[df_filtrado_email_final["Contactados por Campaña"].apply(limpiar_valor_kpi) == "si"].copy()

if df_email_accion.empty:
    st.info("No hay datos de prospección por correo para las campañas y filtros seleccionados.")
else:
    st.metric("Prospectos Contactados por Email", f"{len(df_email_accion):,}")
    
    email_respuestas = df_email_accion[df_email_accion["Respuesta Email"].apply(lambda x: limpiar_valor_kpi(x) not in ["no", "", "nan"])].shape[0]
    email_sesiones_agendadas = df_email_accion[df_email_accion["Sesion Agendada Email"].apply(limpiar_valor_kpi) == "si"].shape[0]

    e_col1, e_col2 = st.columns(2)
    e_col1.metric("Respuestas (Email)", f"{email_respuestas:,}")
    e_col2.metric("Sesiones Agendadas (Email)", f"{email_sesiones_agendadas:,}")
    
    tasa_resp_email = (email_respuestas / len(df_email_accion) * 100) if len(df_email_accion) > 0 else 0
    tasa_sesion_email = (email_sesiones_agendadas / email_respuestas * 100) if email_respuestas > 0 else 0
    
    te_col1, te_col2 = st.columns(2)
    te_col1.metric("Tasa Respuesta / Contacto (Email)", f"{tasa_resp_email:.1f}%")
    te_col2.metric("Tasa Sesión / Resp. (Email)", f"{tasa_sesion_email:.1f}%")

    st.markdown("##### Desempeño por Correo por Campaña")
    if not df_email_accion.empty:
        resumen_email_campana = df_email_accion.groupby("Campaña").agg(
            Contactados_Email=("Campaña", "count"),
            Respuestas_Email=("Respuesta Email", lambda col: (col.apply(lambda x: limpiar_valor_kpi(x) not in ["no", "", "nan"])).sum()),
            Sesiones_Agendadas_Email=("Sesion Agendada Email", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum())
        ).reset_index()
        resumen_email_campana["Tasa Sesión Global (Email %)"] = (
            resumen_email_campana["Sesiones_Agendadas_Email"] / resumen_email_campana["Contactados_Email"] * 100
        ).round(1).fillna(0)
        
        if not resumen_email_campana.empty:
            fig_email_camp_ses = px.bar(
                resumen_email_campana.sort_values(by="Tasa Sesión Global (Email %)", ascending=False).head(10),
                x="Campaña", y="Tasa Sesión Global (Email %)",
                title="Top 10 Campañas por Tasa de Sesión Global (Email)", text_auto=".1f"
            )
            st.plotly_chart(fig_email_camp_ses, use_container_width=True)
            with st.expander("Ver tabla de desempeño por correo por campaña"):
                st.dataframe(resumen_email_campana, use_container_width=True)
        else:
            st.info("No hay datos suficientes para el desglose por correo por campaña.")
    else:
        st.info("No hay acciones de email registradas (Contactados por Campaña = Si) para los filtros aplicados.")
        
st.markdown("---")
st.header("👥 Análisis por Prospectador y Avatar (dentro de Campañas Seleccionadas)")

if not df_manual_accion.empty and "¿Quién Prospecto?" in df_manual_accion.columns and df_manual_accion["¿Quién Prospecto?"].nunique() > 0:
    st.subheader("🛠️ Desempeño Manual por ¿Quién Prospectó?")
    manual_por_prospectador = df_manual_accion.groupby("¿Quién Prospecto?").agg(
        Con_Fecha_Invite_Manual=("¿Quién Prospecto?", "count"),
        Sesiones_Agendadas_Manual=("Sesion Agendada?", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum()) #
    ).reset_index()
    manual_por_prospectador["Tasa_Sesion_Manual_%"] = (manual_por_prospectador["Sesiones_Agendadas_Manual"] / manual_por_prospectador["Con_Fecha_Invite_Manual"] * 100).round(1).fillna(0)
    if not manual_por_prospectador[manual_por_prospectador["¿Quién Prospecto?"] != "N/D"].empty: # Evitar graficar solo "N/D"
        fig_man_prosp = px.bar(manual_por_prospectador[manual_por_prospectador["¿Quién Prospecto?"] != "N/D"].sort_values("Tasa_Sesion_Manual_%", ascending=False), 
                               x="¿Quién Prospecto?", y="Tasa_Sesion_Manual_%", title="Tasa de Sesión (Manual) por Prospectador", text_auto=".1f")
        st.plotly_chart(fig_man_prosp, use_container_width=True)
        with st.expander("Ver detalle manual por prospectador"):
            st.dataframe(manual_por_prospectador, use_container_width=True)

if not df_email_accion.empty and "¿Quién Prospecto?" in df_email_accion.columns and df_email_accion["¿Quién Prospecto?"].nunique() > 0:
    st.subheader("📧 Desempeño Email por ¿Quién Prospectó?")
    email_por_prospectador = df_email_accion.groupby("¿Quién Prospecto?").agg(
        Contactados_Email=("¿Quién Prospecto?", "count"),
        Sesiones_Agendadas_Email=("Sesion Agendada Email", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum())
    ).reset_index()
    email_por_prospectador["Tasa_Sesion_Email_%"] = (email_por_prospectador["Sesiones_Agendadas_Email"] / email_por_prospectador["Contactados_Email"] * 100).round(1).fillna(0)
    if not email_por_prospectador[email_por_prospectador["¿Quién Prospecto?"] != "N/D"].empty:
        fig_email_prosp = px.bar(email_por_prospectador[email_por_prospectador["¿Quién Prospecto?"] != "N/D"].sort_values("Tasa_Sesion_Email_%", ascending=False), 
                                 x="¿Quién Prospecto?", y="Tasa_Sesion_Email_%", title="Tasa de Sesión (Email) por Prospectador", text_auto=".1f")
        st.plotly_chart(fig_email_prosp, use_container_width=True)
        with st.expander("Ver detalle email por prospectador"):
            st.dataframe(email_por_prospectador, use_container_width=True)

if not df_manual_accion.empty and "Avatar" in df_manual_accion.columns and df_manual_accion["Avatar"].nunique() > 0:
    st.subheader("🛠️ Desempeño Manual por Avatar")
    manual_por_avatar = df_manual_accion.groupby("Avatar").agg(
        Con_Fecha_Invite_Manual=("Avatar", "count"),
        Sesiones_Agendadas_Manual=("Sesion Agendada?", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum()) #
    ).reset_index()
    manual_por_avatar["Tasa_Sesion_Manual_%"] = (manual_por_avatar["Sesiones_Agendadas_Manual"] / manual_por_avatar["Con_Fecha_Invite_Manual"] * 100).round(1).fillna(0)
    if not manual_por_avatar[manual_por_avatar["Avatar"] != "N/D"].empty:
        fig_man_av = px.bar(manual_por_avatar[manual_por_avatar["Avatar"] != "N/D"].sort_values("Tasa_Sesion_Manual_%", ascending=False), 
                            x="Avatar", y="Tasa_Sesion_Manual_%", title="Tasa de Sesión (Manual) por Avatar", text_auto=".1f")
        st.plotly_chart(fig_man_av, use_container_width=True)
        with st.expander("Ver detalle manual por avatar"):
            st.dataframe(manual_por_avatar, use_container_width=True)

if not df_email_accion.empty and "Avatar" in df_email_accion.columns and df_email_accion["Avatar"].nunique() > 0:
    st.subheader("📧 Desempeño Email por Avatar")
    email_por_avatar = df_email_accion.groupby("Avatar").agg(
        Contactados_Email=("Avatar", "count"),
        Sesiones_Agendadas_Email=("Sesion Agendada Email", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum())
    ).reset_index()
    email_por_avatar["Tasa_Sesion_Email_%"] = (email_por_avatar["Sesiones_Agendadas_Email"] / email_por_avatar["Contactados_Email"] * 100).round(1).fillna(0)
    if not email_por_avatar[email_por_avatar["Avatar"] != "N/D"].empty:
        fig_email_av = px.bar(email_por_avatar[email_por_avatar["Avatar"] != "N/D"].sort_values("Tasa_Sesion_Email_%", ascending=False), 
                              x="Avatar", y="Tasa_Sesion_Email_%", title="Tasa de Sesión (Email) por Avatar", text_auto=".1f")
        st.plotly_chart(fig_email_av, use_container_width=True)
        with st.expander("Ver detalle email por avatar"):
            st.dataframe(email_por_avatar, use_container_width=True)

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info("Análisis de Campañas por Johnsito ✨. ¡Explora y optimiza!")
