# Prospe/pages/✉️_Mensajes_Personalizados.py

import streamlit as st
import pandas as pd
import sys
import os

# Añadir la raíz del proyecto al path
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datos.carga_datos import cargar_y_limpiar_datos
from filtros.aplicar_filtros import aplicar_filtros
from mensajes.mensajes import (mensaje_1_h2r, mensaje_2_h2r, mensaje_3_h2r,
                               mensaje_1_p2p, mensaje_2_p2p, mensaje_1_o2c,
                               mensaje_2_o2c, mensaje_1_general,
                               mensaje_2_general, plantilla_john_h2r,
                               plantilla_john_p2p, plantilla_john_o2c,
                               plantilla_john_general)
from mensajes.mensajes_streamlit import clasificar_por_proceso
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar, limpiar_nombre_completo


def reset_mensaje_filtros_state():
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
    if 'mensaje_categoria_seleccionada_final' in st.session_state:
        del st.session_state['mensaje_categoria_seleccionada_final']
    if 'mensaje_plantilla_seleccionada_final' in st.session_state:
        del st.session_state['mensaje_plantilla_seleccionada_final']
    st.toast("Filtros de mensajes reiniciados ✅")


st.set_page_config(page_title="Mensajes Personalizados", layout="wide")
st.title("💌 Generador de Mensajes Personalizados")
st.markdown(
    "Filtra prospectos que aceptaron tu invitación y genera mensajes personalizados."
)


@st.cache_data
def get_base_data():
    df_base = cargar_y_limpiar_datos()
    if "Fecha de Invite" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(
            df_base["Fecha de Invite"]):
        df_base["Fecha de Invite"] = pd.to_datetime(df_base["Fecha de Invite"],
                                                    errors='coerce')
    if "Avatar" in df_base.columns:  # Estandarizar avatar después de la carga
        df_base["Avatar"] = df_base["Avatar"].apply(estandarizar_avatar)
    return df_base


df = get_base_data()

if df is None or df.empty:
    st.warning("No se pudieron cargar datos o el DataFrame base está vacío.")
    st.stop()

if 'mensaje_filtros' not in st.session_state:
    reset_mensaje_filtros_state()
if 'mostrar_tabla_mensajes' not in st.session_state:
    st.session_state.mostrar_tabla_mensajes = False

st.subheader("⚙️ Configura los Filtros para tus Mensajes")
st.write("**1. Invite Aceptada:** (Filtro obligatorio: 'Si')")
# El filtro se aplica internamente, no se muestra un widget editable para esto.
st.session_state.mensaje_filtros["invite_aceptada"] = "si"

st.write("**2. Filtros Adicionales (Opcional):**")
with st.expander("Ver/Ocultar Filtros Adicionales"):
    col1_filtros, col2_filtros = st.columns(2)
    with col1_filtros:
        opciones_fuente = ["– Todos –"] + (
            sorted(df["Fuente de la Lista"].dropna().astype(
                str).unique().tolist()) if "Fuente de la Lista" in df.columns
            and not df["Fuente de la Lista"].empty else [])
        st.session_state.mensaje_filtros["fuente_lista"] = st.multiselect(
            "Fuente de la Lista",
            opciones_fuente,
            default=st.session_state.mensaje_filtros.get(
                "fuente_lista", ["– Todos –"]),
            key="ms_fuente_lista_msg_page_v2")

        opciones_proceso = ["– Todos –"] + (
            sorted(df["Proceso"].dropna().astype(str).unique().tolist())
            if "Proceso" in df.columns and not df["Proceso"].empty else [])
        st.session_state.mensaje_filtros["proceso"] = st.multiselect(
            "Proceso",
            opciones_proceso,
            default=st.session_state.mensaje_filtros.get(
                "proceso", ["– Todos –"]),
            key="ms_proceso_msg_page_v2")

        avatares_unicos_filt = ["– Todos –"]
        if "Avatar" in df.columns and not df["Avatar"].empty:
            avatares_unicos_filt.extend(
                sorted(df["Avatar"].dropna().astype(str).unique().tolist()))
        st.session_state.mensaje_filtros["avatar"] = st.multiselect(
            "Avatar",
            avatares_unicos_filt,
            default=st.session_state.mensaje_filtros.get(
                "avatar", ["– Todos –"]),
            key="ms_avatar_msg_page_v2")

    with col2_filtros:
        opciones_pais = ["– Todos –"] + (
            sorted(df["Pais"].dropna().astype(str).unique().tolist())
            if "Pais" in df.columns and not df["Pais"].empty else [])
        st.session_state.mensaje_filtros["pais"] = st.multiselect(
            "País",
            opciones_pais,
            default=st.session_state.mensaje_filtros.get(
                "pais", ["– Todos –"]),
            key="ms_pais_msg_page_v2")

        opciones_industria = ["– Todos –"] + (
            sorted(df["Industria"].dropna().astype(str).unique().tolist())
            if "Industria" in df.columns and not df["Industria"].empty else [])
        st.session_state.mensaje_filtros["industria"] = st.multiselect(
            "Industria",
            opciones_industria,
            default=st.session_state.mensaje_filtros.get(
                "industria", ["– Todos –"]),
            key="ms_industria_msg_page_v2")

        opciones_prospectador = ["– Todos –"] + (
            sorted(df["¿Quién Prospecto?"].dropna().astype(
                str).unique().tolist()) if "¿Quién Prospecto?" in df.columns
            and not df["¿Quién Prospecto?"].empty else [])
        st.session_state.mensaje_filtros["prospectador"] = st.multiselect(
            "¿Quién Prospectó?",
            opciones_prospectador,
            default=st.session_state.mensaje_filtros.get(
                "prospectador", ["– Todos –"]),
            key="ms_prospectador_msg_page_v2")

    with st.container():
        st.markdown("---")
        fecha_min_data_val, fecha_max_data_val = None, None
        if "Fecha de Invite" in df.columns and pd.api.types.is_datetime64_any_dtype(
                df["Fecha de Invite"]):
            valid_dates_filt = df["Fecha de Invite"].dropna()
            if not valid_dates_filt.empty:
                fecha_min_data_val, fecha_max_data_val = valid_dates_filt.min(
                ).date(), valid_dates_filt.max().date()

        col_sesion_filt, col_f1_filt, col_f2_filt = st.columns(3)
        with col_sesion_filt:
            opciones_sesion_filt = ["– Todos –", "Si", "No"]
            current_sesion_val_filt = st.session_state.mensaje_filtros.get(
                "sesion_agendada", "– Todos –")
            if isinstance(current_sesion_val_filt, str):
                if current_sesion_val_filt.lower() == "si":
                    current_sesion_val_filt = "Si"
                elif current_sesion_val_filt.lower() == "no":
                    current_sesion_val_filt = "No"
                elif current_sesion_val_filt not in opciones_sesion_filt:
                    current_sesion_val_filt = "– Todos –"
            else:
                current_sesion_val_filt = "– Todos –"
            st.session_state.mensaje_filtros["sesion_agendada"] = st.selectbox(
                "¿Sesión Agendada?",
                opciones_sesion_filt,
                index=opciones_sesion_filt.index(current_sesion_val_filt),
                key="sb_sesion_agendada_msg_page_v2")

        with col_f1_filt:
            st.session_state.mensaje_filtros["fecha_ini"] = st.date_input(
                "Desde (Fecha de Invite)",
                value=st.session_state.mensaje_filtros.get("fecha_ini", None),
                format='DD/MM/YYYY',
                key="di_fecha_ini_msg_page_v2",
                min_value=fecha_min_data_val,
                max_value=fecha_max_data_val)
        with col_f2_filt:
            st.session_state.mensaje_filtros["fecha_fin"] = st.date_input(
                "Hasta (Fecha de Invite)",
                value=st.session_state.mensaje_filtros.get("fecha_fin", None),
                format='DD/MM/YYYY',
                key="di_fecha_fin_msg_page_v2",
                min_value=fecha_min_data_val,
                max_value=fecha_max_data_val)

st.session_state.mensaje_filtros["busqueda"] = st.text_input(
    "🔎 Buscar en Nombre, Apellido, Empresa, Puesto",
    value=st.session_state.mensaje_filtros.get("busqueda", ""),
    placeholder="Ingrese término y presione Enter",
    key="ti_busqueda_msg_page_v2")

col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("📬 Cargar y Filtrar Prospectos para Mensaje",
                 key="btn_cargar_filtrar_msg_page_v2"):
        st.session_state.mostrar_tabla_mensajes = True
with col_btn2:
    st.button("🧹 Limpiar Filtros de Mensajes",
              on_click=reset_mensaje_filtros_state,
              key="btn_limpiar_filtros_msg_page_v2")

if st.session_state.mostrar_tabla_mensajes:
    st.markdown("---")
    st.subheader("📬 Resultado de los Filtros y Generador de Mensajes")
    df_mensajes_filtrado_temp = df.copy()
    if "¿Invite Aceptada?" in df_mensajes_filtrado_temp.columns:
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[
            df_mensajes_filtrado_temp["¿Invite Aceptada?"].apply(
                limpiar_valor_kpi) ==
            st.session_state.mensaje_filtros["invite_aceptada"]]
    else:
        st.warning("Columna '¿Invite Aceptada?' no encontrada.")
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[0:0]

    if not df_mensajes_filtrado_temp.empty:
        filtro_sesion_para_aplicar = st.session_state.mensaje_filtros.get(
            "sesion_agendada", "– Todos –")
        if filtro_sesion_para_aplicar == "Si":
            filtro_sesion_para_aplicar = "si"
        elif filtro_sesion_para_aplicar == "No":
            filtro_sesion_para_aplicar = "no"
        df_mensajes_filtrado_temp = aplicar_filtros(
            df_mensajes_filtrado_temp,
            st.session_state.mensaje_filtros.get("fuente_lista",
                                                 ["– Todos –"]),
            st.session_state.mensaje_filtros.get("proceso", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("pais", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("industria", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("avatar", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("prospectador",
                                                 ["– Todos –"]), "– Todos –",
            filtro_sesion_para_aplicar,
            st.session_state.mensaje_filtros.get("fecha_ini", None),
            st.session_state.mensaje_filtros.get("fecha_fin", None))
        busqueda_term_final = st.session_state.mensaje_filtros.get(
            "busqueda", "").lower().strip()
        if busqueda_term_final and not df_mensajes_filtrado_temp.empty:
            mask_busqueda = pd.Series([False] * len(df_mensajes_filtrado_temp),
                                      index=df_mensajes_filtrado_temp.index)
            columnas_para_busqueda_texto = ["Empresa", "Puesto"]
            for col_busc in columnas_para_busqueda_texto:
                if col_busc in df_mensajes_filtrado_temp.columns:
                    mask_busqueda |= df_mensajes_filtrado_temp[
                        col_busc].astype(str).str.lower().str.contains(
                            busqueda_term_final, na=False)
            nombre_col_df, apellido_col_df = "Nombre", "Apellido"
            if nombre_col_df in df_mensajes_filtrado_temp.columns and apellido_col_df in df_mensajes_filtrado_temp.columns:
                nombre_completo_busq = (
                    df_mensajes_filtrado_temp[nombre_col_df].fillna('') + ' ' +
                    df_mensajes_filtrado_temp[apellido_col_df].fillna('')
                ).str.lower()
                mask_busqueda |= nombre_completo_busq.str.contains(
                    busqueda_term_final, na=False)
            elif nombre_col_df in df_mensajes_filtrado_temp.columns:
                mask_busqueda |= df_mensajes_filtrado_temp[
                    nombre_col_df].astype(str).str.lower().str.contains(
                        busqueda_term_final, na=False)
            elif apellido_col_df in df_mensajes_filtrado_temp.columns:
                mask_busqueda |= df_mensajes_filtrado_temp[
                    apellido_col_df].astype(str).str.lower().str.contains(
                        busqueda_term_final, na=False)
            df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[
                mask_busqueda]
    df_mensajes_final_display = df_mensajes_filtrado_temp.copy()

    if df_mensajes_final_display.empty:
        st.warning(
            "No se encontraron prospectos que cumplan todos los criterios.")
    else:
        linkedin_col_nombre = "LinkedIn"
        columnas_necesarias_para_display = [
            "Nombre", "Apellido", "Empresa", "Puesto", "Proceso", "Avatar",
            "Fecha de Invite", "¿Quién Prospecto?", linkedin_col_nombre,
            "Sesion Agendada?"
        ]
        for col_exist in columnas_necesarias_para_display:
            if col_exist not in df_mensajes_final_display.columns:
                df_mensajes_final_display[col_exist] = pd.NA
        df_mensajes_final_display["Categoría"] = df_mensajes_final_display[
            "Proceso"].apply(clasificar_por_proceso)
        df_mensajes_final_display[
            "Nombre_Completo_Display"] = df_mensajes_final_display.apply(
                lambda row: limpiar_nombre_completo(row.get("Nombre"),
                                                    row.get("Apellido")),
                axis=1)

        st.markdown("### 📋 Prospectos Encontrados para Mensajes")
        st.write(f"Mostrando **{len(df_mensajes_final_display)}** prospectos.")
        columnas_para_tabla_display = [
            "Nombre_Completo_Display", "Empresa", "Puesto", "Categoría",
            "Avatar", "Fecha de Invite", "¿Quién Prospecto?",
            "Sesion Agendada?", linkedin_col_nombre
        ]
        cols_realmente_en_df_para_tabla = [
            col for col in columnas_para_tabla_display
            if col in df_mensajes_final_display.columns
        ]
        df_tabla_a_mostrar = df_mensajes_final_display[
            cols_realmente_en_df_para_tabla].copy()
        if "Fecha de Invite" in df_tabla_a_mostrar.columns:
            df_tabla_a_mostrar["Fecha de Invite"] = pd.to_datetime(
                df_tabla_a_mostrar["Fecha de Invite"],
                errors='coerce').dt.strftime('%d/%m/%Y')
        st.dataframe(df_tabla_a_mostrar, use_container_width=True)

        st.markdown("---")
        st.markdown("### 📬️ Generador de Mensajes")

        opciones_mensajes = {
            "H2R": {
                "Mensaje 1 H2R": mensaje_1_h2r,
                "Mensaje 2 H2R": mensaje_2_h2r,
                "Mensaje 3 H2R": mensaje_3_h2r,
                "Plantilla John H2R": plantilla_john_h2r
            },
            "P2P": {
                "Mensaje 1 P2P": mensaje_1_p2p,
                "Mensaje 2 P2P": mensaje_2_p2p,
                "Plantilla John P2P": plantilla_john_p2p
            },
            "O2C": {
                "Mensaje 1 O2C": mensaje_1_o2c,
                "Mensaje 2 O2C": mensaje_2_o2c,
                "Plantilla John O2C": plantilla_john_o2c
            },
            "General": {
                "Mensaje 1 General": mensaje_1_general,
                "Mensaje 2 General": mensaje_2_general,
                "Plantilla John General": plantilla_john_general
            }  # Nombre más descriptivo
        }
        categorias_validas_en_df = sorted(
            df_mensajes_final_display["Categoría"].unique().tolist())
        categorias_seleccionables_para_msg = [
            cat for cat in categorias_validas_en_df if cat in opciones_mensajes
        ]

        if not categorias_seleccionables_para_msg:
            st.warning(
                "No hay prospectos con categorías de Proceso válidas (H2R, P2P, O2C, General) en los datos filtrados."
            )
        else:
            col_sel_cat, col_sel_plantilla = st.columns(2)
            with col_sel_cat:
                categoria_sel = st.selectbox(
                    "1. Selecciona una Categoría de Proceso:",
                    categorias_seleccionables_para_msg,
                    key="mensaje_categoria_sel_v3")
            plantillas_para_categoria_sel = opciones_mensajes.get(
                categoria_sel, {})
            nombres_plantillas_para_categoria_sel = list(
                plantillas_para_categoria_sel.keys())

            with col_sel_plantilla:
                if nombres_plantillas_para_categoria_sel:
                    nombre_plantilla_sel = st.selectbox(
                        "2. Escoge una Plantilla de Mensaje:",
                        nombres_plantillas_para_categoria_sel,
                        key="mensaje_plantilla_sel_v3")
                    mensaje_final_seleccionado = plantillas_para_categoria_sel.get(
                        nombre_plantilla_sel, "")
                else:
                    st.warning(
                        f"No hay plantillas para la categoría '{categoria_sel}'."
                    )
                    mensaje_final_seleccionado = ""

            if mensaje_final_seleccionado:
                df_vista_previa_msg = df_mensajes_final_display[
                    df_mensajes_final_display["Categoría"] ==
                    categoria_sel].copy()
                if df_vista_previa_msg.empty:
                    st.info(
                        f"No hay prospectos en la categoría '{categoria_sel}' con los filtros actuales."
                    )
                else:
                    # Este bloque va dentro de Prospe/pages/✉️_Mensajes_Personalizados.py
                    # Específicamente, dentro del if mensaje_final_seleccionado:
                    # y después de: if df_vista_previa_msg.empty: ... else:

                    # --- Lógica para determinar atento/atenta ---
                    def obtener_atencion_genero(avatar_de_fila):
                        # Asumimos que avatar_de_fila YA ES el resultado de estandarizar_avatar()
                        # porque estandarizar_avatar se aplica en get_base_data()
                        avatar_estandarizado_lower = str(
                            avatar_de_fila).lower()

                        # IMPORTANTE: Estas listas deben contener los NOMBRES ESTANDARIZADOS
                        #             (la salida de tu función utils.limpieza.estandarizar_avatar)
                        #             convertidos a minúsculas.
                        # EJEMPLO: Si estandarizar_avatar('Maria R.') devuelve 'María Rivera',
                        #          entonces aquí debes tener 'maría rivera'.
                        nombres_masculinos_clave = [
                            "john bermúdez",  # Ejemplo si estandarizar_avatar('John') es 'John Bermúdez'
                            "johnsito"  # Si 'Johnsito' es un avatar estandarizado posible
                            # o una palabra clave en un avatar masculino estandarizado.
                        ]
                        nombres_femeninos_clave = [
                            "maría rivera",  # Ejemplo si estandarizar_avatar('Maria') es 'María Rivera'
                            "maria",  # Podrías tenerla si es una salida posible de estandarizar_avatar
                            # o si quieres una coincidencia más laxa.
                            "ana",
                            "laura",
                            "isabella"  # Otros nombres femeninos estandarizados (en minúsculas)
                        ]

                        # Usamos 'any' para ver si alguna de las palabras clave está contenida.
                        # Esto es más flexible si el avatar estandarizado es, por ejemplo, "María Rivera (Equipo LATAM)"
                        if any(nombre_masc in avatar_estandarizado_lower
                               for nombre_masc in nombres_masculinos_clave):
                            return "atento"
                        if any(nombre_fem in avatar_estandarizado_lower
                               for nombre_fem in nombres_femeninos_clave):
                            return "atenta"

                        return "atento/a"  # Default si no se puede determinar el género

                    # Generar mensajes personalizados
                    df_vista_previa_msg[
                        "Mensaje_Personalizado"] = df_vista_previa_msg.apply(
                            lambda row: mensaje_final_seleccionado.replace(
                                "{nombre}",
                                str(row.get("Nombre", "")).split()[0]
                                if pd.notna(row.get("Nombre")) and str(
                                    row.get("Nombre")).strip() else "[Nombre]")
                            .replace(
                                "{avatar}",
                                str(row.get(
                                    "Avatar", "Tu Nombre"
                                ))  # Muestra el avatar estandarizado de la fila
                            ).replace(
                                "[Nombre de la empresa]",
                                str(
                                    row.get("Empresa", "[Nombre de la empresa]"
                                            ))
                            ).replace(
                                "{atencion_genero}",
                                obtener_atencion_genero(
                                    row.get("Avatar")
                                )  # Pasa el Avatar (ya estandarizado) de la fila
                            ),
                            axis=1)
                    # --- FIN DE LA LÓGICA DE GÉNERO Y REEMPLAZO ---

                    st.markdown("### 📟 Vista Previa y Descarga de Mensajes")
                    cols_generador_display = [
                        "Nombre_Completo_Display",
                        "Empresa",
                        "Puesto",
                        "Avatar",
                        "Sesion Agendada?",
                        linkedin_col_nombre,  # Asegúrate que linkedin_col_nombre esté definido antes
                        "Mensaje_Personalizado"
                    ]
                    cols_reales_generador = [
                        col for col in cols_generador_display
                        if col in df_vista_previa_msg.columns
                    ]
                    st.dataframe(df_vista_previa_msg[cols_reales_generador],
                                 use_container_width=True,
                                 height=300)
                    # El resto del código para el botón de descarga sigue aquí...

                    @st.cache_data
                    def convert_df_to_csv_final(df_to_convert):
                        cols_descarga_final = [
                            "Nombre_Completo_Display", "Empresa", "Puesto",
                            "Sesion Agendada?", linkedin_col_nombre,
                            "Mensaje_Personalizado"
                        ]
                        cols_exist_descarga_final = [
                            col for col in cols_descarga_final
                            if col in df_to_convert.columns
                        ]
                        if not cols_exist_descarga_final: return None
                        df_csv_export = df_to_convert[
                            cols_exist_descarga_final].fillna('')
                        return df_csv_export.to_csv(
                            index=False).encode('utf-8')

                    csv_data_final = convert_df_to_csv_final(
                        df_vista_previa_msg)
                    if csv_data_final is not None:
                        st.download_button(
                            label="⬇️ Descargar Mensajes Generados (CSV)",
                            data=csv_data_final,
                            file_name=
                            f'mensajes_{categoria_sel.replace(" ", "_").lower()}_{nombre_plantilla_sel.replace(" ", "_").lower()}.csv',
                            mime='text/csv',
                            key="btn_download_csv_msg_page_v2")
            elif nombres_plantillas_para_categoria_sel:
                st.info(
                    "Selecciona una plantilla para generar la vista previa.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
