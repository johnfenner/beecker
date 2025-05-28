import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import sys
import os
from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar
from PIL import Image

# --- Configuración de la Página (única llamada) ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")

# ————————— Teaser Silvestre Dangond —————————
project_root = os.getcwd()
FOTO_ORNITORRINCO_PATH = os.path.join(project_root, "ornitorrinco.png")

# Inicializamos estado para el teaser
if 'first_run' not in st.session_state:
    st.session_state.first_run = True
    st.session_state.msg_count = 0

# Si es la primera vez, mostramos el teaser y detenemos el resto
if st.session_state.first_run:
    if not os.path.exists(FOTO_ORNITORRINCO_PATH):
        st.error(f"No se encontró la imagen teaser en:\n**{FOTO_ORNITORRINCO_PATH}**")
    else:
        teaser = Image.open(FOTO_ORNITORRINCO_PATH)
        st.image(teaser, use_container_width=True)
        st.markdown("### 🎉 ¡Bien chevere! Prepárate para las sorpresas de Silvestre Dangond 🎉")
        if st.button("¡Dame la primera sorpresa!"):
            st.session_state.msg_count = 1
            st.session_state.first_run = False
            st.rerun()
    st.stop()
# ——————————————————————————————————————————————

# --- (Aquí comienza tu código original intacto) ---
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado.")

# --- Funciones de Ayuda Específicas para esta Página ---
# (el resto de tu lógica de cargar datos, limpiar, graficar, etc.)


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
    # Define los valores por defecto explícitamente para cada filtro de la página
    st.session_state.campana_seleccion_principal = []
    st.session_state.campana_filtro_prospectador = ["– Todos –"]
    st.session_state.campana_filtro_pais = ["– Todos –"]
    
    # --- CORRECCIÓN PARA LAS FECHAS ---
    # Asignar None directamente a las claves de los date_input en session_state
    # Estas son las claves que usan los widgets st.date_input
    st.session_state.di_campana_fecha_ini = None # Resetea el valor del widget directamente
    st.session_state.di_campana_fecha_fin = None  # Resetea el valor del widget directamente
    
    # También resetea las claves que usas para leer los valores (por consistencia)
    st.session_state.campana_filtro_fecha_ini = None
    st.session_state.campana_filtro_fecha_fin = None

    st.toast("Todos los filtros de la página de campañas han sido reiniciados.", icon="🧹")
    # El st.rerun() se llamará después del botón en el flujo principal.

# ... (resto de las funciones de ayuda: calcular_kpis_df_campana, mostrar_embudo_para_campana, generar_tabla_comparativa_campanas_filtrada) ...
# (SIN CAMBIOS EN ESAS FUNCIONES)
def calcular_kpis_df_campana(df_filtrado_campana):
    if df_filtrado_campana.empty:
        return {
            "total_prospectos": 0, "invites_aceptadas": 0,
            "primeros_mensajes_enviados": 0, "respuestas_primer_mensaje": 0,
            "sesiones_agendadas": 0, "tasa_aceptacion": 0,
            "tasa_respuesta_vs_aceptadas": 0, "tasa_sesion_vs_respuesta": 0,
            "tasa_sesion_global": 0
        }
    total_prospectos = len(df_filtrado_campana)
    invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str))) #
    primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan"] #
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str))) #

    tasa_aceptacion = (invites_aceptadas / total_prospectos * 100) if total_prospectos > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0
    tasa_sesion_vs_respuesta = (sesiones_agendadas / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global = (sesiones_agendadas / total_prospectos * 100) if total_prospectos > 0 else 0
    return {
        "total_prospectos": int(total_prospectos), "invites_aceptadas": int(invites_aceptadas),
        "primeros_mensajes_enviados": int(primeros_mensajes_enviados),
        "respuestas_primer_mensaje": int(respuestas_primer_mensaje),
        "sesiones_agendadas": int(sesiones_agendadas), "tasa_aceptacion": tasa_aceptacion,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta": tasa_sesion_vs_respuesta,
        "tasa_sesion_global": tasa_sesion_global,
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
    st.caption(f"Embudo basado en {kpis_campana['total_prospectos']:,} prospectos iniciales para la selección actual.")

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
            "Prospectos": kpis["total_prospectos"], "Aceptadas": kpis["invites_aceptadas"],
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
    st.rerun() # Forzar rerun para que los widgets se actualicen

# Solo mostrar el expander y los filtros si hay una campaña seleccionada
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
        if not all(p in opciones_prospectador_camp for p in default_prospectador): # Verifica que cada elemento del default esté en las opciones
            default_prospectador = ["– Todos –"] if "– Todos –" in opciones_prospectador_camp else []
        st.session_state.campana_filtro_prospectador = st.multiselect(
            "¿Quién Prospectó?", options=opciones_prospectador_camp,
            default=default_prospectador, key="ms_campana_prospectador"
        )

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
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        if "Fecha de Invite" in df_campanas_filtradas_por_seleccion.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion["Fecha de Invite"]):
            valid_dates = df_campanas_filtradas_por_seleccion["Fecha de Invite"].dropna()
            if not valid_dates.empty:
                min_fecha_invite_camp = valid_dates.min().date()
                max_fecha_invite_camp = valid_dates.max().date()
        
        # Leer el valor del date_input directamente, que usa su propia key interna o la que le asignemos.
        # Usamos las claves de session_state campana_filtro_fecha_ini/fin para *leer* el valor después.
        val_fecha_ini = st.date_input(
            "Fecha de Invite Desde:", 
            value=st.session_state.campana_filtro_fecha_ini, # El callback resetea esto a None
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_ini" # Key explícita para el widget
        )
        val_fecha_fin = st.date_input(
            "Fecha de Invite Hasta:", 
            value=st.session_state.campana_filtro_fecha_fin, # El callback resetea esto a None
            min_value=min_fecha_invite_camp, max_value=max_fecha_invite_camp, 
            format="DD/MM/YYYY", key="di_campana_fecha_fin" # Key explícita para el widget
        )
        # Actualizar las claves de session_state que usamos para aplicar los filtros
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

# Usar los valores actualizados de session_state para las fechas
fecha_ini_aplicar = st.session_state.campana_filtro_fecha_ini
fecha_fin_aplicar = st.session_state.campana_filtro_fecha_fin

if fecha_ini_aplicar and fecha_fin_aplicar and \
   "Fecha de Invite" in df_aplicar_filtros.columns and \
   pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
    fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
    df_aplicar_filtros = df_aplicar_filtros[
        (df_aplicar_filtros["Fecha de Invite"] >= fecha_ini_dt) &
        (df_aplicar_filtros["Fecha de Invite"] <= fecha_fin_dt)
    ]
elif fecha_ini_aplicar and "Fecha de Invite" in df_aplicar_filtros.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    fecha_ini_dt = datetime.datetime.combine(fecha_ini_aplicar, datetime.time.min)
    df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros["Fecha de Invite"] >= fecha_ini_dt]
elif fecha_fin_aplicar and "Fecha de Invite" in df_aplicar_filtros.columns and pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    fecha_fin_dt = datetime.datetime.combine(fecha_fin_aplicar, datetime.time.max)
    df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros["Fecha de Invite"] <= fecha_fin_dt]

df_final_analisis_campana = df_aplicar_filtros.copy()

# --- Sección de Resultados y Visualizaciones ---
# (El resto del código para mostrar KPIs, embudo, comparativas, rendimiento por prospectador y tabla de detalle
# permanece igual que en la versión anterior, ya que opera sobre df_final_analisis_campana)
# ... (COPIAR Y PEGAR EL RESTO DEL CÓDIGO DESDE LA VERSIÓN ANTERIOR AQUÍ) ...
# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")

if df_final_analisis_campana.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
else:
    st.markdown("### Indicadores Clave (KPIs) - Agregado de Selección")
    kpis_calculados_campana_agregado = calcular_kpis_df_campana(df_final_analisis_campana)
    kpi_cols_agg = st.columns(4)
    kpi_cols_agg[0].metric("Total Prospectos", f"{kpis_calculados_campana_agregado['total_prospectos']:,}")
    kpi_cols_agg[1].metric("Invites Aceptadas", f"{kpis_calculados_campana_agregado['invites_aceptadas']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_aceptacion']:.1f}% de Prospectos")
    kpi_cols_agg[2].metric("Respuestas 1er Msj", f"{kpis_calculados_campana_agregado['respuestas_primer_mensaje']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas")
    kpi_cols_agg[3].metric("Sesiones Agendadas", f"{kpis_calculados_campana_agregado['sesiones_agendadas']:,}",
                           f"{kpis_calculados_campana_agregado['tasa_sesion_global']:.1f}% de Prospectos")
    if kpis_calculados_campana_agregado['sesiones_agendadas'] > 0 and kpis_calculados_campana_agregado['respuestas_primer_mensaje'] > 0 :
         st.caption(f"Tasa de Sesiones vs Respuestas (Agregado): {kpis_calculados_campana_agregado['tasa_sesion_vs_respuesta']:.1f}%")

    st.markdown("### Embudo de Conversión - Agregado de Selección")
    mostrar_embudo_para_campana(kpis_calculados_campana_agregado, "Embudo de Conversión (Agregado de Selección y Filtros)")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla y gráficos comparan las campañas seleccionadas, considerando los filtros de '¿Quién Prospectó?', 'País' y 'Fechas' aplicados arriba.")
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(df_final_analisis_campana, st.session_state.campana_seleccion_principal)
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros aplicados)")
            cols_enteros_comp = ["Prospectos", "Aceptadas", "Respuestas", "Sesiones"]
            format_dict_comp = {"Tasa Aceptación (%)": "{:.1f}%", "Tasa Respuesta (vs Acept.) (%)": "{:.1f}%", "Tasa Sesiones (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Global (%)": "{:.1f}%"}
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            st.dataframe(df_tabla_comp.sort_values(by="Tasa Sesión Global (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            st.subheader("Gráfico: Tasa de Sesión Global por Campaña (con filtros aplicados)")
            df_graf_comp_tasa_global = df_tabla_comp[df_tabla_comp["Prospectos"] > 0].sort_values(by="Tasa Sesión Global (%)", ascending=False)
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
        df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?").apply(lambda x: pd.Series(calcular_kpis_df_campana(x))).reset_index()
        df_prospectador_camp_display = df_prospectador_camp[(df_prospectador_camp['total_prospectos'] > 0)][["¿Quién Prospecto?", "total_prospectos", "invites_aceptadas", "respuestas_primer_mensaje", "sesiones_agendadas", "tasa_sesion_global"]].rename(columns={"total_prospectos": "Prospectos", "invites_aceptadas": "Aceptadas", "respuestas_primer_mensaje": "Respuestas", "sesiones_agendadas": "Sesiones", "tasa_sesion_global": "Tasa Sesión Global (%)"}).sort_values(by="Sesiones", ascending=False)
        cols_enteros_prosp = ["Prospectos", "Aceptadas", "Respuestas", "Sesiones"]
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
            elif len(st.session_state.campana_filtro_prospectador) > 1 and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1: # Si se seleccionaron múltiples explícitamente y hay más de uno en los datos resultantes
                mostrar_grafico_prospectador = True
            if mostrar_grafico_prospectador:
                fig_prosp_camp_bar = px.bar(df_prospectador_camp_display.sort_values(by="Tasa Sesión Global (%)", ascending=False), x="¿Quién Prospecto?", y="Tasa Sesión Global (%)", title="Tasa de Sesión Global por Prospectador (Selección Actual)", text="Tasa Sesión Global (%)", color="Tasa Sesión Global (%)")
                fig_prosp_camp_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar, use_container_width=True)
        else: st.caption("No hay datos de rendimiento por prospectador para la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible.")

    st.markdown("### Detalle de Prospectos (para la selección actual)")
    indices_filtrados = df_final_analisis_campana.index
    df_detalle_original_filtrado = df_original_completo.loc[indices_filtrados].copy()
    if not df_detalle_original_filtrado.empty:
        df_display_tabla_campana_detalle = pd.DataFrame()
        for col_orig in df_detalle_original_filtrado.columns:
            if pd.api.types.is_datetime64_any_dtype(df_detalle_original_filtrado[col_orig]):
                 df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_detalle_original_filtrado[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            elif pd.api.types.is_numeric_dtype(df_detalle_original_filtrado[col_orig]) and (df_detalle_original_filtrado[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or pd.api.types.is_integer_dtype(df_detalle_original_filtrado[col_orig].dropna())):
                 df_display_tabla_campana_detalle[col_orig] = df_detalle_original_filtrado[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A")
            else:
                 df_display_tabla_campana_detalle[col_orig] = df_detalle_original_filtrado[col_orig].astype(str).fillna("N/A")
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()
        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_original_filtrado)
        nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
        st.download_button(label="⬇️ Descargar Detalle Completo de Campaña (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
