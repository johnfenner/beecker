# Nombre del archivo: ✉️_Mensajes_Personalizados.py

import streamlit as st
import pandas as pd
import sys
import os

# Añadir la raíz del proyecto al path
# Esto es útil si tus módulos (datos, filtros, mensajes, utils) están en directorios paralelos a la carpeta 'pages'
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Importar tus módulos locales
# ASEGÚRATE que las rutas de importación son correctas para la estructura de tu proyecto
try:
    from datos.carga_datos import cargar_y_limpiar_datos
    from filtros.aplicar_filtros import aplicar_filtros # Asegúrate si esta función se usa en alguna parte fuera de este script
    from mensajes.mensajes import (
        mensaje_1_h2r, mensaje_2_h2r, mensaje_3_h2r, mensaje_1_p2p, mensaje_2_p2p,
        mensaje_1_o2c, mensaje_2_o2c, mensaje_1_general, mensaje_2_general,
        plantilla_john_h2r, plantilla_john_p2p, plantilla_john_o2c,
        plantilla_john_general)
    from mensajes.mensajes_streamlit import clasificar_por_proceso
    from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar, limpiar_nombre_completo
except ImportError as e:
    st.error(f"Error al importar módulos locales: {e}")
    st.info("Por favor, verifica la estructura de tu proyecto y las rutas en las declaraciones 'from ... import ...'.")
    st.stop() # Detiene la ejecución si hay un error de importación


# --- FUNCIÓN DE FILTRADO PERSONALIZADA PARA MENSAJES ---
# Esta función aplica los filtros seleccionados por el usuario.
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
        # Verifica si la columna 'Pais' existe antes de filtrar
        if "Pais" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Pais"].isin(pais)]
        else:
             st.warning("La columna 'Pais' no se encontró en los datos.")


    if industria and "– Todos –" not in industria:
         # Verifica si la columna 'Industria' existe antes de filtrar
        if "Industria" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Industria"].isin(industria)]
        else:
             st.warning("La columna 'Industria' no se encontró en los datos.")


    if avatar and "– Todos –" not in avatar:
         # Verifica si la columna 'Avatar' existe antes de filtrar
        if "Avatar" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["Avatar"].isin(avatar)]
        else:
             st.warning("La columna 'Avatar' no se encontró en los datos.")


    if prospectador and "– Todos –" not in prospectador:
         # Verifica si la columna '¿Quién Prospecto?' existe antes de filtrar
        if "¿Quién Prospecto?" in df_filtrado.columns:
            df_filtrado = df_filtrado[df_filtrado["¿Quién Prospecto?"].isin(prospectador)]
        else:
            st.warning("La columna '¿Quién Prospecto?' no se encontró en los datos.")


    if sesion_agendada and sesion_agendada != "– Todos –":
        # Verifica si la columna 'Sesion Agendada?' existe antes de filtrar
        if "Sesion Agendada?" in df_filtrado.columns:
            # Asegurarse de que 'sesion_agendada' del filtro coincida con los valores normalizados
             df_filtrado = df_filtrado[
                df_filtrado["Sesion Agendada?"].apply(lambda x: str(x).strip().lower() == str(sesion_agendada).strip().lower())
            ]
        else:
            st.warning("La columna 'Sesion Agendada?' no se encontró en los datos.")


    if fecha_ini and fecha_fin and columna_fecha in df_filtrado.columns:
        # Asegurarse de que la columna de fecha sea datetime antes de filtrar por rango
        if pd.api.types.is_datetime64_any_dtype(df_filtrado[columna_fecha]):
            df_filtrado = df_filtrado[
                (df_filtrado[columna_fecha].dt.date >= fecha_ini) &
                (df_filtrado[columna_fecha].dt.date <= fecha_fin)
            ]
        else:
             st.warning(f"La columna '{columna_fecha}' no tiene formato de fecha/hora para el filtro de rango.")


    return df_filtrado


# Función para reiniciar el estado de los filtros de mensajes
def reset_mensaje_filtros_state():
    st.session_state.mensaje_filtros = {
        "invite_aceptada": "si", # Este filtro es fijo en esta página
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
    # Limpiar las selecciones de categoría y plantilla al reiniciar filtros
    if 'mensaje_categoria_sel_v3' in st.session_state:
        del st.session_state['mensaje_categoria_sel_v3']
    if 'mensaje_plantilla_sel_v3' in st.session_state:
        del st.session_state['mensaje_plantilla_sel_v3']
    st.toast("Filtros de mensajes reiniciados ✅")


# Configuración de la página de Streamlit
st.set_page_config(page_title="Mensajes Personalizados", layout="wide")
st.title("💌 Generador de Mensajes Personalizados")
st.markdown(
    "Filtra prospectos que aceptaron tu invitación y genera mensajes personalizados."
)


# Carga y limpieza inicial de los datos (cacheada para rendimiento)
@st.cache_data
def get_base_data():
    df_base = cargar_y_limpiar_datos() # Asume que esta función devuelve un DataFrame

    # Convertir columnas de fecha si existen y no son ya datetime
    columna_fecha_primer_mensaje = "Fecha Primer Mensaje"
    if columna_fecha_primer_mensaje in df_base.columns:
        if not pd.api.types.is_datetime64_any_dtype(df_base[columna_fecha_primer_mensaje]):
            df_base[columna_fecha_primer_mensaje] = pd.to_datetime(
                df_base[columna_fecha_primer_mensaje], errors='coerce') # errors='coerce' convierte valores no válidos a NaT

    if "Fecha de Invite" in df_base.columns:
         if not pd.api.types.is_datetime64_any_dtype(df_base["Fecha de Invite"]):
            df_base["Fecha de Invite"] = pd.to_datetime(df_base["Fecha de Invite"],
                                                        errors='coerce')

    # Aplicar estandarización al Avatar si la columna existe
    if "Avatar" in df_base.columns:
        df_base["Avatar"] = df_base["Avatar"].apply(lambda x: estandarizar_avatar(x) if pd.notna(x) else x) # Aplica solo a valores no nulos
        # Reemplazar posibles NaT resultantes de coerce si no se pudieron parsear
        if columna_fecha_primer_mensaje in df_base.columns:
             df_base[columna_fecha_primer_mensaje] = df_base[columna_fecha_primer_mensaje].dt.date # Convertir a solo fecha si es datetime


    # Agregar columnas esenciales si no existen para evitar errores de KeyError más adelante
    columnas_esenciales = [
        "Fuente de la Lista", "Proceso", "Pais", "Industria", "Avatar",
        "¿Quién Prospecto?", "Sesion Agendada?", "¿Invite Aceptada?",
        "Nombre", "Apellido", "Empresa", "Puesto", "LinkedIn",
        columna_fecha_primer_mensaje
        ]
    for col in columnas_esenciales:
        if col not in df_base.columns:
            df_base[col] = pd.NA # O np.nan o "" dependiendo del tipo de dato esperado

    return df_base


# Cargar los datos base
df = get_base_data()

# Verificar si la carga de datos fue exitosa
if df is None or df.empty:
    st.warning("No se pudieron cargar datos o el DataFrame base está vacío. Por favor, verifica el archivo de datos.")
    st.stop() # Detiene la ejecución si no hay datos

# Inicializar el estado de sesión si es necesario
if 'mensaje_filtros' not in st.session_state:
    reset_mensaje_filtros_state()
if 'mostrar_tabla_mensajes' not in st.session_state:
    st.session_state.mostrar_tabla_mensajes = False


# --- Interfaz de usuario para los Filtros ---
st.subheader("⚙️ Configura los Filtros para tus Mensajes")
st.write("**1. Invite Aceptada:** (Filtro obligatorio: 'Si')")
# Este filtro es fijo en esta página según el requerimiento
st.session_state.mensaje_filtros["invite_aceptada"] = "si" # Asegura que siempre esté en 'si'

st.write("**2. Filtros Adicionales (Opcional):**")
with st.expander("Ver/Ocultar Filtros Adicionales"):
    col1_filtros, col2_filtros = st.columns(2)

    with col1_filtros:
        # Asegurarse de que la columna existe antes de obtener opciones
        opciones_fuente = ["– Todos –"] + (
            sorted(df["Fuente de la Lista"].dropna().astype(str).unique().tolist())
            if "Fuente de la Lista" in df.columns and not df["Fuente de la Lista"].empty else [])
        st.session_state.mensaje_filtros["fuente_lista"] = st.multiselect(
            "Fuente de la Lista", opciones_fuente,
            default=st.session_state.mensaje_filtros.get("fuente_lista", ["– Todos –"]),
            key="ms_fuente_lista_msg_page_v3")

        # Asegurarse de que la columna existe antes de obtener opciones
        opciones_proceso = ["– Todos –"] + (
            sorted(df["Proceso"].dropna().astype(str).unique().tolist())
            if "Proceso" in df.columns and not df["Proceso"].empty else [])
        st.session_state.mensaje_filtros["proceso"] = st.multiselect(
            "Proceso", opciones_proceso,
            default=st.session_state.mensaje_filtros.get("proceso", ["– Todos –"]),
            key="ms_proceso_msg_page_v3")

        # Asegurarse de que la columna existe antes de obtener opciones
        avatares_unicos_filt = ["– Todos –"]
        if "Avatar" in df.columns and not df["Avatar"].empty:
            avatares_unicos_filt.extend(sorted(df["Avatar"].dropna().astype(str).unique().tolist()))
        st.session_state.mensaje_filtros["avatar"] = st.multiselect(
            "Avatar", avatares_unicos_filt,
            default=st.session_state.mensaje_filtros.get("avatar", ["– Todos –"]),
            key="ms_avatar_msg_page_v3")

    with col2_filtros:
        # Asegurarse de que la columna existe antes de obtener opciones
        opciones_pais = ["– Todos –"] + (
            sorted(df["Pais"].dropna().astype(str).unique().tolist())
            if "Pais" in df.columns and not df["Pais"].empty else [])
        st.session_state.mensaje_filtros["pais"] = st.multiselect(
            "País", opciones_pais,
            default=st.session_state.mensaje_filtros.get("pais", ["– Todos –"]),
            key="ms_pais_msg_page_v3")

        # Asegurarse de que la columna existe antes de obtener opciones
        opciones_industria = ["– Todos –"] + (
            sorted(df["Industria"].dropna().astype(str).unique().tolist())
            if "Industria" in df.columns and not df["Industria"].empty else [])
        st.session_state.mensaje_filtros["industria"] = st.multiselect(
            "Industria", opciones_industria,
            default=st.session_state.mensaje_filtros.get("industria", ["– Todos –"]),
            key="ms_industria_msg_page_v3")

        # Asegurarse de que la columna existe antes de obtener opciones
        opciones_prospectador = ["– Todos –"] + (
            sorted(df["¿Quién Prospecto?"].dropna().astype(str).unique().tolist())
            if "¿Quién Prospecto?" in df.columns and not df["¿Quién Prospecto?"].empty else [])
        st.session_state.mensaje_filtros["prospectador"] = st.multiselect(
            "¿Quién Prospectó?", opciones_prospectador,
            default=st.session_state.mensaje_filtros.get("prospectador", ["– Todos –"]),
            key="ms_prospectador_msg_page_v3")

    with st.container():
        st.markdown("---")
        fecha_min_data_val, fecha_max_data_val = None, None
        columna_fecha_para_ui = "Fecha Primer Mensaje"
        # Asegurarse de que la columna de fecha existe y es datetime antes de obtener min/max
        if columna_fecha_para_ui in df.columns and pd.api.types.is_datetime64_any_dtype(df[columna_fecha_para_ui]):
             valid_dates_filt = df[columna_fecha_para_ui].dropna()
             if not valid_dates_filt.empty:
                 # Asegurarse de que son objetos date para el date_input
                 fecha_min_data_val = valid_dates_filt.min().date()
                 fecha_max_data_val = valid_dates_filt.max().date()

        col_sesion_filt, col_f1_filt, col_f2_filt = st.columns(3)
        with col_sesion_filt:
            opciones_sesion_filt = ["– Todos –", "Si", "No"]
            current_sesion_val_filt = st.session_state.mensaje_filtros.get("sesion_agendada", "– Todos –")
            # Normalizar el valor actual para que coincida con las opciones si es necesario
            if isinstance(current_sesion_val_filt, str):
                 lower_val = current_sesion_val_filt.strip().lower()
                 if lower_val == "si": current_sesion_val_filt = "Si"
                 elif lower_val == "no": current_sesion_val_filt = "No"
                 else: current_sesion_val_filt = "– Todos –" # Default si no es ni "Si" ni "No"

            # Asegurar que el valor por defecto esté en las opciones
            if current_sesion_val_filt not in opciones_sesion_filt:
                 current_sesion_val_filt = "– Todos –"

            st.session_state.mensaje_filtros["sesion_agendada"] = st.selectbox(
                "¿Sesión Agendada?", opciones_sesion_filt,
                index=opciones_sesion_filt.index(current_sesion_val_filt),
                key="sb_sesion_agendada_msg_page_v3")

        with col_f1_filt:
            # Si no hay fechas válidas, establecer min/max_value a None o la fecha actual si prefieres
            st.session_state.mensaje_filtros["fecha_ini"] = st.date_input(
                "Desde (Fecha Primer Mensaje)",
                value=st.session_state.mensaje_filtros.get("fecha_ini", fecha_min_data_val if fecha_min_data_val else None), # Valor inicial sensible
                format='DD/MM/YYYY',
                key="di_fecha_ini_msg_page_v3",
                min_value=fecha_min_data_val,
                max_value=fecha_max_data_val)
        with col_f2_filt:
            st.session_state.mensaje_filtros["fecha_fin"] = st.date_input(
                "Hasta (Fecha Primer Mensaje)",
                value=st.session_state.mensaje_filtros.get("fecha_fin", fecha_max_data_val if fecha_max_data_val else None), # Valor inicial sensible
                format='DD/MM/YYYY',
                key="di_fecha_fin_msg_page_v3",
                min_value=fecha_min_data_val,
                max_value=fecha_max_data_val)


# Campo de búsqueda de texto
st.session_state.mensaje_filtros["busqueda"] = st.text_input(
    "🔎 Buscar en Nombre, Apellido, Empresa, Puesto",
    value=st.session_state.mensaje_filtros.get("busqueda", ""),
    placeholder="Ingrese término y presione Enter",
    key="ti_busqueda_msg_page_v3")

# Botones de acción (Filtrar y Limpiar)
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("📬 Cargar y Filtrar Prospectos para Mensaje",
                    key="btn_cargar_filtrar_msg_page_v3"):
        st.session_state.mostrar_tabla_mensajes = True # Activa la visualización de resultados

with col_btn2:
    st.button("🧹 Limpiar Filtros de Mensajes",
                on_click=reset_mensaje_filtros_state, # Llama a la función de reinicio
                key="btn_limpiar_filtros_msg_page_v3")


# --- Sección de Resultados y Generador de Mensajes (se muestra al filtrar) ---
if st.session_state.mostrar_tabla_mensajes:
    st.markdown("---")
    st.subheader("📬 Resultado de los Filtros y Generador de Mensajes")

    df_mensajes_filtrado_temp = df.copy()

    # Aplicar el filtro fijo de "Invite Aceptada?"
    if "¿Invite Aceptada?" in df_mensajes_filtrado_temp.columns:
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[
            df_mensajes_filtrado_temp["¿Invite Aceptada?"].apply(
                limpiar_valor_kpi).astype(str).str.lower() ==
            str(st.session_state.mensaje_filtros["invite_aceptada"]).lower()]
    else:
        st.warning("Columna '¿Invite Aceptada?' no encontrada. No se pudo aplicar el filtro obligatorio.")
        df_mensajes_filtrado_temp = pd.DataFrame() # Vaciar si la columna esencial no está


    # Aplicar filtros adicionales solo si hay datos después del filtro obligatorio
    if not df_mensajes_filtrado_temp.empty:
        filtro_sesion_para_aplicar = st.session_state.mensaje_filtros.get("sesion_agendada", "– Todos –")
        # Normalizar el valor del filtro para la función
        if isinstance(filtro_sesion_para_aplicar, str):
            lower_val = filtro_sesion_para_aplicar.strip().lower()
            if lower_val == "si": filtro_sesion_para_aplicar = "Si"
            elif lower_val == "no": filtro_sesion_para_aplicar = "No"
            else: filtro_sesion_para_aplicar = "– Todos –"

        df_mensajes_filtrado_temp = aplicar_filtros_mensajes(
            df_mensajes_filtrado_temp,
            st.session_state.mensaje_filtros.get("fuente_lista", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("proceso", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("pais", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("industria", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("avatar", ["– Todos –"]),
            st.session_state.mensaje_filtros.get("prospectador", ["– Todos –"]),
            filtro_sesion_para_aplicar, # Pasa el valor normalizado
            st.session_state.mensaje_filtros.get("fecha_ini", None),
            st.session_state.mensaje_filtros.get("fecha_fin", None),
            "Fecha Primer Mensaje"
        )

        # Aplicar filtro de búsqueda de texto
        busqueda_term_final = st.session_state.mensaje_filtros.get("busqueda", "").lower().strip()
        if busqueda_term_final and not df_mensajes_filtrado_temp.empty:
             # Realiza la búsqueda en múltiples columnas
             mask_busqueda = pd.Series([False] * len(df_mensajes_filtrado_temp), index=df_mensajes_filtrado_temp.index)
             columnas_para_busqueda_texto = ["Empresa", "Puesto"] # Columnas adicionales para buscar
             for col_busc in columnas_para_busqueda_texto:
                 if col_busc in df_mensajes_filtrado_temp.columns:
                      mask_busqueda |= df_mensajes_filtrado_temp[col_busc].astype(str).str.lower().str.contains(busqueda_term_final, na=False)

             # Búsqueda en Nombre y Apellido combinados o por separado
             nombre_col_df, apellido_col_df = "Nombre", "Apellido"
             if nombre_col_df in df_mensajes_filtrado_temp.columns and apellido_col_df in df_mensajes_filtrado_temp.columns:
                  nombre_completo_busq = (df_mensajes_filtrado_temp[nombre_col_df].fillna('') + ' ' + df_mensajes_filtrado_temp[apellido_col_df].fillna('')).str.lower()
                  mask_busqueda |= nombre_completo_busq.str.contains(busqueda_term_final, na=False)
             elif nombre_col_df in df_mensajes_filtrado_temp.columns:
                  mask_busqueda |= df_mensajes_filtrado_temp[nombre_col_df].astype(str).str.lower().str.contains(busqueda_term_final, na=False)
             elif apellido_col_df in df_mensajes_filtrado_temp.columns:
                  mask_busqueda |= df_mensajes_filtrado_temp[apellido_col_df].astype(str).str.lower().str.contains(busqueda_term_final, na=False)

             df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[mask_busqueda]


    df_mensajes_final_display = df_mensajes_filtrado_temp.copy()


    # --- Mostrar la tabla de resultados ---
    if df_mensajes_final_display.empty:
        st.warning(
            "No se encontraron prospectos que cumplan todos los criterios de filtro.")
    else:
        # Preparar columnas adicionales para la visualización y generación de mensajes
        linkedin_col_nombre = "LinkedIn" # Nombre de la columna de LinkedIn
        columna_fecha_a_mostrar = "Fecha Primer Mensaje"

        # Asegurarse de que las columnas necesarias existan para evitar errores, añadiéndolas si falta alguna
        columnas_esenciales_display = [
            "Nombre", "Apellido", "Empresa", "Puesto", "Proceso", "Avatar",
            columna_fecha_a_mostrar, "¿Quién Prospecto?", linkedin_col_nombre,
            "Sesion Agendada?"
            ]
        for col in columnas_esenciales_display:
            if col not in df_mensajes_final_display.columns:
                df_mensajes_final_display[col] = pd.NA # O "" si prefieres string vacío

        # Clasificar por proceso para la selección de plantilla
        df_mensajes_final_display["Categoría"] = df_mensajes_final_display["Proceso"].apply(clasificar_por_proceso)
        # Crear nombre completo para display
        df_mensajes_final_display["Nombre_Completo_Display"] = df_mensajes_final_display.apply(
                lambda row: limpiar_nombre_completo(row.get("Nombre"), row.get("Apellido")), axis=1)


        st.markdown("### 📋 Prospectos Encontrados para Mensajes")
        st.write(f"Mostrando **{len(df_mensajes_final_display)}** prospectos.")

        # Definir las columnas a mostrar en la tabla principal de resultados
        columnas_para_tabla_display = [
            "Nombre_Completo_Display", "Empresa", "Puesto", "Categoría",
            "Avatar", columna_fecha_a_mostrar, "¿Quién Prospecto?",
            "Sesion Agendada?", linkedin_col_nombre
        ]
        # Filtrar solo las columnas que realmente existen en el DataFrame
        cols_realmente_en_df_para_tabla = [
            col for col in columnas_para_tabla_display
            if col in df_mensajes_final_display.columns
        ]

        df_tabla_a_mostrar = df_mensajes_final_display[cols_realmente_en_df_para_tabla].copy()

        # Formatear la columna de fecha para mostrar
        if columna_fecha_a_mostrar in df_tabla_a_mostrar.columns:
            # Asegurarse de que la columna es datetime antes de formatear
            if pd.api.types.is_datetime64_any_dtype(df_tabla_a_mostrar[columna_fecha_a_mostrar]):
                 df_tabla_a_mostrar[columna_fecha_a_mostrar] = df_tabla_a_mostrar[columna_fecha_a_mostrar].dt.strftime('%d/%m/%Y')
            else:
                 df_tabla_a_mostrar[columna_fecha_a_mostrar] = "Fecha Inválida/No DateType"

        # Mostrar la tabla principal de resultados
        st.dataframe(df_tabla_a_mostrar, use_container_width=True)


        st.markdown("---")
        st.markdown("### 📬️ Generador de Mensajes")

        # Definición de las plantillas de mensajes por categoría
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
            }
        }

        # Obtener las categorías presentes en los datos filtrados que tienen plantillas definidas
        categorias_con_plantillas_definidas = list(opciones_mensajes.keys())
        categorias_validas_en_df = sorted(df_mensajes_final_display["Categoría"].drop_duplicates().dropna().tolist()) # Excluir NaN
        categorias_reales_con_plantillas_en_df = [
            cat for cat in categorias_validas_en_df
            if cat in categorias_con_plantillas_definidas
        ]

        # Opciones para el Selectbox de Categoría
        opcion_todas_las_categorias = "– Todas las Categorías –"
        categorias_seleccionables_para_widget = [opcion_todas_las_categorias] + categorias_reales_con_plantillas_en_df

        # Manejar la selección de categoría
        default_categoria_index = 0
        if 'mensaje_categoria_sel_v3' in st.session_state and st.session_state.mensaje_categoria_sel_v3 in categorias_seleccionables_para_widget:
            default_categoria_index = categorias_seleccionables_para_widget.index(st.session_state.mensaje_categoria_sel_v3)

        # Mostrar selectbox de categoría solo si hay opciones válidas
        if not categorias_reales_con_plantillas_en_df and "General" not in opciones_mensajes:
             st.warning("No hay prospectos con categorías con plantillas definidas en los datos filtrados.")
        else:
            col_sel_cat, col_sel_plantilla = st.columns(2)
            with col_sel_cat:
                categoria_sel_widget = st.selectbox(
                    "1. Selecciona una Categoría de Proceso:",
                    categorias_seleccionables_para_widget,
                    index=default_categoria_index,
                    key="mensaje_categoria_sel_v3"
                )

            # Determinar qué plantillas mostrar según la categoría seleccionada
            plantillas_para_categoria_sel = {}
            nombres_plantillas_para_categoria_sel = []
            categoria_usada_para_plantillas = ""

            if categoria_sel_widget == opcion_todas_las_categorias:
                if "General" in opciones_mensajes:
                    plantillas_para_categoria_sel = opciones_mensajes["General"]
                    nombres_plantillas_para_categoria_sel = list(plantillas_para_categoria_sel.keys())
                    categoria_usada_para_plantillas = "General"
                else:
                    st.warning("La opción 'Todas las Categorías' requiere que exista una categoría 'General' con plantillas.")
            elif categoria_sel_widget in opciones_mensajes:
                plantillas_para_categoria_sel = opciones_mensajes.get(categoria_sel_widget, {})
                nombres_plantillas_para_categoria_sel = list(plantillas_para_categoria_sel.keys())
                categoria_usada_para_plantillas = categoria_sel_widget

            with col_sel_plantilla:
                # Manejar la selección de plantilla
                default_plantilla_index = 0
                if 'mensaje_plantilla_sel_v3' in st.session_state and st.session_state.mensaje_plantilla_sel_v3 in nombres_plantillas_para_categoria_sel:
                    default_plantilla_index = nombres_plantillas_para_categoria_sel.index(st.session_state.mensaje_plantilla_sel_v3)

                nombre_plantilla_sel = None # Inicializar a None
                if nombres_plantillas_para_categoria_sel:
                    nombre_plantilla_sel = st.selectbox(
                        "2. Escoge una Plantilla de Mensaje:",
                        nombres_plantillas_para_categoria_sel,
                        index=default_plantilla_index,
                        key="mensaje_plantilla_sel_v3"
                    )
                    mensaje_final_seleccionado = plantillas_para_categoria_sel.get(nombre_plantilla_sel, "")
                else:
                    st.info(f"No hay plantillas disponibles para la categoría '{categoria_sel_widget}'.")
                    mensaje_final_seleccionado = "" # No hay plantilla seleccionada si no hay opciones


            # --- Generación y Visualización de Mensajes ---
            if mensaje_final_seleccionado:
                # Filtrar el DataFrame base para generar mensajes solo para la categoría seleccionada (o todas si aplica)
                if categoria_sel_widget == opcion_todas_las_categorias:
                    # Si es "Todas", usar todos los prospectos que tengan una categoría con plantilla definida
                     df_vista_previa_msg = df_mensajes_final_display[
                         df_mensajes_final_display["Categoría"].isin(categorias_reales_con_plantillas_en_df)
                         ].copy()
                else:
                    # Si es una categoría específica, usar solo los prospectos de esa categoría
                    df_vista_previa_msg = df_mensajes_final_display[
                        df_mensajes_final_display["Categoría"] == categoria_sel_widget
                    ].copy()

                # Si no hay prospectos en la categoría seleccionada después de los filtros...
                if df_vista_previa_msg.empty:
                    st.info(
                        f"No hay prospectos en la categoría '{categoria_sel_widget}' con los filtros actuales para generar mensajes."
                    )
                else:
                    # Función auxiliar para determinar el género del avatar para el saludo
                    def obtener_atencion_genero(avatar_de_fila):
                        avatar_estandarizado_lower = str(avatar_de_fila).lower().strip() if pd.notna(avatar_de_fila) else ""
                        # Define palabras clave o nombres para determinar el género del avatar
                        nombres_masculinos_clave = ["john", "juan", "carlos", "pedro"] # Ejemplos
                        nombres_femeninos_clave = ["maría", "ana", "laura", "isabella", "maria"] # Ejemplos

                        if any(keyword in avatar_estandarizado_lower for keyword in nombres_masculinos_clave):
                            return "atento"
                        if any(keyword in avatar_estandarizado_lower for keyword in nombres_femeninos_clave):
                            return "atenta"
                        return "atento/a" # Valor por defecto si no se puede determinar

                    # Generar la columna de Mensaje Personalizado aplicando la plantilla
                    df_vista_previa_msg["Mensaje_Personalizado"] = df_vista_previa_msg.apply(
                            lambda row: mensaje_final_seleccionado.replace(
                                "{nombre}",
                                # Usa el primer nombre si existe, si no, usa un placeholder
                                str(row.get("Nombre", "")).split()[0] if pd.notna(row.get("Nombre")) and str(row.get("Nombre")).strip() else "[Nombre]"
                            ).replace(
                                "{avatar}",
                                # Usa el Avatar si existe, si no, usa un placeholder
                                str(row.get("Avatar", "Tu Nombre")).strip() if pd.notna(row.get("Avatar")) else "[Avatar]"
                            ).replace(
                                "[Nombre de la empresa]",
                                # Usa el nombre de la empresa si existe, si no, usa un placeholder
                                str(row.get("Empresa", "[Nombre de la empresa]")).strip() if pd.notna(row.get("Empresa")) else "[Nombre de la empresa]"
                            ).replace(
                                "{atencion_genero}",
                                # Determina el saludo basado en el Avatar
                                obtener_atencion_genero(row.get("Avatar"))
                            ),
                            axis=1
                        )

                    # --- Visualización de la tabla de mensajes generados con selección ---
                    st.markdown("### 📟 Vista Previa de Mensajes Generados")
                    st.markdown("💡 **Haz click en una fila en la tabla siguiente para ver el mensaje completo y copiarlo fácilmente.**")

                    # Columnas a mostrar en la tabla de vista previa (sin el mensaje completo)
                    cols_generador_display = [
                        "Nombre_Completo_Display", "Empresa", "Puesto",
                        "Avatar", "Sesion Agendada?", linkedin_col_nombre
                        # 'Mensaje_Personalizado' se quita de aquí para mostrarse en el text_area
                    ]
                    # Asegurarse de que las columnas existan antes de mostrarlas
                    cols_reales_generador = [
                        col for col in cols_generador_display
                        if col in df_vista_previa_msg.columns
                    ]

                    # Mostrar la tabla de vista previa y permitir la selección de una fila
                    # La variable selected_rows_data contendrá la información de la selección
                    selected_rows_data = st.dataframe(
                        df_vista_previa_msg[cols_reales_generador], # Mostrar solo las columnas seleccionadas
                        use_container_width=True,
                        height=300,
                        selection_mode="single-row", # Habilita la selección de una única fila
                        hide_index=True # Oculta el índice por defecto de pandas
                    )

                    # --- Mostrar el Mensaje Completo en un Área de Texto al Seleccionar una Fila ---
                    selected_indices = []
                    # CORRECCIÓN MÁS ROBUSTA APLICADA AQUÍ: Verificación segura de la selección
                    # Comprobamos si selected_rows_data es un diccionario y si tiene la estructura de selección esperada
                    if isinstance(selected_rows_data, dict) and "selection" in selected_rows_data and "rows" in selected_rows_data["selection"]:
                         selected_indices = selected_rows_data["selection"]["rows"] # Esto será una lista de índices (vacía o con 1 elemento)

                    # Si la lista de índices seleccionados NO está vacía (es decir, se seleccionó una fila)
                    if selected_indices:
                        # Obtener el índice de la primera (y única, en modo single-row) fila seleccionada
                        selected_index = selected_indices[0]
                        # Recuperar los datos completos de esa fila del DataFrame original con los mensajes generados
                        selected_prospect = df_vista_previa_msg.iloc[selected_index]

                        st.markdown("---")
                        st.subheader(f"Mensaje completo para {selected_prospect.get('Nombre_Completo_Display', 'el prospecto seleccionado')}:")
                        st.info(f"**Categoría:** {selected_prospect.get('Categoría', 'N/A')} | **Plantilla:** {nombre_plantilla_sel}")

                        # Mostrar el mensaje completo en un text_area para facilitar la copia
                        st.text_area(
                            "Copiar mensaje (presiona Ctrl+A para seleccionar todo, luego Ctrl+C):",
                            selected_prospect.get('Mensaje_Personalizado', 'Mensaje no disponible.'),
                            height=250, # Ajusta la altura según necesites
                            key=f"selected_message_copy_{selected_index}_v4" # Clave única para el widget text_area basada en el índice de la fila
                        )
                    else:
                        # Mostrar un mensaje si no hay fila seleccionada
                        st.info("Selecciona un prospecto en la tabla de arriba para ver su mensaje completo aquí.")

                    st.markdown("---") # Separador antes del botón de descarga

                    # --- Sección de Descarga ---
                    @st.cache_data
                    def convert_df_to_csv_final(df_to_convert_csv):
                        # Columnas que se incluirán en el archivo CSV de descarga
                        cols_descarga = [
                            "Nombre_Completo_Display", "Empresa", "Puesto",
                            "Sesion Agendada?", linkedin_col_nombre,
                            "Mensaje_Personalizado" # Incluir la columna del mensaje para la descarga
                        ]
                        # Filtrar solo las columnas que existen en el DataFrame antes de exportar
                        cols_exist_descarga = [
                            col for col in cols_descarga
                            if col in df_to_convert_csv.columns
                        ]
                        # Si no hay columnas para descargar, retorna None
                        if not cols_exist_descarga: return None

                        # Seleccionar las columnas y llenar valores nulos con string vacío para la exportación
                        df_csv_export = df_to_convert_csv[cols_exist_descarga].fillna('')
                        # Convertir el DataFrame a formato CSV con codificación UTF-8
                        return df_csv_export.to_csv(index=False).encode('utf-8')

                    # Generar los datos CSV para la descarga
                    # Usamos df_vista_previa_msg que contiene la columna 'Mensaje_Personalizado' generada
                    csv_data_final = convert_df_to_csv_final(df_vista_previa_msg)

                    # Generar el nombre del archivo CSV basado en la categoría y plantilla seleccionadas
                    # Asegurarse de que el nombre sea válido para un archivo (reemplazar espacios, lower case)
                    nombre_archivo_cat_final = categoria_usada_para_plantillas if categoria_sel_widget == opcion_todas_las_categorias and categoria_usada_para_plantillas else categoria_sel_widget
                    if nombre_archivo_cat_final == opcion_todas_las_categorias:
                        nombre_archivo_cat_final = "todas_categorias" # Nombre genérico si se seleccionó la opción "Todas"

                    # Mostrar el botón de descarga si los datos CSV se generaron correctamente
                    if csv_data_final is not None:
                        st.download_button(
                            label="⬇️ Descargar Mensajes Generados (CSV)",
                            data=csv_data_final,
                            file_name=
                            f'mensajes_{nombre_archivo_cat_final.replace(" ", "_").lower()}_{nombre_plantilla_sel.replace(" ", "_").lower() if nombre_plantilla_sel else "sin_plantilla"}.csv',
                            mime='text/csv',
                            key="btn_download_csv_msg_page_v3"
                        )
                    else:
                         st.info("No hay datos de mensajes generados para descargar con los filtros y plantilla actuales.")

            # Mensaje si no se seleccionó una plantilla
            elif nombres_plantillas_para_categoria_sel:
                st.info(
                    "Selecciona una plantilla de mensaje para generar la vista previa y la opción de descarga.")
            # Mensaje si no hay plantillas disponibles para la categoría
            # Esto ya se maneja dentro del bloque else del segundo selectbox, pero se deja por claridad
            # else:
            #      st.info(f"No hay plantillas definidas para la categoría '{categoria_sel_widget}'.")


# --- Pie de página ---
st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
