# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io

# Asumiendo que estas funciones están correctamente definidas en tus módulos
# y que cargar_y_limpiar_datos() devuelve TODOS los registros de las campañas.
from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("""
Analiza el rendimiento detallado de tus campañas. Comienza seleccionando una o varias campañas para ver su **Universo Total Original de Registros**.
Luego, aplica filtros adicionales para definir una **'Selección Filtrada'**. Sobre esta selección se calcularán los KPIs y embudos de conversión
para los flujos de prospección manual y por email.
""")

# --- Funciones de Ayuda ---
@st.cache_data
def obtener_datos_base_campanas():
    df_completo = cargar_y_limpiar_datos()
    if df_completo is None or df_completo.empty:
        st.error("No se pudieron cargar los datos. Verifica la fuente de datos (cargar_y_limpiar_datos).")
        return pd.DataFrame(), pd.DataFrame()

    if 'Campaña' not in df_completo.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo

    # df_base_campanas DEBE contener TODOS los registros de campañas con nombre, sin otros filtros.
    df_base_campanas = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy()

    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion", "Fecha de Sesion Email"]
    # Aplicar conversión de fechas a df_base_campanas y df_original_completo (que es una copia de df_completo)
    for df_proc in [df_base_campanas, df_completo]: # df_original_completo se usa para el detalle descargable
        for col in date_cols_to_check:
            if col in df_proc.columns and not pd.api.types.is_datetime64_any_dtype(df_proc[col]):
                df_proc[col] = pd.to_datetime(df_proc[col], errors='coerce')
        
        if "Avatar" in df_proc.columns: # Estandarizar Avatar en ambos
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar)

    return df_base_campanas, df_completo


def inicializar_estado_filtros_campana():
    default_filters = {
        "campana_seleccion_principal": [],
        "campana_filtro_prospectador": ["– Todos –"],
        "campana_filtro_pais": ["– Todos –"],
        "campana_filtro_fecha_ini": None,
        "campana_filtro_fecha_fin": None,
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
    st.toast("Todos los filtros de la página de campañas han sido reiniciados.", icon="🧹")


def calcular_kpis_df_campana(df_seleccion_filtrada, total_original_correspondiente_a_seleccion=None):
    # df_seleccion_filtrada es el "Universo de Selección Filtrada" para una campaña o un agregado.
    # total_original_correspondiente_a_seleccion es el universo total original del cual proviene df_seleccion_filtrada.
    empty_kpis = {
        "total_original_correspondiente": total_original_correspondiente_a_seleccion if total_original_correspondiente_a_seleccion is not None else 0,
        "total_registros_seleccion_filtrada": 0,
        "porc_original_en_seleccion_filtrada": 0,
        "manual_prospectados_o_invitados": 0, "manual_invites_aceptadas": 0,
        "manual_primeros_mensajes_enviados": 0, "manual_respuestas_primer_mensaje": 0,
        "manual_sesiones_agendadas": 0,
        "manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada": 0,
        "manual_tasa_aceptacion_vs_invitados": 0, "manual_tasa_respuesta_vs_aceptadas": 0,
        "manual_tasa_sesion_vs_respuesta": 0, "manual_tasa_sesion_global_vs_invitados": 0,
        "email_contactados": 0, "email_respuestas": 0, "email_sesiones_agendadas": 0,
        "email_tasa_contacto_iniciado_vs_seleccion_filtrada": 0,
        "email_tasa_respuesta_vs_contactados": 0, "email_tasa_sesion_vs_respuesta": 0,
        "email_tasa_sesion_global_vs_contactados": 0,
        "total_sesiones_agendadas": 0
    }
    if df_seleccion_filtrada.empty:
        # Incluso si la selección filtrada es vacía, queremos retornar el total original si se proveyó
        return empty_kpis

    total_registros_seleccion_filtrada = len(df_seleccion_filtrada)
    porc_original_en_seleccion_filtrada = 0
    if total_original_correspondiente_a_seleccion is not None and total_original_correspondiente_a_seleccion > 0:
        porc_original_en_seleccion_filtrada = (total_registros_seleccion_filtrada / total_original_correspondiente_a_seleccion * 100)

    # --- KPIs de Prospección Manual ---
    manual_prospectados_o_invitados = df_seleccion_filtrada["Fecha de Invite"].notna().sum() if "Fecha de Invite" in df_seleccion_filtrada else 0
    manual_invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_seleccion_filtrada.get("¿Invite Aceptada?", pd.Series(dtype=str)))
    manual_primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_seleccion_filtrada.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    manual_respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan", "none"]
        for x in df_seleccion_filtrada.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    manual_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_seleccion_filtrada.get("Sesion Agendada?", pd.Series(dtype=str)))

    manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada = (manual_prospectados_o_invitados / total_registros_seleccion_filtrada * 100) if total_registros_seleccion_filtrada > 0 else 0
    manual_tasa_aceptacion_vs_invitados = (manual_invites_aceptadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    manual_tasa_respuesta_vs_aceptadas = (manual_respuestas_primer_mensaje / manual_invites_aceptadas * 100) if manual_invites_aceptadas > 0 else 0
    manual_tasa_sesion_vs_respuesta = (manual_sesiones_agendadas / manual_respuestas_primer_mensaje * 100) if manual_respuestas_primer_mensaje > 0 else 0
    manual_tasa_sesion_global_vs_invitados = (manual_sesiones_agendadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    
    # --- KPIs de Prospección por Email ---
    email_contactados = sum(limpiar_valor_kpi(x) == "si" for x in df_seleccion_filtrada.get("Contactados por Campaña", pd.Series(dtype=str)))
    email_respuestas = sum(limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] for x in df_seleccion_filtrada.get("Respuesta Email", pd.Series(dtype=str)))
    email_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_seleccion_filtrada.get("Sesion Agendada Email", pd.Series(dtype=str)))

    email_tasa_contacto_iniciado_vs_seleccion_filtrada = (email_contactados / total_registros_seleccion_filtrada * 100) if total_registros_seleccion_filtrada > 0 else 0
    email_tasa_respuesta_vs_contactados = (email_respuestas / email_contactados * 100) if email_contactados > 0 else 0
    email_tasa_sesion_vs_respuesta = (email_sesiones_agendadas / email_respuestas * 100) if email_respuestas > 0 else 0
    email_tasa_sesion_global_vs_contactados = (email_sesiones_agendadas / email_contactados * 100) if email_contactados > 0 else 0

    total_sesiones_agendadas = manual_sesiones_agendadas + email_sesiones_agendadas

    return {
        "total_original_correspondiente": total_original_correspondiente_a_seleccion if total_original_correspondiente_a_seleccion is not None else 0,
        "total_registros_seleccion_filtrada": int(total_registros_seleccion_filtrada),
        "porc_original_en_seleccion_filtrada": porc_original_en_seleccion_filtrada,
        "manual_prospectados_o_invitados": int(manual_prospectados_o_invitados),
        "manual_invites_aceptadas": int(manual_invites_aceptadas),
        "manual_primeros_mensajes_enviados": int(manual_primeros_mensajes_enviados),
        "manual_respuestas_primer_mensaje": int(manual_respuestas_primer_mensaje),
        "manual_sesiones_agendadas": int(manual_sesiones_agendadas),
        "manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada": manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada,
        "manual_tasa_aceptacion_vs_invitados": manual_tasa_aceptacion_vs_invitados,
        "manual_tasa_respuesta_vs_aceptadas": manual_tasa_respuesta_vs_aceptadas,
        "manual_tasa_sesion_vs_respuesta": manual_tasa_sesion_vs_respuesta,
        "manual_tasa_sesion_global_vs_invitados": manual_tasa_sesion_global_vs_invitados,
        "email_contactados": int(email_contactados),
        "email_respuestas": int(email_respuestas),
        "email_sesiones_agendadas": int(email_sesiones_agendadas),
        "email_tasa_contacto_iniciado_vs_seleccion_filtrada": email_tasa_contacto_iniciado_vs_seleccion_filtrada,
        "email_tasa_respuesta_vs_contactados": email_tasa_respuesta_vs_contactados,
        "email_tasa_sesion_vs_respuesta": email_tasa_sesion_vs_respuesta,
        "email_tasa_sesion_global_vs_contactados": email_tasa_sesion_global_vs_contactados,
        "total_sesiones_agendadas": int(total_sesiones_agendadas)
    }

def mostrar_embudo_para_campana(kpis_campana, tipo_embudo="manual", titulo_embudo_base="Embudo de Conversión"):
    etapas_embudo, cantidades_embudo = [], []
    sub_caption = ""
    # La base para los embudos es siempre la "Selección Filtrada"
    base_del_embudo = kpis_campana["total_registros_seleccion_filtrada"]

    if tipo_embudo == "manual":
        etapas_embudo = ["Registros en Selección (Filtrada)", "Invites Enviadas", "Invites Aceptadas", "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas (Manual)"]
        cantidades_embudo = [
            base_del_embudo, kpis_campana["manual_prospectados_o_invitados"],
            kpis_campana["manual_invites_aceptadas"], kpis_campana["manual_primeros_mensajes_enviados"],
            kpis_campana["manual_respuestas_primer_mensaje"], kpis_campana["manual_sesiones_agendadas"]
        ]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Manual"
        sub_caption = f"Embudo manual basado en {base_del_embudo:,} registros en la selección filtrada."
        if kpis_campana["manual_prospectados_o_invitados"] == 0 and kpis_campana["manual_sesiones_agendadas"] == 0 : # Si no hay ni prospectados ni sesiones, no mostrar
             st.info(f"No hay actividad de prospección manual iniciada para la selección actual.")
             return

    elif tipo_embudo == "email":
        etapas_embudo = ["Registros en Selección (Filtrada)", "Contactados por Email", "Respuestas Email", "Sesiones Agendadas (Email)"]
        cantidades_embudo = [
            base_del_embudo, kpis_campana["email_contactados"],
            kpis_campana["email_respuestas"], kpis_campana["email_sesiones_agendadas"]
        ]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Email"
        sub_caption = f"Embudo de email basado en {base_del_embudo:,} registros en la selección filtrada."
        if kpis_campana["email_contactados"] == 0 and kpis_campana["email_sesiones_agendadas"] == 0:
            st.info(f"No hay actividad de contacto por email iniciada para la selección actual.")
            return
    else:
        st.error("Tipo de embudo no reconocido.")
        return

    if sum(cantidades_embudo) == 0 : # Chequeo adicional
        st.info(f"No hay datos suficientes para generar el embudo de '{tipo_embudo}' para la selección actual.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    
    porcentajes_vs_anterior = [100.0] if not df_embudo.empty else []
    for i in range(1, len(df_embudo)):
        porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
        porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    
    porcentajes_vs_inicio_embudo = []
    if not df_embudo.empty and df_embudo['Cantidad'][0] > 0: # df_embudo['Cantidad'][0] es base_del_embudo
        porcentajes_vs_inicio_embudo = [(c / df_embudo['Cantidad'][0] * 100) for c in df_embudo['Cantidad']]
    elif not df_embudo.empty: # Si la cantidad inicial es 0 pero hay etapas
        porcentajes_vs_inicio_embudo = [0.0] * len(df_embudo)
        if len(porcentajes_vs_inicio_embudo) > 0: porcentajes_vs_inicio_embudo[0] = 100.0 # La primera etapa es 100% de sí misma
    df_embudo['% vs Inicio Embudo'] = porcentajes_vs_inicio_embudo


    df_embudo['Texto'] = df_embudo.apply(
        lambda row: f"{row['Cantidad']:,}<br>({row['% vs Anterior']:.1f}% vs Ant.)<br>({row['% vs Inicio Embudo']:.1f}% vs Inicio Sel.)", axis=1
    )
    if not df_embudo.empty:
         df_embudo.loc[0, 'Texto'] = f"{df_embudo.loc[0, 'Cantidad']:,}<br>(100% de Selección Filtrada)"


    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text',
                             connector={"line": {"color": "royalblue", "dash": "dot", "width": 2}})
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(sub_caption)


def generar_tabla_comparativa_campanas_filtrada(df_base_global_para_originales, df_total_seleccion_filtrada_general, lista_nombres_campanas_seleccionadas):
    datos_comparativa = []
    if df_total_seleccion_filtrada_general.empty or not lista_nombres_campanas_seleccionadas:
        return pd.DataFrame(datos_comparativa)

    for nombre_campana in lista_nombres_campanas_seleccionadas:
        # Universo original de esta campaña específica
        total_original_esta_campana = df_base_global_para_originales[df_base_global_para_originales['Campaña'] == nombre_campana].shape[0]
        
        # Parte de la selección filtrada general que pertenece a esta campaña
        df_campana_individual_filtrada = df_total_seleccion_filtrada_general[df_total_seleccion_filtrada_general['Campaña'] == nombre_campana]
        
        # Calcular KPIs para esta parte, pasando el total original correspondiente a ELLA
        kpis = calcular_kpis_df_campana(df_campana_individual_filtrada, total_original_esta_campana)
        
        datos_comparativa.append({
            "Campaña": nombre_campana,
            "Total Original Camp.": total_original_esta_campana,
            "Registros Sel. Filtrada": kpis["total_registros_seleccion_filtrada"], # De esta campaña individual
            "% Orig. en Sel. Filt.": kpis["porc_original_en_seleccion_filtrada"], # % de esta campaña que pasó filtros
            # Manual
            "Inv. Enviadas": kpis["manual_prospectados_o_invitados"], "Tasa Prosp. Man. Inic. (%)": kpis["manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada"],
            "Inv. Aceptadas": kpis["manual_invites_aceptadas"], "Resp. 1er Msj": kpis["manual_respuestas_primer_mensaje"],
            "Sesiones Manual": kpis["manual_sesiones_agendadas"], "Tasa Acept. (vs Inv. Env.) (%)": kpis["manual_tasa_aceptacion_vs_invitados"],
            "Tasa Resp. (vs Acept.) (%)": kpis["manual_tasa_respuesta_vs_aceptadas"], "Tasa Sesión Man. (vs Resp.) (%)": kpis["manual_tasa_sesion_vs_respuesta"],
            "Tasa Sesión Man. Global (vs Inv. Env.) (%)": kpis["manual_tasa_sesion_global_vs_invitados"],
            # Email
            "Email Contact.": kpis["email_contactados"], "Tasa Cont. Email Inic. (%)": kpis["email_tasa_contacto_iniciado_vs_seleccion_filtrada"],
            "Email Resp.": kpis["email_respuestas"], "Sesiones Email": kpis["email_sesiones_agendadas"],
            "Tasa Resp. Email (vs Cont.) (%)": kpis["email_tasa_respuesta_vs_contactados"], "Tasa Sesión Email (vs Resp.) (%)": kpis["email_tasa_sesion_vs_respuesta"],
            "Tasa Sesión Email Global (vs Cont.) (%)": kpis["email_tasa_sesion_global_vs_contactados"],
            # Combinado
            "Total Sesiones": kpis["total_sesiones_agendadas"]
        })
    return pd.DataFrame(datos_comparativa)


# --- Carga de Datos Base ---
# df_base_campanas_global DEBE contener todos los registros originales por campaña.
# df_original_completo es una copia de lo que devuelve cargar_y_limpiar_datos(), usado para la descarga de detalle.
df_base_campanas_global, df_original_completo_para_detalle = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No hay datos base de campañas para analizar. Verifica `cargar_y_limpiar_datos()` y la fuente de datos.")
    st.stop()

# --- Sección 1: Selección de Campaña(s) y Universo Total Original ---
st.markdown("---")
st.subheader("1. Selección de Campaña(s) y Universo Total Original")
lista_campanas_disponibles_global = sorted(df_base_campanas_global['Campaña'].astype(str).unique()) #astype(str) para evitar errores con tipos mixtos
if not lista_campanas_disponibles_global:
    st.warning("No se encontraron nombres de campañas en los datos cargados.")
    st.stop()

st.session_state.campana_seleccion_principal = st.multiselect(
    "Elige la(s) campaña(s) a analizar:",
    options=lista_campanas_disponibles_global,
    default=st.session_state.campana_seleccion_principal,
    key="ms_campana_seleccion_principal"
)

universo_total_original_combinado_para_seleccion = 0 # Este será el Nivel 1 Agregado
df_campanas_seleccionadas_originales = pd.DataFrame() # Este será el Nivel 1 como DataFrame

if st.session_state.campana_seleccion_principal:
    st.markdown("#### Universo Total de Registros Originales para Campaña(s) Seleccionada(s)")
    st.caption("Este es el conteo total de registros asignados a cada campaña seleccionada en la base de datos, *antes* de aplicar cualquier filtro de página.")
    
    df_campanas_seleccionadas_originales = df_base_campanas_global[
        df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
    ].copy()
    universo_total_original_combinado_para_seleccion = len(df_campanas_seleccionadas_originales)

    if len(st.session_state.campana_seleccion_principal) > 1:
        # Mostrar desglose si hay múltiples campañas
        cols_totales_orig = st.columns(len(st.session_state.campana_seleccion_principal))
        temp_sum_check = 0
        for i, camp_name in enumerate(st.session_state.campana_seleccion_principal):
            # Calcular el total original directamente de df_base_campanas_global para cada campaña
            total_records_camp = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name].shape[0]
            temp_sum_check += total_records_camp # Esto debería ser igual a universo_total_original_combinado_para_seleccion si no hay duplicados o problemas
            with cols_totales_orig[i]:
                st.metric(label=f"'{camp_name}' (Total Original)", value=f"{total_records_camp:,}")
        # El gran total ya se calcula con len(df_campanas_seleccionadas_originales)
        st.metric(label="GRAN TOTAL ORIGINAL (Suma de Campañas Seleccionadas)", value=f"{universo_total_original_combinado_para_seleccion:,}")

    elif len(st.session_state.campana_seleccion_principal) == 1:
        # Si solo una campaña, el gran total es el total de esa campaña
        st.metric(label=f"GRAN TOTAL ORIGINAL ('{st.session_state.campana_seleccion_principal[0]}')", value=f"{universo_total_original_combinado_para_seleccion:,}")
    st.markdown("---")


# --- Sección 2: Filtros Adicionales para definir la 'Selección Filtrada' ---
st.subheader("2. Filtros Adicionales para Definir la 'Selección Filtrada'")
st.caption("Estos filtros (Prospectador, País, Fecha de Invite) se aplican sobre el 'Universo Total Original' de las campañas seleccionadas arriba.")

if st.button("Limpiar Filtros de Página", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
    st.rerun()

if not st.session_state.campana_seleccion_principal:
    st.info("Por favor, selecciona al menos una campaña (Sección 1) para visualizar los datos y aplicar filtros.")
    st.stop()

# df_final_analisis_campana será la "Selección Filtrada"
df_final_analisis_campana = df_campanas_seleccionadas_originales.copy() # Partimos del Nivel 1 (DataFrame)

with st.expander("Aplicar filtros detallados", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        # Filtro Prospectador (opera sobre los prospectadores presentes en df_campanas_seleccionadas_originales)
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_seleccionadas_originales["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        # Lógica para mantener selección si es válida, o resetear
        current_prospectador_selection = st.session_state.campana_filtro_prospectador
        if not all(p in opciones_prospectador_camp for p in current_prospectador_selection):
            current_prospectador_selection = ["– Todos –"]
        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó? (Filtro para prospección manual)", options=opciones_prospectador_camp,
            default=current_prospectador_selection, key="ms_campana_prospectador"
        )
        
        # Filtro País
        opciones_pais_camp = ["– Todos –"] + sorted(
            df_campanas_seleccionadas_originales["Pais"].dropna().astype(str).unique()
        )
        current_pais_selection = st.session_state.campana_filtro_pais
        if not all(p in opciones_pais_camp for p in current_pais_selection):
            current_pais_selection = ["– Todos –"]
        st.session_state.campana_filtro_pais = st.multiselect(
            "País del Prospecto", options=opciones_pais_camp,
            default=current_pais_selection, key="ms_campana_pais"
        )

    with col_f2:
        # Filtro Fechas (basado en Fecha de Invite)
        min_fecha, max_fecha = (None, None)
        if "Fecha de Invite" in df_campanas_seleccionadas_originales.columns and \
           not df_campanas_seleccionadas_originales["Fecha de Invite"].dropna().empty:
            min_fecha = df_campanas_seleccionadas_originales["Fecha de Invite"].dropna().min().date()
            max_fecha = df_campanas_seleccionadas_originales["Fecha de Invite"].dropna().max().date()
        
        st.session_state.campana_filtro_fecha_ini = st.date_input(
            "Filtrar por Fecha de Invite Desde:", 
            value=st.session_state.campana_filtro_fecha_ini,
            min_value=min_fecha, max_value=max_fecha, 
            format="DD/MM/YYYY", key="di_campana_fecha_ini",
            help="Este filtro de fecha se aplica a la columna 'Fecha de Invite'."
        )
        st.session_state.campana_filtro_fecha_fin = st.date_input(
            "Filtrar por Fecha de Invite Hasta:", 
            value=st.session_state.campana_filtro_fecha_fin,
            min_value=min_fecha, max_value=max_fecha, 
            format="DD/MM/YYYY", key="di_campana_fecha_fin",
            help="Este filtro de fecha se aplica a la columna 'Fecha de Invite'."
        )

# Aplicar filtros de página para obtener la "Selección Filtrada"
if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
    df_final_analisis_campana = df_final_analisis_campana[
        df_final_analisis_campana["¿Quién Prospecto?"].isin(st.session_state.campana_filtro_prospectador)
    ]
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_final_analisis_campana = df_final_analisis_campana[
        df_final_analisis_campana["Pais"].isin(st.session_state.campana_filtro_pais)
    ]

if "Fecha de Invite" in df_final_analisis_campana.columns and pd.api.types.is_datetime64_any_dtype(df_final_analisis_campana["Fecha de Invite"]):
    if st.session_state.campana_filtro_fecha_ini:
        df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Fecha de Invite"] >= pd.to_datetime(st.session_state.campana_filtro_fecha_ini)]
    if st.session_state.campana_filtro_fecha_fin:
        df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Fecha de Invite"] <= pd.to_datetime(st.session_state.campana_filtro_fecha_fin).replace(hour=23, minute=59, second=59)]


# --- Sección 3: Resultados Agregados (basados en 'Selección Filtrada') ---
st.markdown("---")
st.header(f"📊 Resultados Agregados para '{', '.join(st.session_state.campana_seleccion_principal)}' (sobre Selección Filtrada)")

if df_campanas_seleccionadas_originales.empty : # Chequeo si no se seleccionó campaña
     st.info("Selecciona al menos una campaña en la Sección 1 para continuar.")
     st.stop()
elif df_final_analisis_campana.empty and not df_campanas_seleccionadas_originales.empty : # Si había original pero filtros la vaciaron
    st.warning(f"La 'Selección Filtrada' está vacía (0 registros de {universo_total_original_combinado_para_seleccion:,} originales seleccionados). "
               "Esto significa que ningún registro del universo original de las campañas seleccionadas cumple con todos los criterios de filtro de página (Prospectador, País, Fechas de Invite). "
               "Intenta ajustar los filtros en la Sección 2.")
else: # Hay datos en la selección filtrada
    # Calcular KPIs agregados sobre la selección filtrada final.
    # El segundo argumento es el total original del cual esta selección filtrada es un subconjunto.
    kpis_agregados = calcular_kpis_df_campana(df_final_analisis_campana, universo_total_original_combinado_para_seleccion)

    st.metric(label="Universo de Selección Filtrada (Registros)", value=f"{kpis_agregados['total_registros_seleccion_filtrada']:,}",
              help=f"Registros que cumplen filtros de página. Representan el {kpis_agregados['porc_original_en_seleccion_filtrada']:.1f}% del Gran Total Original de {kpis_agregados['total_original_correspondiente']:,} registros de las campañas seleccionadas.")
    st.metric(label="Total Sesiones Agendadas (Manual + Email)", value=f"{kpis_agregados['total_sesiones_agendadas']:,}")
    
    st.markdown("---")
    st.markdown("### KPIs de Prospección Manual (sobre Selección Filtrada)")
    if kpis_agregados['manual_prospectados_o_invitados'] > 0 or kpis_agregados['manual_sesiones_agendadas'] > 0 :
        m_cols1 = st.columns(3)
        m_cols1[0].metric("Invites Enviadas (Prosp. Manual Inic.)", f"{kpis_agregados['manual_prospectados_o_invitados']:,}", f"{kpis_agregados['manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada']:.1f}% de Sel. Filtrada")
        m_cols1[1].metric("Invites Aceptadas", f"{kpis_agregados['manual_invites_aceptadas']:,}", f"{kpis_agregados['manual_tasa_aceptacion_vs_invitados']:.1f}% de Inv. Env.")
        m_cols1[2].metric("Sesiones (Manual)", f"{kpis_agregados['manual_sesiones_agendadas']:,}", f"{kpis_agregados['manual_tasa_sesion_global_vs_invitados']:.1f}% de Inv. Env.")
        m_cols2 = st.columns(2) # Para Msj Enviados y Respuestas
        m_cols2[0].metric("1ros Msj. Enviados", f"{kpis_agregados['manual_primeros_mensajes_enviados']:,}") # Tasa vs Aceptadas podría ser útil aquí
        m_cols2[1].metric("Respuestas 1er Msj.", f"{kpis_agregados['manual_respuestas_primer_mensaje']:,}", f"{kpis_agregados['manual_tasa_respuesta_vs_aceptadas']:.1f}% de Acept.")
        if kpis_agregados['manual_sesiones_agendadas'] > 0 and kpis_agregados['manual_respuestas_primer_mensaje'] > 0: st.caption(f"Tasa de Sesiones Manual vs Respuestas: {kpis_agregados['manual_tasa_sesion_vs_respuesta']:.1f}%")
    else: st.info("No hay datos de prospección manual significativos para la selección filtrada actual.")

    st.markdown("---")
    st.markdown("### KPIs de Prospección por Email (sobre Selección Filtrada)")
    if kpis_agregados['email_contactados'] > 0 or kpis_agregados['email_sesiones_agendadas'] > 0:
        e_cols1 = st.columns(3)
        e_cols1[0].metric("Emails Contactados (Prosp. Email Inic.)", f"{kpis_agregados['email_contactados']:,}", f"{kpis_agregados['email_tasa_contacto_iniciado_vs_seleccion_filtrada']:.1f}% de Sel. Filtrada")
        e_cols1[1].metric("Respuestas Email", f"{kpis_agregados['email_respuestas']:,}", f"{kpis_agregados['email_tasa_respuesta_vs_contactados']:.1f}% de Contact.")
        e_cols1[2].metric("Sesiones (Email)", f"{kpis_agregados['email_sesiones_agendadas']:,}", f"{kpis_agregados['email_tasa_sesion_global_vs_contactados']:.1f}% de Contact.")
        if kpis_agregados['email_sesiones_agendadas'] > 0 and kpis_agregados['email_respuestas'] > 0: st.caption(f"Tasa de Sesiones Email vs Respuestas: {kpis_agregados['email_tasa_sesion_vs_respuesta']:.1f}%")
    else: st.info("No hay datos de prospección por email significativos para la selección filtrada actual.")
    
    st.markdown("---")
    st.subheader("Embudos de Conversión (desde Selección Filtrada)")
    col_embudo1, col_embudo2 = st.columns(2)
    with col_embudo1: mostrar_embudo_para_campana(kpis_agregados, tipo_embudo="manual", titulo_embudo_base="Embudo Manual")
    with col_embudo2: mostrar_embudo_para_campana(kpis_agregados, tipo_embudo="email", titulo_embudo_base="Embudo Email")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas")
        # df_base_campanas_global tiene TODOS los registros originales
        # df_final_analisis_campana es la SELECCIÓN FILTRADA GENERAL (de todas las campañas seleccionadas, ya filtrada por página)
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_base_campanas_global, df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs")
            cols_enteros_comp = ["Total Original Camp.", "Registros Sel. Filtrada", "Inv. Enviadas", "Inv. Aceptadas", "Resp. 1er Msj", "Sesiones Manual", "Email Contact.", "Email Resp.", "Sesiones Email", "Total Sesiones"]
            format_dict_comp = {
                "% Orig. en Sel. Filt.": "{:.1f}%", 
                "Tasa Prosp. Man. Inic. (%)": "{:.1f}%", "Tasa Acept. (vs Inv. Env.) (%)": "{:.1f}%", 
                "Tasa Resp. (vs Acept.) (%)": "{:.1f}%", "Tasa Sesión Man. (vs Resp.) (%)": "{:.1f}%", 
                "Tasa Sesión Man. Global (vs Inv. Env.) (%)": "{:.1f}%",
                "Tasa Cont. Email Inic. (%)": "{:.1f}%", "Tasa Resp. Email (vs Cont.) (%)": "{:.1f}%", 
                "Tasa Sesión Email (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Email Global (vs Cont.) (%)": "{:.1f}%"
            }
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            st.dataframe(df_tabla_comp.sort_values(by="Total Sesiones", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            # (Aquí puedes añadir gráficos comparativos basados en df_tabla_comp si lo deseas)
        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    # --- Rendimiento por Prospectador ---
    st.markdown("### Rendimiento por Prospectador (Flujo Manual sobre su parte de la Selección Filtrada)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        df_prospectador_camp_list = []
        # Agrupar por prospectador sobre la selección filtrada GENERAL
        for prospectador, df_grupo_prospectador in df_final_analisis_campana.groupby("¿Quién Prospecto?"):
            # Para el rendimiento por prospectador, el "total original" sería el total de la parte de la 
            # selección filtrada que le corresponde a ESE prospectador.
            # No es el total original de la campaña, sino su "universo de trabajo" dentro de la sel. filtrada.
            kpis_prospectador = calcular_kpis_df_campana(df_grupo_prospectador, len(df_grupo_prospectador)) 
            if kpis_prospectador["manual_prospectados_o_invitados"] > 0:
                df_prospectador_camp_list.append({
                    "¿Quién Prospecto?": prospectador,
                    "Su Universo en Sel. Filtrada": kpis_prospectador["total_registros_seleccion_filtrada"], # len(df_grupo_prospectador)
                    "Invites Enviadas": kpis_prospectador["manual_prospectados_o_invitados"],
                    "% Prosp. Inic. (vs su Universo)": kpis_prospectador["manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada"],
                    "Sesiones (Manual)": kpis_prospectador["manual_sesiones_agendadas"],
                    "Tasa Sesión Global (Manual vs Inv. Env.) (%)": kpis_prospectador["manual_tasa_sesion_global_vs_invitados"]
                })
        if df_prospectador_camp_list:
            df_prospectador_camp_display = pd.DataFrame(df_prospectador_camp_list).sort_values(by="Sesiones (Manual)", ascending=False)
            cols_enteros_prosp = ["Su Universo en Sel. Filtrada", "Invites Enviadas", "Sesiones (Manual)"]
            format_dict_prosp = {"% Prosp. Inic. (vs su Universo)": "{:.1f}%", "Tasa Sesión Global (Manual vs Inv. Env.) (%)": "{:.1f}%"}
            for col_int_prosp in cols_enteros_prosp:
                if col_int_prosp in df_prospectador_camp_display.columns: 
                    df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int)
                    format_dict_prosp[col_int_prosp] = "{:,}"
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            # (Gráfico de rendimiento por prospectador - lógica se mantiene)
        else: st.caption("No hay datos de rendimiento por prospectador para la actividad manual en la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible para el análisis por prospectador.")

    # --- Detalle de Prospectos ---
    st.markdown("### Detalle de Prospectos (de la Selección Filtrada)")
    # df_final_analisis_campana es la selección filtrada.
    # Queremos mostrar el detalle original de estos prospectos filtrados, usando df_original_completo_para_detalle
    indices_filtrados = df_final_analisis_campana.index
    # Asegurarse que los índices existen en df_original_completo_para_detalle
    indices_validos_en_original = df_original_completo_para_detalle.index.intersection(indices_filtrados)
    df_detalle_a_mostrar = df_original_completo_para_detalle.loc[indices_validos_en_original].copy() 
    
    if not df_detalle_a_mostrar.empty:
        columnas_relevantes = ["Campaña", "Nombre", "Apellido", "¿Quién Prospecto?", "Pais", "Fecha de Invite", "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", "Sesion Agendada?", "Fecha Sesion", "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email", "Fecha de Sesion Email", "Avatar"]
        columnas_existentes_para_detalle = [col for col in columnas_relevantes if col in df_detalle_a_mostrar.columns]
        df_display_tabla_campana_detalle_prep = df_detalle_a_mostrar[columnas_existentes_para_detalle].copy()

        df_display_tabla_campana_detalle = pd.DataFrame()
        for col_orig in df_display_tabla_campana_detalle_prep.columns:
            if pd.api.types.is_datetime64_any_dtype(df_display_tabla_campana_detalle_prep[col_orig]): 
                df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_display_tabla_campana_detalle_prep[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            else: 
                df_display_tabla_campana_detalle[col_orig] = df_display_tabla_campana_detalle_prep[col_orig].astype(str).fillna("N/A").replace("nan", "N/A").replace("NaT", "N/A")
        
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        
        @st.cache_data # Cachear la conversión a Excel
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()

        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_a_mostrar) # Descargar el detalle que se está mostrando
        nombres_campana_str = "_".join(st.session_state.campana_seleccion_principal).replace(" ", "")[:50]
        nombre_archivo_excel_detalle = f"detalle_sel_filtrada_{nombres_campana_str}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle de Selección Filtrada (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Plataforma analítica potenciada por IA y el ingenio de Johnsito. ✨"
)
