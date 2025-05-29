# pages/🎯_Análisis_de_Campañas.py

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

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado.")

@st.cache_data
def obtener_datos_base_campanas():
    df_completo = cargar_y_limpiar_datos()
    if df_completo is None or df_completo.empty:
        return pd.DataFrame(), pd.DataFrame()

    if 'Campaña' not in df_completo.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame(), df_completo

    df_base_campanas = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy()

    date_cols = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"]
    for col in date_cols:
        if col in df_base_campanas.columns:
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
        if col in df_completo.columns:
            df_completo[col] = pd.to_datetime(df_completo[col], errors='coerce')

    for df_proc in [df_base_campanas, df_completo]:
        if "Avatar" in df_proc.columns:
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar)
    return df_base_campanas, df_completo


def inicializar_estado_filtros_campana():
    defaults = {
        "campana_seleccion_principal": [],
        "campana_filtro_prospectador": ["– Todos –"],
        "campana_filtro_pais": ["– Todos –"],
        "campana_filtro_fecha_ini": None,
        "campana_filtro_fecha_fin": None,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val
        elif key in ["campana_seleccion_principal", "campana_filtro_prospectador", "campana_filtro_pais"] and not isinstance(st.session_state[key], list):
            st.session_state[key] = val


def resetear_filtros_callback():
    st.session_state.campana_seleccion_principal = []
    st.session_state.campana_filtro_prospectador = ["– Todos –"]
    st.session_state.campana_filtro_pais = ["– Todos –"]
    st.session_state.campana_filtro_fecha_ini = None
    st.session_state.campana_filtro_fecha_fin = None
    st.toast("Filtros reiniciados.", icon="🧹")


def calcular_kpis_df_campana(df_filtrado):
    total = len(df_filtrado)
    invites = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado.get("¿Invite Aceptada?", []))
    mensajes = sum(pd.notna(x) and str(x).strip().lower() not in ["no", ""] for x in df_filtrado.get("Fecha Primer Mensaje", []))
    respuestas = sum(limpiar_valor_kpi(x) not in ["no", "", "nan"] for x in df_filtrado.get("Respuesta Primer Mensaje", []))
    sesiones = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado.get("Sesion Agendada?", []))
    tasa_invite = (invites / total * 100) if total else 0
    tasa_resp = (respuestas / invites * 100) if invites else 0
    tasa_sesion = (sesiones / respuestas * 100) if respuestas else 0
    tasa_global = (sesiones / total * 100) if total else 0
    return {
        "total_prospectos": total,
        "invites_aceptadas": invites,
        "primeros_mensajes_enviados": mensajes,
        "respuestas_primer_mensaje": respuestas,
        "sesiones_agendadas": sesiones,
        "tasa_aceptacion": tasa_invite,
        "tasa_respuesta_vs_aceptadas": tasa_resp,
        "tasa_sesion_vs_respuesta": tasa_sesion,
        "tasa_sesion_global": tasa_global,
    }


def mostrar_embudo_para_campana(kpis, titulo="Embudo de Conversión de Campaña"):
    etapas = [
        "Prospectos en Campaña", "Invites Aceptadas",
        "1er Mensaje Enviado", "Respuesta 1er Mensaje", "Sesiones Agendadas"
    ]
    valores = [
        kpis["total_prospectos"], kpis["invites_aceptadas"],
        kpis["primeros_mensajes_enviados"], kpis["respuestas_primer_mensaje"],
        kpis["sesiones_agendadas"]
    ]
    fig = px.funnel(x=etapas, y=valores, title=titulo)
    st.plotly_chart(fig, use_container_width=True)


def generar_tabla_comparativa_campanas_filtrada(df, campanas):
    # Implementación existente...
    pass

# ---- Carga y Estado ----
df_base, df_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()
if df_base.empty:
    st.stop()

# --- Sección 1: Selección ---
st.subheader("1. Selección de Campaña(s)")
opciones = df_base['Campaña'].sort_values().unique().tolist()
st.multiselect("Campañas", options=opciones, key="campana_seleccion_principal")
st.button("Resetear Filtros", on_click=resetear_filtros_callback)

# --- Filtros Avanzados ---
with st.expander("Filtros Avanzados"):
    prospectadores = ["– Todos –"] + df_base['Prospectador'].dropna().unique().tolist()
    st.multiselect("Por Prospectador", options=prospectadores, key="campana_filtro_prospectador")
    paises = ["– Todos –"] + df_base['País'].dropna().unique().tolist()
    st.multiselect("Por País", options=paises, key="campana_filtro_pais")
    col1, col2 = st.columns(2)
    col1.date_input("Desde", key="campana_filtro_fecha_ini")
    col2.date_input("Hasta", key="campana_filtro_fecha_fin")

# --- Aplicar Filtros ---
df_filtrado = df_base.copy()
if st.session_state.campana_seleccion_principal:
    df_filtrado = df_filtrado[df_filtrado['Campaña'].isin(st.session_state.campana_seleccion_principal)]
if st.session_state.campana_filtro_prospectador and "– Todos –" not in st.session_state.campana_filtro_prospectador:
    df_filtrado = df_filtrado[df_filtrado['Prospectador'].isin(st.session_state.campana_filtro_prospectador)]
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_filtrado = df_filtrado[df_filtrado['País'].isin(st.session_state.campana_filtro_pais)]
if st.session_state.campana_filtro_fecha_ini:
    df_filtrado = df_filtrado[df_filtrado['Fecha de Invite'] >= pd.to_datetime(st.session_state.campana_filtro_fecha_ini)]
if st.session_state.campana_filtro_fecha_fin:
    df_filtrado = df_filtrado[df_filtrado['Fecha de Invite'] <= pd.to_datetime(st.session_state.campana_filtro_fecha_fin)]

# --- Sección de Resultados ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")
if not df_filtrado.empty:
    # NUEVA MÉTRICA: Datos totales en la campaña
    df_datos = df_base[df_base['Campaña'].isin(st.session_state.campana_seleccion_principal)]
    total_datos = len(df_datos)

    st.markdown("### Indicadores Clave (KPIs)")
    kpis = calcular_kpis_df_campana(df_filtrado)
    cols = st.columns(5)
    cols[0].metric("Datos en Campaña", f"{total_datos:,}")
    cols[1].metric("Total Prospectos", f"{kpis['total_prospectos']:,}")
    cols[2].metric("Invites Aceptadas", f"{kpis['invites_aceptadas']:,}", f"{kpis['tasa_aceptacion']:.1f}%")
    cols[3].metric("Respuestas 1er Mensaje", f"{kpis['respuestas_primer_mensaje']:,}", f"{kpis['tasa_respuesta_vs_aceptadas']:.1f}%")
    cols[4].metric("Sesiones Agendadas", f"{kpis['sesiones_agendadas']:,}", f"{kpis['tasa_sesion_global']:.1f}%")
    st.caption(f"Tasa de Sesiones vs Respuestas: {kpis['tasa_sesion_vs_respuesta']:.1f}%")
    
    st.markdown("### Embudo de Conversión")
    mostrar_embudo_para_campana(kpis)

    st.markdown("### Comparativa entre Prospectadores")
    generar_tabla_comparativa_campanas_filtrada(df_filtrado, st.session_state.campana_seleccion_principal)

    # Detalle y export
    with st.expander("Detalle Completo"):
        st.dataframe(df_filtrado)
        buffer = io.BytesIO()
        df_filtrado.to_excel(buffer, index=False)
        st.download_button("⬇️ Descargar Detalle", data=buffer.getvalue(), file_name="detalle_campana.xlsx")
else:
    st.warning("No hay datos para la selección actual.")

st.markdown("---")
st.info("Esta plataforma ha sido realizada por Johnsito ✨ 😊")
