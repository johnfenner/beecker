# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import sys
import os
from datos.carga_datos import cargar_y_limpiar_datos #
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar #

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado.")

# --- Funciones de Ayuda Específicas para esta Página ---

@st.cache_data
def obtener_datos_base_campanas():
    df_completo = cargar_y_limpiar_datos() #
    if df_completo is None or df_completo.empty:
        return pd.DataFrame(), pd.DataFrame()

    if 'Campaña' not in df_completo.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo

    df_base_campanas = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy()

    # Columnas de fecha manuales existentes
    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"]
    for col in date_cols_to_check:
        if col in df_base_campanas.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas[col]):
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
        if col in df_completo.columns and not pd.api.types.is_datetime64_any_dtype(df_completo[col]):
             df_completo[col] = pd.to_datetime(df_completo[col], errors='coerce')

    # Asegurarnos de convertir también la columna de fecha de sesión por email
    email_date_cols = ["Fecha de Sesion Email"]
    for col in email_date_cols:
        if col in df_base_campanas.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas[col]):
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
        if col in df_completo.columns and not pd.api.types.is_datetime64_any_dtype(df_completo[col]):
            df_completo[col] = pd.to_datetime(df_completo[col], errors='coerce')
    
    # Asegurarnos que las columnas booleanas de email existan, sino crearlas vacías (o con "no" por defecto)
    # Esto evita errores en calcular_kpis_df_campana si las columnas no existen
    email_bool_cols = ["Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email"]
    for df_proc in [df_base_campanas, df_completo]:
        for col_bool_email in email_bool_cols:
            if col_bool_email not in df_proc.columns:
                df_proc[col_bool_email] = "no" # O pd.NA, dependiendo de cómo limpiar_valor_kpi maneje esto

    for df_proc in [df_base_campanas, df_completo]:
        if "Avatar" in df_proc.columns:
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar) #

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

def calcular_kpis_df_campana(df):
    if df.empty:
        return {
            "total_prospectos": 0, "invites_aceptadas": 0,
            "primeros_mensajes_enviados": 0, "respuestas_primer_mensaje": 0,
            "sesiones_agendadas": 0, "tasa_aceptacion": 0,
            "tasa_respuesta_vs_aceptadas": 0, "tasa_sesion_vs_respuesta": 0,
            "tasa_sesion_global": 0,
            # KPIs email
            "contactados_email": 0, "respuestas_email": 0, "sesiones_email": 0,
            "tasa_respuesta_email": 0, "tasa_sesion_email": 0
        }

    # — KPIs manuales existentes —
    total_prospectos = len(df)
    invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df.get("¿Invite Aceptada?", pd.Series(dtype=str))) #
    primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan"] #
        for x in df.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df.get("Sesion Agendada?", pd.Series(dtype=str))) #

    tasa_aceptacion = (invites_aceptadas / total_prospectos * 100) if total_prospectos > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0
    tasa_sesion_vs_respuesta = (sesiones_agendadas / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global = (sesiones_agendadas / total_prospectos * 100) if total_prospectos > 0 else 0

    # — KPIs email —
    contactados_email = sum(limpiar_valor_kpi(x) == "si" for x in df.get("Contactados por Campaña", pd.Series(dtype=str))) #
    respuestas_email = sum(limpiar_valor_kpi(x) == "si" for x in df.get("Respuesta Email", pd.Series(dtype=str))) #
    sesiones_email = sum(limpiar_valor_kpi(x) == "si" for x in df.get("Sesion Agendada Email", pd.Series(dtype=str))) #

    tasa_respuesta_email = (respuestas_email / contactados_email * 100) if contactados_email > 0 else 0
    tasa_sesion_email = (sesiones_email / respuestas_email * 100) if respuestas_email > 0 else 0
    
    return {
        # KPIs manuales…
        "total_prospectos": int(total_prospectos), "invites_aceptadas": int(invites_aceptadas),
        "primeros_mensajes_enviados": int(primeros_mensajes_enviados),
        "respuestas_primer_mensaje": int(respuestas_primer_mensaje),
        "sesiones_agendadas": int(sesiones_agendadas), 
        "tasa_aceptacion": tasa_aceptacion,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta": tasa_sesion_vs_respuesta,
        "tasa_sesion_global": tasa_sesion_global,
        # KPIs email
        "contactados_email": int(contactados_email),
        "respuestas_email": int(respuestas_email),
        "sesiones_email": int(sesiones_email),
        "tasa_respuesta_email": tasa_respuesta_email,
        "tasa_sesion_email": tasa_sesion_email
    }

def mostrar_embudo_para_campana(kpis_campana, titulo_embudo="Embudo de Conversión de Campaña"):
    etapas_embudo = [
        "Prospectos en Campaña", "Invites Aceptadas",
        "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas"
    ]
    cantidades_embudo = [
        kpis_campana["total_prospectos"], kpis_campana["invites_aceptadas"],
        kpis_campana["primeros_mensajes_enviados"], kpis_campana["respuestas_primer_mensaje"],
        kpis_campana["sesiones_agendadas"]
    ]
    if sum(cantidades_embudo) == 0:
        st.info("No hay datos suficientes para generar el embudo de conversión manual para la selección actual.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    porcentajes_vs_anterior = [100.0] # El primero es el 100% de sí mismo (o no se muestra)
    if df_embudo['Cantidad'][0] > 0: # Para evitar división por cero si no hay prospectos
        textos = [f"{df_embudo['Cantidad'][0]:,}"]
        for i in range(1, len(df_embudo)):
            porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
            porcentajes_vs_anterior.append(porcentaje)
            textos.append(f"{df_embudo['Cantidad'][i]:,} ({porcentaje:.1f}%)")
        df_embudo['Texto'] = textos
    else:
        df_embudo['Texto'] = df_embudo['Cantidad'].apply(lambda x: f"{x:,}")


    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text') # textinfo='text' para usar la columna Texto
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(f"Embudo manual basado en {kpis_campana['total_prospectos']:,} prospectos iniciales para la selección actual.")

def mostrar_embudo_email(kpis, titulo="Embudo Email (Campaña)"):
    etapas = ["Contactados Email", "Respuestas Email", "Sesiones Email"]
    cantidades = [
        kpis["contactados_email"],
        kpis["respuestas_email"],
        kpis["sesiones_email"]
    ]
    if sum(cantidades) == 0:
        st.info("No hay datos de email suficientes para generar el embudo.")
        return
    
    df_e = pd.DataFrame({"Etapa": etapas, "Cantidad": cantidades})
    
    # Calcular porcentajes vs anterior para el texto
    textos_embudo_email = []
    if cantidades[0] > 0: # Contactados Email
        textos_embudo_email.append(f"{cantidades[0]:,}")
        if cantidades[0] > 0 and cantidades[1] >= 0: # Respuestas Email
            tasa_resp_email = (cantidades[1] / cantidades[0] * 100) if cantidades[0] > 0 else 0
            textos_embudo_email.append(f"{cantidades[1]:,} ({tasa_resp_email:.1f}%)")
            if cantidades[1] > 0 and cantidades[2] >= 0: # Sesiones Email
                tasa_ses_email = (cantidades[2] / cantidades[1] * 100) if cantidades[1] > 0 else 0
                textos_embudo_email.append(f"{cantidades[2]:,} ({tasa_ses_email:.1f}%)")
            elif cantidades[2] == 0 :
                 textos_embudo_email.append(f"0 (0.0%)")
            else: # Caso donde respuestas es 0 pero podria haber sesiones (ilógico, pero por robustez)
                textos_embudo_email.append(f"{cantidades[2]:,}")

        elif cantidades[1] == 0: # Si respuestas es 0, sesiones también debería serlo o mostrar 0%
            textos_embudo_email.append(f"0 (0.0%)")
            textos_embudo_email.append(f"0 (0.0%)")

    else: # Si no hay contactados, todo es 0
        textos_embudo_email = [f"{c:,}" for c in cantidades]

    # Asegurar que textos_embudo_email tenga la misma longitud que etapas
    if len(textos_embudo_email) < len(etapas):
        textos_embudo_email.extend([f"{cantidades[i]:,}" for i in range(len(textos_embudo_email), len(etapas))])
    
    df_e["Texto"] = textos_embudo_email[:len(etapas)]


    fig = px.funnel(df_e, y="Etapa", x="Cantidad", title=titulo, text="Texto", category_orders={"Etapa": etapas})
    fig.update_traces(textposition='inside', textinfo='text')
    st.plotly_chart(fig, use_container_width=True)
    if kpis["contactados_email"] > 0:
      st.caption(f"Embudo email basado en {kpis['contactados_email']:,} prospectos contactados por email para la selección actual.")

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
            # KPIs manuales…
            "Prospectos": kpis["total_prospectos"], 
            "Aceptadas": kpis["invites_aceptadas"],
            "Respuestas": kpis["respuestas_primer_mensaje"], 
            "Sesiones": kpis["sesiones_agendadas"],
            "Tasa Aceptación (%)": kpis["tasa_aceptacion"],
            "Tasa Respuesta (vs Acept.) (%)": kpis["tasa_respuesta_vs_aceptadas"],
            "Tasa Sesiones (vs Resp.) (%)": kpis["tasa_sesion_vs_respuesta"],
            "Tasa Sesión Global (%)": kpis["tasa_sesion_global"],
            # KPIs email
            "Contactados Email": kpis["contactados_email"],
            "Respuestas Email": kpis["respuestas_email"],
            "Sesiones Email": kpis["sesiones_email"],
            "Tasa Resp Email (%)": kpis["tasa_respuesta_email"],
            "Tasa Sesión Email (%)": kpis["tasa_sesion_email"],
        })
    return pd.DataFrame(datos_comparativa)


# --- Carga de Datos Base ---
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No se pudieron cargar los datos base de campañas o están vacíos.")
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

# --- Sección de Filtros Adicionales ---
st.markdown("---")
st.subheader("2. Filtros Adicionales")

if st.button("Limpiar Filtros", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros_total"):
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
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        default_prospectador = st.session_state.campana_filtro_prospectador
        if not all(p in opciones_prospectador_camp for p in default_prospectador if p != "– Todos –"): 
            default_prospectador = ["– Todos –"] 
        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó?", options=opciones_prospectador_camp,
            default=default_prospectador, key="ms_campana_prospectador"
        )

        opciones_pais_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["Pais"].dropna().astype(str).unique()
        )
        default_pais = st.session_state.campana_filtro_pais
        if not all(p in opciones_pais_camp for p in default_pais if p != "– Todos –"):
             default_pais = ["– Todos –"] 
        st.session_state.campana_filtro_pais = st.multiselect(
            "País del Prospecto", options=opciones_pais_camp,
            default=default_pais, key="ms_campana_pais"
        )
    with col_f2:
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        # Usaremos 'Fecha de Invite' como la columna de fecha principal para el filtro de rango.
        # Si necesitas filtrar por 'Fecha de Sesion Email' u otra, ajusta esta lógica.
        columna_fecha_para_filtro = "Fecha de Invite" # Podrías hacerlo configurable si es necesario

        if columna_fecha_para_filtro in df_campanas_filtradas_por_seleccion.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion[columna_fecha_para_filtro]):
            valid_dates = df_campanas_filtradas_por_seleccion[columna_fecha_para_filtro].dropna()
            if not valid_dates.empty:
                min_fecha_invite_camp = valid_dates.min().date()
                max_fecha_invite_camp = valid_dates.max().date()
        
        val_fecha_ini = st.date_input(
            f"{columna_fecha_para_filtro} Desde:", 
            value=st.session_state.get('di_campana_fecha_ini'), 
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_ini" 
        )
        val_fecha_fin = st.date_input(
            f"{columna_fecha_para_filtro} Hasta:", 
            value=st.session_state.get('di_campana_fecha_fin'), 
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_fin" 
        )
        st.session_state.campana_filtro_fecha_ini = val_fecha_ini
        st.session_state.campana_filtro_fecha_fin = val_fecha_fin


# Aplicar filtros
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
columna_fecha_para_filtro_aplicacion = "Fecha de Invite" # Asegúrate que sea la misma que arriba

if fecha_ini_aplicar and fecha_fin_aplicar and \
   columna_fecha_para_filtro_aplicacion in df_aplicar_filtros.columns and \
   pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros[columna_fecha_para_filtro_aplicacion]):
    try:
        fecha_ini_dt = pd.to_datetime(fecha_ini_aplicar)
        fecha_fin_dt = pd.to_datetime(fecha_fin_aplicar) + pd.Timedelta(days=1) # para incluir el día final completo
        df_aplicar_filtros = df_aplicar_filtros[
            (df_aplicar_filtros[columna_fecha_para_filtro_aplicacion] >= fecha_ini_dt) &
            (df_aplicar_filtros[columna_fecha_para_filtro_aplicacion] < fecha_fin_dt) # Usar < para el día siguiente a las 00:00
        ]
    except Exception as e:
        st.error(f"Error al convertir fechas para el filtro: {e}")

elif fecha_ini_aplicar and columna_fecha_para_filtro_aplicacion in df_aplicar_filtros.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros[columna_fecha_para_filtro_aplicacion]):
    try:
        fecha_ini_dt = pd.to_datetime(fecha_ini_aplicar)
        df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros[columna_fecha_para_filtro_aplicacion] >= fecha_ini_dt]
    except Exception as e:
        st.error(f"Error al convertir fecha de inicio para el filtro: {e}")
elif fecha_fin_aplicar and columna_fecha_para_filtro_aplicacion in df_aplicar_filtros.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros[columna_fecha_para_filtro_aplicacion]):
    try:
        fecha_fin_dt = pd.to_datetime(fecha_fin_aplicar) + pd.Timedelta(days=1)
        df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros[columna_fecha_para_filtro_aplicacion] < fecha_fin_dt]
    except Exception as e:
        st.error(f"Error al convertir fecha de fin para el filtro: {e}")

df_final_analisis_campana = df_aplicar_filtros.copy()

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")

if df_final_analisis_campana.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
else:
    kpis_calculados_campana_agregado = calcular_kpis_df_campana(df_final_analisis_campana)
    
    st.markdown("### 📈 Indicadores Clave Manuales (Agregado de Selección)")
    kpi_cols_agg = st.columns(4)
    kpi_cols_agg[0].metric("Total Prospectos", f"{kpis_calculados_campana_agregado['total_prospectos']:,}")
    kpi_cols_agg[1].metric("Invites Aceptadas", f"{kpis_calculados_campana_agregado['invites_aceptadas']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_aceptacion']:.1f}% de Prospectos")
    kpi_cols_agg[2].metric("Respuestas 1er Msj", f"{kpis_calculados_campana_agregado['respuestas_primer_mensaje']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas")
    kpi_cols_agg[3].metric("Sesiones Agendadas (Manual)", f"{kpis_calculados_campana_agregado['sesiones_agendadas']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_sesion_global']:.1f}% de Prospectos")
    if kpis_calculados_campana_agregado['sesiones_agendadas'] > 0 and kpis_calculados_campana_agregado['respuestas_primer_mensaje'] > 0 :
         st.caption(f"Tasa de Sesiones Manuales vs Respuestas (Agregado): {kpis_calculados_campana_agregado['tasa_sesion_vs_respuesta']:.1f}%")

    # KPIs de Email
    st.markdown("### 📧 Indicadores Email (Agregado de Selección)")
    email_cols = st.columns(3)
    email_cols[0].metric(
        "Contactados Email", f"{kpis_calculados_campana_agregado['contactados_email']:,}"
    )
    email_cols[1].metric(
        "Respuestas Email", f"{kpis_calculados_campana_agregado['respuestas_email']:,}",
        f"{kpis_calculados_campana_agregado['tasa_respuesta_email']:.1f}%"
    )
    email_cols[2].metric(
        "Sesiones Email", f"{kpis_calculados_campana_agregado['sesiones_email']:,}",
        f"{kpis_calculados_campana_agregado['tasa_sesion_email']:.1f}%"
    )
    
    # Embudos
    col_embudo1, col_embudo2 = st.columns(2)
    with col_embudo1:
        st.markdown("### Embudo de Conversión – Canal Manual")
        mostrar_embudo_para_campana(kpis_calculados_campana_agregado, "Embudo Manual (Agregado)")
    
    with col_embudo2:
        st.markdown("### Embudo de Conversión – Canal Email")
        mostrar_embudo_email(kpis_calculados_campana_agregado, "Embudo Email (Agregado)")


    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla y gráficos comparan las campañas seleccionadas, considerando los filtros de '¿Quién Prospectó?', 'País' y 'Fechas' aplicados arriba.")
        
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros aplicados)")
            
            cols_enteros_comp = [
                "Prospectos", "Aceptadas", "Respuestas", "Sesiones",
                "Contactados Email", "Respuestas Email", "Sesiones Email"
            ]
            format_dict_comp = {
                "Tasa Aceptación (%)": "{:.1f}%", 
                "Tasa Respuesta (vs Acept.) (%)": "{:.1f}%", 
                "Tasa Sesiones (vs Resp.) (%)": "{:.1f}%", 
                "Tasa Sesión Global (%)": "{:.1f}%",
                "Tasa Resp Email (%)": "{:.1f}%", # NUEVO
                "Tasa Sesión Email (%)": "{:.1f}%" # NUEVO
            }
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    # Asegurar que la columna se convierta a numérico antes de intentar formatear como entero
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}" # Formato con comas para miles

            # Actualización del format_dict_comp para incluir los nuevos campos de email
            format_dict_comp.update({
                "Contactados Email": "{:,}",
                "Respuestas Email": "{:,}",
                "Sesiones Email": "{:,}",
                "Tasa Resp Email (%)": "{:.1f}%",
                "Tasa Sesión Email (%)": "{:.1f}%"
            })
            
            # Reordenar columnas para mejor visualización (opcional)
            column_order = [
                "Campaña", "Prospectos", "Aceptadas", "Tasa Aceptación (%)", 
                "Respuestas", "Tasa Respuesta (vs Acept.) (%)", 
                "Sesiones", "Tasa Sesiones (vs Resp.) (%)", "Tasa Sesión Global (%)",
                "Contactados Email", "Respuestas Email", "Tasa Resp Email (%)",
                "Sesiones Email", "Tasa Sesión Email (%)"
            ]
            # Filtrar columnas existentes en df_tabla_comp para evitar errores si alguna no está
            column_order_exist = [col for col in column_order if col in df_tabla_comp.columns]


            st.dataframe(df_tabla_comp[column_order_exist].sort_values(by="Tasa Sesión Global (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            
            # Gráficos comparativos (se pueden añadir más para los KPIs de email si se desea)
            st.subheader("Gráfico: Tasa de Sesión Global por Campaña (con filtros aplicados)")
            df_graf_comp_tasa_global = df_tabla_comp[df_tabla_comp["Prospectos"] > 0].sort_values(by="Tasa Sesión Global (%)", ascending=False)
            if not df_graf_comp_tasa_global.empty:
                fig_comp_tsg = px.bar(df_graf_comp_tasa_global, x="Campaña", y="Tasa Sesión Global (%)", title="Comparativa: Tasa de Sesión Global (Manual)", text="Tasa Sesión Global (%)", color="Campaña")
                fig_comp_tsg.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg, use_container_width=True)
            else: st.caption("No hay datos suficientes para el gráfico de tasa de sesión global comparativa con los filtros actuales.")

            st.subheader("Gráfico: Tasa de Sesión Email por Campaña (con filtros aplicados)")
            df_graf_comp_tasa_email = df_tabla_comp[df_tabla_comp["Contactados Email"] > 0].sort_values(by="Tasa Sesión Email (%)", ascending=False)
            if not df_graf_comp_tasa_email.empty:
                fig_comp_tse = px.bar(df_graf_comp_tasa_email, x="Campaña", y="Tasa Sesión Email (%)", title="Comparativa: Tasa de Sesión (Email)", text="Tasa Sesión Email (%)", color="Campaña")
                fig_comp_tse.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tse.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tse, use_container_width=True)
            else: st.caption("No hay datos suficientes para el gráfico de tasa de sesión email comparativa con los filtros actuales.")


            st.subheader("Gráfico: Volumen de Sesiones Agendadas (Manual) por Campaña (con filtros aplicados)")
            df_graf_comp_vol_sesiones = df_tabla_comp[df_tabla_comp["Sesiones"] > 0].sort_values(by="Sesiones", ascending=False)
            if not df_graf_comp_vol_sesiones.empty:
                fig_comp_vol = px.bar(df_graf_comp_vol_sesiones, x="Campaña", y="Sesiones", title="Comparativa: Volumen de Sesiones Agendadas (Manual)", text="Sesiones", color="Campaña")
                fig_comp_vol.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_comp_vol.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_vol, use_container_width=True)
            else: st.caption("No hay campañas con sesiones manuales agendadas para el gráfico de volumen comparativo con los filtros actuales.")

            st.subheader("Gráfico: Volumen de Sesiones Agendadas (Email) por Campaña (con filtros aplicados)")
            df_graf_comp_vol_sesiones_email = df_tabla_comp[df_tabla_comp["Sesiones Email"] > 0].sort_values(by="Sesiones Email", ascending=False)
            if not df_graf_comp_vol_sesiones_email.empty:
                fig_comp_vol_email = px.bar(df_graf_comp_vol_sesiones_email, x="Campaña", y="Sesiones Email", title="Comparativa: Volumen de Sesiones Agendadas (Email)", text="Sesiones Email", color="Campaña")
                fig_comp_vol_email.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_comp_vol_email.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_vol_email, use_container_width=True)
            else: st.caption("No hay campañas con sesiones email agendadas para el gráfico de volumen comparativo con los filtros actuales.")

        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    st.markdown("### Rendimiento por Prospectador (para la selección actual)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        # Recalcular KPIs por prospectador, ahora la función devuelve también los de email
        df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?").apply(lambda x: pd.Series(calcular_kpis_df_campana(x))).reset_index()
        
        # Seleccionar columnas relevantes para mostrar, incluyendo las de email
        columnas_prospectador_display = [
            "¿Quién Prospecto?", "total_prospectos", "invites_aceptadas", 
            "respuestas_primer_mensaje", "sesiones_agendadas", "tasa_sesion_global",
            "contactados_email", "respuestas_email", "sesiones_email", "tasa_sesion_email" # Nuevas columnas
        ]
        # Filtrar columnas que realmente existen en df_prospectador_camp para evitar KeyErrors
        columnas_prospectador_display = [col for col in columnas_prospectador_display if col in df_prospectador_camp.columns]

        df_prospectador_camp_display = df_prospectador_camp[
            (df_prospectador_camp['total_prospectos'] > 0) | (df_prospectador_camp.get('contactados_email', 0) > 0) # Mostrar si hay actividad manual O email
        ][columnas_prospectador_display].rename(columns={
            "total_prospectos": "Prospectos Man.", 
            "invites_aceptadas": "Aceptadas Man.", 
            "respuestas_primer_mensaje": "Respuestas Man.", 
            "sesiones_agendadas": "Sesiones Man.", 
            "tasa_sesion_global": "Tasa Sesión Global Man. (%)",
            "contactados_email": "Contactados Email",
            "respuestas_email": "Respuestas Email",
            "sesiones_email": "Sesiones Email",
            "tasa_sesion_email": "Tasa Sesión Email (%)"
        }).sort_values(by="Sesiones Man.", ascending=False) # O por otra métrica combinada

        cols_enteros_prosp = ["Prospectos Man.", "Aceptadas Man.", "Respuestas Man.", "Sesiones Man.", "Contactados Email", "Respuestas Email", "Sesiones Email"]
        format_dict_prosp = {
            "Tasa Sesión Global Man. (%)": "{:.1f}%",
            "Tasa Sesión Email (%)": "{:.1f}%"
            }

        for col_int_prosp in cols_enteros_prosp:
            if col_int_prosp in df_prospectador_camp_display.columns:
                df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int)
                format_dict_prosp[col_int_prosp] = "{:,}"
        
        if not df_prospectador_camp_display.empty:
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            
            mostrar_grafico_prospectador_manual = False
            if "– Todos –" in st.session_state.campana_filtro_prospectador and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador_manual = True
            elif len(st.session_state.campana_filtro_prospectador) > 1 and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador_manual = True
            
            if mostrar_grafico_prospectador_manual and "Tasa Sesión Global Man. (%)" in df_prospectador_camp_display.columns:
                fig_prosp_camp_bar_manual = px.bar(df_prospectador_camp_display.sort_values(by="Tasa Sesión Global Man. (%)", ascending=False), 
                                             x="¿Quién Prospecto?", y="Tasa Sesión Global Man. (%)", 
                                             title="Tasa de Sesión Global Manual por Prospectador", text="Tasa Sesión Global Man. (%)", color="¿Quién Prospecto?") #Color por Prospectador
                fig_prosp_camp_bar_manual.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar_manual.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar_manual, use_container_width=True)

            if mostrar_grafico_prospectador_manual and "Tasa Sesión Email (%)" in df_prospectador_camp_display.columns and df_prospectador_camp_display["Contactados Email"].sum() > 0 : # Solo si hay datos de email
                fig_prosp_camp_bar_email = px.bar(df_prospectador_camp_display[df_prospectador_camp_display["Contactados Email"] > 0].sort_values(by="Tasa Sesión Email (%)", ascending=False), 
                                             x="¿Quién Prospecto?", y="Tasa Sesión Email (%)", 
                                             title="Tasa de Sesión Email por Prospectador", text="Tasa Sesión Email (%)", color="¿Quién Prospecto?") #Color por Prospectador
                fig_prosp_camp_bar_email.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar_email.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar_email, use_container_width=True)

        else: st.caption("No hay datos de rendimiento por prospectador para la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible.")

    st.markdown("### Detalle de Prospectos (para la selección actual)")
    indices_filtrados = df_final_analisis_campana.index
    df_detalle_original_filtrado = df_original_completo.loc[indices_filtrados].copy()
    if not df_detalle_original_filtrado.empty:
        # Seleccionar y reordenar columnas para la tabla de detalle, incluyendo las nuevas de email
        columnas_detalle = [
            "Campaña", "Prospecto", "¿Quién Prospecto?", "Pais", "Ciudad", "Cargo", "Empresa", 
            "Fecha de Invite", "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", 
            "Sesion Agendada?", "Fecha Sesion", 
            "Contactados por Campaña", "Respuesta Email", "Sesion Agendada Email", "Fecha de Sesion Email", # Nuevas columnas de email
            "Status General", "Motivo No Interes", "Observaciones", "Link al Perfil"
        ]
        # Mantener solo las columnas que existen en el DataFrame para evitar errores
        columnas_detalle_existentes = [col for col in columnas_detalle if col in df_detalle_original_filtrado.columns]
        df_display_tabla_campana_detalle_seleccionada = df_detalle_original_filtrado[columnas_detalle_existentes]


        df_display_tabla_campana_detalle_formateada = pd.DataFrame()
        for col_orig in df_display_tabla_campana_detalle_seleccionada.columns: # Usar el df con columnas seleccionadas
            if pd.api.types.is_datetime64_any_dtype(df_display_tabla_campana_detalle_seleccionada[col_orig]):
                 df_display_tabla_campana_detalle_formateada[col_orig] = pd.to_datetime(df_display_tabla_campana_detalle_seleccionada[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            elif pd.api.types.is_numeric_dtype(df_display_tabla_campana_detalle_seleccionada[col_orig]) and \
                 (df_display_tabla_campana_detalle_seleccionada[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or \
                  pd.api.types.is_integer_dtype(df_display_tabla_campana_detalle_seleccionada[col_orig].dropna())):
                 df_display_tabla_campana_detalle_formateada[col_orig] = df_display_tabla_campana_detalle_seleccionada[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A")
            else:
                 df_display_tabla_campana_detalle_formateada[col_orig] = df_display_tabla_campana_detalle_seleccionada[col_orig].astype(str).fillna("N/A")
        
        st.dataframe(df_display_tabla_campana_detalle_formateada, height=400, use_container_width=True)
        
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()

        # Usar el dataframe con columnas seleccionadas y datos originales para el Excel
        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_display_tabla_campana_detalle_seleccionada)
        
        nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle de Campaña (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
