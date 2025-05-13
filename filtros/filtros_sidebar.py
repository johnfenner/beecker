# En el archivo: filtros_sidebar.py

import streamlit as st
import datetime # No se usa directamente, pero es bueno tenerlo por si acaso para fechas
import pandas as pd


# Función para resetear el estado de los filtros a sus valores por defecto
def reset_filters_state():
    """Resets all filter keys in st.session_state to their default values."""
    st.session_state["filtro_fuente_lista"] = ["– Todos –"]
    st.session_state["filtro_proceso"] = ["– Todos –"]
    st.session_state["filtro_pais"] = ["– Todos –"]
    st.session_state["filtro_industria"] = ["– Todos –"]
    st.session_state["filtro_avatar"] = ["– Todos –"]
    st.session_state["filtro_prospectador"] = ["– Todos –"]
    st.session_state["filtro_invite_aceptada_simple"] = "– Todos –"
    st.session_state["filtro_sesion_agendada"] = "– Todos –"
    st.session_state["busqueda"] = ""
    st.session_state["fecha_ini"] = None
    st.session_state["fecha_fin"] = None
    st.toast("Filtros reiniciados ✅")


# Función genérica para crear selectores múltiples (Multiselect) - Usa st.multiselect
def crear_multiselect(df, columna, etiqueta, key):
    """Creates a multiselect widget for a given column, managing state with key."""
    if key not in st.session_state:
        st.session_state[key] = ["– Todos –"]

    options = ["– Todos –"]
    if columna in df.columns and not df[columna].empty:
        valores_data = sorted(df[columna].dropna().astype(str).unique())
        options = ["– Todos –"] + valores_data

    current_value = st.session_state[key]
    # Asegurarse que el valor actual en session_state sea válido con las opciones disponibles
    valid_value = [val for val in current_value if val in options]

    if len(valid_value) != len(current_value) or not valid_value: # si no hay valores válidos o se eliminaron opciones
        st.session_state[key] = ["– Todos –"] if "– Todos –" in options else ([options[0]] if options else [])


    # Usar st.multiselect y actualizar st.session_state[key] directamente
    # Streamlit maneja la actualización del valor en session_state basado en la interacción del widget si la key coincide.
    st.session_state[key] = st.multiselect(
        etiqueta,
        options,
        default=st.session_state[key], # Usar el valor actual del session_state como default
        key=f"widget_{key}" # Usar una key diferente para el widget si la key de session_state se usa en otro lado
                            # o asegurarse que la key es única para el widget.
                            # Si la key del widget es la misma que la de session_state, Streamlit la maneja bien.
    )
    return st.session_state[key]


# Función genérica para crear selectores simples (Selectbox) - Usa st.selectbox
def crear_selectbox(df, columna, etiqueta, key):
    """Creates a selectbox widget for a given column, normalizing options and managing state with key."""
    if key not in st.session_state:
        st.session_state[key] = "– Todos –"

    options = ["– Todos –"]
    if columna in df.columns and not df[columna].empty:
        # Normalizar los valores para evitar duplicados por capitalización o espacios
        valores_unicos_normalizados = df[columna].dropna().astype(
            str).str.strip().str.title().unique()
        valores_ordenados_para_filtro = sorted(
            valores_unicos_normalizados.tolist())
        options = ["– Todos –"] + valores_ordenados_para_filtro

    widget_value = st.session_state[key]

    # Si el valor actual en session_state no es una opción válida, resetear a "– Todos –"
    if widget_value not in options:
        st.session_state[key] = "– Todos –"
        widget_value = st.session_state[key] # Actualizar widget_value después del posible reseteo

    # Determinar el índice para el valor por defecto del widget
    index_valor = options.index(widget_value) if widget_value in options else 0

    # Usar st.selectbox y Streamlit actualizará st.session_state[key]
    st.session_state[key] = st.selectbox(
        etiqueta,
        options,
        index=index_valor,
        key=f"widget_{key}" # Similar al multiselect, considerar la gestión de la key del widget
    )
    return st.session_state[key]


# --- FUNCIÓN PRINCIPAL PARA MOSTRAR FILTROS ---


def mostrar_filtros_sidebar(df, modo_fechas="invite"):
    """Displays all filter widgets in the sidebar using columns for horizontal grouping."""
    st.sidebar.header("🎯 Filtros de Búsqueda")

    # Inicializar estado si no existe (esto ya estaba, lo mantenemos)
    # Aunque las funciones crear_multiselect/crear_selectbox ya lo hacen, no está de más
    if "filtro_fuente_lista" not in st.session_state:
        st.session_state["filtro_fuente_lista"] = ["– Todos –"]
    if "filtro_proceso" not in st.session_state:
        st.session_state["filtro_proceso"] = ["– Todos –"]
    # ... (mantener todas las inicializaciones de session_state si es necesario) ...
    if "fecha_ini" not in st.session_state:
        st.session_state["fecha_ini"] = None # Usar None para date_input si no hay fecha inicial
    if "fecha_fin" not in st.session_state:
        st.session_state["fecha_fin"] = None


    st.sidebar.subheader("Filtros de Origen")
    col1_1, col1_2 = st.sidebar.columns(2)
    with col1_1:
        # La función crear_multiselect ya actualiza session_state, no es necesario reasignar
        crear_multiselect(df, "Fuente de la Lista",
                                                "Fuente de la Lista",
                                                "filtro_fuente_lista")
    with col1_2:
        crear_multiselect(df, "Proceso", "Proceso",
                                           "filtro_proceso")

    col2_1, col2_2 = st.sidebar.columns(2)
    with col2_1:
        crear_multiselect(df, "Pais", "País", "filtro_pais")
    with col2_2:
        crear_multiselect(df, "Industria", "Industria",
                                             "filtro_industria")

    col3_1, col3_2 = st.sidebar.columns(2)
    with col3_1:
        crear_multiselect(df, "Avatar", "Avatar",
                                          "filtro_avatar")
    with col3_2:
        crear_multiselect(df, "¿Quién Prospecto?",
                                                "¿Quién Prospectó?",
                                                "filtro_prospectador")

    st.sidebar.subheader("Filtros de Interacción")
    col_invite, col_sesion = st.sidebar.columns(2)
    with col_invite:
        crear_selectbox(
            df, "¿Invite Aceptada?", "¿Invite Aceptada?",
            "filtro_invite_aceptada_simple")
    with col_sesion:
        crear_selectbox(df, "Sesion Agendada?",
                                                 "¿Sesión Agendada?",
                                                 "filtro_sesion_agendada")

    st.sidebar.subheader("Filtro de Fechas")
    col_f1, col_f2 = st.sidebar.columns(2)

    fecha_min_data = None
    fecha_max_data = None
    
    # --- SECCIÓN MODIFICADA PARA USAR LA COLUMNA DE FECHA CORRECTA ---
    # Reemplaza "Fecha Primer Mensaje" con el nombre real de tu columna de primer mensaje
    nombre_columna_para_rango_fechas = (
        "Fecha Primer Mensaje" if modo_fechas == "primer_mensaje" else "Fecha de Invite"
    ) 

    if nombre_columna_para_rango_fechas in df.columns:
        # Asegurarse que la columna es de tipo datetime
        if not pd.api.types.is_datetime64_any_dtype(df[nombre_columna_para_rango_fechas]):
            # Intentar convertirla si no lo es, idealmente esto se hace al cargar los datos
            try:
                df[nombre_columna_para_rango_fechas] = pd.to_datetime(df[nombre_columna_para_rango_fechas], errors='coerce')
            except Exception: # Captura una excepción más genérica si la conversión falla
                st.sidebar.warning(f"No se pudo convertir la columna '{nombre_columna_para_rango_fechas}' a fecha.")
                # Continuar sin min/max si la conversión falla
        
        # Proceder solo si es datetime después de la conversión (o si ya lo era)
        if pd.api.types.is_datetime64_any_dtype(df[nombre_columna_para_rango_fechas]):
            valid_dates = df[nombre_columna_para_rango_fechas].dropna() 
            if not valid_dates.empty:
                fecha_min_data = valid_dates.min().date()
                fecha_max_data = valid_dates.max().date()
    else:
        st.sidebar.warning(f"Columna '{nombre_columna_para_rango_fechas}' no encontrada para el rango de fechas.")
    # --- FIN DE SECCIÓN MODIFICADA ---

    with col_f1:
        # st.date_input actualiza st.session_state[key] directamente
        st.session_state["fecha_ini"] = st.date_input(
            "Desde (Primer Mensaje)",  # <--- ETIQUETA MODIFICADA (Opcional, pero recomendado)
            value=st.session_state.get("fecha_ini", None), # Usar None para permitir que el usuario elija
            format='DD/MM/YYYY',
            key="widget_fecha_ini", # Usar una key diferente para el widget para evitar conflictos con la de session_state si hay re-renders complejos
            min_value=fecha_min_data,
            max_value=fecha_max_data
        )
    with col_f2:
        st.session_state["fecha_fin"] = st.date_input(
            "Hasta (Primer Mensaje)",  # <--- ETIQUETA MODIFICADA (Opcional, pero recomendado)
            value=st.session_state.get("fecha_fin", None),
            format='DD/MM/YYYY',
            key="widget_fecha_fin",
            min_value=fecha_min_data,
            max_value=fecha_max_data
        )

    st.sidebar.subheader("Búsqueda")
    st.session_state["busqueda"] = st.sidebar.text_input( # Actualiza session_state directamente
        "🔎 Buscar (Nombre, Apellido, Empresa, Puesto)",
        value=st.session_state.get("busqueda", ""),
        placeholder="Ingrese término y presione Enter",
        key="widget_busqueda"
    )

    st.sidebar.button("🧹 Limpiar Todos los Filtros",
                      on_click=reset_filters_state)

    # La sentencia de retorno simplemente obtiene los valores del session_state
    return (st.session_state.get("filtro_fuente_lista", ["– Todos –"]),
            st.session_state.get("filtro_proceso", ["– Todos –"]),
            st.session_state.get("filtro_pais", ["– Todos –"]),
            st.session_state.get("filtro_industria", ["– Todos –"]),
            st.session_state.get("filtro_avatar", ["– Todos –"]),
            st.session_state.get("filtro_prospectador", ["– Todos –"]),
            st.session_state.get("filtro_invite_aceptada_simple", "– Todos –"),
            st.session_state.get("filtro_sesion_agendada", "– Todos –"),
            st.session_state.get("fecha_ini", None),
            st.session_state.get("fecha_fin", None), 
            st.session_state.get("busqueda", "")
    )
# En el archivo: filtros_sidebar.py

import streamlit as st
import datetime # No se usa directamente, pero es bueno tenerlo por si acaso para fechas
import pandas as pd


# Función para resetear el estado de los filtros a sus valores por defecto
def reset_filters_state():
    """Resets all filter keys in st.session_state to their default values."""
    st.session_state["filtro_fuente_lista"] = ["– Todos –"]
    st.session_state["filtro_proceso"] = ["– Todos –"]
    st.session_state["filtro_pais"] = ["– Todos –"]
    st.session_state["filtro_industria"] = ["– Todos –"]
    st.session_state["filtro_avatar"] = ["– Todos –"]
    st.session_state["filtro_prospectador"] = ["– Todos –"]
    st.session_state["filtro_invite_aceptada_simple"] = "– Todos –"
    st.session_state["filtro_sesion_agendada"] = "– Todos –"
    st.session_state["busqueda"] = ""
    st.session_state["fecha_ini"] = None
    st.session_state["fecha_fin"] = None
    st.toast("Filtros reiniciados ✅")


# Función genérica para crear selectores múltiples (Multiselect) - Usa st.multiselect
def crear_multiselect(df, columna, etiqueta, key):
    """Creates a multiselect widget for a given column, managing state with key."""
    if key not in st.session_state:
        st.session_state[key] = ["– Todos –"]

    options = ["– Todos –"]
    if columna in df.columns and not df[columna].empty:
        valores_data = sorted(df[columna].dropna().astype(str).unique())
        options = ["– Todos –"] + valores_data

    current_value = st.session_state[key]
    # Asegurarse que el valor actual en session_state sea válido con las opciones disponibles
    valid_value = [val for val in current_value if val in options]

    if len(valid_value) != len(current_value) or not valid_value: # si no hay valores válidos o se eliminaron opciones
        st.session_state[key] = ["– Todos –"] if "– Todos –" in options else ([options[0]] if options else [])


    # Usar st.multiselect y actualizar st.session_state[key] directamente
    # Streamlit maneja la actualización del valor en session_state basado en la interacción del widget si la key coincide.
    st.session_state[key] = st.multiselect(
        etiqueta,
        options,
        default=st.session_state[key], # Usar el valor actual del session_state como default
        key=f"widget_{key}" # Usar una key diferente para el widget si la key de session_state se usa en otro lado
                            # o asegurarse que la key es única para el widget.
                            # Si la key del widget es la misma que la de session_state, Streamlit la maneja bien.
    )
    return st.session_state[key]


# Función genérica para crear selectores simples (Selectbox) - Usa st.selectbox
def crear_selectbox(df, columna, etiqueta, key):
    """Creates a selectbox widget for a given column, normalizing options and managing state with key."""
    if key not in st.session_state:
        st.session_state[key] = "– Todos –"

    options = ["– Todos –"]
    if columna in df.columns and not df[columna].empty:
        # Normalizar los valores para evitar duplicados por capitalización o espacios
        valores_unicos_normalizados = df[columna].dropna().astype(
            str).str.strip().str.title().unique()
        valores_ordenados_para_filtro = sorted(
            valores_unicos_normalizados.tolist())
        options = ["– Todos –"] + valores_ordenados_para_filtro

    widget_value = st.session_state[key]

    # Si el valor actual en session_state no es una opción válida, resetear a "– Todos –"
    if widget_value not in options:
        st.session_state[key] = "– Todos –"
        widget_value = st.session_state[key] # Actualizar widget_value después del posible reseteo

    # Determinar el índice para el valor por defecto del widget
    index_valor = options.index(widget_value) if widget_value in options else 0

    # Usar st.selectbox y Streamlit actualizará st.session_state[key]
    st.session_state[key] = st.selectbox(
        etiqueta,
        options,
        index=index_valor,
        key=f"widget_{key}" # Similar al multiselect, considerar la gestión de la key del widget
    )
    return st.session_state[key]


# --- FUNCIÓN PRINCIPAL PARA MOSTRAR FILTROS ---


def mostrar_filtros_sidebar(df, modo_fechas="invite"):
    """Displays all filter widgets in the sidebar using columns for horizontal grouping."""
    st.sidebar.header("🎯 Filtros de Búsqueda")

    # Inicializar estado si no existe (esto ya estaba, lo mantenemos)
    # Aunque las funciones crear_multiselect/crear_selectbox ya lo hacen, no está de más
    if "filtro_fuente_lista" not in st.session_state:
        st.session_state["filtro_fuente_lista"] = ["– Todos –"]
    if "filtro_proceso" not in st.session_state:
        st.session_state["filtro_proceso"] = ["– Todos –"]
    # ... (mantener todas las inicializaciones de session_state si es necesario) ...
    if "fecha_ini" not in st.session_state:
        st.session_state["fecha_ini"] = None # Usar None para date_input si no hay fecha inicial
    if "fecha_fin" not in st.session_state:
        st.session_state["fecha_fin"] = None


    st.sidebar.subheader("Filtros de Origen")
    col1_1, col1_2 = st.sidebar.columns(2)
    with col1_1:
        # La función crear_multiselect ya actualiza session_state, no es necesario reasignar
        crear_multiselect(df, "Fuente de la Lista",
                                                "Fuente de la Lista",
                                                "filtro_fuente_lista")
    with col1_2:
        crear_multiselect(df, "Proceso", "Proceso",
                                           "filtro_proceso")

    col2_1, col2_2 = st.sidebar.columns(2)
    with col2_1:
        crear_multiselect(df, "Pais", "País", "filtro_pais")
    with col2_2:
        crear_multiselect(df, "Industria", "Industria",
                                             "filtro_industria")

    col3_1, col3_2 = st.sidebar.columns(2)
    with col3_1:
        crear_multiselect(df, "Avatar", "Avatar",
                                          "filtro_avatar")
    with col3_2:
        crear_multiselect(df, "¿Quién Prospecto?",
                                                "¿Quién Prospectó?",
                                                "filtro_prospectador")

    st.sidebar.subheader("Filtros de Interacción")
    col_invite, col_sesion = st.sidebar.columns(2)
    with col_invite:
        crear_selectbox(
            df, "¿Invite Aceptada?", "¿Invite Aceptada?",
            "filtro_invite_aceptada_simple")
    with col_sesion:
        crear_selectbox(df, "Sesion Agendada?",
                                                 "¿Sesión Agendada?",
                                                 "filtro_sesion_agendada")

    st.sidebar.subheader("Filtro de Fechas")
    col_f1, col_f2 = st.sidebar.columns(2)

    fecha_min_data = None
    fecha_max_data = None
    
    # --- SECCIÓN MODIFICADA PARA USAR LA COLUMNA DE FECHA CORRECTA ---
    # Reemplaza "Fecha Primer Mensaje" con el nombre real de tu columna de primer mensaje
    nombre_columna_para_rango_fechas = (
        "Fecha Primer Mensaje" if modo_fechas == "primer_mensaje" else "Fecha de Invite"
    ) 

    if nombre_columna_para_rango_fechas in df.columns:
        # Asegurarse que la columna es de tipo datetime
        if not pd.api.types.is_datetime64_any_dtype(df[nombre_columna_para_rango_fechas]):
            # Intentar convertirla si no lo es, idealmente esto se hace al cargar los datos
            try:
                df[nombre_columna_para_rango_fechas] = pd.to_datetime(df[nombre_columna_para_rango_fechas], errors='coerce')
            except Exception: # Captura una excepción más genérica si la conversión falla
                st.sidebar.warning(f"No se pudo convertir la columna '{nombre_columna_para_rango_fechas}' a fecha.")
                # Continuar sin min/max si la conversión falla
        
        # Proceder solo si es datetime después de la conversión (o si ya lo era)
        if pd.api.types.is_datetime64_any_dtype(df[nombre_columna_para_rango_fechas]):
            valid_dates = df[nombre_columna_para_rango_fechas].dropna() 
            if not valid_dates.empty:
                fecha_min_data = valid_dates.min().date()
                fecha_max_data = valid_dates.max().date()
    else:
        st.sidebar.warning(f"Columna '{nombre_columna_para_rango_fechas}' no encontrada para el rango de fechas.")
    # --- FIN DE SECCIÓN MODIFICADA ---

    with col_f1:
        # st.date_input actualiza st.session_state[key] directamente
        st.session_state["fecha_ini"] = st.date_input(
            "Desde (Primer Mensaje)",  # <--- ETIQUETA MODIFICADA (Opcional, pero recomendado)
            value=st.session_state.get("fecha_ini", None), # Usar None para permitir que el usuario elija
            format='DD/MM/YYYY',
            key="widget_fecha_ini", # Usar una key diferente para el widget para evitar conflictos con la de session_state si hay re-renders complejos
            min_value=fecha_min_data,
            max_value=fecha_max_data
        )
    with col_f2:
        st.session_state["fecha_fin"] = st.date_input(
            "Hasta (Primer Mensaje)",  # <--- ETIQUETA MODIFICADA (Opcional, pero recomendado)
            value=st.session_state.get("fecha_fin", None),
            format='DD/MM/YYYY',
            key="widget_fecha_fin",
            min_value=fecha_min_data,
            max_value=fecha_max_data
        )

    st.sidebar.subheader("Búsqueda")
    st.session_state["busqueda"] = st.sidebar.text_input( # Actualiza session_state directamente
        "🔎 Buscar (Nombre, Apellido, Empresa, Puesto)",
        value=st.session_state.get("busqueda", ""),
        placeholder="Ingrese término y presione Enter",
        key="widget_busqueda"
    )

    st.sidebar.button("🧹 Limpiar Todos los Filtros",
                      on_click=reset_filters_state)

    # La sentencia de retorno simplemente obtiene los valores del session_state
    return (st.session_state.get("filtro_fuente_lista", ["– Todos –"]),
            st.session_state.get("filtro_proceso", ["– Todos –"]),
            st.session_state.get("filtro_pais", ["– Todos –"]),
            st.session_state.get("filtro_industria", ["– Todos –"]),
            st.session_state.get("filtro_avatar", ["– Todos –"]),
            st.session_state.get("filtro_prospectador", ["– Todos –"]),
            st.session_state.get("filtro_invite_aceptada_simple", "– Todos –"),
            st.session_state.get("filtro_sesion_agendada", "– Todos –"),
            st.session_state.get("fecha_ini", None),
            st.session_state.get("fecha_fin", None), 
            st.session_state.get("busqueda", "")
    )
