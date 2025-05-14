# Nombre del archivo: ✉️_Mensajes_Personalizados.py

import streamlit as st
import pandas as pd
import sys
import os

# Añadir la raíz del proyecto al path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datos.carga_datos import cargar_y_limpiar_datos
from filtros.aplicar_filtros import aplicar_filtros
from mensajes.mensajes import (
    mensaje_1_h2r, mensaje_2_h2r, mensaje_3_h2r, mensaje_1_p2p, mensaje_2_p2p,
    mensaje_1_o2c, mensaje_2_o2c, mensaje_1_general, mensaje_2_general,
    plantilla_john_h2r, plantilla_john_p2p, plantilla_john_o2c, plantilla_john_general)
from mensajes.mensajes_streamlit import clasificar_por_proceso
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar, limpiar_nombre_completo

# --- NUEVA FUNCIÓN DE FILTRADO ESPECÍFICA PARA MENSAJES ---
def aplicar_filtros_mensajes(
    df,
    fuente_lista, proceso, pais, industria, avatar,
    prospectador, sesion_agendada, fecha_ini, fecha_fin,
    columna_fecha="Fecha Primer Mensaje"
):
    df_filtrado = df.copy()

    if fuente_lista and "– Todos –" not in fuente_lista:
        df_filtrado = df_filtrado[df_filtrado["Fuente de la Lista"].isin(fuente_lista)]

    if proceso and "– Todos –" not in proceso:
        df_filtrado = df_filtrado[df_filtrado["Proceso"].isin(proceso)]

    if pais and "– Todos –" not in pais:
        df_filtrado = df_filtrado[df_filtrado["Pais"].isin(pais)]

    if industria and "– Todos –" not in industria:
        df_filtrado = df_filtrado[df_filtrado["Industria"].isin(industria)]

    if avatar and "– Todos –" not in avatar:
        df_filtrado = df_filtrado[df_filtrado["Avatar"].isin(avatar)]

    if prospectador and "– Todos –" not in prospectador:
        df_filtrado = df_filtrado[df_filtrado["¿Quién Prospecto?"].isin(prospectador)]

    if sesion_agendada != "– Todos –":
        df_filtrado = df_filtrado[
            df_filtrado["Sesion Agendada?"]
            .apply(lambda x: str(x).strip().lower() == sesion_agendada.strip().lower())
        ]

    if fecha_ini and fecha_fin and columna_fecha in df_filtrado.columns:
        if pd.api.types.is_datetime64_any_dtype(df_filtrado[columna_fecha]):
            df_filtrado = df_filtrado[
                (df_filtrado[columna_fecha].dt.date >= fecha_ini) &
                (df_filtrado[columna_fecha].dt.date <= fecha_fin)
            ]

    return df_filtrado


# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Mensajes Personalizados", layout="wide")
st.title("💌 Generador de Mensajes Personalizados")
st.markdown("Filtra prospectos que aceptaron tu invitación y genera mensajes personalizados.")


@st.cache_data
def get_base_data():
    df_base = cargar_y_limpiar_datos()

    if "Fecha Primer Mensaje" in df_base.columns:
        df_base["Fecha Primer Mensaje"] = pd.to_datetime(df_base["Fecha Primer Mensaje"], errors='coerce')

    if "Fecha de Invite" in df_base.columns:
        df_base["Fecha de Invite"] = pd.to_datetime(df_base["Fecha de Invite"], errors='coerce')

    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].apply(estandarizar_avatar)

    return df_base


df = get_base_data()

if df is None or df.empty:
    st.warning("No se pudieron cargar datos o el DataFrame base está vacío.")
    st.stop()

if 'mensaje_filtros' not in st.session_state:
    st.session_state["mensaje_filtros"] = {
        "invite_aceptada": "si",
        "fuente_lista": ["– Todos –"],
        "proceso": ["– Todos –"],
        "avatar": ["– Todos –"],
        "pais": ["– Todos –"],
        "industria": ["– Todos –"],
        "prospectador": ["– Todos –"],
        "sesion_agendada": "– Todos –",
        "fecha_ini": None,
        "fecha_fin": None,
        "busqueda": ""
    }
if 'mostrar_tabla_mensajes' not in st.session_state:
    st.session_state.mostrar_tabla_mensajes = False

# --- BOTONES ---
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("📬 Cargar y Filtrar Prospectos para Mensaje"):
        st.session_state.mostrar_tabla_mensajes = True
with col_btn2:
    if st.button("🧹 Limpiar Filtros"):
        st.session_state.mensaje_filtros = {
            "invite_aceptada": "si",
            "fuente_lista": ["– Todos –"],
            "proceso": ["– Todos –"],
            "avatar": ["– Todos –"],
            "pais": ["– Todos –"],
            "industria": ["– Todos –"],
            "prospectador": ["– Todos –"],
            "sesion_agendada": "– Todos –",
            "fecha_ini": None,
            "fecha_fin": None,
            "busqueda": ""
        }
        st.session_state.mostrar_tabla_mensajes = False

# --- FILTRADO Y MOSTRADO ---
if st.session_state.mostrar_tabla_mensajes:
    st.markdown("---")
    st.subheader("📬 Resultado de los Filtros y Generador de Mensajes")
    df_mensajes_filtrado_temp = df.copy()

    if "¿Invite Aceptada?" in df_mensajes_filtrado_temp.columns:
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[
            df_mensajes_filtrado_temp["¿Invite Aceptada?"]
            .apply(limpiar_valor_kpi).astype(str).str.lower()
            == st.session_state.mensaje_filtros["invite_aceptada"].lower()
        ]

    filtro_sesion_para_aplicar = st.session_state.mensaje_filtros.get("sesion_agendada", "– Todos –").lower()

    df_mensajes_filtrado_temp = aplicar_filtros_mensajes(
        df_mensajes_filtrado_temp,
        st.session_state.mensaje_filtros["fuente_lista"],
        st.session_state.mensaje_filtros["proceso"],
        st.session_state.mensaje_filtros["pais"],
        st.session_state.mensaje_filtros["industria"],
        st.session_state.mensaje_filtros["avatar"],
        st.session_state.mensaje_filtros["prospectador"],
        filtro_sesion_para_aplicar,
        st.session_state.mensaje_filtros["fecha_ini"],
        st.session_state.mensaje_filtros["fecha_fin"],
        columna_fecha="Fecha Primer Mensaje"
    )

    # --- BÚSQUEDA DE TEXTO ---
    termino = st.session_state.mensaje_filtros.get("busqueda", "").strip().lower()
    if termino:
        mask = pd.Series([False] * len(df_mensajes_filtrado_temp), index=df_mensajes_filtrado_temp.index)
        columnas_texto = ["Nombre", "Apellido", "Empresa", "Puesto"]
        for col in columnas_texto:
            if col in df_mensajes_filtrado_temp.columns:
                mask |= df_mensajes_filtrado_temp[col].astype(str).str.lower().str.contains(termino, na=False)
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[mask]

    st.dataframe(df_mensajes_filtrado_temp, use_container_width=True)

