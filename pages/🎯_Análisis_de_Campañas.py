# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
# Ensure these imports are correct based on your project structure
# from datos.carga_datos import cargar_y_limpiar_datos
# from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

# --- START: MOCK FUNCTIONS (Remove or replace with your actual imports) ---
# Mocking for standalone execution if actual imports are not available
def cargar_y_limpiar_datos():
    data = {
        'Campaña': ['Campaña H25', 'Campaña H25', 'Campaña Alpha', 'Campaña H25', 'Campaña Beta', 'Campaña Alpha', 'Campaña H25', 'Campaña H25', 'Campaña Beta', 'Campaña H25', None, 'Campaña Alpha'],
        'Fecha de Invite': [pd.NaT, '2023-01-05', '2023-01-10', '2023-01-15', pd.NaT, '2023-02-01', '2023-02-05', pd.NaT, '2023-02-10', '2023-02-15', '2023-03-01', '2023-03-05'],
        '¿Invite Aceptada?': ['no', 'si', 'si', 'no', 'si', 'si', 'si', 'no', 'si', 'si', 'no', 'si'],
        'Fecha Primer Mensaje': [pd.NaT, '2023-01-06', '2023-01-11', pd.NaT, '2023-01-21', '2023-02-02', '2023-02-06', pd.NaT, '2023-02-11', '2023-02-16', pd.NaT, '2023-03-06'],
        'Respuesta Primer Mensaje': ['no', 'si', 'si', 'no', 'no', 'si', 'no', 'no', 'si', 'si', 'no', 'si'],
        'Sesion Agendada?': ['no', 'si', 'no', 'no', 'no', 'si', 'no', 'no', 'no', 'si', 'no', 'no'],
        'Contactados por Campaña': ['no', 'si', 'si', 'no', 'si', 'si', 'no', 'si', 'si', 'no', 'no', 'si'], # Added for email flow
        'Respuesta Email': ['no', 'si', 'no', 'no', 'no', 'si', 'no', 'no', 'no', 'no', 'no', 'si'],       # Added for email flow
        'Sesion Agendada Email': ['no', 'no', 'no', 'no', 'no', 'si', 'no', 'no', 'no', 'no', 'no', 'no'],# Added for email flow
        '¿Quién Prospecto?': ['Juan', 'Maria', 'Pedro', 'Juan', 'Ana', 'Pedro', 'Maria', 'Juan', 'Ana', 'Maria', 'Luis', 'Pedro'],
        'Pais': ['Colombia', 'Mexico', 'Argentina', 'Colombia', 'Chile', 'Argentina', 'Mexico', 'Colombia', 'Chile', 'Mexico', 'España', 'Argentina'],
        'Avatar': ['Tipo A', 'Tipo B', 'Tipo A', 'Tipo A', 'Tipo C', 'Tipo A', 'Tipo B', 'Tipo A', 'Tipo C', 'Tipo B', 'Tipo D', 'Tipo A'],
        'ID_Prospecto': range(1, 13) # Ensuring unique IDs for proper indexing later
    }
    df = pd.DataFrame(data)
    for col in ['Fecha de Invite', 'Fecha Primer Mensaje']:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

def limpiar_valor_kpi(valor):
    if pd.isna(valor):
        return ""
    return str(valor).strip().lower()

def estandarizar_avatar(avatar):
    # Simple mock, replace with your actual logic
    if pd.isna(avatar): return "No Especificado"
    avatar_lower = str(avatar).lower()
    if "tipo a" in avatar_lower: return "A"
    if "tipo b" in avatar_lower: return "B"
    if "tipo c" in avatar_lower: return "C"
    return "Otro"
# --- END: MOCK FUNCTIONS ---


# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado, partiendo del universo total de registros asignados.")

# --- Funciones de Ayuda Específicas para esta Página ---

@st.cache_data
def obtener_datos_base_campanas():
    df_completo = cargar_y_limpiar_datos() # This should load ALL prospects, including those with campaign names
    if df_completo is None or df_completo.empty:
        st.error("No se pudieron cargar los datos. Verifica la fuente.")
        return pd.DataFrame(), pd.DataFrame()

    if 'Campaña' not in df_completo.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo # Return df_completo as the second element

    # df_base_campanas_global will contain ALL records that have a campaign assigned. This is our Nivel 0.
    df_base_campanas_global = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy()
    # df_original_completo is used for fetching details later, ensuring we have all original columns.
    # It can be df_completo itself or a copy if manipulations are done on df_completo that shouldn't affect details.
    # For now, let's assume df_completo is what we want for details if it contains all necessary columns.
    # If df_base_campanas_global is already a subset of df_completo, we use its indices on df_completo for details.
    # The key is df_base_campanas_global is the master for campaign-assigned records.

    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"] # Add other date cols if any
    for col in date_cols_to_check:
        if col in df_base_campanas_global.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas_global[col]):
            df_base_campanas_global[col] = pd.to_datetime(df_base_campanas_global[col], errors='coerce')
        # Also ensure date columns are handled in df_completo if it's used separately for details
        if col in df_completo.columns and not pd.api.types.is_datetime64_any_dtype(df_completo[col]):
             df_completo[col] = pd.to_datetime(df_completo[col], errors='coerce')

    for df_proc in [df_base_campanas_global, df_completo]:
        if "Avatar" in df_proc.columns: # Ensure Avatar exists before applying
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar)

    return df_base_campanas_global, df_completo # df_original_completo is now df_completo

def inicializar_estado_filtros_campana():
    default_filters = {
        "campana_seleccion_principal": [],
        "campana_filtro_prospectador": ["– Todos –"],
        "campana_filtro_pais": ["– Todos –"],
        "campana_filtro_fecha_ini": None,
        "campana_filtro_fecha_fin": None,
        "gran_total_original_combinado": 0, # For Nivel 1
    }
    for key, value in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = value
        elif key in ["campana_seleccion_principal", "campana_filtro_prospectador", "campana_filtro_pais"] and not isinstance(st.session_state[key], list):
             st.session_state[key] = default_filters[key]


def resetear_filtros_campana_callback():
    st.session_state.campana_seleccion_principal = []
    st.session_state.campana_filtro_prospectador = ["– Todos –"]
    st.session_state.campana_filtro_pais = ["– Todos –"]
    st.session_state.di_campana_fecha_ini = None
    st.session_state.di_campana_fecha_fin = None
    st.session_state.campana_filtro_fecha_ini = None
    st.session_state.campana_filtro_fecha_fin = None
    st.session_state.gran_total_original_combinado = 0
    st.toast("Todos los filtros de la página de campañas han sido reiniciados.", icon="🧹")

def calcular_kpis_df_campana(df_filtrado_campana):
    # This df_filtrado_campana is the "Universo de Selección Filtrada" for aggregate,
    # or "Registros en Sel. Filtrada de esta campaña" for comparative table.
    if df_filtrado_campana.empty:
        return {
            "registros_en_seleccion_filtrada": 0, # Base for this calculation
            # Manual Flow
            "invites_enviadas_manual": 0, "invites_aceptadas": 0,
            "primeros_mensajes_enviados": 0, "respuestas_primer_mensaje": 0,
            "sesiones_agendadas_manual": 0,
            "tasa_prospeccion_manual_iniciada": 0, "tasa_aceptacion_invite": 0,
            "tasa_respuesta_vs_aceptadas": 0, "tasa_sesion_vs_respuesta_manual": 0,
            "tasa_sesion_global_manual": 0, # vs registros_en_seleccion_filtrada
            # Email Flow
            "emails_contactados": 0, "respuestas_email": 0, "sesiones_agendadas_email": 0,
            "tasa_contacto_email_iniciado": 0, "tasa_respuesta_email": 0,
            "tasa_sesion_vs_respuesta_email": 0, "tasa_sesion_global_email": 0, # vs registros_en_seleccion_filtrada
        }

    registros_en_seleccion_filtrada = len(df_filtrado_campana)

    # --- Manual Flow KPIs ---
    invites_enviadas_manual = df_filtrado_campana["Fecha de Invite"].notna().sum() # Nivel 3 definition
    invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str)))
    primeros_mensajes_enviados = sum( # After invite is accepted
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan", "si"] # Assuming 'si' here means they replied positively, adjust if 'si' means just "replied"
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str)) if limpiar_valor_kpi(x) == "si" # only count 'si' as a response
    )
    sesiones_agendadas_manual = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str)))

    tasa_prospeccion_manual_iniciada = (invites_enviadas_manual / registros_en_seleccion_filtrada * 100) if registros_en_seleccion_filtrada > 0 else 0
    tasa_aceptacion_invite = (invites_aceptadas / invites_enviadas_manual * 100) if invites_enviadas_manual > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0 # Or vs primeros_mensajes_enviados
    tasa_sesion_vs_respuesta_manual = (sesiones_agendadas_manual / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global_manual = (sesiones_agendadas_manual / registros_en_seleccion_filtrada * 100) if registros_en_seleccion_filtrada > 0 else 0

    # --- Email Flow KPIs ---
    emails_contactados = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Contactados por Campaña", pd.Series(dtype=str)))
    respuestas_email = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Respuesta Email", pd.Series(dtype=str)))
    sesiones_agendadas_email = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada Email", pd.Series(dtype=str)))

    tasa_contacto_email_iniciado = (emails_contactados / registros_en_seleccion_filtrada * 100) if registros_en_seleccion_filtrada > 0 else 0
    tasa_respuesta_email = (respuestas_email / emails_contactados * 100) if emails_contactados > 0 else 0
    tasa_sesion_vs_respuesta_email = (sesiones_agendadas_email / respuestas_email * 100) if respuestas_email > 0 else 0
    tasa_sesion_global_email = (sesiones_agendadas_email / registros_en_seleccion_filtrada * 100) if registros_en_seleccion_filtrada > 0 else 0

    return {
        "registros_en_seleccion_filtrada": int(registros_en_seleccion_filtrada),
        # Manual
        "invites_enviadas_manual": int(invites_enviadas_manual),
        "invites_aceptadas": int(invites_aceptadas),
        "primeros_mensajes_enviados": int(primeros_mensajes_enviados), # This is after acceptance
        "respuestas_primer_mensaje": int(respuestas_primer_mensaje),
        "sesiones_agendadas_manual": int(sesiones_agendadas_manual),
        "tasa_prospeccion_manual_iniciada": tasa_prospeccion_manual_iniciada,
        "tasa_aceptacion_invite": tasa_aceptacion_invite,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta_manual": tasa_sesion_vs_respuesta_manual,
        "tasa_sesion_global_manual": tasa_sesion_global_manual,
        # Email
        "emails_contactados": int(emails_contactados),
        "respuestas_email": int(respuestas_email),
        "sesiones_agendadas_email": int(sesiones_agendadas_email),
        "tasa_contacto_email_iniciado": tasa_contacto_email_iniciado,
        "tasa_respuesta_email": tasa_respuesta_email,
        "tasa_sesion_vs_respuesta_email": tasa_sesion_vs_respuesta_email,
        "tasa_sesion_global_email": tasa_sesion_global_email,
    }

def mostrar_embudo_para_flujo(kpis_flujo, flujo_seleccion_filtrada_count, titulo_embudo, tipo_flujo="manual"):
    etapas_embudo = []
    cantidades_embudo = []

    if tipo_flujo == "manual":
        etapas_embudo = [
            "Registros en Selección Filtrada", "Invites Enviadas (Manual)", "Invites Aceptadas",
            "Respuesta 1er Mensaje (Manual)", "Sesiones Agendadas (Manual)"
        ]
        cantidades_embudo = [
            flujo_seleccion_filtrada_count, kpis_flujo["invites_enviadas_manual"], kpis_flujo["invites_aceptadas"],
            kpis_flujo["respuestas_primer_mensaje"], kpis_flujo["sesiones_agendadas_manual"]
        ]
    elif tipo_flujo == "email":
        etapas_embudo = [
            "Registros en Selección Filtrada", "Emails Contactados", "Respuestas Email",
            "Sesiones Agendadas (Email)"
        ]
        cantidades_embudo = [
            flujo_seleccion_filtrada_count, kpis_flujo["emails_contactados"], kpis_flujo["respuestas_email"],
            kpis_flujo["sesiones_agendadas_email"]
        ]
    else:
        st.error("Tipo de flujo no válido para el embudo.")
        return

    if sum(cantidades_embudo) == 0 or flujo_seleccion_filtrada_count == 0 :
        st.info(f"No hay datos suficientes para generar el embudo de '{tipo_flujo}' para la selección actual.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    
    # % vs Anterior: First stage is always 100% of itself in terms of progression for THIS funnel's view
    porcentajes_vs_anterior = []
    if not df_embudo.empty:
        porcentajes_vs_anterior.append(100.0) # Registros en Selección Filtrada vs itself (or first step vs itself)
        for i in range(1, len(df_embudo)):
            porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
            porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    
    # % vs Total (Selección Filtrada): How each step fares against the initial pool for this funnel
    df_embudo['% vs Total Flujo'] = df_embudo.apply(
        lambda row: (row['Cantidad'] / flujo_seleccion_filtrada_count * 100) if flujo_seleccion_filtrada_count > 0 else 0.0, axis=1
    )

    df_embudo['Texto'] = df_embudo.apply(
        lambda row: f"{row['Cantidad']:,}<br>({row['% vs Anterior']:.1f}% vs Ant.)<br>({row['% vs Total Flujo']:.1f}% vs Sel.Filt.)", axis=1
    )
    # Special text for the first bar
    if not df_embudo.empty:
        df_embudo.loc[0, 'Texto'] = f"{df_embudo.loc[0, 'Cantidad']:,}<br>(Base: {df_embudo.loc[0, '% vs Total Flujo']:.1f}%)"


    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text')
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(f"Embudo basado en {flujo_seleccion_filtrada_count:,} registros en la Selección Filtrada para este flujo.")


def generar_tabla_comparativa_campanas_filtrada(
    df_filtrado_con_filtros_pagina, # This is df_final_analisis_campana
    lista_nombres_campanas_seleccionadas,
    df_base_campanas_global # Needed for "Total Original Campaña"
    ):
    datos_comparativa = []
    if df_filtrado_con_filtros_pagina.empty or not lista_nombres_campanas_seleccionadas:
        return pd.DataFrame(datos_comparativa)

    for nombre_campana in lista_nombres_campanas_seleccionadas:
        # Nivel 1: Total Original para ESTA campaña
        total_original_esta_campana = df_base_campanas_global[
            df_base_campanas_global['Campaña'] == nombre_campana
        ].shape[0]

        # Parte de la "Selección Filtrada" (Nivel 2) que pertenece a esta campaña
        df_campana_individual_filtrada = df_filtrado_con_filtros_pagina[
            df_filtrado_con_filtros_pagina['Campaña'] == nombre_campana
        ]
        registros_sel_filtrada_esta_campana = len(df_campana_individual_filtrada)
        
        percent_original_en_sel_filt = (registros_sel_filtrada_esta_campana / total_original_esta_campana * 100) if total_original_esta_campana > 0 else 0

        # Nivel 3: KPIs para esta campaña, basados en sus registros en la selección filtrada
        kpis = calcular_kpis_df_campana(df_campana_individual_filtrada) # kpis["registros_en_seleccion_filtrada"] IS registros_sel_filtrada_esta_campana

        datos_comparativa.append({
            "Campaña": nombre_campana,
            "Total Original": total_original_esta_campana,
            "En Sel. Filtrada": registros_sel_filtrada_esta_campana,
            "% Original en Sel. Filt.": percent_original_en_sel_filt,
            # Manual Flow
            "Invites Env. (M)": kpis["invites_enviadas_manual"],
            "Invites Acpt. (M)": kpis["invites_aceptadas"],
            "Resp. 1er Msj (M)": kpis["respuestas_primer_mensaje"],
            "Sesiones (M)": kpis["sesiones_agendadas_manual"],
            "Tasa Sesión Global (M) (%)": kpis["tasa_sesion_global_manual"],
            # Email Flow
            "Emails Cont. (E)": kpis["emails_contactados"],
            "Resp. Email (E)": kpis["respuestas_email"],
            "Sesiones (E)": kpis["sesiones_agendadas_email"],
            "Tasa Sesión Global (E) (%)": kpis["tasa_sesion_global_email"],
        })
    return pd.DataFrame(datos_comparativa)


# --- Carga de Datos Base (Nivel 0) ---
# df_base_campanas_global contains ALL records that have a campaign assigned.
# df_original_completo is the raw data from source, used for pulling details later with all original columns.
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No hay datos de campañas para analizar. Por favor, verifica la fuente de datos.")
    st.stop()

# --- Sección de Selección de Campaña Principal (Pre Nivel 1) ---
st.markdown("---")
st.subheader("1. Selección de Campaña(s)")
lista_campanas_disponibles_global = sorted(df_base_campanas_global['Campaña'].unique())
if not lista_campanas_disponibles_global:
    st.warning("No se encontraron nombres de campañas en los datos cargados.")
    st.stop()

st.session_state.campana_seleccion_principal = st.multiselect(
    "Elige la(s) campaña(s) a analizar:",
    options=lista_campanas_disponibles_global,
    default=st.session_state.campana_seleccion_principal,
    key="ms_campana_seleccion_principal"
)

# --- NIVEL 1: Visualización del Universo Total Original ---
if st.session_state.campana_seleccion_principal:
    st.markdown("---")
    st.subheader("Nivel 1: Universo Total Original de Registros Asignados")
    gran_total_original_combinado = 0
    
    # Prepare columns for metrics
    num_selected_campaigns = len(st.session_state.campana_seleccion_principal)
    cols_nivel1 = st.columns(num_selected_campaigns + 1) # One extra for the grand total

    for i, camp_name in enumerate(st.session_state.campana_seleccion_principal):
        total_original_camp = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name].shape[0]
        gran_total_original_combinado += total_original_camp
        with cols_nivel1[i]:
            st.metric(f"{camp_name} (Total Original)", f"{total_original_camp:,}")
    
    with cols_nivel1[num_selected_campaigns]: # Last column for grand total
        st.metric("Gran Total Original Combinado", f"{gran_total_original_combinado:,}")
    st.session_state.gran_total_original_combinado = gran_total_original_combinado # Store for Nivel 2 calc
else:
    st.info("Por favor, selecciona al menos una campaña para comenzar el análisis.")
    st.stop() # Stop if no campaign is selected for further processing

# --- Sección de Filtros Adicionales (Para Nivel 2) ---
st.markdown("---")
st.subheader("2. Filtros Adicionales (sobre Campañas Seleccionadas)")

if st.button("Limpiar Filtros de Página", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
    st.rerun()

# df_campanas_filtradas_por_seleccion is the subset of df_base_campanas_global for the selected campaigns.
# This is the dataset UPON WHICH page filters will be applied.
df_campanas_seleccionadas_original_scope = df_base_campanas_global[
    df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
].copy()

with st.expander("Aplicar filtros detallados a la(s) campaña(s) seleccionada(s)", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_seleccionadas_original_scope["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        # Logic to ensure default value is valid
        current_prospectador_filter = st.session_state.get("campana_filtro_prospectador", ["– Todos –"])
        if not all(p in opciones_prospectador_camp for p in current_prospectador_filter):
            current_prospectador_filter = ["– Todos –"]

        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó?", options=opciones_prospectador_camp,
            default=current_prospectador_filter, key="ms_campana_prospectador"
        )

        opciones_pais_camp = ["– Todos –"] + sorted(
            df_campanas_seleccionadas_original_scope["Pais"].dropna().astype(str).unique()
        )
        current_pais_filter = st.session_state.get("campana_filtro_pais", ["– Todos –"])
        if not all(p in opciones_pais_camp for p in current_pais_filter):
            current_pais_filter = ["– Todos –"]

        st.session_state.campana_filtro_pais = st.multiselect(
            "País del Prospecto", options=opciones_pais_camp,
            default=current_pais_filter, key="ms_campana_pais"
        )
    with col_f2:
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        if "Fecha de Invite" in df_campanas_seleccionadas_original_scope.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_seleccionadas_original_scope["Fecha de Invite"]):
            valid_dates = df_campanas_seleccionadas_original_scope["Fecha de Invite"].dropna()
            if not valid_dates.empty:
                min_fecha_invite_camp = valid_dates.min().date()
                max_fecha_invite_camp = valid_dates.max().date()
        
        val_fecha_ini = st.date_input(
            "Fecha de Invite Desde:", 
            value=st.session_state.campana_filtro_fecha_ini,
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_ini"
        )
        val_fecha_fin = st.date_input(
            "Fecha de Invite Hasta:", 
            value=st.session_state.campana_filtro_fecha_fin,
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_fin"
        )
        st.session_state.campana_filtro_fecha_ini = val_fecha_ini
        st.session_state.campana_filtro_fecha_fin = val_fecha_fin

# Aplicar filtros de página
df_aplicar_filtros_pagina = df_campanas_seleccionadas_original_scope.copy() # Start with data from selected campaigns

if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
    df_aplicar_filtros_pagina = df_aplicar_filtros_pagina[
        df_aplicar_filtros_pagina["¿Quién Prospecto?"].isin(st.session_state.campana_filtro_prospectador)
    ]
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_aplicar_filtros_pagina = df_aplicar_filtros_pagina[
        df_aplicar_filtros_pagina["Pais"].isin(st.session_state.campana_filtro_pais)
    ]

fecha_ini_aplicar = st.session_state.campana_filtro_fecha_ini
fecha_fin_aplicar = st.session_state.campana_filtro_fecha_fin

if fecha_ini_aplicar and "Fecha de Invite" in df_aplicar_filtros_pagina.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros_pagina["Fecha de Invite"]):
    fecha_ini_dt = pd.Timestamp(datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min))
    df_aplicar_filtros_pagina = df_aplicar_filtros_pagina[df_aplicar_filtros_pagina["Fecha de Invite"].dropna() >= fecha_ini_dt]

if fecha_fin_aplicar and "Fecha de Invite" in df_aplicar_filtros_pagina.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros_pagina["Fecha de Invite"]):
    fecha_fin_dt = pd.Timestamp(datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max))
    df_aplicar_filtros_pagina = df_aplicar_filtros_pagina[df_aplicar_filtros_pagina["Fecha de Invite"].dropna() <= fecha_fin_dt]

# This is our "Universo de Selección Filtrada" (Nivel 2)
df_final_analisis_campana = df_aplicar_filtros_pagina.copy()

# --- NIVEL 2: Métricas de la "Selección Filtrada" ---
st.markdown("---")
st.subheader("Nivel 2: Universo de Selección Filtrada (Tras Aplicar Filtros de Página)")
total_seleccion_filtrada = len(df_final_analisis_campana)
gran_total_original_combinado = st.session_state.get("gran_total_original_combinado", 0) # Retrieve from Nivel 1

percent_del_gran_total_original = (total_seleccion_filtrada / gran_total_original_combinado * 100) if gran_total_original_combinado > 0 else 0

nivel2_cols = st.columns(2)
with nivel2_cols[0]:
    st.metric("Registros en Selección Filtrada", f"{total_seleccion_filtrada:,}")
with nivel2_cols[1]:
    st.metric("% del Gran Total Original en Selección Filtrada", f"{percent_del_gran_total_original:.1f}%")
st.caption(f"Estos {total_seleccion_filtrada:,} registros son la base (100%) para los KPIs y embudos detallados a continuación.")


# --- NIVEL 3: Sección de Resultados y Visualizaciones (KPIs y Embudos) ---
st.markdown("---")
st.header(f"📊 Nivel 3: Resultados Detallados para la Selección Filtrada")
st.markdown(f"Campaña(s) Analizada(s): {', '.join(st.session_state.campana_seleccion_principal)}")

if df_final_analisis_campana.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s) en Nivel 2.")
else:
    st.markdown("### Indicadores Clave (KPIs) - Agregado de Selección Filtrada")
    # KPIs calculated on df_final_analisis_campana (Universo de Selección Filtrada)
    kpis_agregados = calcular_kpis_df_campana(df_final_analisis_campana)

    st.markdown("#### Flujo de Prospección Manual")
    kpi_cols_manual_agg = st.columns(4)
    kpi_cols_manual_agg[0].metric("Registros en Sel. Filtrada", f"{kpis_agregados['registros_en_seleccion_filtrada']:,}")
    kpi_cols_manual_agg[1].metric("Invites Enviadas (Manual)", f"{kpis_agregados['invites_enviadas_manual']:,}",
                                  f"{kpis_agregados['tasa_prospeccion_manual_iniciada']:.1f}% de Sel. Filtrada")
    kpi_cols_manual_agg[2].metric("Invites Aceptadas", f"{kpis_agregados['invites_aceptadas']:,}",
                                  f"{kpis_agregados['tasa_aceptacion_invite']:.1f}% de Invites Enviadas")
    kpi_cols_manual_agg[3].metric("Sesiones Agendadas (Manual)", f"{kpis_agregados['sesiones_agendadas_manual']:,}",
                                  f"{kpis_agregados['tasa_sesion_global_manual']:.1f}% de Sel. Filtrada")
    
    # Additional manual metrics if space or desired
    # st.caption(f"Respuestas 1er Mensaje (Manual): {kpis_agregados['respuestas_primer_mensaje']:,} ({kpis_agregados['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas)")
    # st.caption(f"Tasa Sesión vs Respuesta (Manual): {kpis_agregados['tasa_sesion_vs_respuesta_manual']:.1f}%")

    st.markdown("#### Flujo de Prospección por Email")
    kpi_cols_email_agg = st.columns(4)
    # Assuming 'Contactados por Campaña', 'Respuesta Email', 'Sesion Agendada Email' are in your df
    kpi_cols_email_agg[0].metric("Registros en Sel. Filtrada", f"{kpis_agregados['registros_en_seleccion_filtrada']:,}")
    kpi_cols_email_agg[1].metric("Emails Contactados", f"{kpis_agregados['emails_contactados']:,}",
                                 f"{kpis_agregados['tasa_contacto_email_iniciado']:.1f}% de Sel. Filtrada")
    kpi_cols_email_agg[2].metric("Respuestas Email", f"{kpis_agregados['respuestas_email']:,}",
                                 f"{kpis_agregados['tasa_respuesta_email']:.1f}% de Emails Contactados")
    kpi_cols_email_agg[3].metric("Sesiones Agendadas (Email)", f"{kpis_agregados['sesiones_agendadas_email']:,}",
                                 f"{kpis_agregados['tasa_sesion_global_email']:.1f}% de Sel. Filtrada")

    st.markdown("### Embudos de Conversión - Agregado de Selección Filtrada")
    col_embudo1, col_embudo2 = st.columns(2)
    with col_embudo1:
        mostrar_embudo_para_flujo(kpis_agregados, kpis_agregados['registros_en_seleccion_filtrada'], "Embudo Flujo Manual (vs Sel. Filtrada)", tipo_flujo="manual")
    with col_embudo2:
        mostrar_embudo_para_flujo(kpis_agregados, kpis_agregados['registros_en_seleccion_filtrada'], "Embudo Flujo Email (vs Sel. Filtrada)", tipo_flujo="email")


    # --- NIVEL 4: Tabla Comparativa ---
    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Nivel 4: Comparativa Detallada entre Campañas")
        st.caption("Considera los filtros de página aplicados (Nivel 2). Las KPIs se calculan sobre los 'Registros en Sel. Filtrada' de CADA campaña.")
        
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(
            df_final_analisis_campana, # This is the "Selección Filtrada" global
            st.session_state.campana_seleccion_principal,
            df_base_campanas_global # Needed for "Total Original Campaña"
        )

        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs por Campaña")
            
            cols_a_formatear_abs = ["Total Original", "En Sel. Filtrada", "Invites Env. (M)", "Invites Acpt. (M)", "Resp. 1er Msj (M)", "Sesiones (M)", "Emails Cont. (E)", "Resp. Email (E)", "Sesiones (E)"]
            cols_a_formatear_pct = ["% Original en Sel. Filt.", "Tasa Sesión Global (M) (%)", "Tasa Sesión Global (E) (%)"]
            
            format_dict_comp = {}
            for col in cols_a_formatear_abs:
                if col in df_tabla_comp.columns:
                     format_dict_comp[col] = "{:,}"
            for col in cols_a_formatear_pct:
                if col in df_tabla_comp.columns:
                    format_dict_comp[col] = "{:.1f}%"

            st.dataframe(df_tabla_comp.sort_values(by="Tasa Sesión Global (M) (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            
            # Example Comparative Bar Chart (Manual Flow Global Session Rate)
            st.subheader("Gráfico Comparativo: Tasa de Sesión Global (Manual) por Campaña")
            df_graf_comp_tsg_m = df_tabla_comp[df_tabla_comp["En Sel. Filtrada"] > 0].sort_values(by="Tasa Sesión Global (M) (%)", ascending=False)
            if not df_graf_comp_tsg_m.empty:
                fig_comp_tsg_m = px.bar(df_graf_comp_tsg_m, x="Campaña", y="Tasa Sesión Global (M) (%)", title="Comparativa: Tasa de Sesión Global (Manual)", text="Tasa Sesión Global (M) (%)", color="Campaña")
                fig_comp_tsg_m.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg_m.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg_m, use_container_width=True)
            else: st.caption("No hay datos suficientes para el gráfico comparativo de tasa de sesión global manual con los filtros actuales.")
        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    st.markdown("### Rendimiento por Prospectador (para la Selección Filtrada Actual)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        # Group by prospector on the df_final_analisis_campana (Nivel 2 data)
        # The kpis calculated here will be based on the portion of Nivel 2 data handled by each prospector
        df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?").apply(lambda x: pd.Series(calcular_kpis_df_campana(x))).reset_index()
        
        # Displaying a simplified table for prospector performance
        df_prospectador_display = df_prospectador_camp[
            (df_prospectador_camp['registros_en_seleccion_filtrada'] > 0) # Use the new base count
        ][["¿Quién Prospecto?", "registros_en_seleccion_filtrada", "invites_enviadas_manual", "sesiones_agendadas_manual", "tasa_sesion_global_manual", "emails_contactados", "sesiones_agendadas_email", "tasa_sesion_global_email"]]
        
        df_prospectador_display = df_prospectador_display.rename(columns={
            "registros_en_seleccion_filtrada": "Prospectos (Sel.Filt.)",
            "invites_enviadas_manual": "Invites Env. (M)",
            "sesiones_agendadas_manual": "Sesiones (M)",
            "tasa_sesion_global_manual": "Tasa Sesión Global (M) (%)",
            "emails_contactados": "Emails Cont. (E)",
            "sesiones_agendadas_email": "Sesiones (E)",
            "tasa_sesion_global_email": "Tasa Sesión Global (E) (%)"
        }).sort_values(by="Sesiones (M)", ascending=False)

        format_dict_prosp = {
            "Tasa Sesión Global (M) (%)": "{:.1f}%", "Tasa Sesión Global (E) (%)": "{:.1f}%",
            "Prospectos (Sel.Filt.)": "{:,}", "Invites Env. (M)": "{:,}", "Sesiones (M)": "{:,}",
            "Emails Cont. (E)": "{:,}", "Sesiones (E)": "{:,}"
        }
        if not df_prospectador_display.empty:
            st.dataframe(df_prospectador_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            # Add charts for prospector performance if desired, similar to campaign comparison
        else: st.caption("No hay datos de rendimiento por prospectador para la selección filtrada actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible.")


    st.markdown("### Detalle de Prospectos (de la Selección Filtrada Actual)")
    # Get original details for records that are in df_final_analisis_campana
    # We use df_original_completo and filter it by the index of df_final_analisis_campana
    # This assumes that indices are preserved or that there's a unique ID to join on.
    # If df_final_analisis_campana is a copy of a slice from df_base_campanas_global, which itself
    # is a slice of df_original_completo, then indices should align if not reset.
    
    # Ensure indices are aligned. If 'ID_Prospecto' or similar unique key exists, use it.
    # For this example, assuming direct index alignment from original load.
    # If df_final_analisis_campana underwent operations that reset or changed its index,
    # you'd need a reliable key (e.g., 'ID_Prospecto') to merge back to df_original_completo.

    # If df_original_completo is the true source and df_base_campanas_global was created from it,
    # and df_final_analisis_campana from df_base_campanas_global, their indices *should* correspond
    # to rows in df_original_completo IF no index-altering operations occurred without preserving a key.
    
    # A safer way if indices are not guaranteed:
    # Assuming df_final_analisis_campana has all necessary columns from df_original_completo because it's a filtered version.
    # If not, you'd merge df_final_analisis_campana (with just IDs) back to df_original_completo.
    # For simplicity here, we'll assume df_final_analisis_campana contains sufficient detail or its indices map to df_original_completo.
    # Let's display df_final_analisis_campana directly for detail view, or fetch specific columns from df_original_completo.

    # Correct approach: Use indices from df_final_analisis_campana to select rows from df_original_completo
    if not df_final_analisis_campana.empty and not df_original_completo.empty:
        # Ensure df_original_completo has an index that can be used by .loc
        # If df_final_analisis_campana.index are positions, they might not match df_original_completo's index if it's not a simple 0-based RangeIndex
        # Simplest case: if df_final_analisis_campana is a direct filter of df_original_completo (via df_base_campanas_global)
        # then their indices are from the same "universe".
        
        # Make sure df_original_completo is indexed if it's not already, e.g. by a unique ID column if one exists.
        # If no specific unique ID was set as index, it would have a default RangeIndex.
        # Let's assume 'ID_Prospecto' is a unique key present in both df_original_completo and df_final_analisis_campana
        if 'ID_Prospecto' in df_final_analisis_campana.columns and 'ID_Prospecto' in df_original_completo.columns:
            ids_in_final_selection = df_final_analisis_campana['ID_Prospecto'].unique()
            df_detalle_display = df_original_completo[df_original_completo['ID_Prospecto'].isin(ids_in_final_selection)].copy()
        else: # Fallback to index if no unique ID - this can be risky if indices were reset
            st.warning("Consider adding a unique 'ID_Prospecto' column for robust detail display.")
            df_detalle_display = df_original_completo.loc[df_final_analisis_campana.index].copy()


        if not df_detalle_display.empty:
            # Formatting for display (similar to your original code)
            df_display_formatted_detail = pd.DataFrame()
            for col_orig in df_detalle_display.columns:
                if pd.api.types.is_datetime64_any_dtype(df_detalle_display[col_orig]):
                    df_display_formatted_detail[col_orig] = pd.to_datetime(df_detalle_display[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
                elif pd.api.types.is_numeric_dtype(df_detalle_display[col_orig]) and \
                     (df_detalle_display[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or \
                      pd.api.types.is_integer_dtype(df_detalle_display[col_orig].dropna())):
                    df_display_formatted_detail[col_orig] = df_detalle_display[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A") # Be careful with replacing '0' if 0 is a valid distinct value
                else:
                    df_display_formatted_detail[col_orig] = df_detalle_display[col_orig].astype(str).fillna("N/A")
            
            st.dataframe(df_display_formatted_detail, height=400, use_container_width=True)

            @st.cache_data # Caching the conversion function
            def convertir_df_a_excel_campana_detalle(df_conv):
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
                return output.getvalue()
            
            excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_display) # Download the unformatted (original types) version
            nombre_archivo_excel_detalle = f"detalle_seleccion_filtrada_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
            st.download_button(
                label="⬇️ Descargar Detalle de Selección Filtrada (Excel)", 
                data=excel_data_campana_detalle, 
                file_name=nombre_archivo_excel_detalle, 
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_excel_campana_detalle_filtrado"
            )
        else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales (df_final_analisis_campana o df_original_completo is empty).")


st.markdown("---")
st.info("Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊")ef convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO();
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer: df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()
        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_original_filtrado)
        nombres_campana_str = "_".join(st.session_state.campana_seleccion_principal).replace(" ", "")[:50]
        nombre_archivo_excel_detalle = f"detalle_sel_filtrada_{nombres_campana_str}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle de Selección Filtrada (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info("Plataforma analítica potenciada por IA y el ingenio de Johnsito. ✨")
