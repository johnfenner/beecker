# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
# import sys # No se usa directamente
# import os  # No se usa directamente

# Asumiendo que estas funciones están correctamente definidas en tus módulos
from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado, incluyendo flujos de prospección manual y por email, partiendo del total de registros en campaña y luego de la selección filtrada.")

# --- Funciones de Ayuda Específicas para esta Página ---

@st.cache_data
def obtener_datos_base_campanas():
    df_completo = cargar_y_limpiar_datos() #
    if df_completo is None or df_completo.empty:
        st.error("No se pudieron cargar los datos. Verifica la fuente de datos.")
        return pd.DataFrame(), pd.DataFrame()

    if 'Campaña' not in df_completo.columns: #
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo

    df_base_campanas = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy() #

    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion", "Fecha de Sesion Email"] #
    for df_proc in [df_base_campanas, df_completo]:
        for col in date_cols_to_check:
            if col in df_proc.columns and not pd.api.types.is_datetime64_any_dtype(df_proc[col]):
                df_proc[col] = pd.to_datetime(df_proc[col], errors='coerce') #
        
        if "Avatar" in df_proc.columns:
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

def calcular_kpis_df_campana(df_filtrado_campana):
    # df_filtrado_campana es el "Universo de Selección Filtrada"
    empty_kpis = {
        "total_registros_seleccion_filtrada": 0,
        # Manual KPIs
        "manual_prospectados_o_invitados": 0, "manual_invites_aceptadas": 0,
        "manual_primeros_mensajes_enviados": 0, "manual_respuestas_primer_mensaje": 0,
        "manual_sesiones_agendadas": 0,
        "manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada": 0, # Nueva tasa
        "manual_tasa_aceptacion_vs_invitados": 0, "manual_tasa_respuesta_vs_aceptadas": 0,
        "manual_tasa_sesion_vs_respuesta": 0, "manual_tasa_sesion_global_vs_invitados": 0,
        # Email KPIs
        "email_contactados": 0, "email_respuestas": 0, "email_sesiones_agendadas": 0,
        "email_tasa_contacto_iniciado_vs_seleccion_filtrada": 0, # Nueva tasa
        "email_tasa_respuesta_vs_contactados": 0, "email_tasa_sesion_vs_respuesta": 0,
        "email_tasa_sesion_global_vs_contactados": 0,
        # Combined
        "total_sesiones_agendadas": 0
    }
    if df_filtrado_campana.empty:
        return empty_kpis

    total_registros_seleccion_filtrada = len(df_filtrado_campana) #

    # --- KPIs de Prospección Manual ---
    manual_prospectados_o_invitados = df_filtrado_campana["Fecha de Invite"].notna().sum() if "Fecha de Invite" in df_filtrado_campana else 0 #
    manual_invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str)))
    manual_primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    manual_respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan", "none"]
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    manual_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str)))

    manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada = (manual_prospectados_o_invitados / total_registros_seleccion_filtrada * 100) if total_registros_seleccion_filtrada > 0 else 0
    manual_tasa_aceptacion_vs_invitados = (manual_invites_aceptadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    manual_tasa_respuesta_vs_aceptadas = (manual_respuestas_primer_mensaje / manual_invites_aceptadas * 100) if manual_invites_aceptadas > 0 else 0
    manual_tasa_sesion_vs_respuesta = (manual_sesiones_agendadas / manual_respuestas_primer_mensaje * 100) if manual_respuestas_primer_mensaje > 0 else 0
    manual_tasa_sesion_global_vs_invitados = (manual_sesiones_agendadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    
    # --- KPIs de Prospección por Email ---
    email_contactados = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Contactados por Campaña", pd.Series(dtype=str))) #
    email_respuestas = sum(limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] for x in df_filtrado_campana.get("Respuesta Email", pd.Series(dtype=str)))
    email_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada Email", pd.Series(dtype=str)))

    email_tasa_contacto_iniciado_vs_seleccion_filtrada = (email_contactados / total_registros_seleccion_filtrada * 100) if total_registros_seleccion_filtrada > 0 else 0
    email_tasa_respuesta_vs_contactados = (email_respuestas / email_contactados * 100) if email_contactados > 0 else 0
    email_tasa_sesion_vs_respuesta = (email_sesiones_agendadas / email_respuestas * 100) if email_respuestas > 0 else 0
    email_tasa_sesion_global_vs_contactados = (email_sesiones_agendadas / email_contactados * 100) if email_contactados > 0 else 0

    total_sesiones_agendadas = manual_sesiones_agendadas + email_sesiones_agendadas

    return {
        "total_registros_seleccion_filtrada": int(total_registros_seleccion_filtrada),
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

def mostrar_embudo_para_campana(kpis_campana, tipo_embudo="manual", titulo_embudo_base="Embudo de Conversión"): #
    etapas_embudo, cantidades_embudo = [], []
    sub_caption = ""
    base_del_embudo = kpis_campana["total_registros_seleccion_filtrada"] #

    if tipo_embudo == "manual":
        etapas_embudo = [
            "Registros en Selección (Filtrada)", "Invites Enviadas", "Invites Aceptadas", #
            "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas (Manual)"
        ]
        cantidades_embudo = [
            base_del_embudo, kpis_campana["manual_prospectados_o_invitados"], #
            kpis_campana["manual_invites_aceptadas"], kpis_campana["manual_primeros_mensajes_enviados"],
            kpis_campana["manual_respuestas_primer_mensaje"], kpis_campana["manual_sesiones_agendadas"]
        ]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Manual"
        sub_caption = f"Embudo manual basado en {base_del_embudo:,} registros en la selección filtrada."
        # Solo mostrar si hay alguna actividad manual iniciada o sesiones
        if kpis_campana["manual_prospectados_o_invitados"] == 0 and kpis_campana["manual_sesiones_agendadas"] == 0:
             st.info(f"No hay actividad de prospección manual iniciada para la selección actual.")
             return

    elif tipo_embudo == "email":
        etapas_embudo = [
             "Registros en Selección (Filtrada)", "Contactados por Email", "Respuestas Email", "Sesiones Agendadas (Email)" #
        ]
        cantidades_embudo = [
            base_del_embudo, kpis_campana["email_contactados"], #
            kpis_campana["email_respuestas"], kpis_campana["email_sesiones_agendadas"]
        ]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Email"
        sub_caption = f"Embudo de email basado en {base_del_embudo:,} registros en la selección filtrada."
        # Solo mostrar si hay alguna actividad de email iniciada o sesiones
        if kpis_campana["email_contactados"] == 0 and kpis_campana["email_sesiones_agendadas"] == 0:
            st.info(f"No hay actividad de contacto por email iniciada para la selección actual.")
            return
    else:
        st.error("Tipo de embudo no reconocido.")
        return

    if sum(cantidades_embudo) == 0 : # Chequeo adicional por si acaso, aunque los anteriores deberían cubrirlo
        st.info(f"No hay datos suficientes para generar el embudo de '{tipo_embudo}' para la selección actual.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    
    porcentajes_vs_anterior = [100.0] if not df_embudo.empty else []
    for i in range(1, len(df_embudo)):
        porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
        porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    
    porcentajes_vs_inicio_embudo = []
    if not df_embudo.empty and df_embudo['Cantidad'][0] > 0:
        porcentajes_vs_inicio_embudo = [(c / df_embudo['Cantidad'][0] * 100) for c in df_embudo['Cantidad']]
    elif not df_embudo.empty: # Si la cantidad inicial es 0 pero hay etapas
        porcentajes_vs_inicio_embudo = [0.0] * len(df_embudo)
        if len(porcentajes_vs_inicio_embudo) > 0: porcentajes_vs_inicio_embudo[0] = 100.0


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

def generar_tabla_comparativa_campanas_filtrada(df_filtrado_con_filtros_pagina, lista_nombres_campanas_seleccionadas): #
    datos_comparativa = []
    if df_filtrado_con_filtros_pagina.empty or not lista_nombres_campanas_seleccionadas:
        return pd.DataFrame(datos_comparativa)

    for nombre_campana in lista_nombres_campanas_seleccionadas:
        df_campana_individual_filtrada = df_filtrado_con_filtros_pagina[
            df_filtrado_con_filtros_pagina['Campaña'] == nombre_campana
        ]
        kpis = calcular_kpis_df_campana(df_campana_individual_filtrada)
        datos_comparativa.append({
            "Campaña": nombre_campana,
            "Registros Sel. Filtrada": kpis["total_registros_seleccion_filtrada"], #
            # Manual
            "Inv. Enviadas": kpis["manual_prospectados_o_invitados"],
            "Tasa Prosp. Man. Inic. (%)": kpis["manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada"], #
            "Inv. Aceptadas": kpis["manual_invites_aceptadas"],
            "Resp. 1er Msj": kpis["manual_respuestas_primer_mensaje"],
            "Sesiones Manual": kpis["manual_sesiones_agendadas"],
            "Tasa Acept. (vs Inv. Env.) (%)": kpis["manual_tasa_aceptacion_vs_invitados"],
            "Tasa Resp. (vs Acept.) (%)": kpis["manual_tasa_respuesta_vs_aceptadas"],
            "Tasa Sesión Man. (vs Resp.) (%)": kpis["manual_tasa_sesion_vs_respuesta"],
            "Tasa Sesión Man. Global (vs Inv. Env.) (%)": kpis["manual_tasa_sesion_global_vs_invitados"],
            # Email
            "Email Contact.": kpis["email_contactados"],
            "Tasa Cont. Email Inic. (%)": kpis["email_tasa_contacto_iniciado_vs_seleccion_filtrada"], #
            "Email Resp.": kpis["email_respuestas"],
            "Sesiones Email": kpis["email_sesiones_agendadas"],
            "Tasa Resp. Email (vs Cont.) (%)": kpis["email_tasa_respuesta_vs_contactados"],
            "Tasa Sesión Email (vs Resp.) (%)": kpis["email_tasa_sesion_vs_respuesta"],
            "Tasa Sesión Email Global (vs Cont.) (%)": kpis["email_tasa_sesion_global_vs_contactados"],
            # Combinado
            "Total Sesiones": kpis["total_sesiones_agendadas"]
        })
    return pd.DataFrame(datos_comparativa)


# --- Carga de Datos Base ---
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas() #
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No hay datos base de campañas para analizar. Revisa la carga de datos.")
    st.stop()

# --- Sección de Selección de Campaña Principal ---
st.markdown("---")
st.subheader("1. Selección de Campaña(s) y Totales Originales")
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

if st.session_state.campana_seleccion_principal:
    st.markdown("#### Universo Total de Registros por Campaña Seleccionada")
    st.caption("Estos son los totales de registros asignados a cada campaña *antes* de aplicar cualquier filtro de página (Prospectador, País, Fechas de Invite).")
    cols_totales_orig = st.columns(len(st.session_state.campana_seleccion_principal))
    for i, camp_name in enumerate(st.session_state.campana_seleccion_principal):
        total_records_in_camp_original = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name].shape[0] #
        
        df_camp_original_dates = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name]
        min_fecha_camp, max_fecha_camp = None, None
        # Considerar múltiples columnas de fecha para el rango de actividad de la campaña
        # Por simplicidad, usaremos Fecha de Invite si existe, si no, podríamos buscar otras.
        date_col_for_range = "Fecha de Invite" # Podría ser configurable o más inteligente
        if date_col_for_range in df_camp_original_dates.columns and df_camp_original_dates[date_col_for_range].notna().any():
            min_fecha_camp = df_camp_original_dates[date_col_for_range].min().strftime('%d/%m/%Y')
            max_fecha_camp = df_camp_original_dates[date_col_for_range].max().strftime('%d/%m/%Y')
        
        fecha_info = ""
        if min_fecha_camp and max_fecha_camp:
            fecha_info = f"<br><small>Rango (Invites): {min_fecha_camp} - {max_fecha_camp}</small>"
        
        with cols_totales_orig[i]:
            st.metric(label=f"'{camp_name}' (Total Original)", value=f"{total_records_in_camp_original:,}")
            if fecha_info:
                st.markdown(fecha_info, unsafe_allow_html=True)
    st.markdown("---")


# --- Sección de Filtros Adicionales ---
st.subheader("2. Filtros Adicionales (aplican al universo total de las campañas seleccionadas)")

if st.button("Limpiar Filtros de Página", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
    st.rerun()

if not st.session_state.campana_seleccion_principal:
    st.info("Por favor, selecciona al menos una campaña para visualizar los datos y aplicar filtros.")
    st.stop()

df_campanas_filtradas_por_seleccion_inicial = df_base_campanas_global[
    df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
].copy()

with st.expander("Aplicar filtros detallados a la(s) campaña(s) seleccionada(s)", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion_inicial["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        default_prospectador = st.session_state.campana_filtro_prospectador
        if not all(p in opciones_prospectador_camp for p in default_prospectador):
            default_prospectador = ["– Todos –"] if "– Todos –" in opciones_prospectador_camp else []
        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó? (Filtro para prospección manual)", options=opciones_prospectador_camp,
            default=default_prospectador, key="ms_campana_prospectador"
        )
        opciones_pais_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion_inicial["Pais"].dropna().astype(str).unique()
        )
        default_pais = st.session_state.campana_filtro_pais
        if not all(p in opciones_pais_camp for p in default_pais):
             default_pais = ["– Todos –"] if "– Todos –" in opciones_pais_camp else []
        st.session_state.campana_filtro_pais = st.multiselect(
            "País del Prospecto", options=opciones_pais_camp,
            default=default_pais, key="ms_campana_pais"
        )
    with col_f2:
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        if "Fecha de Invite" in df_campanas_filtradas_por_seleccion_inicial.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion_inicial["Fecha de Invite"]):
            valid_dates = df_campanas_filtradas_por_seleccion_inicial["Fecha de Invite"].dropna()
            if not valid_dates.empty:
                min_fecha_invite_camp = valid_dates.min().date()
                max_fecha_invite_camp = valid_dates.max().date()
        
        val_fecha_ini = st.date_input(
            "Filtrar por Fecha de Invite Desde:", 
            value=st.session_state.campana_filtro_fecha_ini,
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_ini",
            help="Este filtro de fecha se aplica a la columna 'Fecha de Invite'."
        )
        val_fecha_fin = st.date_input(
            "Filtrar por Fecha de Invite Hasta:", 
            value=st.session_state.campana_filtro_fecha_fin,
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_fin",
            help="Este filtro de fecha se aplica a la columna 'Fecha de Invite'."
        )
        st.session_state.campana_filtro_fecha_ini = val_fecha_ini
        st.session_state.campana_filtro_fecha_fin = val_fecha_fin

# Aplicar filtros de página para obtener el "Universo de Selección Filtrada"
df_final_analisis_campana = df_campanas_filtradas_por_seleccion_inicial.copy() # Este es el df_filtrado_campana para calcular_kpis

if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
    df_final_analisis_campana = df_final_analisis_campana[
        df_final_analisis_campana["¿Quién Prospecto?"].isin(st.session_state.campana_filtro_prospectador)
    ]
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_final_analisis_campana = df_final_analisis_campana[
        df_final_analisis_campana["Pais"].isin(st.session_state.campana_filtro_pais)
    ]

fecha_ini_aplicar = st.session_state.campana_filtro_fecha_ini
fecha_fin_aplicar = st.session_state.campana_filtro_fecha_fin

if "Fecha de Invite" in df_final_analisis_campana.columns and pd.api.types.is_datetime64_any_dtype(df_final_analisis_campana["Fecha de Invite"]):
    if fecha_ini_aplicar and fecha_fin_aplicar:
        fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
        fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
        df_final_analisis_campana = df_final_analisis_campana[
            (df_final_analisis_campana["Fecha de Invite"] >= fecha_ini_dt) &
            (df_final_analisis_campana["Fecha de Invite"] <= fecha_fin_dt)
        ]
    elif fecha_ini_aplicar:
        fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
        df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Fecha de Invite"] >= fecha_ini_dt]
    elif fecha_fin_aplicar:
        fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
        df_final_analisis_campana = df_final_analisis_campana[df_final_analisis_campana["Fecha de Invite"] <= fecha_fin_dt]

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados Agregados para: {', '.join(st.session_state.campana_seleccion_principal)}")
st.caption("Los KPIs y embudos a continuación se basan en el 'Universo de Selección Filtrada' (es decir, después de aplicar los filtros de página).")

if df_final_analisis_campana.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
else:
    kpis_agregados = calcular_kpis_df_campana(df_final_analisis_campana)

    st.metric(label="Universo de Selección Filtrada (Registros)", value=f"{kpis_agregados['total_registros_seleccion_filtrada']:,}",
              help="Total de registros que cumplen con la selección de campaña Y los filtros de página. Base para los % de inicio de flujos.")
    st.metric(label="Total Sesiones Agendadas (Manual + Email)", value=f"{kpis_agregados['total_sesiones_agendadas']:,}")
    
    st.markdown("---")
    st.markdown("### KPIs de Prospección Manual (sobre Selección Filtrada)")
    if kpis_agregados['manual_prospectados_o_invitados'] > 0 or kpis_agregados['manual_sesiones_agendadas'] > 0 :
        m_cols1 = st.columns(3)
        m_cols1[0].metric("Invites Enviadas (Prosp. Manual Inic.)", f"{kpis_agregados['manual_prospectados_o_invitados']:,}",
                        f"{kpis_agregados['manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada']:.1f}% de Sel. Filtrada")
        m_cols1[1].metric("Invites Aceptadas", f"{kpis_agregados['manual_invites_aceptadas']:,}",
                        f"{kpis_agregados['manual_tasa_aceptacion_vs_invitados']:.1f}% de Inv. Env.")
        m_cols1[2].metric("Sesiones (Manual)", f"{kpis_agregados['manual_sesiones_agendadas']:,}",
                        f"{kpis_agregados['manual_tasa_sesion_global_vs_invitados']:.1f}% de Inv. Env.")
        
        m_cols2 = st.columns(2)
        m_cols2[0].metric("1ros Msj. Enviados", f"{kpis_agregados['manual_primeros_mensajes_enviados']:,}")
        m_cols2[1].metric("Respuestas 1er Msj.", f"{kpis_agregados['manual_respuestas_primer_mensaje']:,}",
                        f"{kpis_agregados['manual_tasa_respuesta_vs_aceptadas']:.1f}% de Acept.")
        
        if kpis_agregados['manual_sesiones_agendadas'] > 0 and kpis_agregados['manual_respuestas_primer_mensaje'] > 0:
            st.caption(f"Tasa de Sesiones Manual vs Respuestas: {kpis_agregados['manual_tasa_sesion_vs_respuesta']:.1f}%")
    else:
        st.info("No hay datos de prospección manual significativos para la selección filtrada actual.")

    st.markdown("---")
    st.markdown("### KPIs de Prospección por Email (sobre Selección Filtrada)")
    if kpis_agregados['email_contactados'] > 0 or kpis_agregados['email_sesiones_agendadas'] > 0:
        e_cols1 = st.columns(3)
        e_cols1[0].metric("Emails Contactados (Prosp. Email Inic.)", f"{kpis_agregados['email_contactados']:,}",
                          f"{kpis_agregados['email_tasa_contacto_iniciado_vs_seleccion_filtrada']:.1f}% de Sel. Filtrada")
        e_cols1[1].metric("Respuestas Email", f"{kpis_agregados['email_respuestas']:,}",
                        f"{kpis_agregados['email_tasa_respuesta_vs_contactados']:.1f}% de Contact.")
        e_cols1[2].metric("Sesiones (Email)", f"{kpis_agregados['email_sesiones_agendadas']:,}",
                        f"{kpis_agregados['email_tasa_sesion_global_vs_contactados']:.1f}% de Contact.")
        if kpis_agregados['email_sesiones_agendadas'] > 0 and kpis_agregados['email_respuestas'] > 0:
            st.caption(f"Tasa de Sesiones Email vs Respuestas: {kpis_agregados['email_tasa_sesion_vs_respuesta']:.1f}%")
    else:
        st.info("No hay datos de prospección por email significativos para la selección filtrada actual.")
    
    st.markdown("---")
    st.subheader("Embudos de Conversión (desde Selección Filtrada)")
    col_embudo1, col_embudo2 = st.columns(2)
    with col_embudo1:
        mostrar_embudo_para_campana(kpis_agregados, tipo_embudo="manual", titulo_embudo_base="Embudo Manual")
    with col_embudo2:
        mostrar_embudo_para_campana(kpis_agregados, tipo_embudo="email", titulo_embudo_base="Embudo Email")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (sobre Selección Filtrada)")
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs")
            cols_enteros_comp = [
                "Registros Sel. Filtrada", "Inv. Enviadas", "Inv. Aceptadas", "Resp. 1er Msj", 
                "Sesiones Manual", "Email Contact.", "Email Resp.", "Sesiones Email", "Total Sesiones"
            ]
            format_dict_comp = {
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

            st.subheader("Gráficos Comparativos")
            # Gráfico: Tasa de Inicio Prospección Manual
            df_g_tim = df_tabla_comp[df_tabla_comp["Registros Sel. Filtrada"] > 0].sort_values(by="Tasa Prosp. Man. Inic. (%)", ascending=False)
            if not df_g_tim.empty:
                fig_g_tim = px.bar(df_g_tim, x="Campaña", y="Tasa Prosp. Man. Inic. (%)", title="Comparativa: % Prospección Manual Iniciada (vs Sel. Filtrada)", text="Tasa Prosp. Man. Inic. (%)", color="Campaña")
                fig_g_tim.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                st.plotly_chart(fig_g_tim, use_container_width=True)

            # Gráfico: Tasa de Inicio Contacto Email
            df_g_tce = df_tabla_comp[df_tabla_comp["Registros Sel. Filtrada"] > 0].sort_values(by="Tasa Cont. Email Inic. (%)", ascending=False)
            if not df_g_tce.empty:
                fig_g_tce = px.bar(df_g_tce, x="Campaña", y="Tasa Cont. Email Inic. (%)", title="Comparativa: % Contacto Email Iniciado (vs Sel. Filtrada)", text="Tasa Cont. Email Inic. (%)", color="Campaña")
                fig_g_tce.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                st.plotly_chart(fig_g_tce, use_container_width=True)

            # (Puedes añadir más gráficos comparativos para otras tasas globales si lo deseas)

        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    st.markdown("### Rendimiento por Prospectador (Flujo Manual sobre Selección Filtrada)")
    # (El resto del código de rendimiento por prospectador y detalle de prospectos se mantiene igual,
    # ya que opera sobre df_final_analisis_campana, que es la selección filtrada,
    # y los KPIs manuales ya están definidos en calcular_kpis_df_campana)
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        df_prospectador_camp_list = []
        for prospectador, df_grupo in df_final_analisis_campana.groupby("¿Quién Prospecto?"):
            kpis_prospectador = calcular_kpis_df_campana(df_grupo)
            if kpis_prospectador["manual_prospectados_o_invitados"] > 0:
                df_prospectador_camp_list.append({
                    "¿Quién Prospecto?": prospectador,
                    "Registros en su Sel. Filtrada": kpis_prospectador["total_registros_seleccion_filtrada"],
                    "Invites Enviadas": kpis_prospectador["manual_prospectados_o_invitados"],
                    "Tasa Prosp. Inic. (vs su Sel.) (%)" : kpis_prospectador["manual_tasa_prospeccion_iniciada_vs_seleccion_filtrada"],
                    "Sesiones (Manual)": kpis_prospectador["manual_sesiones_agendadas"],
                    "Tasa Sesión Global (Manual vs Inv. Env.) (%)": kpis_prospectador["manual_tasa_sesion_global_vs_invitados"]
                })
        
        if df_prospectador_camp_list:
            df_prospectador_camp_display = pd.DataFrame(df_prospectador_camp_list)
            df_prospectador_camp_display = df_prospectador_camp_display.sort_values(by="Sesiones (Manual)", ascending=False)

            cols_enteros_prosp = ["Registros en su Sel. Filtrada", "Invites Enviadas", "Sesiones (Manual)"]
            format_dict_prosp = {
                "Tasa Prosp. Inic. (vs su Sel.) (%)": "{:.1f}%",
                "Tasa Sesión Global (Manual vs Inv. Env.) (%)": "{:.1f}%"
            }
            for col_int_prosp in cols_enteros_prosp:
                if col_int_prosp in df_prospectador_camp_display.columns:
                    df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int)
                    format_dict_prosp[col_int_prosp] = "{:,}"
            
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            
            mostrar_grafico_prospectador = False
            # (Lógica para mostrar gráfico se mantiene)
            if ("– Todos –" in st.session_state.campana_filtro_prospectador and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1) or \
               (len(st.session_state.campana_filtro_prospectador) > 1 and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1 and \
                not ("– Todos –" in st.session_state.campana_filtro_prospectador and len(st.session_state.campana_filtro_prospectador) == 1) ):
                mostrar_grafico_prospectador = True


            if mostrar_grafico_prospectador:
                fig_prosp_camp_bar = px.bar(
                    df_prospectador_camp_display.sort_values(by="Tasa Sesión Global (Manual vs Inv. Env.) (%)", ascending=False), 
                    x="¿Quién Prospecto?", y="Tasa Sesión Global (Manual vs Inv. Env.) (%)", 
                    title="Tasa de Sesión Global (Manual vs Invites Enviadas) por Prospectador", 
                    text="Tasa Sesión Global (Manual vs Inv. Env.) (%)", color="Tasa Sesión Global (Manual vs Inv. Env.) (%)")
                fig_prosp_camp_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                st.plotly_chart(fig_prosp_camp_bar, use_container_width=True)
        else: st.caption("No hay datos de rendimiento por prospectador para la actividad manual en la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible para el análisis por prospectador.")

    st.markdown("### Detalle de Prospectos (de la Selección Filtrada)")
    indices_filtrados = df_final_analisis_campana.index
    df_detalle_original_filtrado = df_original_completo.loc[indices_filtrados].copy() 
    
    if not df_detalle_original_filtrado.empty:
        columnas_relevantes = [
            "Campaña", "Nombre", "Apellido", "¿Quién Prospecto?", "Pais", "Fecha de Invite", 
            "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", "Sesion Agendada?", "Fecha Sesion",
            "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email", "Fecha de Sesion Email", "Avatar"
        ]
        columnas_existentes_para_detalle = [col for col in columnas_relevantes if col in df_detalle_original_filtrado.columns]
        df_display_tabla_campana_detalle_prep = df_detalle_original_filtrado[columnas_existentes_para_detalle].copy()

        df_display_tabla_campana_detalle = pd.DataFrame()
        for col_orig in df_display_tabla_campana_detalle_prep.columns:
            if pd.api.types.is_datetime64_any_dtype(df_display_tabla_campana_detalle_prep[col_orig]):
                 df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_display_tabla_campana_detalle_prep[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            else:
                 df_display_tabla_campana_detalle[col_orig] = df_display_tabla_campana_detalle_prep[col_orig].astype(str).fillna("N/A").replace("nan", "N/A").replace("NaT", "N/A")
        
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()

        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_original_filtrado)
        nombres_campana_str = "_".join(st.session_state.campana_seleccion_principal).replace(" ", "")[:50]
        nombre_archivo_excel_detalle = f"detalle_sel_filtrada_{nombres_campana_str}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle de Selección Filtrada (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Plataforma analítica potenciada por IA y el ingenio de Johnsito. ✨"
)
