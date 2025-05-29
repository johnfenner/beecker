# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import sys
import os
# from datos.carga_datos import cargar_y_limpiar_datos #
# from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar #

# Placeholder for imports if running standalone
def cargar_y_limpiar_datos():
    # Create a more comprehensive dummy DataFrame
    data = {
        'Campaña': ['C1 Alpha', 'C1 Alpha', 'C2 Beta', 'C1 Alpha', 'C2 Beta', 'C3 Gamma', 'C1 Alpha', 'C2 Beta', 'C3 Gamma', 'C1 Alpha', None, 'C4 Delta'],
        'Fecha de Invite': pd.to_datetime(['2023-01-01', '2023-01-05', '2023-01-10', '2023-01-15', '2023-01-20', '2023-02-01', '2023-02-05', '2023-02-10', '2023-02-15', '2023-02-20', '2023-03-01', '2023-03-05']),
        '¿Invite Aceptada?': ['si', 'si', 'no', 'si', 'si', 'si', 'no', 'si', 'si', 'si', 'no', 'si'],
        'Fecha Primer Mensaje': pd.to_datetime([None, '2023-01-06', None, '2023-01-17', '2023-01-22', '2023-02-03', None, '2023-02-12', '2023-02-18', '2023-02-21', None, '2023-03-07']),
        'Respuesta Primer Mensaje': ['no', 'si', None, 'si', 'no', 'si', None, 'si', 'no', 'si', None, 'si'],
        'Sesion Agendada?': ['no', 'si', None, 'no', 'no', 'si', None, 'si', 'no', 'no', None, 'si'],
        'Fecha Sesion': pd.to_datetime([None, '2023-01-10', None, None, None, '2023-02-10', None, '2023-02-20', None, None, None, '2023-03-15']),
        '¿Quién Prospecto?': ['Juan', 'Maria', 'Pedro', 'Juan', 'Maria', 'Ana', 'Juan', 'Pedro', 'Ana', 'Maria', 'Juan', 'Luis'],
        'Pais': ['Colombia', 'Mexico', 'Argentina', 'Colombia', 'Mexico', 'España', 'Colombia', 'Argentina', 'España', 'Mexico', 'Colombia', 'Chile'],
        'Avatar': ['Emprendedor Endeudado', 'Dueño PYME', 'Freelancer Exitoso', 'Emprendedor Endeudado', 'Dueño PYME', 'Coach Consolidado', 'Emprendedor Endeudado', 'Freelancer Exitoso', 'Coach Consolidado', 'Dueño PYME', 'Emprendedor Endeudado', 'Nuevo Avatar'],
        'Otros Datos': range(12) # to make rows unique for df_original_completo
    }
    df = pd.DataFrame(data)
    df['Fecha de Invite'] = pd.to_datetime(df['Fecha de Invite'])
    df['Fecha Primer Mensaje'] = pd.to_datetime(df['Fecha Primer Mensaje'], errors='coerce')
    df['Fecha Sesion'] = pd.to_datetime(df['Fecha Sesion'], errors='coerce')
    return df

def limpiar_valor_kpi(valor):
    if pd.isna(valor): return ""
    return str(valor).strip().lower()

def estandarizar_avatar(avatar):
    if pd.isna(avatar): return "No Especificado"
    avatar = str(avatar).strip().lower()
    # Add your specific standardization rules here if any
    # Example:
    if "emprendedor" in avatar and "deuda" in avatar: return "Emprendedor Endeudado"
    if "pyme" in avatar: return "Dueño PYME"
    return avatar.title()


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

    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"]
    for col in date_cols_to_check:
        if col in df_base_campanas.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas[col]):
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
        if col in df_completo.columns and not pd.api.types.is_datetime64_any_dtype(df_completo[col]):
             df_completo[col] = pd.to_datetime(df_completo[col], errors='coerce')

    for df_proc in [df_base_campanas, df_completo]:
        if "Avatar" in df_proc.columns:
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar) #

    return df_base_campanas, df_completo

def inicializar_estado_filtros_campana():
    default_filters = {
        "campana_seleccion_principal": [],
        "campana_filtro_prospectador": ["– Todos –"],
        "campana_filtro_pais": ["– Todos –"],
        "campana_filtro_fecha_ini": None, # Clave para fecha inicio
        "campana_filtro_fecha_fin": None,  # Clave para fecha fin
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
            "prospectos_tras_filtros": 0, "invites_aceptadas": 0,
            "primeros_mensajes_enviados": 0, "respuestas_primer_mensaje": 0,
            "sesiones_agendadas": 0, "tasa_aceptacion": 0,
            "tasa_respuesta_vs_aceptadas": 0, "tasa_sesion_vs_respuesta": 0,
            "tasa_sesion_global": 0
        }
    prospectos_tras_filtros = len(df_filtrado_campana) # Nombre cambiado para claridad
    invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str))) #
    primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan", "none"] #
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str))) #

    tasa_aceptacion = (invites_aceptadas / prospectos_tras_filtros * 100) if prospectos_tras_filtros > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0
    tasa_sesion_vs_respuesta = (sesiones_agendadas / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global = (sesiones_agendadas / prospectos_tras_filtros * 100) if prospectos_tras_filtros > 0 else 0
    return {
        "prospectos_tras_filtros": int(prospectos_tras_filtros), "invites_aceptadas": int(invites_aceptadas),
        "primeros_mensajes_enviados": int(primeros_mensajes_enviados),
        "respuestas_primer_mensaje": int(respuestas_primer_mensaje),
        "sesiones_agendadas": int(sesiones_agendadas), "tasa_aceptacion": tasa_aceptacion,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta": tasa_sesion_vs_respuesta,
        "tasa_sesion_global": tasa_sesion_global,
    }

def mostrar_embudo_para_campana(kpis_campana, titulo_embudo="Embudo de Conversión de Campaña"):
    etapas_embudo = [
        "Prospectos (Tras Filtros)", "Invites Aceptadas", # Nombre cambiado para claridad
        "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas"
    ]
    cantidades_embudo = [
        kpis_campana["prospectos_tras_filtros"], kpis_campana["invites_aceptadas"],
        kpis_campana["primeros_mensajes_enviados"], kpis_campana["respuestas_primer_mensaje"],
        kpis_campana["sesiones_agendadas"]
    ]
    if sum(cantidades_embudo) == 0:
        st.info("No hay datos suficientes para generar el embudo de conversión para la selección actual.")
        return

    df_embudo = pd.DataFrame({"Etapa": etapas_embudo, "Cantidad": cantidades_embudo})
    porcentajes_vs_anterior = [100.0]
    for i in range(1, len(df_embudo)):
        porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100) if df_embudo['Cantidad'][i-1] > 0 else 0.0
        porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    df_embudo['Texto'] = df_embudo.apply(lambda row: f"{row['Cantidad']:,} ({row['% vs Anterior']:.1f}%)", axis=1)

    fig_embudo = px.funnel(df_embudo, y='Etapa', x='Cantidad', title=titulo_embudo, text='Texto', category_orders={"Etapa": etapas_embudo})
    fig_embudo.update_traces(textposition='inside', textinfo='text')
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(f"Embudo basado en {kpis_campana['prospectos_tras_filtros']:,} prospectos (tras filtros) para la selección actual.")

def generar_tabla_comparativa_campanas_filtrada(
        df_filtrado_con_filtros_pagina,
        lista_nombres_campanas_seleccionadas,
        df_base_campanas_global_param # <-- NUEVO PARÁMETRO
    ):
    datos_comparativa = []
    if df_filtrado_con_filtros_pagina.empty or not lista_nombres_campanas_seleccionadas:
        # Incluso si no hay datos filtrados, podríamos querer mostrar los registros originales
        if not lista_nombres_campanas_seleccionadas:
            return pd.DataFrame(datos_comparativa)
        # Si hay campañas seleccionadas pero df_filtrado_con_filtros_pagina está vacío
        for nombre_campana in lista_nombres_campanas_seleccionadas:
            total_datos_originales_campana = len(df_base_campanas_global_param[df_base_campanas_global_param['Campaña'] == nombre_campana])
            kpis = calcular_kpis_df_campana(pd.DataFrame()) # KPIs serán cero
            datos_comparativa.append({
                "Campaña": nombre_campana,
                "Registros Originales": total_datos_originales_campana, # <-- NUEVA MÉTRICA
                "Prospectos (Tras Filtros)": kpis["prospectos_tras_filtros"], # Nombre cambiado
                "Aceptadas": kpis["invites_aceptadas"],
                "Respuestas": kpis["respuestas_primer_mensaje"], "Sesiones": kpis["sesiones_agendadas"],
                "Tasa Aceptación (%)": kpis["tasa_aceptacion"],
                "Tasa Respuesta (vs Acept.) (%)": kpis["tasa_respuesta_vs_aceptadas"],
                "Tasa Sesiones (vs Resp.) (%)": kpis["tasa_sesion_vs_respuesta"],
                "Tasa Sesión Global (%)": kpis["tasa_sesion_global"]
            })
        return pd.DataFrame(datos_comparativa)


    for nombre_campana in lista_nombres_campanas_seleccionadas:
        df_campana_individual_filtrada = df_filtrado_con_filtros_pagina[
            df_filtrado_con_filtros_pagina['Campaña'] == nombre_campana
        ]
        kpis = calcular_kpis_df_campana(df_campana_individual_filtrada)
        
        # Calcular total de datos originales para esta campaña específica
        total_datos_originales_campana = len(df_base_campanas_global_param[df_base_campanas_global_param['Campaña'] == nombre_campana])

        datos_comparativa.append({
            "Campaña": nombre_campana,
            "Registros Originales": total_datos_originales_campana, # <-- NUEVA MÉTRICA
            "Prospectos (Tras Filtros)": kpis["prospectos_tras_filtros"], # Nombre cambiado
            "Aceptadas": kpis["invites_aceptadas"],
            "Respuestas": kpis["respuestas_primer_mensaje"], "Sesiones": kpis["sesiones_agendadas"],
            "Tasa Aceptación (%)": kpis["tasa_aceptacion"],
            "Tasa Respuesta (vs Acept.) (%)": kpis["tasa_respuesta_vs_aceptadas"],
            "Tasa Sesiones (vs Resp.) (%)": kpis["tasa_sesion_vs_respuesta"],
            "Tasa Sesión Global (%)": kpis["tasa_sesion_global"]
        })
    return pd.DataFrame(datos_comparativa)


# --- Carga de Datos Base ---
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()

if df_base_campanas_global.empty:
    st.warning("No se pudieron cargar los datos base de campañas. La aplicación no puede continuar.")
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
].copy() # Este es el df base para las campañas seleccionadas, ANTES de filtros de página

with st.expander("Aplicar filtros detallados a la(s) campaña(s) seleccionada(s)", expanded=True):
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        # Prospectador
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        default_prospectador = st.session_state.campana_filtro_prospectador
        if not isinstance(default_prospectador, list) or not all(p in opciones_prospectador_camp for p in default_prospectador):
            default_prospectador = ["– Todos –"]
        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó?", options=opciones_prospectador_camp,
            default=default_prospectador, key="ms_campana_prospectador"
        )
        # País
        opciones_pais_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["Pais"].dropna().astype(str).unique()
        )
        default_pais = st.session_state.campana_filtro_pais
        if not isinstance(default_pais, list) or not all(p in opciones_pais_camp for p in default_pais):
             default_pais = ["– Todos –"]
        st.session_state.campana_filtro_pais = st.multiselect(
            "País del Prospecto", options=opciones_pais_camp,
            default=default_pais, key="ms_campana_pais"
        )
    with col_f2:
        # Fechas
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        col_fecha_invite = "Fecha de Invite" # Asegúrate que este es el nombre correcto
        if col_fecha_invite in df_campanas_filtradas_por_seleccion.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion[col_fecha_invite]):
            valid_dates = df_campanas_filtradas_por_seleccion[col_fecha_invite].dropna()
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
df_aplicar_filtros = df_campanas_filtradas_por_seleccion.copy() # Comienza con las campañas seleccionadas

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
col_fecha_invite = "Fecha de Invite"

if col_fecha_invite in df_aplicar_filtros.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros[col_fecha_invite]):
    # Asegurar que la columna de fecha no tenga NaT para la comparación, o manejarla
    df_aplicar_filtros[col_fecha_invite] = pd.to_datetime(df_aplicar_filtros[col_fecha_invite], errors='coerce')
    
    if fecha_ini_aplicar and fecha_fin_aplicar:
        fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
        fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
        df_aplicar_filtros = df_aplicar_filtros[
            (df_aplicar_filtros[col_fecha_invite].notna()) &
            (df_aplicar_filtros[col_fecha_invite] >= fecha_ini_dt) &
            (df_aplicar_filtros[col_fecha_invite] <= fecha_fin_dt)
        ]
    elif fecha_ini_aplicar:
        fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
        df_aplicar_filtros = df_aplicar_filtros[
            (df_aplicar_filtros[col_fecha_invite].notna()) &
            (df_aplicar_filtros[col_fecha_invite] >= fecha_ini_dt)
        ]
    elif fecha_fin_aplicar:
        fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
        df_aplicar_filtros = df_aplicar_filtros[
            (df_aplicar_filtros[col_fecha_invite].notna()) &
            (df_aplicar_filtros[col_fecha_invite] <= fecha_fin_dt)
        ]

df_final_analisis_campana = df_aplicar_filtros.copy() # Este es el df FINALMENTE filtrado para análisis

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")

if df_campanas_filtradas_por_seleccion.empty : # Chequea si la selección inicial ya es vacía
    st.warning("No hay datos para la(s) campaña(s) seleccionada(s) en el origen.")
elif df_final_analisis_campana.empty and not df_campanas_filtradas_por_seleccion.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
    # AÚN ASÍ MOSTRAR TOTAL REGISTROS ORIGINALES Y TABLA COMPARATIVA CON REGISTROS ORIGINALES
    
    # Calcular total de datos originales para las campañas seleccionadas (antes de filtros de página)
    df_seleccion_original_para_conteo = df_base_campanas_global[
        df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
    ]
    total_datos_originales_seleccion = len(df_seleccion_original_para_conteo)
    
    st.markdown("### Indicadores Clave (KPIs) - Agregado de Selección")
    kpi_cols_agg = st.columns(5) # Ajustado a 5 columnas
    kpi_cols_agg[0].metric("Total Registros en Campaña(s) (Original)", f"{total_datos_originales_seleccion:,}")

    kpis_vacio = calcular_kpis_df_campana(pd.DataFrame()) # KPIs serán cero
    kpi_cols_agg[1].metric("Prospectos (Tras Filtros)", f"{kpis_vacio['prospectos_tras_filtros']:,}")
    kpi_cols_agg[2].metric("Invites Aceptadas", f"{kpis_vacio['invites_aceptadas']:,}", f"0.0% de Prospectos")
    kpi_cols_agg[3].metric("Respuestas 1er Msj", f"{kpis_vacio['respuestas_primer_mensaje']:,}", f"0.0% de Aceptadas")
    kpi_cols_agg[4].metric("Sesiones Agendadas", f"{kpis_vacio['sesiones_agendadas']:,}", f"0.0% de Prospectos")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla compara las campañas seleccionadas. 'Registros Originales' muestra el total de datos antes de filtros. Otros KPIs consideran los filtros de '¿Quién Prospectó?', 'País' y 'Fechas' aplicados arriba.")
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(
            df_final_analisis_campana, # Será un DF vacío, pero la función lo maneja
            st.session_state.campana_seleccion_principal,
            df_base_campanas_global # <--- Pasar el DF base global
        )
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros aplicados)")
            cols_enteros_comp = ["Registros Originales", "Prospectos (Tras Filtros)", "Aceptadas", "Respuestas", "Sesiones"] # Añadida nueva métrica
            format_dict_comp = {"Tasa Aceptación (%)": "{:.1f}%", "Tasa Respuesta (vs Acept.) (%)": "{:.1f}%", "Tasa Sesiones (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Global (%)": "{:.1f}%"}
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            st.dataframe(df_tabla_comp.sort_values(by="Tasa Sesión Global (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos suficientes para la tabla comparativa.")


else: # df_final_analisis_campana NO está vacío
    st.markdown("### Indicadores Clave (KPIs) - Agregado de Selección")
    
    # Calcular total de datos originales para las campañas seleccionadas (antes de filtros de página)
    df_seleccion_original_para_conteo = df_base_campanas_global[
        df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
    ]
    total_datos_originales_seleccion = len(df_seleccion_original_para_conteo)
    
    kpis_calculados_campana_agregado = calcular_kpis_df_campana(df_final_analisis_campana)
    
    kpi_cols_agg = st.columns(5) # Ajustado a 5 columnas
    kpi_cols_agg[0].metric("Total Registros en Campaña(s) (Original)", f"{total_datos_originales_seleccion:,}")
    kpi_cols_agg[1].metric("Prospectos (Tras Filtros)", f"{kpis_calculados_campana_agregado['prospectos_tras_filtros']:,}")
    kpi_cols_agg[2].metric("Invites Aceptadas", f"{kpis_calculados_campana_agregado['invites_aceptadas']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_aceptacion']:.1f}% de Prospectos")
    kpi_cols_agg[3].metric("Respuestas 1er Msj", f"{kpis_calculados_campana_agregado['respuestas_primer_mensaje']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas")
    kpi_cols_agg[4].metric("Sesiones Agendadas", f"{kpis_calculados_campana_agregado['sesiones_agendadas']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_sesion_global']:.1f}% de Prospectos")
    
    if kpis_calculados_campana_agregado['sesiones_agendadas'] > 0 and kpis_calculados_campana_agregado['respuestas_primer_mensaje'] > 0 :
         st.caption(f"Tasa de Sesiones vs Respuestas (Agregado): {kpis_calculados_campana_agregado['tasa_sesion_vs_respuesta']:.1f}%")

    st.markdown("### Embudo de Conversión - Agregado de Selección")
    mostrar_embudo_para_campana(kpis_calculados_campana_agregado, "Embudo de Conversión (Agregado de Selección y Filtros)")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla compara las campañas seleccionadas. 'Registros Originales' muestra el total de datos antes de filtros. Otros KPIs consideran los filtros de '¿Quién Prospectó?', 'País' y 'Fechas' aplicados arriba.")
        
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(
            df_final_analisis_campana, # Este es el DF con filtros de página aplicados
            st.session_state.campana_seleccion_principal,
            df_base_campanas_global # <--- Pasar el DF base global para conteo original
        )
        
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros aplicados)")
            cols_enteros_comp = ["Registros Originales", "Prospectos (Tras Filtros)", "Aceptadas", "Respuestas", "Sesiones"] # Añadida nueva métrica y nombre cambiado
            format_dict_comp = {"Tasa Aceptación (%)": "{:.1f}%", "Tasa Respuesta (vs Acept.) (%)": "{:.1f}%", "Tasa Sesiones (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Global (%)": "{:.1f}%"}
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            
            st.dataframe(df_tabla_comp.sort_values(by="Tasa Sesión Global (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            
            st.subheader("Gráfico: Tasa de Sesión Global por Campaña (con filtros aplicados)")
            # Usar 'Prospectos (Tras Filtros)' para la condición del gráfico
            df_graf_comp_tasa_global = df_tabla_comp[df_tabla_comp["Prospectos (Tras Filtros)"] > 0].sort_values(by="Tasa Sesión Global (%)", ascending=False)
            if not df_graf_comp_tasa_global.empty:
                fig_comp_tsg = px.bar(df_graf_comp_tasa_global, x="Campaña", y="Tasa Sesión Global (%)", title="Comparativa: Tasa de Sesión Global", text="Tasa Sesión Global (%)", color="Campaña")
                fig_comp_tsg.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_comp_tsg.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_tsg, use_container_width=True)
            else: st.caption("No hay datos suficientes para el gráfico de tasa de sesión global comparativa con los filtros actuales.")
            
            st.subheader("Gráfico: Volumen de Sesiones Agendadas por Campaña (con filtros aplicados)")
            df_graf_comp_vol_sesiones = df_tabla_comp[df_tabla_comp["Sesiones"] > 0].sort_values(by="Sesiones", ascending=False)
            if not df_graf_comp_vol_sesiones.empty:
                fig_comp_vol = px.bar(df_graf_comp_vol_sesiones, x="Campaña", y="Sesiones", title="Comparativa: Volumen de Sesiones Agendadas", text="Sesiones", color="Campaña")
                fig_comp_vol.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_comp_vol.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_comp_vol, use_container_width=True)
            else: st.caption("No hay campañas con sesiones agendadas para el gráfico de volumen comparativo con los filtros actuales.")
        else: st.info("No hay datos suficientes para generar la comparativa entre las campañas seleccionadas con los filtros aplicados.")

    st.markdown("### Rendimiento por Prospectador (para la selección actual)")
    if "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        # Usar 'prospectos_tras_filtros' que es la salida de calcular_kpis_df_campana
        df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?").apply(lambda x: pd.Series(calcular_kpis_df_campana(x))).reset_index()
        df_prospectador_camp_display = df_prospectador_camp[
            (df_prospectador_camp['prospectos_tras_filtros'] > 0) # Usar el nombre correcto
        ][["¿Quién Prospecto?", "prospectos_tras_filtros", "invites_aceptadas", "respuestas_primer_mensaje", "sesiones_agendadas", "tasa_sesion_global"]].rename(
            columns={"prospectos_tras_filtros": "Prospectos (Tras Filtros)", "invites_aceptadas": "Aceptadas", "respuestas_primer_mensaje": "Respuestas", "sesiones_agendadas": "Sesiones", "tasa_sesion_global": "Tasa Sesión Global (%)"}
        ).sort_values(by="Sesiones", ascending=False)
        
        cols_enteros_prosp = ["Prospectos (Tras Filtros)", "Aceptadas", "Respuestas", "Sesiones"] # Nombre cambiado
        format_dict_prosp = {"Tasa Sesión Global (%)": "{:.1f}%"}
        for col_int_prosp in cols_enteros_prosp:
            if col_int_prosp in df_prospectador_camp_display.columns:
                df_prospectador_camp_display[col_int_prosp] = pd.to_numeric(df_prospectador_camp_display[col_int_prosp], errors='coerce').fillna(0).astype(int)
                format_dict_prosp[col_int_prosp] = "{:,}"
        
        if not df_prospectador_camp_display.empty:
            st.dataframe(df_prospectador_camp_display.style.format(format_dict_prosp), use_container_width=True, hide_index=True)
            
            mostrar_grafico_prospectador = False
            if "– Todos –" in st.session_state.campana_filtro_prospectador and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True
            elif isinstance(st.session_state.campana_filtro_prospectador, list) and len(st.session_state.campana_filtro_prospectador) > 1 and "– Todos –" not in st.session_state.campana_filtro_prospectador and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True
            
            if mostrar_grafico_prospectador:
                fig_prosp_camp_bar = px.bar(df_prospectador_camp_display.sort_values(by="Tasa Sesión Global (%)", ascending=False), x="¿Quién Prospecto?", y="Tasa Sesión Global (%)", title="Tasa de Sesión Global por Prospectador (Selección Actual)", text="Tasa Sesión Global (%)", color="Tasa Sesión Global (%)") # Considerar color por ¿Quién Prospecto?
                fig_prosp_camp_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar, use_container_width=True)
        else: st.caption("No hay datos de rendimiento por prospectador para la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible.")

    st.markdown("### Detalle de Prospectos (para la selección actual)")
    # df_final_analisis_campana contiene los índices correctos DESPUÉS de todos los filtros
    # df_original_completo tiene todos los datos originales. Usamos los índices de df_final_analisis_campana para extraer de df_original_completo
    indices_filtrados = df_final_analisis_campana.index 
    # Asegurar que los índices existen en df_original_completo (si se hizo un reset_index en df_final_analisis_campana sin dropear)
    # O mejor, si df_final_analisis_campana es una copia directa con filtros, sus índices son los de df_original_completo
    df_detalle_original_filtrado = df_original_completo.loc[df_original_completo.index.isin(indices_filtrados)].copy()


    if not df_detalle_original_filtrado.empty:
        df_display_tabla_campana_detalle = pd.DataFrame()
        # Definir columnas a mostrar y su orden deseado
        cols_a_mostrar_detalle = [
            "Campaña", "Avatar", "¿Quién Prospecto?", "Pais", "Fecha de Invite", 
            "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", 
            "Sesion Agendada?", "Fecha Sesion"
        ]
        # Tomar solo las columnas que existen en el dataframe
        cols_existentes_detalle = [col for col in cols_a_mostrar_detalle if col in df_detalle_original_filtrado.columns]
        
        for col_orig in cols_existentes_detalle: # Iterar solo sobre las columnas seleccionadas
            if pd.api.types.is_datetime64_any_dtype(df_detalle_original_filtrado[col_orig]):
                 df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_detalle_original_filtrado[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            elif pd.api.types.is_numeric_dtype(df_detalle_original_filtrado[col_orig]) and (df_detalle_original_filtrado[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or pd.api.types.is_integer_dtype(df_detalle_original_filtrado[col_orig].dropna())):
                 df_display_tabla_campana_detalle[col_orig] = df_detalle_original_filtrado[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A") # Considerar no reemplazar 0 con N/A si 0 es un valor válido
            else:
                 df_display_tabla_campana_detalle[col_orig] = df_detalle_original_filtrado[col_orig].astype(str).fillna("N/A")
        
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            # Seleccionar y ordenar columnas también para el Excel
            df_excel_export = df_conv[cols_existentes_detalle].copy()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_excel_export.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()
        
        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_original_filtrado) # Pasar el df con todas las columnas originales
        
        nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
        if not st.session_state.campana_seleccion_principal: # Evitar nombre de archivo feo si no hay selección
            nombre_archivo_excel_detalle = "detalle_campañas_sin_seleccion.xlsx"
        else:
            nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(s.replace(' ', '_') for s in st.session_state.campana_seleccion_principal)}.xlsx"


        st.download_button(label="⬇️ Descargar Detalle de Selección Actual (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
