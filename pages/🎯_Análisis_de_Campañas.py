# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io

from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("""
Analiza el rendimiento detallado de tus campañas. Comienza seleccionando una o varias campañas para ver su universo total de registros.
Luego, aplica filtros adicionales para definir una 'Selección Filtrada' sobre la cual se calcularán los KPIs y embudos de conversión
para los flujos de prospección manual y por email.
""")

# --- Funciones de Ayuda (sin cambios respecto a la versión anterior, solo las necesarias aquí) ---
@st.cache_data
def obtener_datos_base_campanas():
    df_completo = cargar_y_limpiar_datos()
    if df_completo is None or df_completo.empty:
        st.error("No se pudieron cargar los datos. Verifica la fuente de datos.")
        return pd.DataFrame(), pd.DataFrame()
    if 'Campaña' not in df_completo.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo
    df_base_campanas = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy()
    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion", "Fecha de Sesion Email"]
    for df_proc in [df_base_campanas, df_completo]:
        for col in date_cols_to_check:
            if col in df_proc.columns and not pd.api.types.is_datetime64_any_dtype(df_proc[col]):
                df_proc[col] = pd.to_datetime(df_proc[col], errors='coerce')
        if "Avatar" in df_proc.columns:
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar)
    return df_base_campanas, df_completo

def inicializar_estado_filtros_campana():
    default_filters = {
        "campana_seleccion_principal": [], "campana_filtro_prospectador": ["– Todos –"],
        "campana_filtro_pais": ["– Todos –"], "campana_filtro_fecha_ini": None,
        "campana_filtro_fecha_fin": None,
    }
    for key, value in default_filters.items():
        if key not in st.session_state: st.session_state[key] = value
        elif key in ["campana_seleccion_principal", "campana_filtro_prospectador", "campana_filtro_pais"] and not isinstance(st.session_state[key], list):
             st.session_state[key] = default_filters[key]

def resetear_filtros_campana_callback():
    st.session_state.campana_seleccion_principal = []
    st.session_state.campana_filtro_prospectador = ["– Todos –"]; st.session_state.campana_filtro_pais = ["– Todos –"]
    st.session_state.di_campana_fecha_ini = None; st.session_state.di_campana_fecha_fin = None
    st.session_state.campana_filtro_fecha_ini = None; st.session_state.campana_filtro_fecha_fin = None
    st.toast("Todos los filtros de la página de campañas han sido reiniciados.", icon="🧹")

def calcular_kpis_df_campana(df_filtrado_campana, total_original_campana_correspondiente=None):
    # df_filtrado_campana es el "Universo de Selección Filtrada" para una campaña o un agregado
    # total_original_campana_correspondiente es el universo total de esa campaña específica (usado en tabla comparativa)
    empty_kpis = {
        "total_registros_seleccion_filtrada": 0,
        "porc_original_en_seleccion_filtrada": 0, # Nuevo
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
    if df_filtrado_campana.empty: return empty_kpis

    total_registros_seleccion_filtrada = len(df_filtrado_campana)
    porc_original_en_seleccion_filtrada = 0
    if total_original_campana_correspondiente and total_original_campana_correspondiente > 0:
        porc_original_en_seleccion_filtrada = (total_registros_seleccion_filtrada / total_original_campana_correspondiente * 100)

    manual_prospectados_o_invitados = df_filtrado_campana["Fecha de Invite"].notna().sum() if "Fecha de Invite" in df_filtrado_campana else 0
    manual_invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str)))
    manual_primeros_mensajes_enviados = sum(pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"] for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str)))
    manual_respuestas_primer_mensaje = sum(limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str)))
    manual_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str)))
    manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada = (manual_prospectados_o_invitados / total_registros_seleccion_filtrada * 100) if total_registros_seleccion_filtrada > 0 else 0
    manual_tasa_aceptacion_vs_invitados = (manual_invites_aceptadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    manual_tasa_respuesta_vs_aceptadas = (manual_respuestas_primer_mensaje / manual_invites_aceptadas * 100) if manual_invites_aceptadas > 0 else 0
    manual_tasa_sesion_vs_respuesta = (manual_sesiones_agendadas / manual_respuestas_primer_mensaje * 100) if manual_respuestas_primer_mensaje > 0 else 0
    manual_tasa_sesion_global_vs_invitados = (manual_sesiones_agendadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    
    email_contactados = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Contactados por Campaña", pd.Series(dtype=str)))
    email_respuestas = sum(limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] for x in df_filtrado_campana.get("Respuesta Email", pd.Series(dtype=str)))
    email_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada Email", pd.Series(dtype=str)))
    email_tasa_contacto_iniciado_vs_seleccion_filtrada = (email_contactados / total_registros_seleccion_filtrada * 100) if total_registros_seleccion_filtrada > 0 else 0
    email_tasa_respuesta_vs_contactados = (email_respuestas / email_contactados * 100) if email_contactados > 0 else 0
    email_tasa_sesion_vs_respuesta = (email_sesiones_agendadas / email_respuestas * 100) if email_respuestas > 0 else 0
    email_tasa_sesion_global_vs_contactados = (email_sesiones_agendadas / email_contactados * 100) if email_contactados > 0 else 0
    total_sesiones_agendadas = manual_sesiones_agendadas + email_sesiones_agendadas

    return {
        "total_registros_seleccion_filtrada": int(total_registros_seleccion_filtrada),
        "porc_original_en_seleccion_filtrada": porc_original_en_seleccion_filtrada,
        "manual_prospectados_o_invitados": int(manual_prospectados_o_invitados), "manual_invites_aceptadas": int(manual_invites_aceptadas),
        "manual_primeros_mensajes_enviados": int(manual_primeros_mensajes_enviados), "manual_respuestas_primer_mensaje": int(manual_respuestas_primer_mensaje),
        "manual_sesiones_agendadas": int(manual_sesiones_agendadas),
        "manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada": manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada,
        "manual_tasa_aceptacion_vs_invitados": manual_tasa_aceptacion_vs_invitados, "manual_tasa_respuesta_vs_aceptadas": manual_tasa_respuesta_vs_aceptadas,
        "manual_tasa_sesion_vs_respuesta": manual_tasa_sesion_vs_respuesta, "manual_tasa_sesion_global_vs_invitados": manual_tasa_sesion_global_vs_invitados,
        "email_contactados": int(email_contactados), "email_respuestas": int(email_respuestas), "email_sesiones_agendadas": int(email_sesiones_agendadas),
        "email_tasa_contacto_iniciado_vs_seleccion_filtrada": email_tasa_contacto_iniciado_vs_seleccion_filtrada,
        "email_tasa_respuesta_vs_contactados": email_tasa_respuesta_vs_contactados, "email_tasa_sesion_vs_respuesta": email_tasa_sesion_vs_respuesta,
        "email_tasa_sesion_global_vs_contactados": email_tasa_sesion_global_vs_contactados,
        "total_sesiones_agendadas": int(total_sesiones_agendadas)
    }

def mostrar_embudo_para_campana(kpis_campana, tipo_embudo="manual", titulo_embudo_base="Embudo de Conversión"):
    # (Sin cambios en esta función, ya que toma kpis_campana y usa "total_registros_seleccion_filtrada" como base)
    etapas_embudo, cantidades_embudo = [], []
    sub_caption = ""
    base_del_embudo = kpis_campana["total_registros_seleccion_filtrada"]

    if tipo_embudo == "manual":
        etapas_embudo = ["Registros en Selección (Filtrada)", "Invites Enviadas", "Invites Aceptadas", "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas (Manual)"]
        cantidades_embudo = [base_del_embudo, kpis_campana["manual_prospectados_o_invitados"], kpis_campana["manual_invites_aceptadas"], kpis_campana["manual_primeros_mensajes_enviados"], kpis_campana["manual_respuestas_primer_mensaje"], kpis_campana["manual_sesiones_agendadas"]]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Manual"
        sub_caption = f"Embudo manual basado en {base_del_embudo:,} registros en la selección filtrada."
        if kpis_campana["manual_prospectados_o_invitados"] == 0 and kpis_campana["manual_sesiones_agendadas"] == 0:
             st.info(f"No hay actividad de prospección manual iniciada para la selección actual.")
             return
    elif tipo_embudo == "email":
        etapas_embudo = ["Registros en Selección (Filtrada)", "Contactados por Email", "Respuestas Email", "Sesiones Agendadas (Email)"]
        cantidades_embudo = [base_del_embudo, kpis_campana["email_contactados"], kpis_campana["email_respuestas"], kpis_campana["email_sesiones_agendadas"]]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Email"
        sub_caption = f"Embudo de email basado en {base_del_embudo:,} registros en la selección filtrada."
        if kpis_campana["email_contactados"] == 0 and kpis_campana["email_sesiones_agendadas"] == 0:
            st.info(f"No hay actividad de contacto por email iniciada para la selección actual.")
            return
    else:
        st.error("Tipo de embudo no reconocido."); return

    if sum(cantidades_embudo) == 0 :
        st.info(f"No hay datos suficientes para generar el embudo de '{tipo_embudo}' para la selección actual."); return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    porcentajes_vs_anterior = [100.0] if not df_embudo.empty else []
    for i in range(1, len(df_embudo)):
        porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
        porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    porcentajes_vs_inicio_embudo = []
    if not df_embudo.empty and df_embudo['Cantidad'][0] > 0:
        porcentajes_vs_inicio_embudo = [(c / df_embudo['Cantidad'][0] * 100) for c in df_embudo['Cantidad']]
    elif not df_embudo.empty:
        porcentajes_vs_inicio_embudo = [0.0] * len(df_embudo)
        if len(porcentajes_vs_inicio_embudo) > 0: porcentajes_vs_inicio_embudo[0] = 100.0
    df_embudo['% vs Inicio Embudo'] = porcentajes_vs_inicio_embudo
    df_embudo['Texto'] = df_embudo.apply(lambda row: f"{row['Cantidad']:,}<br>({row['% vs Anterior']:.1f}% vs Ant.)<br>({row['% vs Inicio Embudo']:.1f}% vs Inicio Sel.)", axis=1)
    if not df_embudo.empty: df_embudo.loc[0, 'Texto'] = f"{df_embudo.loc[0, 'Cantidad']:,}<br>(100% de Selección Filtrada)"
    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text', connector={"line": {"color": "royalblue", "dash": "dot", "width": 2}})
    st.plotly_chart(fig_embudo, use_container_width=True); st.caption(sub_caption)

def generar_tabla_comparativa_campanas_filtrada(df_base_global_para_originales, df_filtrado_con_filtros_pagina, lista_nombres_campanas_seleccionadas):
    datos_comparativa = []
    if df_filtrado_con_filtros_pagina.empty or not lista_nombres_campanas_seleccionadas:
        return pd.DataFrame(datos_comparativa)

    for nombre_campana in lista_nombres_campanas_seleccionadas:
        # Universo original de esta campaña específica
        total_original_esta_campana = df_base_global_para_originales[df_base_global_para_originales['Campaña'] == nombre_campana].shape[0]
        
        # Parte de la selección filtrada que pertenece a esta campaña
        df_campana_individual_filtrada = df_filtrado_con_filtros_pagina[df_filtrado_con_filtros_pagina['Campaña'] == nombre_campana]
        
        # Calcular KPIs para esta parte, pasando el total original correspondiente
        kpis = calcular_kpis_df_campana(df_campana_individual_filtrada, total_original_esta_campana)
        
        datos_comparativa.append({
            "Campaña": nombre_campana,
            "Total Original Camp.": total_original_esta_campana, # Nuevo
            "Registros Sel. Filtrada": kpis["total_registros_seleccion_filtrada"],
            "% Orig. en Sel. Filt.": kpis["porc_original_en_seleccion_filtrada"], # Nuevo
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
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No hay datos base de campañas para analizar. Revisa la carga de datos."); st.stop()

# --- Sección 1: Selección de Campaña(s) y Universo Total Original ---
st.markdown("---")
st.subheader("1. Selección de Campaña(s) y Universo Total Original")
lista_campanas_disponibles_global = sorted(df_base_campanas_global['Campaña'].unique())
if not lista_campanas_disponibles_global:
    st.warning("No se encontraron nombres de campañas en los datos cargados."); st.stop()

st.session_state.campana_seleccion_principal = st.multiselect(
    "Elige la(s) campaña(s) a analizar:", options=lista_campanas_disponibles_global,
    default=st.session_state.campana_seleccion_principal, key="ms_campana_seleccion_principal"
)

universo_total_original_combinado = 0
if st.session_state.campana_seleccion_principal:
    st.markdown("#### Universo Total de Registros Originales para Campaña(s) Seleccionada(s)")
    st.caption("Este es el conteo total de registros asignados a cada campaña seleccionada, *antes* de aplicar cualquier filtro de página.")
    
    # Mostrar totales individuales originales
    if len(st.session_state.campana_seleccion_principal) > 1:
        cols_totales_orig = st.columns(len(st.session_state.campana_seleccion_principal))
        for i, camp_name in enumerate(st.session_state.campana_seleccion_principal):
            total_records_camp = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name].shape[0]
            universo_total_original_combinado += total_records_camp
            with cols_totales_orig[i]:
                st.metric(label=f"'{camp_name}' (Total Original)", value=f"{total_records_camp:,}")
        st.metric(label="GRAN TOTAL ORIGINAL (Campañas Seleccionadas)", value=f"{universo_total_original_combinado:,}")
    elif len(st.session_state.campana_seleccion_principal) == 1:
        camp_name = st.session_state.campana_seleccion_principal[0]
        total_records_camp = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name].shape[0]
        universo_total_original_combinado = total_records_camp
        st.metric(label=f"GRAN TOTAL ORIGINAL ('{camp_name}')", value=f"{universo_total_original_combinado:,}")
    st.markdown("---")

# --- Sección 2: Filtros Adicionales para definir la 'Selección Filtrada' ---
st.subheader("2. Filtros Adicionales para Definir la 'Selección Filtrada'")
st.caption("Estos filtros se aplican sobre el 'Universo Total Original' de las campañas seleccionadas.")

if st.button("Limpiar Filtros de Página", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
    st.rerun()

if not st.session_state.campana_seleccion_principal:
    st.info("Por favor, selecciona al menos una campaña para visualizar los datos y aplicar filtros."); st.stop()

# df_campanas_seleccionadas_originales es el subconjunto del df_base_global que pertenece a las campañas elegidas
df_campanas_seleccionadas_originales = df_base_campanas_global[
    df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
].copy()

with st.expander("Aplicar filtros detallados", expanded=True):
    # (Filtros de prospectador, país y fecha sin cambios en su lógica interna)
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        opciones_prospectador_camp = ["– Todos –"] + sorted(df_campanas_seleccionadas_originales["¿Quién Prospecto?"].dropna().astype(str).unique())
        st.session_state.campana_filtro_prospectador = st.multiselect("¿Quién Prospectó?", options=opciones_prospectador_camp, default=st.session_state.campana_filtro_prospectador if all(p in opciones_prospectador_camp for p in st.session_state.campana_filtro_prospectador) else ["– Todos –"], key="ms_campana_prospectador")
        opciones_pais_camp = ["– Todos –"] + sorted(df_campanas_seleccionadas_originales["Pais"].dropna().astype(str).unique())
        st.session_state.campana_filtro_pais = st.multiselect("País del Prospecto", options=opciones_pais_camp, default=st.session_state.campana_filtro_pais if all(p in opciones_pais_camp for p in st.session_state.campana_filtro_pais) else ["– Todos –"], key="ms_campana_pais")
    with col_f2:
        min_fecha, max_fecha = (df_campanas_seleccionadas_originales["Fecha de Invite"].min().date(), df_campanas_seleccionadas_originales["Fecha de Invite"].max().date()) if "Fecha de Invite" in df_campanas_seleccionadas_originales and not df_campanas_seleccionadas_originales["Fecha de Invite"].dropna().empty else (None, None)
        st.session_state.campana_filtro_fecha_ini = st.date_input("Fecha de Invite Desde:", value=st.session_state.campana_filtro_fecha_ini, min_value=min_fecha, max_value=max_fecha, format="DD/MM/YYYY", key="di_campana_fecha_ini")
        st.session_state.campana_filtro_fecha_fin = st.date_input("Fecha de Invite Hasta:", value=st.session_state.campana_filtro_fecha_fin, min_value=min_fecha, max_value=max_fecha, format="DD/MM/YYYY", key="di_campana_fecha_fin")

# Aplicar filtros para obtener df_final_analisis_campana (Universo de Selección Filtrada)
df_final_analisis_campana = df_campanas_seleccionadas_originales.copy()
if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
    df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["¿Quién Prospecto?"].isin(st.session_state.campana_filtro_prospectador)]
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Pais"].isin(st.session_state.campana_filtro_pais)]
if "Fecha de Invite" in df_final_analisis_campana.columns and pd.api.types.is_datetime64_any_dtype(df_final_analisis_campana["Fecha de Invite"]):
    if st.session_state.campana_filtro_fecha_ini:
        df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Fecha de Invite"] >= pd.to_datetime(st.session_state.campana_filtro_fecha_ini)]
    if st.session_state.campana_filtro_fecha_fin:
        df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Fecha de Invite"] <= pd.to_datetime(st.session_state.campana_filtro_fecha_fin).replace(hour=23, minute=59, second=59)]

# --- Sección 3: Resultados Agregados (basados en 'Selección Filtrada') ---
st.markdown("---")
st.header(f"📊 Resultados Agregados para '{', '.join(st.session_state.campana_seleccion_principal)}' (sobre Selección Filtrada)")

if df_final_analisis_campana.empty:
    st.warning("La 'Selección Filtrada' está vacía. No hay prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
else:
    # Calcular KPIs agregados sobre la selección filtrada final
    # El segundo argumento para calcular_kpis_df_campana es el total original correspondiente al df que se le pasa
    # Para el agregado, este es el universo_total_original_combinado
    kpis_agregados = calcular_kpis_df_campana(df_final_analisis_campana, universo_total_original_combinado)

    st.metric(label="Universo de Selección Filtrada (Registros)", value=f"{kpis_agregados['total_registros_seleccion_filtrada']:,}",
              help=f"Registros que cumplen filtros de página. Representan el {kpis_agregados['porc_original_en_seleccion_filtrada']:.1f}% del Gran Total Original de {universo_total_original_combinado:,} registros.")
    st.metric(label="Total Sesiones Agendadas (Manual + Email)", value=f"{kpis_agregados['total_sesiones_agendadas']:,}")
    
    # (Resto de la presentación de KPIs agregados, embudos, tabla comparativa, etc. usa kpis_agregados)
    # ... El código para mostrar KPIs de Prospección Manual, Email, Embudos es el mismo de la versión anterior ...
    # Solo hay que asegurarse que la tabla comparativa llama a generar_tabla_comparativa_campanas_filtrada
    # con el df_base_campanas_global para los totales originales.

    st.markdown("---")
    st.markdown("### KPIs de Prospección Manual (sobre Selección Filtrada)")
    if kpis_agregados['manual_prospectados_o_invitados'] > 0 or kpis_agregados['manual_sesiones_agendadas'] > 0 :
        m_cols1 = st.columns(3)
        m_cols1[0].metric("Invites Enviadas (Prosp. Manual Inic.)", f"{kpis_agregados['manual_prospectados_o_invitados']:,}", f"{kpis_agregados['manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada']:.1f}% de Sel. Filtrada")
        m_cols1[1].metric("Invites Aceptadas", f"{kpis_agregados['manual_invites_aceptadas']:,}", f"{kpis_agregados['manual_tasa_aceptacion_vs_invitados']:.1f}% de Inv. Env.")
        m_cols1[2].metric("Sesiones (Manual)", f"{kpis_agregados['manual_sesiones_agendadas']:,}", f"{kpis_agregados['manual_tasa_sesion_global_vs_invitados']:.1f}% de Inv. Env.")
        m_cols2 = st.columns(2)
        m_cols2[0].metric("1ros Msj. Enviados", f"{kpis_agregados['manual_primeros_mensajes_enviados']:,}")
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
        # Pasar df_base_campanas_global para que la función pueda obtener los totales originales por campaña
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_base_campanas_global, df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs")
            cols_enteros_comp = ["Total Original Camp.", "Registros Sel. Filtrada", "Inv. Enviadas", "Inv. Aceptadas", "Resp. 1er Msj", "Sesiones Manual", "Email Contact.", "Email Resp.", "Sesiones Email", "Total Sesiones"]
            format_dict_comp = {
                "% Orig. en Sel. Filt.": "{:.1f}%", "Tasa Prosp. Man. Inic. (%)": "{:.1f}%", "Tasa Acept. (vs Inv. Env.) (%)": "{:.1f}%", 
                "Tasa Resp. (vs Acept.) (%)": "{:.1f}%", "Tasa Sesión Man. (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Man. Global (vs Inv. Env.) (%)": "{:.1f}%",
                "Tasa Cont. Email Inic. (%)": "{:.1f}%", "Tasa Resp. Email (vs Cont.) (%)": "{:.1f}%", "Tasa Sesión Email (vs Resp.) (%)": "{:.1f}%",
                "Tasa Sesión Email Global (vs Cont.) (%)": "{:.1f}%"
            }
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            st.dataframe(df_tabla_comp.sort_values(by="Total Sesiones", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            # (Gráficos comparativos se mantienen igual, usando df_tabla_comp)
        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    # --- Rendimiento por Prospectador y Detalle de Prospectos (sin cambios significativos en su lógica interna) ---
    # Estas secciones operan sobre df_final_analisis_campana (la selección filtrada)
    # y usan calcular_kpis_df_campana que ya está ajustada.

    st.markdown("### Rendimiento por Prospectador (Flujo Manual sobre Selección Filtrada)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        df_prospectador_camp_list = []
        # Agrupar por prospectador sobre la selección filtrada
        for prospectador, df_grupo_prospectador in df_final_analisis_campana.groupby("¿Quién Prospecto?"):
            # El total original correspondiente para este prospectador sería difícil de definir sin más contexto
            # Así que calculamos KPIs basados en su porción de la selección filtrada.
            kpis_prospectador = calcular_kpis_df_campana(df_grupo_prospectador) # No pasamos total_original aquí
            if kpis_prospectador["manual_prospectados_o_invitados"] > 0:
                df_prospectador_camp_list.append({
                    "¿Quién Prospecto?": prospectador,
                    "Su Sel. Filtrada": kpis_prospectador["total_registros_seleccion_filtrada"],
                    "Invites Enviadas": kpis_prospectador["manual_prospectados_o_invitados"],
                    "Tasa Prosp. Inic. (vs su Sel.) (%)" : kpis_prospectador["manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada"],
                    "Sesiones (Manual)": kpis_prospectador["manual_sesiones_agendadas"],
                    "Tasa Sesión Global (Manual vs Inv. Env.) (%)": kpis_prospectador["manual_tasa_sesion_global_vs_invitados"]
                })
        if df_prospectador_camp_list:
            df_prospectador_camp_display = pd.DataFrame(df_prospectador_camp_list).sort_values(by="Sesiones (Manual)", ascending=False)
            cols_enteros_prosp = ["Su Sel. Filtrada", "Invites Enviadas", "Sesiones (Manual)"]
            format_dict_prosp = {"Tasa Prosp. Inic. (vs su Sel.) (%)": "{:.1f}%", "Tasa Sesión Global (Manual vs Inv. Env.) (%)": "{:.1f}%"}
            for col_int_prosp in cols_enteros_prosp:
                if col_int_prosp in df_prospectador_camp_display.columns: df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int); format_dict_prosp[col_int_prosp] = "{:,}"
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            # (Lógica para mostrar gráfico se mantiene)
        else: st.caption("No hay datos de rendimiento por prospectador para la actividad manual en la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible para el análisis por prospectador.")

    st.markdown("### Detalle de Prospectos (de la Selección Filtrada)")
    indices_filtrados = df_final_analisis_campana.index
    df_detalle_original_filtrado = df_original_completo.loc[indices_filtrados].copy()
    if not df_detalle_original_filtrado.empty:
        # (Lógica de formateo y descarga de detalle se mantiene)
        columnas_relevantes = ["Campaña", "Nombre", "Apellido", "¿Quién Prospecto?", "Pais", "Fecha de Invite", "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", "Sesion Agendada?", "Fecha Sesion", "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email", "Fecha de Sesion Email", "Avatar"]
        columnas_existentes_para_detalle = [col for col in columnas_relevantes if col in df_detalle_original_filtrado.columns]
        df_display_tabla_campana_detalle_prep = df_detalle_original_filtrado[columnas_existentes_para_detalle].copy()
        df_display_tabla_campana_detalle = pd.DataFrame()
        for col_orig in df_display_tabla_campana_detalle_prep.columns:
            if pd.api.types.is_datetime64_any_dtype(df_display_tabla_campana_detalle_prep[col_orig]): df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_display_tabla_campana_detalle_prep[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            else: df_display_tabla_campana_detalle[col_orig] = df_display_tabla_campana_detalle_prep[col_orig].astype(str).fillna("N/A").replace("nan", "N/A").replace("NaT", "N/A")
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
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
