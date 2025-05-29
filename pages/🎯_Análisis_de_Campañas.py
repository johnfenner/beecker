# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import sys
import os
# Ensure these imports are correct based on your project structure
# Assuming 'datos' and 'utils' are in the same parent directory as 'pages'
# or yourPYTHONPATH is set up correctly.
# If 'pages' is a top-level folder, and 'datos', 'utils' are siblings:
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datos.carga_datos import cargar_y_limpiar_datos #
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar #

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado, incluyendo interacciones manuales y por email.")

# --- Funciones de Ayuda Específicas para esta Página ---

@st.cache_data
def obtener_datos_base_campanas():
    df_completo_original = cargar_y_limpiar_datos() #
    if df_completo_original is None or df_completo_original.empty:
        st.error("No se pudieron cargar los datos. Verifica la fuente de datos.")
        return pd.DataFrame(), pd.DataFrame()

    if 'Campaña' not in df_completo_original.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo_original # Return original even if 'Campaña' is missing for other uses

    # df_base_campanas: data actively part of manual prospecting for selected campaigns
    df_base_campanas = df_completo_original[df_completo_original['Campaña'].notna() & (df_completo_original['Campaña'] != '')].copy()

    # Ensure all relevant date columns are converted
    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion", "Fecha de Sesion Email"]
    for col in date_cols_to_check:
        if col in df_base_campanas.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas[col]):
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
        if col in df_completo_original.columns and not pd.api.types.is_datetime64_any_dtype(df_completo_original[col]):
            df_completo_original[col] = pd.to_datetime(df_completo_original[col], errors='coerce')

    # Estandarizar Avatar en ambos dataframes
    for df_proc in [df_base_campanas, df_completo_original]:
        if "Avatar" in df_proc.columns:
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar) #

    return df_base_campanas, df_completo_original

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
    if df_filtrado_campana is None or df_filtrado_campana.empty:
        return {
            # Manual KPIs
            "total_prospectos_manual": 0, "invites_aceptadas": 0,
            "primeros_mensajes_enviados": 0, "respuestas_primer_mensaje": 0,
            "sesiones_agendadas_manual": 0, "tasa_aceptacion": 0,
            "tasa_respuesta_vs_aceptadas": 0, "tasa_sesion_vs_respuesta": 0,
            "tasa_sesion_global_manual": 0,
            # Email KPIs
            "contactados_email": 0, "respuestas_email": 0, "sesiones_agendadas_email": 0,
            "tasa_respuesta_email_vs_contactados": 0, "tasa_sesion_email_vs_respuestas": 0,
            "tasa_sesion_global_email": 0 # Vs contactados por email
        }

    # Manual Prospecting KPIs
    total_prospectos_manual = len(df_filtrado_campana) # Prospectos activamente en la campaña manual DESPUÉS DE FILTROS DE PÁGINA
    invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str))) #
    primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan", "noaplica", "no aplica"] #
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    sesiones_agendadas_manual = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str))) #

    tasa_aceptacion = (invites_aceptadas / total_prospectos_manual * 100) if total_prospectos_manual > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0
    tasa_sesion_vs_respuesta = (sesiones_agendadas_manual / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global_manual = (sesiones_agendadas_manual / total_prospectos_manual * 100) if total_prospectos_manual > 0 else 0

    # Email Campaign KPIs - these columns should exist in df_filtrado_campana
    contactados_email = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Contactados por Campaña", pd.Series(dtype=str))) #
    respuestas_email = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Respuesta Email", pd.Series(dtype=str))) #
    sesiones_agendadas_email = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada Email", pd.Series(dtype=str))) #

    tasa_respuesta_email_vs_contactados = (respuestas_email / contactados_email * 100) if contactados_email > 0 else 0
    tasa_sesion_email_vs_respuestas = (sesiones_agendadas_email / respuestas_email * 100) if respuestas_email > 0 else 0
    tasa_sesion_global_email = (sesiones_agendadas_email / contactados_email * 100) if contactados_email > 0 else 0
    
    return {
        # Manual
        "total_prospectos_manual": int(total_prospectos_manual), "invites_aceptadas": int(invites_aceptadas),
        "primeros_mensajes_enviados": int(primeros_mensajes_enviados),
        "respuestas_primer_mensaje": int(respuestas_primer_mensaje),
        "sesiones_agendadas_manual": int(sesiones_agendadas_manual), 
        "tasa_aceptacion": tasa_aceptacion,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta": tasa_sesion_vs_respuesta,
        "tasa_sesion_global_manual": tasa_sesion_global_manual,
        # Email
        "contactados_email": int(contactados_email), 
        "respuestas_email": int(respuestas_email), 
        "sesiones_agendadas_email": int(sesiones_agendadas_email),
        "tasa_respuesta_email_vs_contactados": tasa_respuesta_email_vs_contactados, 
        "tasa_sesion_email_vs_respuestas": tasa_sesion_email_vs_respuestas,
        "tasa_sesion_global_email": tasa_sesion_global_email
    }

def mostrar_embudo_para_campana(kpis_campana, titulo_embudo="Embudo de Conversión de Campaña (Manual)"):
    # Este embudo utiliza 'total_prospectos_manual' que es el número de prospectos
    # DESPUÉS de aplicar los filtros de la página.
    # Si se quiere un embudo desde "Prospectos Disponibles (Base)", se necesitaría pasar ese valor.
    etapas_embudo = [
        "Prospectos en Proceso Manual (Post-Filtros)", "Invites Aceptadas", # Clarified label
        "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas (Manual)"
    ]
    cantidades_embudo = [
        kpis_campana["total_prospectos_manual"], kpis_campana["invites_aceptadas"],
        kpis_campana["primeros_mensajes_enviados"], kpis_campana["respuestas_primer_mensaje"],
        kpis_campana["sesiones_agendadas_manual"]
    ]
    if sum(cantidades_embudo) == 0: # or kpis_campana["total_prospectos_manual"] == 0
        st.info("No hay datos suficientes para generar el embudo de conversión manual para la selección y filtros actuales.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    porcentajes_vs_anterior = [100.0] 
    if df_embudo['Cantidad'][0] > 0: 
        for i in range(1, len(df_embudo)):
            porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
            porcentajes_vs_anterior.append(porcentaje)
    else: 
        porcentajes_vs_anterior.extend([0.0] * (len(df_embudo) -1))
        
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    df_embudo['Texto'] = df_embudo.apply(lambda row: f"{row['Cantidad']:,} ({row['% vs Anterior']:.1f}%)", axis=1)

    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text')
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(f"Embudo manual basado en {kpis_campana['total_prospectos_manual']:,} prospectos en proceso manual (después de aplicar filtros de página) para la selección actual.")

def generar_tabla_comparativa_campanas_filtrada(df_filtrado_con_filtros_pagina, lista_nombres_campanas_seleccionadas):
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
            # Manual KPIs
            "Prospectos Proc. Manual (Post-Filtros)": kpis["total_prospectos_manual"], # Clarified label
            "Aceptadas": kpis["invites_aceptadas"],
            "Respuestas Manual": kpis["respuestas_primer_mensaje"], 
            "Sesiones Manual": kpis["sesiones_agendadas_manual"],
            "Tasa Aceptación (%)": kpis["tasa_aceptacion"],
            "Tasa Respuesta Man. (vs Acept.) (%)": kpis["tasa_respuesta_vs_aceptadas"],
            "Tasa Sesiones Man. (vs Resp.) (%)": kpis["tasa_sesion_vs_respuesta"],
            "Tasa Sesión Global Man. (%)": kpis["tasa_sesion_global_manual"],
            # Email KPIs
            "Contactados Email": kpis["contactados_email"],
            "Respuestas Email": kpis["respuestas_email"],
            "Sesiones Email": kpis["sesiones_agendadas_email"],
            "Tasa Respuesta Email (%)": kpis["tasa_respuesta_email_vs_contactados"],
            "Tasa Sesión Email (vs Resp.) (%)": kpis["tasa_sesion_email_vs_respuestas"],
            "Tasa Sesión Global Email (%)": kpis["tasa_sesion_global_email"]
        })
    return pd.DataFrame(datos_comparativa)


# --- Carga de Datos Base ---
df_base_campanas_global, df_original_completo_global = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty and df_original_completo_global.empty:
    st.error("No se pudieron cargar datos. La aplicación no puede continuar.")
    st.stop()
elif df_base_campanas_global.empty and not df_original_completo_global.empty : # Only base is empty
    st.warning("No hay datos de campañas activas para análisis de prospección (df_base_campanas_global está vacío), "
                "pero se podrían mostrar totales si hay datos en df_original_completo_global.")
elif df_original_completo_global.empty and not df_base_campanas_global.empty: # Only original is empty (unlikely if base is derived from it)
    st.warning("Los datos originales completos (df_original_completo_global) están vacíos. "
                "Algunos KPIs generales podrían no mostrarse.")


# --- Sección de Selección de Campaña Principal ---
st.markdown("---")
st.subheader("1. Selección de Campaña(s)")

if 'Campaña' in df_original_completo_global.columns and not df_original_completo_global['Campaña'].dropna().empty:
    lista_campanas_disponibles_global = sorted(df_original_completo_global['Campaña'].dropna().unique())
elif 'Campaña' in df_base_campanas_global.columns and not df_base_campanas_global['Campaña'].dropna().empty: # Fallback to base if original is problematic
    lista_campanas_disponibles_global = sorted(df_base_campanas_global['Campaña'].dropna().unique())
    st.warning("Usando lista de campañas desde df_base_campanas_global ya que df_original_completo_global no tiene campañas o está vacío.")
else:
    lista_campanas_disponibles_global = []
    
if not lista_campanas_disponibles_global:
    st.error("No se encontraron nombres de campañas en los datos cargados. La aplicación no puede continuar.")
    st.stop()

st.session_state.campana_seleccion_principal = st.multiselect(
    "Elige la(s) campaña(s) a analizar:",
    options=lista_campanas_disponibles_global,
    default=st.session_state.campana_seleccion_principal,
    key="ms_campana_seleccion_principal"
)

# --- Sección de Filtros Adicionales ---
st.markdown("---")
st.subheader("2. Filtros Adicionales")

if st.button("Limpiar Filtros", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
    st.rerun() 

if not st.session_state.campana_seleccion_principal:
    st.info("Por favor, selecciona al menos una campaña para visualizar los datos y aplicar filtros.")
    st.stop()

# df_campanas_filtradas_por_seleccion: Data filtered by selected campaign names.
# MODIFIED: Ahora se basa en df_original_completo_global para incluir todos los datos de la campaña.
if not df_original_completo_global.empty and 'Campaña' in df_original_completo_global.columns:
    df_campanas_filtradas_por_seleccion = df_original_completo_global[
        df_original_completo_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
    ].copy()
else:
    # Este caso no debería alcanzarse si se seleccionan campañas,
    # ya que df_original_completo_global es la fuente de la lista de campañas.
    # Se crea un DataFrame vacío para prevenir errores posteriores si, por alguna razón, sucede.
    df_campanas_filtradas_por_seleccion = pd.DataFrame()
    st.warning("Advertencia: No se pudo obtener la base de datos completa original para las campañas seleccionadas. Los resultados pueden estar incompletos.")


# If after selecting campaigns, df_campanas_filtradas_por_seleccion is empty,
# it means there's no data for these campaigns in df_original_completo_global.
# (This comment is adjusted based on the new logic)
# df_final_analisis_campana will be based on this, so if it's empty, manual KPIs will be 0.
# Email KPIs are calculated on df_final_analisis_campana, so they also need this df to be populated.

with st.expander("Aplicar filtros detallados a la(s) campaña(s) seleccionada(s)", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        if not df_campanas_filtradas_por_seleccion.empty: # Only show these filters if there's data to filter
            if "¿Quién Prospecto?" in df_campanas_filtradas_por_seleccion.columns:
                opciones_prospectador_camp = ["– Todos –"] + sorted(
                    df_campanas_filtradas_por_seleccion["¿Quién Prospecto?"].dropna().astype(str).unique()
                )
                default_prospectador = st.session_state.campana_filtro_prospectador
                if not all(p in opciones_prospectador_camp for p in default_prospectador):
                    default_prospectador = ["– Todos –"] if "– Todos –" in opciones_prospectador_camp else []
                st.session_state.campana_filtro_prospectador = st.multiselect(
                    "¿Quién Prospectó? (Manual)", options=opciones_prospectador_camp,
                    default=default_prospectador, key="ms_campana_prospectador"
                )
            else:
                st.caption("Columna '¿Quién Prospecto?' no disponible.")
                st.session_state.campana_filtro_prospectador = ["– Todos –"]

            if "Pais" in df_campanas_filtradas_por_seleccion.columns:
                opciones_pais_camp = ["– Todos –"] + sorted(
                    df_campanas_filtradas_por_seleccion["Pais"].dropna().astype(str).unique()
                )
                default_pais = st.session_state.campana_filtro_pais
                if not all(p in opciones_pais_camp for p in default_pais):
                    default_pais = ["– Todos –"] if "– Todos –" in opciones_pais_camp else []
                st.session_state.campana_filtro_pais = st.multiselect(
                    "País del Prospecto", options=opciones_pais_camp,
                    default=default_pais, key="ms_campana_pais"
                )
            else:
                st.caption("Columna 'Pais' no disponible.")
                st.session_state.campana_filtro_pais = ["– Todos –"]
        else:
            st.caption("No hay datos para aplicar filtros de Prospectador o País para las campañas seleccionadas.")
            st.session_state.campana_filtro_prospectador = ["– Todos –"]
            st.session_state.campana_filtro_pais = ["– Todos –"]


    with col_f2:
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        date_filter_column = "Fecha de Invite" 

        if not df_campanas_filtradas_por_seleccion.empty and \
            date_filter_column in df_campanas_filtradas_por_seleccion.columns and \
            pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion[date_filter_column]):
            valid_dates = df_campanas_filtradas_por_seleccion[date_filter_column].dropna()
            if not valid_dates.empty:
                min_fecha_invite_camp = valid_dates.min().date()
                max_fecha_invite_camp = valid_dates.max().date()
        
        val_fecha_ini = st.date_input(
            f"{date_filter_column} Desde:", 
            value=st.session_state.campana_filtro_fecha_ini,
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_ini",
            disabled=df_campanas_filtradas_por_seleccion.empty or date_filter_column not in df_campanas_filtradas_por_seleccion.columns or not pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion.get(date_filter_column))

        )
        val_fecha_fin = st.date_input(
            f"{date_filter_column} Hasta:", 
            value=st.session_state.campana_filtro_fecha_fin, 
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_fin",
            disabled=df_campanas_filtradas_por_seleccion.empty or date_filter_column not in df_campanas_filtradas_por_seleccion.columns or not pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion.get(date_filter_column))
        )
        if df_campanas_filtradas_por_seleccion.empty or date_filter_column not in df_campanas_filtradas_por_seleccion.columns or not pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion.get(date_filter_column)):
            st.caption(f"Columna '{date_filter_column}' no disponible o no es de tipo fecha para filtrar.")
            st.session_state.campana_filtro_fecha_ini = None
            st.session_state.campana_filtro_fecha_fin = None
        else:
            st.session_state.campana_filtro_fecha_ini = val_fecha_ini
            st.session_state.campana_filtro_fecha_fin = val_fecha_fin


# Aplicar filtros
df_aplicar_filtros_temp = df_campanas_filtradas_por_seleccion.copy()

if not df_aplicar_filtros_temp.empty: # Proceed with filtering only if there's data
    if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
        if "¿Quién Prospecto?" in df_aplicar_filtros_temp.columns:
            df_aplicar_filtros_temp = df_aplicar_filtros_temp[
                df_aplicar_filtros_temp["¿Quién Prospecto?"].isin(st.session_state.campana_filtro_prospectador)
            ]
    if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
        if "Pais" in df_aplicar_filtros_temp.columns:
            df_aplicar_filtros_temp = df_aplicar_filtros_temp[
                df_aplicar_filtros_temp["Pais"].isin(st.session_state.campana_filtro_pais)
            ]

    fecha_ini_aplicar = st.session_state.campana_filtro_fecha_ini
    fecha_fin_aplicar = st.session_state.campana_filtro_fecha_fin

    if date_filter_column in df_aplicar_filtros_temp.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros_temp[date_filter_column]):
        # Ensure the column is actually datetime before filtering
        df_aplicar_filtros_temp[date_filter_column] = pd.to_datetime(df_aplicar_filtros_temp[date_filter_column], errors='coerce')
        
        if fecha_ini_aplicar and fecha_fin_aplicar:
            fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
            fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
            df_aplicar_filtros_temp = df_aplicar_filtros_temp[
                (df_aplicar_filtros_temp[date_filter_column].notna()) &
                (df_aplicar_filtros_temp[date_filter_column] >= fecha_ini_dt) &
                (df_aplicar_filtros_temp[date_filter_column] <= fecha_fin_dt)
            ]
        elif fecha_ini_aplicar:
            fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
            df_aplicar_filtros_temp = df_aplicar_filtros_temp[
                (df_aplicar_filtros_temp[date_filter_column].notna()) &
                (df_aplicar_filtros_temp[date_filter_column] >= fecha_ini_dt)
            ]
        elif fecha_fin_aplicar:
            fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
            df_aplicar_filtros_temp = df_aplicar_filtros_temp[
                (df_aplicar_filtros_temp[date_filter_column].notna()) &
                (df_aplicar_filtros_temp[date_filter_column] <= fecha_fin_dt)
            ]

df_final_analisis_campana = df_aplicar_filtros_temp.copy()

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")

# 1. Total de registros originales para la(s) campaña(s) seleccionada(s)
total_registros_originales_seleccion = 0
if not df_original_completo_global.empty and 'Campaña' in df_original_completo_global.columns:
    df_temp_original_seleccion = df_original_completo_global[
        df_original_completo_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
    ]
    if not df_temp_original_seleccion.empty:
        total_registros_originales_seleccion = len(df_temp_original_seleccion)

st.metric("Total Registros Originales en Campaña(s) Seleccionada(s)", f"{total_registros_originales_seleccion:,}")
st.caption("Este es el número total de entradas listadas bajo el/los nombre(s) de campaña seleccionados en los datos fuente, antes de cualquier filtro o preparación para prospección.")

# 2. Total de prospectos disponibles en la base de campañas (df_base_campanas_global) para la selección
total_prospectos_disponibles_base = 0
if not df_base_campanas_global.empty and 'Campaña' in df_base_campanas_global.columns:
    df_temp_disponibles_seleccion = df_base_campanas_global[
        df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
    ]
    if not df_temp_disponibles_seleccion.empty:
        total_prospectos_disponibles_base = len(df_temp_disponibles_seleccion)
st.metric("Prospectos Disponibles para Prospección (Base de Campaña)", f"{total_prospectos_disponibles_base:,}")
st.caption("Este es el número de registros con un nombre de campaña válido en la base preparada para prospección (df_base_campanas_global), antes de aplicar filtros adicionales de esta página (como prospectador, país o fecha).")


st.markdown("---") # Separator before detailed KPIs


if df_final_analisis_campana.empty and total_registros_originales_seleccion == 0 and total_prospectos_disponibles_base == 0:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s), y no hay registros base ni originales para mostrar.")
else:
    # kpis_calculados_campana_agregado se calcula sobre df_final_analisis_campana
    # que es df_original_completo_global -> filtrado por campana_seleccion_principal -> filtrado por filtros de página
    kpis_calculados_campana_agregado = calcular_kpis_df_campana(df_final_analisis_campana)
    
    st.markdown("### Indicadores Clave (KPIs) - Agregado de Selección (Manual y Email) _(Basado en prospectos post-filtros de página)_")
    
    st.subheader("Métricas de Prospección Manual")
    # 'total_prospectos_manual' en kpis_calculados_campana_agregado es len(df_final_analisis_campana)
    # que es el número de prospectos DESPUÉS de todos los filtros de la página.
    kpi_cols_manual_agg = st.columns(4)
    kpi_cols_manual_agg[0].metric("Prospectos en Proceso (Post-Filtros)", f"{kpis_calculados_campana_agregado['total_prospectos_manual']:,}")
    kpi_cols_manual_agg[1].metric("Invites Aceptadas", f"{kpis_calculados_campana_agregado['invites_aceptadas']:,}",
                                f"{kpis_calculados_campana_agregado['tasa_aceptacion']:.1f}% de Prosp. en Proceso")
    kpi_cols_manual_agg[2].metric("Respuestas 1er Msj (Manual)", f"{kpis_calculados_campana_agregado['respuestas_primer_mensaje']:,}",
                                f"{kpis_calculados_campana_agregado['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas")
    kpi_cols_manual_agg[3].metric("Sesiones Agendadas (Manual)", f"{kpis_calculados_campana_agregado['sesiones_agendadas_manual']:,}",
                                f"{kpis_calculados_campana_agregado['tasa_sesion_global_manual']:.1f}% de Prosp. en Proceso")
    if kpis_calculados_campana_agregado['sesiones_agendadas_manual'] > 0 and kpis_calculados_campana_agregado['respuestas_primer_mensaje'] > 0 :
            st.caption(f"Tasa de Sesiones Man. vs Respuestas Man. (Agregado): {kpis_calculados_campana_agregado['tasa_sesion_vs_respuesta']:.1f}%")

    st.subheader("Métricas de Campaña por Email")
    kpi_cols_email_agg = st.columns(4)
    kpi_cols_email_agg[0].metric("Contactados por Email (Post-Filtros)", f"{kpis_calculados_campana_agregado['contactados_email']:,}")
    kpi_cols_email_agg[1].metric("Respuestas Email (Post-Filtros)", f"{kpis_calculados_campana_agregado['respuestas_email']:,}",
                                f"{kpis_calculados_campana_agregado['tasa_respuesta_email_vs_contactados']:.1f}% de Contactados Email")
    kpi_cols_email_agg[2].metric("Sesiones Agendadas (Email) (Post-Filtros)", f"{kpis_calculados_campana_agregado['sesiones_agendadas_email']:,}",
                                f"{kpis_calculados_campana_agregado['tasa_sesion_global_email']:.1f}% de Contactados Email")
    
    total_sesiones_combinadas = kpis_calculados_campana_agregado['sesiones_agendadas_manual'] + kpis_calculados_campana_agregado['sesiones_agendadas_email']
    kpi_cols_email_agg[3].metric("TOTAL SESIONES (Man + Email) (Post-Filtros)", f"{total_sesiones_combinadas:,}")
    
    if kpis_calculados_campana_agregado['sesiones_agendadas_email'] > 0 and kpis_calculados_campana_agregado['respuestas_email'] > 0:
        st.caption(f"Tasa de Sesiones Email vs Respuestas Email (Agregado): {kpis_calculados_campana_agregado['tasa_sesion_email_vs_respuestas']:.1f}%")

    if df_final_analisis_campana.empty and (total_registros_originales_seleccion > 0 or total_prospectos_disponibles_base > 0) : # Added condition
            st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro de página para la(s) campaña(s) seleccionada(s). "
                        "Los KPIs de Prospección Manual y Email de arriba serán 0 o no representativos de una acción filtrada.")


    st.markdown("### Embudo de Conversión - Prospección Manual (Agregado de Selección y Filtros de Página)")
    # Adjusted title for clarity with new base data
    titulo_embudo_modificado = "Embudo de Conversión Manual (Todos los Datos de Campaña, Post-Filtros de Página)"
    if kpis_calculados_campana_agregado["total_prospectos_manual"] == total_registros_originales_seleccion and not any([
        st.session_state.campana_filtro_prospectador != ["– Todos –"] and st.session_state.campana_filtro_prospectador,
        st.session_state.campana_filtro_pais != ["– Todos –"] and st.session_state.campana_filtro_pais,
        st.session_state.campana_filtro_fecha_ini,
        st.session_state.campana_filtro_fecha_fin
    ]):
        # If no filters applied and total_prospectos_manual matches total_registros_originales_seleccion
        # it means we are looking at all original data for the campaign.
        pass # Keep modified title
    else:
        # If filters are applied, or if total_prospectos_manual is different due to other reasons
        titulo_embudo_modificado = "Embudo de Conversión Manual (Agregado de Selección y Filtros de Página)"
        
    mostrar_embudo_para_campana(kpis_calculados_campana_agregado, titulo_embudo_modificado)


    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla y gráficos comparan las campañas seleccionadas, considerando los filtros de página aplicados.")
        
        # df_final_analisis_campana is already filtered by page filters.
        # generar_tabla_comparativa_campanas_filtrada will iterate through selected campaigns
        # and filter df_final_analisis_campana for each to calculate KPIs.
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros de página aplicados)")
            
            # Adjust column name based on the new understanding of "total_prospectos_manual"
            df_tabla_comp = df_tabla_comp.rename(columns={"Prospectos Proc. Manual (Post-Filtros)": "Prospectos en Proceso (Post-Filtros)"})
            
            cols_enteros_comp = [
                "Prospectos en Proceso (Post-Filtros)", "Aceptadas", "Respuestas Manual", "Sesiones Manual",
                "Contactados Email", "Respuestas Email", "Sesiones Email"
            ]
            format_dict_comp = {
                "Tasa Aceptación (%)": "{:.1f}%", 
                "Tasa Respuesta Man. (vs Acept.) (%)": "{:.1f}%", 
                "Tasa Sesiones Man. (vs Resp.) (%)": "{:.1f}%", 
                "Tasa Sesión Global Man. (%)": "{:.1f}%",
                "Tasa Respuesta Email (%)": "{:.1f}%",
                "Tasa Sesión Email (vs Resp.) (%)": "{:.1f}%",
                "Tasa Sesión Global Email (%)": "{:.1f}%"
            }
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            
            st.dataframe(df_tabla_comp.sort_values(by="Tasa Sesión Global Man. (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            
            st.subheader("Gráficos Comparativos (con filtros de página aplicados)")
            df_graf_comp_tsg_manual = df_tabla_comp[df_tabla_comp["Prospectos en Proceso (Post-Filtros)"] > 0].sort_values(by="Tasa Sesión Global Man. (%)", ascending=False)
            if not df_graf_comp_tsg_manual.empty:
                fig_comp_tsg_man = px.bar(df_graf_comp_tsg_manual, x="Campaña", y="Tasa Sesión Global Man. (%)", title="Comparativa: Tasa de Sesión Global (Manual)", text="Tasa Sesión Global Man. (%)", color="Campaña")
                fig_comp_tsg_man.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg_man.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg_man, use_container_width=True)
            else: st.caption("No hay datos suficientes para el gráfico de tasa de sesión global manual comparativa.")

            df_graf_comp_tsg_email = df_tabla_comp[df_tabla_comp["Contactados Email"] > 0].sort_values(by="Tasa Sesión Global Email (%)", ascending=False)
            if not df_graf_comp_tsg_email.empty:
                fig_comp_tsg_email = px.bar(df_graf_comp_tsg_email, x="Campaña", y="Tasa Sesión Global Email (%)", title="Comparativa: Tasa de Sesión Global (Email)", text="Tasa Sesión Global Email (%)", color="Campaña")
                fig_comp_tsg_email.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg_email.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg_email, use_container_width=True)
            else: st.caption("No hay datos suficientes para el gráfico de tasa de sesión global por email comparativa.")

            df_graf_comp_vol_sesiones = df_tabla_comp.melt(
                id_vars=['Campaña'], 
                value_vars=['Sesiones Manual', 'Sesiones Email'], 
                var_name='Tipo de Sesión', 
                value_name='Cantidad de Sesiones'
            )
            df_graf_comp_vol_sesiones = df_graf_comp_vol_sesiones[df_graf_comp_vol_sesiones["Cantidad de Sesiones"] > 0]

            if not df_graf_comp_vol_sesiones.empty:
                fig_comp_vol = px.bar(df_graf_comp_vol_sesiones, x="Campaña", y="Cantidad de Sesiones", 
                                        title="Comparativa: Volumen de Sesiones (Manual vs Email)", 
                                        text="Cantidad de Sesiones", color="Tipo de Sesión", barmode="group")
                fig_comp_vol.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_comp_vol.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_vol, use_container_width=True)
            else: st.caption("No hay campañas con sesiones agendadas (manual o email) para el gráfico de volumen comparativo.")
        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros de página aplicados.")

    st.markdown("### Rendimiento por Prospectador (Prospección Manual - para la selección actual y filtros de página)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        # Ensure the calculation is done on a valid DataFrame, even if empty after filters
        if not df_final_analisis_campana.empty:
            df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?", dropna=False).apply(lambda x: pd.Series(calcular_kpis_df_campana(x))).reset_index()
        else:
            df_prospectador_camp = pd.DataFrame(columns=["¿Quién Prospecto?", "total_prospectos_manual", "invites_aceptadas", 
                                                        "respuestas_primer_mensaje", "sesiones_agendadas_manual", "tasa_sesion_global_manual"])


        df_prospectador_camp_display = df_prospectador_camp[
            (df_prospectador_camp['total_prospectos_manual'] > 0) 
        ][[
            "¿Quién Prospecto?", "total_prospectos_manual", "invites_aceptadas", 
            "respuestas_primer_mensaje", "sesiones_agendadas_manual", "tasa_sesion_global_manual"
        ]].rename(columns={
            "total_prospectos_manual": "Prosp. en Proceso (Post-Filtros)", # Adjusted Name
            "invites_aceptadas": "Aceptadas", 
            "respuestas_primer_mensaje": "Respuestas Manual", 
            "sesiones_agendadas_manual": "Sesiones Manual", 
            "tasa_sesion_global_manual": "Tasa Sesión Global Man. (%)"
        }).sort_values(by="Sesiones Manual", ascending=False)
        
        cols_enteros_prosp = ["Prosp. en Proceso (Post-Filtros)", "Aceptadas", "Respuestas Manual", "Sesiones Manual"]
        format_dict_prosp = {"Tasa Sesión Global Man. (%)": "{:.1f}%"}
        for col_int_prosp in cols_enteros_prosp:
            if col_int_prosp in df_prospectador_camp_display.columns:
                df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int)
                format_dict_prosp[col_int_prosp] = "{:,}"
        
        if not df_prospectador_camp_display.empty:
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            
            mostrar_grafico_prospectador = False
            if ("– Todos –" in st.session_state.campana_filtro_prospectador or not st.session_state.campana_filtro_prospectador) and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True
            elif st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador and len(st.session_state.campana_filtro_prospectador) > 1 and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True

            if mostrar_grafico_prospectador:
                fig_prosp_camp_bar = px.bar(df_prospectador_camp_display.sort_values(by="Tasa Sesión Global Man. (%)", ascending=False), 
                                            x="¿Quién Prospecto?", y="Tasa Sesión Global Man. (%)", 
                                            title="Tasa de Sesión Global (Manual) por Prospectador (Selección Actual, Post-Filtros)", 
                                            text="Tasa Sesión Global Man. (%)", color="Tasa Sesión Global Man. (%)") 
                fig_prosp_camp_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar, use_container_width=True)
        else: st.caption("No hay datos de rendimiento por prospectador manual para la selección actual y filtros de página.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible para el análisis de rendimiento por prospectador.")

    st.markdown("### Detalle de Prospectos (para la selección actual y filtros de página aplicados)")
    # df_final_analisis_campana contains the data after all selections and filters, based on df_original_completo_global.
    # We want to display the original rows from df_original_completo_global that correspond to these filtered indices.
    # However, if df_final_analisis_campana was manipulated (e.g. columns added/removed not in original),
    # directly using its indices on df_original_completo_global might be tricky if indices are not perfectly aligned or reset.
    # A safer approach is to display df_final_analisis_campana itself, as it's the data used for KPIs.
    # The request for "detalle original" might imply showing all original columns for the filtered rows.
    # The existing logic uses indices from df_final_analisis_campana on df_original_completo_global.
    # Let's ensure indices are compatible. df_final_analisis_campana is a copy and then filtered version of
    # a slice of df_original_completo_global, so indices should be fine.
    
    df_detalle_para_mostrar = df_final_analisis_campana.copy() # This already has all records for the campaign, post-filters

    if not df_detalle_para_mostrar.empty:
        df_display_tabla_campana_detalle = pd.DataFrame()
        # Use columns from df_detalle_para_mostrar, which is the actual filtered data
        for col_orig in df_detalle_para_mostrar.columns:
            if pd.api.types.is_datetime64_any_dtype(df_detalle_para_mostrar[col_orig]):
                df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_detalle_para_mostrar[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            elif pd.api.types.is_numeric_dtype(df_detalle_para_mostrar[col_orig]) and \
                (df_detalle_para_mostrar[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or \
                pd.api.types.is_integer_dtype(df_detalle_para_mostrar[col_orig].dropna())):
                df_display_tabla_campana_detalle[col_orig] = df_detalle_para_mostrar[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A") 
            else:
                df_display_tabla_campana_detalle[col_orig] = df_detalle_para_mostrar[col_orig].astype(str).fillna("N/A")
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()
        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_para_mostrar) # Use df_detalle_para_mostrar for download
        
        nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle de Campaña Filtrado (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con la selección y filtros de página actuales.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊 "
)
