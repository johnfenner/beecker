# Proyecto/🏠_Dashboard_Principal.py

import streamlit as st
import pandas as pd
import sys
import os
import shutil

# Copiar secrets.toml en Render si es necesario
if os.environ.get("RENDER") == "true":
    src = "/etc/secrets/secrets.toml"
    dst_dir = "/opt/render/project/src/.streamlit"
    dst = os.path.join(dst_dir, "secrets.toml")

    os.makedirs(dst_dir, exist_ok=True)
    if not os.path.isfile(dst):
        shutil.copy(src, dst)
        
# Añadir la raíz del proyecto al path para poder importar módulos
project_root = os.path.abspath(os.path.dirname(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# --- IMPORTS MODULARES ---
from datos.carga_datos import cargar_y_limpiar_datos, cargar_y_procesar_datos
from filtros.filtros_sidebar import mostrar_filtros_sidebar
from filtros.aplicar_filtros import aplicar_filtros
from componentes.tabla_prospectos import mostrar_tabla_filtrada
from componentes.indicadores_kpis import mostrar_kpis
from componentes.embudo_conversion import mostrar_embudo
from componentes.resumen_ejecutivo import mostrar_resumen_ejecutivo
from componentes.top_industrias_paises import mostrar_analisis_dimension_agendamiento_flexible
from componentes.analisis_procesos import mostrar_analisis_procesos_con_prospectador
from componentes.analisis_avatars import mostrar_analisis_por_avatar
# --- NUEVA LÍNEA ---
from componentes.analisis_prospectadores import mostrar_analisis_por_prospectador 
from componentes.oportunidades_calientes import mostrar_oportunidades_calientes

from utils.limpieza import limpiar_valor_kpi

# --- CONFIGURACIÓN GENERAL ---
st.set_page_config(page_title="Dashboard", 
                   layout="wide")
st.title("📈 Dashboard — Master DataBase")

# --- INYECTAR CSS ---
st.markdown(
    """
    <style>
    section[data-testid="stSidebar"] { width: 380px !important; }
    section[data-testid="stSidebar"] .stSidebarContent { padding-top: 20px; padding-left: 20px; padding-right: 20px; }
    .highlight-rate { font-size: 1.1em; font-weight: bold; color: #28a745; display: block; margin-top: 5px; }
    </style>
    """,
    unsafe_allow_html=True,
)

# --- SIDEBAR CONTENT ---
SIDEBAR_IMAGE_PATH = os.path.join(project_root, "logo.jpeg")
try:
    st.sidebar.image(SIDEBAR_IMAGE_PATH, width=150)
except Exception as e:
    st.sidebar.warning(f"⚠️ Error al cargar el logo: {e}")

st.sidebar.markdown("""
**Plataforma de Análisis de Prospección**:
Explora métricas clave y gestiona tus leads.
""")

# --- CARGA DE DATOS ---
@st.cache_data
def get_processed_data():
    df_base_loaded = cargar_y_limpiar_datos()
    if df_base_loaded is None or df_base_loaded.empty:
        return pd.DataFrame()
    df_processed_loaded = cargar_y_procesar_datos(df_base_loaded.copy())
    return df_processed_loaded


df_global = get_processed_data()

if df_global.empty:
    st.error("No se pudieron cargar datos. El dashboard no puede continuar.")
    st.stop()

# --- CÁLCULO DE MÉTRICAS BASE ---
total_base = len(df_global)
base_inv_acept = sum(limpiar_valor_kpi(x) == "si" for x in df_global["¿Invite Aceptada?"]) if "¿Invite Aceptada?" in df_global.columns else 0
base_primeros_mensajes_enviados_count = sum(pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"] for x in df_global["Fecha Primer Mensaje"]) if "Fecha Primer Mensaje" in df_global.columns else 0
base_resp_primer = sum(limpiar_valor_kpi(x) not in ["no", "", "nan"] for x in df_global["Respuesta Primer Mensaje"]) if "Respuesta Primer Mensaje" in df_global.columns else 0
base_sesiones = sum(limpiar_valor_kpi(x) == "si" for x in df_global["Sesion Agendada?"]) if "Sesion Agendada?" in df_global.columns else 0

base_kpis_counts = {
    "total_base": total_base, "inv_acept": base_inv_acept,
    "primeros_mensajes_enviados_count": base_primeros_mensajes_enviados_count,
    "resp_primer": base_resp_primer, "sesiones": base_sesiones
}

# --- FILTROS Y PROCESAMIENTO ---
(filtro_fuente_lista, filtro_proceso, filtro_pais, filtro_industria,
 filtro_avatar, filtro_prospectador, filtro_invite_aceptada_simple,
 filtro_sesion_agendada, fecha_ini, fecha_fin,
 busqueda_texto) = mostrar_filtros_sidebar(df_global.copy())

df_filtrado_sidebar = aplicar_filtros(
    df_global.copy(), filtro_fuente_lista, filtro_proceso, filtro_pais,
    filtro_industria, filtro_avatar, filtro_prospectador,
    filtro_invite_aceptada_simple, filtro_sesion_agendada, fecha_ini,
    fecha_fin)

df_kpis = df_filtrado_sidebar.copy()
df_tabla_detalle = df_filtrado_sidebar.copy()

if busqueda_texto:
    busq_term = busqueda_texto.lower().strip()
    if busq_term:
        mask = pd.Series([False] * len(df_tabla_detalle), index=df_tabla_detalle.index)
        columnas_busqueda = ["Empresa", "Puesto", "Nombre", "Apellido"]
        for col in columnas_busqueda:
            if col in df_tabla_detalle.columns:
                 mask |= df_tabla_detalle[col].astype(str).str.lower().str.contains(busq_term, na=False)
        df_tabla_detalle = df_tabla_detalle[mask]

# --- RENDERIZADO DEL DASHBOARD ---

# 1. Tablas Visuales Separadas
st.header("📊 Detalle de Prospectos Filtrados")

# SECCIÓN DE EVELYN COMENTADA
# df_evelyn = df_tabla_detalle[df_tabla_detalle['Fuente_Analista'] == 'Evelyn']
# st.subheader(f"Prospectos de Evelyn ({len(df_evelyn)})")
# mostrar_tabla_filtrada(df_evelyn, key_suffix="evelyn")

# st.markdown("<br>", unsafe_allow_html=True)

df_equipo_principal = df_tabla_detalle[df_tabla_detalle['Fuente_Analista'] == 'Equipo Principal']
st.subheader(f"Prospectos del Equipo Principal ({len(df_equipo_principal)})")
mostrar_tabla_filtrada(df_equipo_principal, key_suffix="principal")

st.markdown("<br><br>", unsafe_allow_html=True)

# 2. El resto de tu dashboard, que funciona con datos unificados (df_kpis)
(filtered_total, filtered_primeros_mensajes_enviados_count, filtered_inv_acept,
 filtered_resp_primer, filtered_sesiones,
 _) = mostrar_kpis(df_kpis, base_kpis_counts, limpiar_valor_kpi)

mostrar_embudo(filtered_total, filtered_inv_acept, filtered_resp_primer,
               filtered_sesiones, filtered_primeros_mensajes_enviados_count,
               base_kpis_counts["total_base"], base_kpis_counts["inv_acept"],
               base_kpis_counts["primeros_mensajes_enviados_count"],
               base_kpis_counts["resp_primer"], base_kpis_counts["sesiones"])

st.header("💡 ¿Dónde Enfocar tus Esfuerzos de Prospección?")

if "Industria" in df_kpis.columns:
    mostrar_analisis_dimension_agendamiento_flexible(df_kpis, "Industria", "Industrias", top_n_grafico=10, mostrar_tabla_completa=False)
else:
    st.caption("Columna 'Industria' no encontrada para análisis.")

if "Pais" in df_kpis.columns:
    mostrar_analisis_dimension_agendamiento_flexible(df_kpis, "Pais", "Países", top_n_grafico=10, mostrar_tabla_completa=True)
else:
    st.caption("Columna 'Pais' no encontrada para análisis.")

if "Puesto" in df_kpis.columns:
    mostrar_analisis_dimension_agendamiento_flexible(df_kpis, "Puesto", "Puestos", top_n_grafico=10, mostrar_tabla_completa=False)
else:
    st.caption("Columna 'Puesto' no encontrada para análisis.")

if "Proceso" in df_kpis.columns:
    mostrar_analisis_procesos_con_prospectador(df_kpis, top_n_grafico_proceso=10, mostrar_tabla_proceso=True)
else:
    st.caption("Columna 'Proceso' no encontrada para análisis de procesos.")

# --- SECCIÓN DE ANÁLISIS DE RENDIMIENTO (MODIFICADA) ---
# Se añade la llamada a la nueva función justo antes de la de Avatares.
mostrar_analisis_por_prospectador(df_kpis)
mostrar_analisis_por_avatar(df_kpis)

mostrar_resumen_ejecutivo(df_kpis, limpiar_valor_kpi, base_kpis_counts, filtered_sesiones)

# --- PIE DE PÁGINA ---
st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊 '."
)
