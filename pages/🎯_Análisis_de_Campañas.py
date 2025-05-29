# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import sys # No se usa directamente, pero puede ser útil para debugging de paths
import os  # No se usa directamente

# Asumiendo que estas funciones están correctamente definidas en tus módulos
from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado, incluyendo flujos de prospección manual y por email.")

# --- Funciones de Ayuda Específicas para esta Página ---

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

    # Convertir columnas de fecha a datetime
    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion", "Fecha de Sesion Email"]
    for df_proc in [df_base_campanas, df_completo]: # Aplicar a ambos DataFrames
        for col in date_cols_to_check:
            if col in df_proc.columns and not pd.api.types.is_datetime64_any_dtype(df_proc[col]):
                df_proc[col] = pd.to_datetime(df_proc[col], errors='coerce')
        
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
    if df_filtrado_campana.empty:
        return {
            "total_registros_seleccion": 0,
            # Manual KPIs
            "manual_prospectados_o_invitados": 0, "manual_invites_aceptadas": 0,
            "manual_primeros_mensajes_enviados": 0, "manual_respuestas_primer_mensaje": 0,
            "manual_sesiones_agendadas": 0,
            "manual_tasa_invite_enviada_vs_seleccion": 0, "manual_tasa_aceptacion_vs_invitados": 0,
            "manual_tasa_respuesta_vs_aceptadas": 0, "manual_tasa_sesion_vs_respuesta": 0,
            "manual_tasa_sesion_global_vs_invitados": 0,
            # Email KPIs
            "email_contactados": 0, "email_respuestas": 0, "email_sesiones_agendadas": 0,
            "email_tasa_respuesta_vs_contactados": 0, "email_tasa_sesion_vs_respuesta": 0,
            "email_tasa_sesion_global_vs_contactados": 0,
            # Combined
            "total_sesiones_agendadas": 0
        }

    total_registros_seleccion = len(df_filtrado_campana)

    # --- KPIs de Prospección Manual ---
    manual_prospectados_o_invitados = df_filtrado_campana["Fecha de Invite"].notna().sum() if "Fecha de Invite" in df_filtrado_campana else 0
    manual_invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str)))
    manual_primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    manual_respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] # Añadido "none" por si acaso
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    manual_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str)))

    manual_tasa_invite_enviada_vs_seleccion = (manual_prospectados_o_invitados / total_registros_seleccion * 100) if total_registros_seleccion > 0 else 0
    manual_tasa_aceptacion_vs_invitados = (manual_invites_aceptadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    manual_tasa_respuesta_vs_aceptadas = (manual_respuestas_primer_mensaje / manual_invites_aceptadas * 100) if manual_invites_aceptadas > 0 else 0
    manual_tasa_sesion_vs_respuesta = (manual_sesiones_agendadas / manual_respuestas_primer_mensaje * 100) if manual_respuestas_primer_mensaje > 0 else 0
    manual_tasa_sesion_global_vs_invitados = (manual_sesiones_agendadas / manual_prospectados_o_invitados * 100) if manual_prospectados_o_invitados > 0 else 0
    
    # --- KPIs de Prospección por Email ---
    # Asegúrate que los nombres de columna 'Contactados por Campaña', 'Respuesta Email', 'Sesion Agendada Email' son exactos.
    email_contactados = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Contactados por Campaña", pd.Series(dtype=str)))
    email_respuestas = sum(limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] for x in df_filtrado_campana.get("Respuesta Email", pd.Series(dtype=str)))
    email_sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada Email", pd.Series(dtype=str)))

    email_tasa_respuesta_vs_contactados = (email_respuestas / email_contactados * 100) if email_contactados > 0 else 0
    email_tasa_sesion_vs_respuesta = (email_sesiones_agendadas / email_respuestas * 100) if email_respuestas > 0 else 0
    email_tasa_sesion_global_vs_contactados = (email_sesiones_agendadas / email_contactados * 100) if email_contactados > 0 else 0

    # --- KPIs Combinados ---
    total_sesiones_agendadas = manual_sesiones_agendadas + email_sesiones_agendadas # Asume que son mutuamente excluyentes o que una sesión es única

    return {
        "total_registros_seleccion": int(total_registros_seleccion),
        # Manual
        "manual_prospectados_o_invitados": int(manual_prospectados_o_invitados),
        "manual_invites_aceptadas": int(manual_invites_aceptadas),
        "manual_primeros_mensajes_enviados": int(manual_primeros_mensajes_enviados),
        "manual_respuestas_primer_mensaje": int(manual_respuestas_primer_mensaje),
        "manual_sesiones_agendadas": int(manual_sesiones_agendadas),
        "manual_tasa_invite_enviada_vs_seleccion": manual_tasa_invite_enviada_vs_seleccion,
        "manual_tasa_aceptacion_vs_invitados": manual_tasa_aceptacion_vs_invitados,
        "manual_tasa_respuesta_vs_aceptadas": manual_tasa_respuesta_vs_aceptadas,
        "manual_tasa_sesion_vs_respuesta": manual_tasa_sesion_vs_respuesta,
        "manual_tasa_sesion_global_vs_invitados": manual_tasa_sesion_global_vs_invitados,
        # Email
        "email_contactados": int(email_contactados),
        "email_respuestas": int(email_respuestas),
        "email_sesiones_agendadas": int(email_sesiones_agendadas),
        "email_tasa_respuesta_vs_contactados": email_tasa_respuesta_vs_contactados,
        "email_tasa_sesion_vs_respuesta": email_tasa_sesion_vs_respuesta,
        "email_tasa_sesion_global_vs_contactados": email_tasa_sesion_global_vs_contactados,
        # Combined
        "total_sesiones_agendadas": int(total_sesiones_agendadas)
    }

def mostrar_embudo_para_campana(kpis_campana, tipo_embudo="manual", titulo_embudo_base="Embudo de Conversión"):
    etapas_embudo, cantidades_embudo = [], []
    sub_caption = ""

    if tipo_embudo == "manual":
        etapas_embudo = [
            "Registros en Selección", "Invites Enviadas", "Invites Aceptadas",
            "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas (Manual)"
        ]
        cantidades_embudo = [
            kpis_campana["total_registros_seleccion"], kpis_campana["manual_prospectados_o_invitados"],
            kpis_campana["manual_invites_aceptadas"], kpis_campana["manual_primeros_mensajes_enviados"],
            kpis_campana["manual_respuestas_primer_mensaje"], kpis_campana["manual_sesiones_agendadas"]
        ]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Manual"
        sub_caption = f"Embudo manual basado en {kpis_campana['total_registros_seleccion']:,} registros iniciales en la selección."
        if kpis_campana["manual_prospectados_o_invitados"] == 0 and kpis_campana["manual_sesiones_agendadas"] == 0 : # Si no hay ni prospectados ni sesiones, no mostrar
             st.info(f"No hay datos suficientes para el embudo de flujo manual para la selección actual.")
             return


    elif tipo_embudo == "email":
        # Solo mostrar si hay contactados por email
        if kpis_campana["email_contactados"] == 0 and kpis_campana["email_sesiones_agendadas"] == 0:
            st.info(f"No hay datos de contacto por email para generar este embudo en la selección actual.")
            return
        etapas_embudo = [
             "Contactados por Email", "Respuestas Email", "Sesiones Agendadas (Email)"
        ] # Podrías añadir "Registros en Selección" si quieres que parta del mismo total general
          # "total_registros_seleccion"
        cantidades_embudo = [
            kpis_campana["email_contactados"], kpis_campana["email_respuestas"],
            kpis_campana["email_sesiones_agendadas"]
        ]
        titulo_embudo = f"{titulo_embudo_base} - Flujo Email"
        sub_caption = f"Embudo de email basado en {kpis_campana['email_contactados']:,} prospectos contactados por email."
    
    else:
        st.error("Tipo de embudo no reconocido.")
        return

    if sum(cantidades_embudo) == 0:
        st.info(f"No hay datos suficientes para generar el embudo de '{tipo_embudo}' para la selección actual.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    # Filtrar etapas con 0 para que el embudo no se corte prematuramente si una etapa intermedia es 0 pero las siguientes no
    # df_embudo = df_embudo[df_embudo["Cantidad"] > 0] # Considerar si esto es deseable o no
    # if df_embudo.empty:
    #    st.info(f"No hay datos positivos para generar el embudo de '{tipo_embudo}' después del filtrado de ceros.")
    #    return

    porcentajes_vs_anterior = [100.0] if not df_embudo.empty else []
    for i in range(1, len(df_embudo)):
        porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
        porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    
    # Calcular % vs el primer paso del embudo actual
    porcentajes_vs_primero = [100.0] if not df_embudo.empty else []
    if not df_embudo.empty and df_embudo['Cantidad'][0] > 0:
        for i in range(1, len(df_embudo)):
            porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][0] * 100)
            porcentajes_vs_primero.append(porcentaje)
    df_embudo['% vs Inicio Embudo'] = porcentajes_vs_primero


    df_embudo['Texto'] = df_embudo.apply(
        lambda row: f"{row['Cantidad']:,}<br>({row['% vs Anterior']:.1f}% vs Ant.)<br>({row['% vs Inicio Embudo']:.1f}% vs Inicio)", axis=1
    )
    if not df_embudo.empty: # Asegurar que el texto de la primera fila es correcto
         df_embudo.loc[0, 'Texto'] = f"{df_embudo.loc[0, 'Cantidad']:,}<br>(100% Inicio)"


    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text',
                             connector={"line": {"color": "royalblue", "dash": "dot", "width": 2}})
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(sub_caption)

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
            "Registros Sel.": kpis["total_registros_seleccion"],
            # Manual
            "Inv. Enviadas": kpis["manual_prospectados_o_invitados"],
            "Inv. Aceptadas": kpis["manual_invites_aceptadas"],
            "Resp. 1er Msj": kpis["manual_respuestas_primer_mensaje"],
            "Sesiones Manual": kpis["manual_sesiones_agendadas"],
            "Tasa Acept. (vs Env.) (%)": kpis["manual_tasa_aceptacion_vs_invitados"],
            "Tasa Resp. (vs Acept.) (%)": kpis["manual_tasa_respuesta_vs_aceptadas"],
            "Tasa Sesión Man. (vs Resp.) (%)": kpis["manual_tasa_sesion_vs_respuesta"],
            "Tasa Sesión Man. Global (vs Inv. Env.) (%)": kpis["manual_tasa_sesion_global_vs_invitados"],
            # Email
            "Email Contact.": kpis["email_contactados"],
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
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No hay datos base de campañas para analizar. Revisa la carga de datos.")
    st.stop()

# --- Sección de Selección de Campaña Principal ---
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

# Mostrar totales originales de las campañas seleccionadas ANTES de filtros de página
if st.session_state.campana_seleccion_principal:
    st.markdown("#### Totales de Registros Originales en Campaña(s) Seleccionada(s)")
    cols_totales_orig = st.columns(len(st.session_state.campana_seleccion_principal))
    for i, camp_name in enumerate(st.session_state.campana_seleccion_principal):
        total_records_in_camp = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name].shape[0]
        # Intentar obtener fechas de inicio y fin de la campaña original (si existen datos de invite)
        df_camp_original = df_base_campanas_global[df_base_campanas_global['Campaña'] == camp_name]
        min_fecha_camp, max_fecha_camp = None, None
        if "Fecha de Invite" in df_camp_original.columns and df_camp_original["Fecha de Invite"].notna().any():
            min_fecha_camp = df_camp_original["Fecha de Invite"].min().strftime('%d/%m/%Y')
            max_fecha_camp = df_camp_original["Fecha de Invite"].max().strftime('%d/%m/%Y')
        
        fecha_info = ""
        if min_fecha_camp and max_fecha_camp:
            fecha_info = f"<br><small>Actividad: {min_fecha_camp} - {max_fecha_camp}</small>"
        
        with cols_totales_orig[i]:
            st.metric(label=f"'{camp_name}'", value=f"{total_records_in_camp:,} registros")
            if fecha_info:
                st.markdown(fecha_info, unsafe_allow_html=True)
    st.caption("Estos son los totales de registros por campaña antes de aplicar cualquier filtro de la página (Prospectador, País, Fechas de Invite).")


# --- Sección de Filtros Adicionales ---
st.markdown("---")
st.subheader("2. Filtros Adicionales (aplican a los datos de las campañas seleccionadas)")

if st.button("Limpiar Filtros de Página", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
    st.rerun()

if not st.session_state.campana_seleccion_principal:
    st.info("Por favor, selecciona al menos una campaña para visualizar los datos y aplicar filtros.")
    st.stop()

df_campanas_filtradas_por_seleccion = df_base_campanas_global[
    df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
].copy()

with st.expander("Aplicar filtros detallados a la(s) campaña(s) seleccionada(s)", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        # Filtro Prospectador
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        default_prospectador = st.session_state.campana_filtro_prospectador
        if not all(p in opciones_prospectador_camp for p in default_prospectador):
            default_prospectador = ["– Todos –"] if "– Todos –" in opciones_prospectador_camp else []
        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó? (Filtro para prospección manual)", options=opciones_prospectador_camp,
            default=default_prospectador, key="ms_campana_prospectador"
        )
        # Filtro País
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
    with col_f2:
        # Filtro Fechas (basado en Fecha de Invite para prospección manual)
        # Nota: Este filtro de fecha actualmente se basa en "Fecha de Invite".
        # Si necesitas filtrar por "Fecha de Sesion Email" u otra, se requeriría lógica adicional
        # o un selector de qué columna de fecha usar para el filtro.
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        if "Fecha de Invite" in df_campanas_filtradas_por_seleccion.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion["Fecha de Invite"]):
            valid_dates = df_campanas_filtradas_por_seleccion["Fecha de Invite"].dropna()
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
df_aplicar_filtros = df_campanas_filtradas_por_seleccion.copy()
if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
    df_aplicar_filtros = df_aplicar_filtros[
        df_aplicar_filtros["¿Quién Prospecto?"].isin(st.session_state.campana_filtro_prospectador)
    ]
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_aplicar_filtros = df_aplicar_filtros[
        df_aplicar_filtros["Pais"].isin(st.session_state.campana_filtro_pais)
    ]

fecha_ini_aplicar = st.session_state.campana_filtro_fecha_ini
fecha_fin_aplicar = st.session_state.campana_filtro_fecha_fin

# Aplicar filtro de fecha (basado en Fecha de Invite)
if "Fecha de Invite" in df_aplicar_filtros.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    if fecha_ini_aplicar and fecha_fin_aplicar:
        fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
        fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
        df_aplicar_filtros = df_aplicar_filtros[
            (df_aplicar_filtros["Fecha de Invite"] >= fecha_ini_dt) &
            (df_aplicar_filtros["Fecha de Invite"] <= fecha_fin_dt)
        ]
    elif fecha_ini_aplicar:
        fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
        df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros["Fecha de Invite"] >= fecha_ini_dt]
    elif fecha_fin_aplicar:
        fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
        df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros["Fecha de Invite"] <= fecha_fin_dt]

df_final_analisis_campana = df_aplicar_filtros.copy()

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados Agregados para: {', '.join(st.session_state.campana_seleccion_principal)}")
st.caption("Todos los KPIs y embudos a continuación se basan en la(s) campaña(s) seleccionada(s) Y los filtros de página aplicados (Prospectador, País, Fechas de Invite).")


if df_final_analisis_campana.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
else:
    kpis_agregados = calcular_kpis_df_campana(df_final_analisis_campana)

    st.metric(label="Total Registros en Selección (después de filtros)", value=f"{kpis_agregados['total_registros_seleccion']:,}")
    st.metric(label="Total Sesiones Agendadas (Manual + Email)", value=f"{kpis_agregados['total_sesiones_agendadas']:,}")
    
    st.markdown("---")
    st.markdown("### KPIs de Prospección Manual (Agregado de Selección)")
    if kpis_agregados['manual_prospectados_o_invitados'] > 0 or kpis_agregados['manual_sesiones_agendadas'] > 0 :
        m_cols1 = st.columns(5)
        m_cols1[0].metric("Invites Enviadas", f"{kpis_agregados['manual_prospectados_o_invitados']:,}",
                        f"{kpis_agregados['manual_tasa_invite_enviada_vs_seleccion']:.1f}% de Sel.")
        m_cols1[1].metric("Invites Aceptadas", f"{kpis_agregados['manual_invites_aceptadas']:,}",
                        f"{kpis_agregados['manual_tasa_aceptacion_vs_invitados']:.1f}% de Inv. Env.")
        m_cols1[2].metric("1ros Msj. Enviados", f"{kpis_agregados['manual_primeros_mensajes_enviados']:,}") # Podrías añadir tasa vs invites aceptadas
        m_cols1[3].metric("Respuestas 1er Msj.", f"{kpis_agregados['manual_respuestas_primer_mensaje']:,}",
                        f"{kpis_agregados['manual_tasa_respuesta_vs_aceptadas']:.1f}% de Acept.")
        m_cols1[4].metric("Sesiones (Manual)", f"{kpis_agregados['manual_sesiones_agendadas']:,}",
                        f"{kpis_agregados['manual_tasa_sesion_global_vs_invitados']:.1f}% de Inv. Env.")
        if kpis_agregados['manual_sesiones_agendadas'] > 0 and kpis_agregados['manual_respuestas_primer_mensaje'] > 0:
            st.caption(f"Tasa de Sesiones Manual vs Respuestas: {kpis_agregados['manual_tasa_sesion_vs_respuesta']:.1f}%")
    else:
        st.info("No hay datos de prospección manual significativos para la selección actual.")


    st.markdown("---")
    st.markdown("### KPIs de Prospección por Email (Agregado de Selección)")
    if kpis_agregados['email_contactados'] > 0 or kpis_agregados['email_sesiones_agendadas'] > 0:
        e_cols1 = st.columns(3)
        e_cols1[0].metric("Emails Contactados", f"{kpis_agregados['email_contactados']:,}")
        e_cols1[1].metric("Respuestas Email", f"{kpis_agregados['email_respuestas']:,}",
                        f"{kpis_agregados['email_tasa_respuesta_vs_contactados']:.1f}% de Contact.")
        e_cols1[2].metric("Sesiones (Email)", f"{kpis_agregados['email_sesiones_agendadas']:,}",
                        f"{kpis_agregados['email_tasa_sesion_global_vs_contactados']:.1f}% de Contact.")
        if kpis_agregados['email_sesiones_agendadas'] > 0 and kpis_agregados['email_respuestas'] > 0:
            st.caption(f"Tasa de Sesiones Email vs Respuestas: {kpis_agregados['email_tasa_sesion_vs_respuesta']:.1f}%")
    else:
        st.info("No hay datos de prospección por email significativos para la selección actual.")
    
    st.markdown("---")
    st.subheader("Embudos de Conversión (Agregado de Selección y Filtros)")
    col_embudo1, col_embudo2 = st.columns(2)
    with col_embudo1:
        mostrar_embudo_para_campana(kpis_agregados, tipo_embudo="manual", titulo_embudo_base="Embudo Manual")
    with col_embudo2:
        mostrar_embudo_para_campana(kpis_agregados, tipo_embudo="email", titulo_embudo_base="Embudo Email")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla y gráficos comparan las campañas seleccionadas, considerando los filtros de '¿Quién Prospectó?', 'País' y 'Fechas de Invite' aplicados arriba.")
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros aplicados)")
            # Definir columnas enteras y formato
            cols_enteros_comp = ["Registros Sel.", "Inv. Enviadas", "Inv. Aceptadas", "Resp. 1er Msj", "Sesiones Manual", "Email Contact.", "Email Resp.", "Sesiones Email", "Total Sesiones"]
            format_dict_comp = {
                "Tasa Acept. (vs Env.) (%)": "{:.1f}%", "Tasa Resp. (vs Acept.) (%)": "{:.1f}%",
                "Tasa Sesión Man. (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Man. Global (vs Inv. Env.) (%)": "{:.1f}%",
                "Tasa Resp. Email (vs Cont.) (%)": "{:.1f}%", "Tasa Sesión Email (vs Resp.) (%)": "{:.1f}%",
                "Tasa Sesión Email Global (vs Cont.) (%)": "{:.1f}%"
            }
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            
            # Ordenar por Total Sesiones
            st.dataframe(df_tabla_comp.sort_values(by="Total Sesiones", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)

            # --- Gráficos Comparativos ---
            st.subheader("Gráficos Comparativos (con filtros aplicados)")
            
            # Gráfico: Tasa de Sesión Manual Global
            df_graf_comp_tsg_manual = df_tabla_comp[df_tabla_comp["Inv. Enviadas"] > 0].sort_values(by="Tasa Sesión Man. Global (vs Inv. Env.) (%)", ascending=False)
            if not df_graf_comp_tsg_manual.empty:
                fig_comp_tsg_man = px.bar(df_graf_comp_tsg_manual, x="Campaña", y="Tasa Sesión Man. Global (vs Inv. Env.) (%)", title="Comparativa: Tasa de Sesión Manual Global", text="Tasa Sesión Man. Global (vs Inv. Env.) (%)", color="Campaña")
                fig_comp_tsg_man.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg_man.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg_man, use_container_width=True)

            # Gráfico: Tasa de Sesión Email Global
            df_graf_comp_tsg_email = df_tabla_comp[df_tabla_comp["Email Contact."] > 0].sort_values(by="Tasa Sesión Email Global (vs Cont.) (%)", ascending=False)
            if not df_graf_comp_tsg_email.empty:
                fig_comp_tsg_email = px.bar(df_graf_comp_tsg_email, x="Campaña", y="Tasa Sesión Email Global (vs Cont.) (%)", title="Comparativa: Tasa de Sesión Email Global", text="Tasa Sesión Email Global (vs Cont.) (%)", color="Campaña")
                fig_comp_tsg_email.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg_email.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg_email, use_container_width=True)

            # Gráfico: Volumen Total de Sesiones
            df_graf_comp_vol_sesiones = df_tabla_comp[df_tabla_comp["Total Sesiones"] > 0].sort_values(by="Total Sesiones", ascending=False)
            if not df_graf_comp_vol_sesiones.empty:
                fig_comp_vol = px.bar(df_graf_comp_vol_sesiones, x="Campaña", y="Total Sesiones", title="Comparativa: Volumen Total de Sesiones Agendadas (Manual + Email)", text="Total Sesiones", color="Campaña")
                fig_comp_vol.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_comp_vol.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_vol, use_container_width=True)
            else: st.caption("No hay campañas con sesiones agendadas para el gráfico de volumen comparativo con los filtros actuales.")
        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    st.markdown("### Rendimiento por Prospectador (para la selección actual - Flujo Manual)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        # Aplicar la función calcular_kpis_df_campana a cada grupo de prospectador
        # Esta función ahora devuelve un diccionario más completo, así que extraemos las partes manuales
        df_prospectador_camp_list = []
        for prospectador, df_grupo in df_final_analisis_campana.groupby("¿Quién Prospecto?"):
            kpis_prospectador = calcular_kpis_df_campana(df_grupo)
            if kpis_prospectador["manual_prospectados_o_invitados"] > 0: # Solo mostrar si hubo actividad manual
                df_prospectador_camp_list.append({
                    "¿Quién Prospecto?": prospectador,
                    "Invites Enviadas": kpis_prospectador["manual_prospectados_o_invitados"],
                    "Invites Aceptadas": kpis_prospectador["manual_invites_aceptadas"],
                    "Respuestas 1er Msj": kpis_prospectador["manual_respuestas_primer_mensaje"],
                    "Sesiones (Manual)": kpis_prospectador["manual_sesiones_agendadas"],
                    "Tasa Sesión Global (Manual vs Inv. Env.) (%)": kpis_prospectador["manual_tasa_sesion_global_vs_invitados"]
                })
        
        if df_prospectador_camp_list:
            df_prospectador_camp_display = pd.DataFrame(df_prospectador_camp_list)
            df_prospectador_camp_display = df_prospectador_camp_display.sort_values(by="Sesiones (Manual)", ascending=False)

            cols_enteros_prosp = ["Invites Enviadas", "Invites Aceptadas", "Respuestas 1er Msj", "Sesiones (Manual)"]
            format_dict_prosp = {"Tasa Sesión Global (Manual vs Inv. Env.) (%)": "{:.1f}%"}
            for col_int_prosp in cols_enteros_prosp:
                if col_int_prosp in df_prospectador_camp_display.columns:
                    df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int)
                    format_dict_prosp[col_int_prosp] = "{:,}"
            
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            
            mostrar_grafico_prospectador = False
            if "– Todos –" in st.session_state.campana_filtro_prospectador and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True
            elif len(st.session_state.campana_filtro_prospectador) > 1 and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True

            if mostrar_grafico_prospectador:
                fig_prosp_camp_bar = px.bar(
                    df_prospectador_camp_display.sort_values(by="Tasa Sesión Global (Manual vs Inv. Env.) (%)", ascending=False), 
                    x="¿Quién Prospecto?", y="Tasa Sesión Global (Manual vs Inv. Env.) (%)", 
                    title="Tasa de Sesión Global (Manual) por Prospectador (Selección Actual)", 
                    text="Tasa Sesión Global (Manual vs Inv. Env.) (%)", color="Tasa Sesión Global (Manual vs Inv. Env.) (%)")
                fig_prosp_camp_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar, use_container_width=True)
        else: st.caption("No hay datos de rendimiento por prospectador para la actividad manual en la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible para el análisis por prospectador.")

    st.markdown("### Detalle de Prospectos (para la selección actual)")
    indices_filtrados = df_final_analisis_campana.index
    # Usar df_original_completo para mostrar todas las columnas originales, pero solo para los índices filtrados
    df_detalle_original_filtrado = df_original_completo.loc[indices_filtrados].copy() 
    
    if not df_detalle_original_filtrado.empty:
        # Seleccionar un subconjunto de columnas relevantes para no saturar, o permitir seleccionar
        columnas_relevantes = [
            "Campaña", "Nombre", "Apellido", "¿Quién Prospecto?", "Pais", "Fecha de Invite", 
            "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", "Sesion Agendada?", "Fecha Sesion",
            "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email", "Fecha de Sesion Email", "Avatar" # Añadir las nuevas
        ]
        # Mantener solo columnas que existen en el df
        columnas_existentes_para_detalle = [col for col in columnas_relevantes if col in df_detalle_original_filtrado.columns]
        df_display_tabla_campana_detalle_prep = df_detalle_original_filtrado[columnas_existentes_para_detalle].copy()


        df_display_tabla_campana_detalle = pd.DataFrame()
        for col_orig in df_display_tabla_campana_detalle_prep.columns:
            if pd.api.types.is_datetime64_any_dtype(df_display_tabla_campana_detalle_prep[col_orig]):
                 df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_display_tabla_campana_detalle_prep[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            # elif pd.api.types.is_numeric_dtype(df_display_tabla_campana_detalle_prep[col_orig]) and \
            #      (df_display_tabla_campana_detalle_prep[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or \
            #       pd.api.types.is_integer_dtype(df_display_tabla_campana_detalle_prep[col_orig].dropna())):
            #      df_display_tabla_campana_detalle[col_orig] = df_display_tabla_campana_detalle_prep[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A") # Esto puede ser confuso si 0 es un valor real
            else:
                 df_display_tabla_campana_detalle[col_orig] = df_display_tabla_campana_detalle_prep[col_orig].astype(str).fillna("N/A").replace("nan", "N/A").replace("NaT", "N/A")
        
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        
        @st.cache_data # Cachear la conversión a Excel
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()

        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_original_filtrado) # Usar el df original completo para descarga
        nombres_campana_str = "_".join(st.session_state.campana_seleccion_principal).replace(" ", "")[:50] # Limitar longitud
        nombre_archivo_excel_detalle = f"detalle_campañas_{nombres_campana_str}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle Completo de Selección (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊 con la ayuda de IA."
)
