import streamlit as st
import pandas as pd
import sys
import os

st.set_page_config(page_title="Mensajes Personalizados", layout="wide")
# Añadir la raíz del proyecto al path
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from datos.carga_datos import cargar_y_limpiar_datos
from filtros.aplicar_filtros import aplicar_filtros
# --- CORRECCIÓN 1: Importar los nombres de variable correctos ---
from mensajes.mensajes import (
    plantilla_h2r_final, plantilla_p2p_final,
    plantilla_o2c_final, plantilla_general_final
)
from mensajes.mensajes_streamlit import clasificar_por_proceso
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar, limpiar_nombre_completo


# --- FUNCIÓN DE FILTRADO PERSONALIZADA PARA MENSAJES ---
def aplicar_filtros_mensajes(
    df,
    fuente_lista, proceso, pais, industria, avatar,
    prospectador, sesion_agendada, fecha_ini, fecha_fin,
    columna_fecha="Fecha Primer Mensaje"
):
    df_filtrado = df.copy()

    if fuente_lista and "– Todos –" not in fuente_lista:
        df_filtrado = df_filtrado[df_filtrado["Fuente de la Lista"].isin(fuente_lista)]
    if proceso and "– Todos –" not in proceso: # Filtro sobre la columna "Proceso" original
        df_filtrado = df_filtrado[df_filtrado["Proceso"].isin(proceso)]
    if pais and "– Todos –" not in pais:
        df_filtrado = df_filtrado[df_filtrado["Pais"].isin(pais)]
    if industria and "– Todos –" not in industria:
        df_filtrado = df_filtrado[df_filtrado["Industria"].isin(industria)]
    if avatar and "– Todos –" not in avatar:
        df_filtrado = df_filtrado[df_filtrado["Avatar"].isin(avatar)]
    if prospectador and "– Todos –" not in prospectador:
        df_filtrado = df_filtrado[df_filtrado["¿Quién Prospecto?"].isin(prospectador)]
    if sesion_agendada and sesion_agendada != "– Todos –":
        df_filtrado = df_filtrado[
            df_filtrado["Sesion Agendada?"].apply(lambda x: str(x).strip().lower() == str(sesion_agendada).strip().lower())
        ]
    if fecha_ini and fecha_fin and columna_fecha in df_filtrado.columns:
        if pd.api.types.is_datetime64_any_dtype(df_filtrado[columna_fecha]):
            df_filtrado = df_filtrado[
                (df_filtrado[columna_fecha].dt.date >= fecha_ini) &
                (df_filtrado[columna_fecha].dt.date <= fecha_fin)
            ]
    return df_filtrado

def reset_mensaje_filtros_state():
    st.session_state.mensaje_filtros = {
        "invite_aceptada": "si", "fuente_lista": ["– Todos –"], "proceso": ["– Todos –"], # Filtro por "Proceso" original
        "avatar": ["– Todos –"], "pais": ["– Todos –"], "industria": ["– Todos –"],
        "prospectador": ["– Todos –"], "sesion_agendada": "– Todos –",
        "fecha_ini": None, "fecha_fin": None, "busqueda": ""
    }
    st.session_state.mostrar_tabla_mensajes = False
    if 'mensaje_categoria_sel_v3' in st.session_state: del st.session_state['mensaje_categoria_sel_v3']
    if 'mensaje_plantilla_sel_v3' in st.session_state: del st.session_state['mensaje_plantilla_sel_v3']
    st.toast("Filtros de mensajes reiniciados ✅")

st.title("💌 Generador de Mensajes Personalizados")
st.markdown("Filtra prospectos que aceptaron tu invitación y genera mensajes personalizados.")

@st.cache_data
def get_base_data():
    df_base = cargar_y_limpiar_datos()
    col_fecha_ppal = "Fecha Primer Mensaje"
    if col_fecha_ppal in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base[col_fecha_ppal]):
        # --- CORRECCIÓN AQUÍ ---
        # Se especifica el formato de fecha para asegurar la correcta interpretación.
        df_base[col_fecha_ppal] = pd.to_datetime(df_base[col_fecha_ppal], format='%d/%m/%Y', errors='coerce')
    if "Fecha de Invite" in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base["Fecha de Invite"]):
        df_base["Fecha de Invite"] = pd.to_datetime(df_base["Fecha de Invite"], errors='coerce')
    if "Avatar" in df_base.columns: df_base["Avatar"] = df_base["Avatar"].apply(estandarizar_avatar)
    return df_base

df = get_base_data()

if df is None or df.empty:
    st.warning("No se pudieron cargar datos o el DataFrame base está vacío.")
    st.stop()

if 'mensaje_filtros' not in st.session_state: reset_mensaje_filtros_state()
if 'mostrar_tabla_mensajes' not in st.session_state: st.session_state.mostrar_tabla_mensajes = False

st.subheader("⚙️ Configura los Filtros para tus Mensajes")
st.write("**1. Invite Aceptada:** (Filtro obligatorio: 'Si')")
st.session_state.mensaje_filtros["invite_aceptada"] = "si"

st.write("**2. Filtros Adicionales (Opcional):**")
with st.expander("Ver/Ocultar Filtros Adicionales"):
    col1_filtros, col2_filtros = st.columns(2)
    with col1_filtros:
        opciones_fuente = ["– Todos –"] + (sorted(df["Fuente de la Lista"].dropna().astype(str).unique().tolist()) if "Fuente de la Lista" in df.columns and not df["Fuente de la Lista"].empty else [])
        st.session_state.mensaje_filtros["fuente_lista"] = st.multiselect("Fuente de la Lista", opciones_fuente, default=st.session_state.mensaje_filtros.get("fuente_lista", ["– Todos –"]), key="ms_fuente_lista_msg_page_v3")
        
        # Filtro para la columna "Proceso" original del DataFrame
        opciones_proceso_col_original = df["Proceso"].dropna().astype(str).unique().tolist() if "Proceso" in df.columns and not df["Proceso"].empty else []
        opciones_proceso_ui_original = ["– Todos –"] + sorted(opciones_proceso_col_original)
        st.session_state.mensaje_filtros["proceso"] = st.multiselect("Proceso (Filtro de Datos)", opciones_proceso_ui_original, default=st.session_state.mensaje_filtros.get("proceso", ["– Todos –"]), key="ms_proceso_col_original_msg_page_v3")
        
        avatares_unicos_filt = ["– Todos –"]
        if "Avatar" in df.columns and not df["Avatar"].empty: avatares_unicos_filt.extend(sorted(df["Avatar"].dropna().astype(str).unique().tolist()))
        st.session_state.mensaje_filtros["avatar"] = st.multiselect("Avatar", avatares_unicos_filt, default=st.session_state.mensaje_filtros.get("avatar", ["– Todos –"]), key="ms_avatar_msg_page_v3")
    with col2_filtros:
        opciones_pais = ["– Todos –"] + (sorted(df["Pais"].dropna().astype(str).unique().tolist()) if "Pais" in df.columns and not df["Pais"].empty else [])
        st.session_state.mensaje_filtros["pais"] = st.multiselect("País", opciones_pais, default=st.session_state.mensaje_filtros.get("pais", ["– Todos –"]), key="ms_pais_msg_page_v3")
        opciones_industria = ["– Todos –"] + (sorted(df["Industria"].dropna().astype(str).unique().tolist()) if "Industria" in df.columns and not df["Industria"].empty else [])
        st.session_state.mensaje_filtros["industria"] = st.multiselect("Industria", opciones_industria, default=st.session_state.mensaje_filtros.get("industria", ["– Todos –"]), key="ms_industria_msg_page_v3")
        opciones_prospectador = ["– Todos –"] + (sorted(df["¿Quién Prospecto?"].dropna().astype(str).unique().tolist()) if "¿Quién Prospecto?" in df.columns and not df["¿Quién Prospecto?"].empty else [])
        st.session_state.mensaje_filtros["prospectador"] = st.multiselect("¿Quién Prospectó?", opciones_prospectador, default=st.session_state.mensaje_filtros.get("prospectador", ["– Todos –"]), key="ms_prospectador_msg_page_v3")

    with st.container():
        st.markdown("---")
        fecha_min_data_val, fecha_max_data_val = None, None
        columna_fecha_para_ui = "Fecha Primer Mensaje"
        if columna_fecha_para_ui in df.columns and pd.api.types.is_datetime64_any_dtype(df[columna_fecha_para_ui]):
            valid_dates_filt = df[columna_fecha_para_ui].dropna()
            if not valid_dates_filt.empty:
                fecha_min_data_val = valid_dates_filt.min().date()
                fecha_max_data_val = valid_dates_filt.max().date()
        col_sesion_filt, col_f1_filt, col_f2_filt = st.columns(3)
        with col_sesion_filt:
            opciones_sesion_filt = ["– Todos –", "Si", "No"]
            current_sesion_val_filt = st.session_state.mensaje_filtros.get("sesion_agendada", "– Todos –")
            if isinstance(current_sesion_val_filt, str):
                if current_sesion_val_filt.strip().lower() == "si": current_sesion_val_filt = "Si"
                elif current_sesion_val_filt.strip().lower() == "no": current_sesion_val_filt = "No"
            if current_sesion_val_filt not in opciones_sesion_filt: current_sesion_val_filt = "– Todos –"
            st.session_state.mensaje_filtros["sesion_agendada"] = st.selectbox("¿Sesión Agendada?", opciones_sesion_filt, index=opciones_sesion_filt.index(current_sesion_val_filt), key="sb_sesion_agendada_msg_page_v3")
        with col_f1_filt:
            st.session_state.mensaje_filtros["fecha_ini"] = st.date_input("Desde (Fecha Primer Mensaje)", value=st.session_state.mensaje_filtros.get("fecha_ini", None), format='DD/MM/YYYY', key="di_fecha_ini_msg_page_v3", min_value=fecha_min_data_val, max_value=fecha_max_data_val)
        with col_f2_filt:
            st.session_state.mensaje_filtros["fecha_fin"] = st.date_input("Hasta (Fecha Primer Mensaje)", value=st.session_state.mensaje_filtros.get("fecha_fin", None), format='DD/MM/YYYY', key="di_fecha_fin_msg_page_v3", min_value=fecha_min_data_val, max_value=fecha_max_data_val)

st.session_state.mensaje_filtros["busqueda"] = st.text_input("🔎 Buscar en Nombre, Apellido, Empresa, Puesto", value=st.session_state.mensaje_filtros.get("busqueda", ""), placeholder="Ingrese término y presione Enter", key="ti_busqueda_msg_page_v3")
col_btn1, col_btn2 = st.columns(2)
with col_btn1:
    if st.button("📬 Cargar y Filtrar Prospectos para Mensaje", key="btn_cargar_filtrar_msg_page_v3"):
        st.session_state.mostrar_tabla_mensajes = True
with col_btn2:
    st.button("🧹 Limpiar Filtros de Mensajes", on_click=reset_mensaje_filtros_state, key="btn_limpiar_filtros_msg_page_v3")

if st.session_state.mostrar_tabla_mensajes:
    st.markdown("---")
    df_mensajes_filtrado_temp = df.copy()
    if "¿Invite Aceptada?" in df_mensajes_filtrado_temp.columns:
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[df_mensajes_filtrado_temp["¿Invite Aceptada?"].apply(limpiar_valor_kpi).astype(str).str.lower() == str(st.session_state.mensaje_filtros["invite_aceptada"]).lower()]
    else:
        st.warning("Columna '¿Invite Aceptada?' no encontrada.")
        df_mensajes_filtrado_temp = pd.DataFrame()

    if not df_mensajes_filtrado_temp.empty:
        filtro_sesion_para_aplicar = st.session_state.mensaje_filtros.get("sesion_agendada", "– Todos –"); isinstance(filtro_sesion_para_aplicar, str)
        if isinstance(filtro_sesion_para_aplicar, str):
            if filtro_sesion_para_aplicar.strip().lower() == "si": filtro_sesion_para_aplicar = "Si"
            elif filtro_sesion_para_aplicar.strip().lower() == "no": filtro_sesion_para_aplicar = "No"
            if filtro_sesion_para_aplicar not in ["Si", "No", "– Todos –"]: filtro_sesion_para_aplicar = "– Todos –"
        
        # Se usa st.session_state.mensaje_filtros.get("proceso") que es el filtro de la columna "Proceso" original
        df_mensajes_filtrado_temp = aplicar_filtros_mensajes(
            df_mensajes_filtrado_temp, 
            st.session_state.mensaje_filtros.get("fuente_lista", ["– Todos –"]), 
            st.session_state.mensaje_filtros.get("proceso", ["– Todos –"]), # Este es el filtro de la columna "Proceso"
            st.session_state.mensaje_filtros.get("pais", ["– Todos –"]), 
            st.session_state.mensaje_filtros.get("industria", ["– Todos –"]), 
            st.session_state.mensaje_filtros.get("avatar", ["– Todos –"]), 
            st.session_state.mensaje_filtros.get("prospectador", ["– Todos –"]), 
            filtro_sesion_para_aplicar, 
            st.session_state.mensaje_filtros.get("fecha_ini", None), 
            st.session_state.mensaje_filtros.get("fecha_fin", None), 
            "Fecha Primer Mensaje"
        )
        busqueda_term_final = st.session_state.mensaje_filtros.get("busqueda", "").lower().strip()
        if busqueda_term_final and not df_mensajes_filtrado_temp.empty:
            mask_busqueda = pd.Series([False] * len(df_mensajes_filtrado_temp), index=df_mensajes_filtrado_temp.index)
            columnas_para_busqueda_texto = ["Empresa", "Puesto"]
            for col_busc in columnas_para_busqueda_texto:
                if col_busc in df_mensajes_filtrado_temp.columns: mask_busqueda |= df_mensajes_filtrado_temp[col_busc].astype(str).str.lower().str.contains(busqueda_term_final, na=False)
            nombre_col_df, apellido_col_df = "Nombre", "Apellido"
            if nombre_col_df in df_mensajes_filtrado_temp.columns and apellido_col_df in df_mensajes_filtrado_temp.columns:
                nombre_completo_busq = (df_mensajes_filtrado_temp[nombre_col_df].fillna('') + ' ' + df_mensajes_filtrado_temp[apellido_col_df].fillna('')).str.lower()
                mask_busqueda |= nombre_completo_busq.str.contains(busqueda_term_final, na=False)
            elif nombre_col_df in df_mensajes_filtrado_temp.columns: mask_busqueda |= df_mensajes_filtrado_temp[nombre_col_df].astype(str).str.lower().str.contains(busqueda_term_final, na=False)
            elif apellido_col_df in df_mensajes_filtrado_temp.columns: mask_busqueda |= df_mensajes_filtrado_temp[apellido_col_df].astype(str).str.lower().str.contains(busqueda_term_final, na=False)
            df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[mask_busqueda]

    df_mensajes_final_display = df_mensajes_filtrado_temp.copy()

    if df_mensajes_final_display.empty:
        st.warning("No se encontraron prospectos que cumplan todos los criterios.")
    else:
        linkedin_col_nombre = "LinkedIn"
        columna_fecha_a_mostrar = "Fecha Primer Mensaje"
        columnas_necesarias_para_display = ["Nombre", "Apellido", "Empresa", "Puesto", "Proceso", "Avatar", columna_fecha_a_mostrar, "¿Quién Prospecto?", linkedin_col_nombre, "Sesion Agendada?"]
        for col_exist in columnas_necesarias_para_display:
            if col_exist not in df_mensajes_final_display.columns: df_mensajes_final_display[col_exist] = pd.NA
        
        if "Proceso" not in df_mensajes_final_display.columns:
            df_mensajes_final_display["Proceso"] = "Desconocido" 
            st.warning("La columna 'Proceso' no se encontró. Se usará 'Desconocido' para derivar 'Categoría'.")
        df_mensajes_final_display["Categoría"] = df_mensajes_final_display["Proceso"].apply(clasificar_por_proceso)
        df_mensajes_final_display["Nombre_Completo_Display"] = df_mensajes_final_display.apply(lambda row: limpiar_nombre_completo(row.get("Nombre"), row.get("Apellido")), axis=1)

        st.markdown("### 📋 Prospectos Encontrados para Mensajes")

         # CONTEO:
        num_prospectos_filtrados = len(df_mensajes_final_display)
        if num_prospectos_filtrados == 1:
            st.info(f"ℹ️ Se encontró **{num_prospectos_filtrados} prospecto** que cumple con los filtros aplicados.")
        else:
            st.info(f"ℹ️ Se encontraron **{num_prospectos_filtrados} prospectos** que cumplen con los filtros aplicados.")
            
        columnas_para_tabla_display = ["Nombre_Completo_Display", "Empresa", "Puesto", "Categoría", "Avatar", columna_fecha_a_mostrar, "¿Quién Prospecto?", "Sesion Agendada?", linkedin_col_nombre]
        cols_realmente_en_df_para_tabla = [col for col in columnas_para_tabla_display if col in df_mensajes_final_display.columns]
        df_tabla_a_mostrar = df_mensajes_final_display[cols_realmente_en_df_para_tabla].copy()
        if columna_fecha_a_mostrar in df_tabla_a_mostrar.columns:
            if not pd.api.types.is_datetime64_any_dtype(df_tabla_a_mostrar[columna_fecha_a_mostrar]): df_tabla_a_mostrar[columna_fecha_a_mostrar] = pd.to_datetime(df_tabla_a_mostrar[columna_fecha_a_mostrar], errors='coerce')
            if pd.api.types.is_datetime64_any_dtype(df_tabla_a_mostrar[columna_fecha_a_mostrar]): df_tabla_a_mostrar[columna_fecha_a_mostrar] = df_tabla_a_mostrar[columna_fecha_a_mostrar].dt.strftime('%d/%m/%Y')
            else: df_tabla_a_mostrar[columna_fecha_a_mostrar] = "Fecha Inválida"
        
        st.markdown("---")
        st.markdown("### 📬️ Generador de Mensajes")

        # --- NUEVA SECCIÓN PARA SELECCIONAR EL SET DE PLANTILLAS ---
        st.markdown("#### **Paso 1: Elige el Set de Plantillas**")
        set_plantillas_seleccionado = st.radio(
            "Selecciona el estilo del mensaje:",
            ("Mensajes John", "Mensajes Karen CH"),
            key="set_plantillas_selector",
            horizontal=True
        )

        opciones_mensajes_base = {}
        if set_plantillas_seleccionado == "Mensajes John":
            opciones_mensajes_base = plantillas_john
        else: # "Mensajes Karen CH"
            opciones_mensajes_base = plantillas_karen
        
        # --- Lógica de selección de categoría y plantilla (adaptada) ---
        st.markdown("#### **Paso 2: Configura la Plantilla Específica**")
        
        categorias_disponibles = ["H2R", "P2P", "O2C", "General"]
        categorias_seleccionables_para_widget_ui = ["– Todas las Categorías –"] + sorted(categorias_disponibles)
        
        col_sel_cat, col_sel_plantilla = st.columns(2)
        with col_sel_cat:
            categoria_sel_widget = st.selectbox(
                "1. Selecciona Categoría de Plantilla:",
                categorias_seleccionables_para_widget_ui,
                key="mensaje_categoria_sel_v3"
            )

        plantillas_para_categoria_sel_ui = {}
        
        # Lógica para determinar qué plantillas mostrar en el segundo selectbox
        if categoria_sel_widget != "– Todas las Categorías –":
            # Cargar plantillas de la categoría específica
            plantillas_para_categoria_sel_ui = opciones_mensajes_base.get(categoria_sel_widget, {}).copy()
            
            # Añadir plantillas alternativas
            if categoria_sel_widget == "General":
                plantillas_para_categoria_sel_ui.update(opciones_mensajes_base.get("TI", {}))
            elif categoria_sel_widget == "P2P":
                plantillas_para_categoria_sel_ui.update(opciones_mensajes_base.get("Aduanas", {}))
        else:
            # Si se eligen "Todas", mostrar las de "General" y "TI" por defecto
            plantillas_para_categoria_sel_ui = opciones_mensajes_base.get("General", {}).copy()
            plantillas_para_categoria_sel_ui.update(opciones_mensajes_base.get("TI", {}))

        nombres_plantillas_para_categoria_sel_ui = list(plantillas_para_categoria_sel_ui.keys())
        
        nombre_plantilla_sel, plantilla_str_seleccionada_directa_ui = None, None
        with col_sel_plantilla:
            if nombres_plantillas_para_categoria_sel_ui:
                nombre_plantilla_sel = st.selectbox(
                    "2. Escoge una Plantilla de Mensaje:", 
                    nombres_plantillas_para_categoria_sel_ui, 
                    key="mensaje_plantilla_sel_v3"
                )
                plantilla_str_seleccionada_directa_ui = plantillas_para_categoria_sel_ui.get(nombre_plantilla_sel, "")
            else:
                st.warning(f"No hay plantillas definidas para la categoría '{categoria_sel_widget}'.")

        # --- Lógica de generación de mensajes (con la adaptación para #Lead y #Empresa) ---
        if plantilla_str_seleccionada_directa_ui:
            # ... (el resto de la lógica para filtrar el df_vista_previa_msg) ...
            
            # --- Dentro de la función generar_mensaje_para_fila ---
            def generar_mensaje_para_fila(row, plantilla_str):
                nombre_prospecto = str(row.get("Nombre", "")).split()[0] if pd.notna(row.get("Nombre")) and str(row.get("Nombre")).strip() else "[Nombre]"
                avatar_prospectador = str(row.get("Avatar", "Tu Nombre"))
                empresa_prospecto = str(row.get("Empresa", "[Empresa]"))
                
                mensaje = plantilla_str
                
                # Reemplazos para plantillas "John"
                mensaje = mensaje.replace("{nombre}", nombre_prospecto)
                mensaje = mensaje.replace("{empresa}", empresa_prospecto)
                mensaje = mensaje.replace("{avatar}", avatar_prospectador)
                
                # Reemplazos para plantillas "Karen"
                mensaje = mensaje.replace("#Lead", nombre_prospecto)
                mensaje = mensaje.replace("#Empresa", empresa_prospecto)
                
                return mensaje

            df_vista_previa_msg["Mensaje_Personalizado"] = df_vista_previa_msg.apply(
                lambda row: generar_mensaje_para_fila(row, plantilla_str_seleccionada_directa_ui),
                axis=1
            )

                st.markdown("### 📟 Vista Previa y Descarga de Mensajes")
                cols_generador_display = ["Nombre_Completo_Display", "Empresa", "Puesto", "Categoría", "Avatar", "Sesion Agendada?", linkedin_col_nombre, "Mensaje_Personalizado"]
                cols_reales_generador = [col for col in cols_generador_display if col in df_vista_previa_msg.columns]
                if "Categoría" not in df_vista_previa_msg.columns and "Proceso" in df_vista_previa_msg.columns: # Doble check
                     df_vista_previa_msg["Categoría"] = df_vista_previa_msg["Proceso"].apply(clasificar_por_proceso)
                st.dataframe(df_vista_previa_msg[cols_reales_generador], use_container_width=True, height=300)

                @st.cache_data
                def convert_df_to_csv_final(df_conv):
                    cols_desc = ["Nombre_Completo_Display", "Empresa", "Puesto", "Categoría", "Sesion Agendada?", linkedin_col_nombre, "Mensaje_Personalizado"]
                    cols_ex_desc = [col for col in cols_desc if col in df_conv.columns]
                    if not cols_ex_desc: return None
                    return df_conv[cols_ex_desc].fillna('').to_csv(index=False).encode('utf-8')

                csv_data = convert_df_to_csv_final(df_vista_previa_msg)
                nombre_archivo_cat = categoria_usada_para_plantillas_ui if categoria_sel_widget == opcion_todas_las_categorias and categoria_usada_para_plantillas_ui else categoria_sel_widget
                if nombre_archivo_cat == opcion_todas_las_categorias: nombre_archivo_cat = "todas_categorias" # Fallback
                if csv_data is not None and nombre_plantilla_sel is not None:
                    st.download_button("⬇️ Descargar Mensajes (CSV)", csv_data, file_name=f'mensajes_{nombre_archivo_cat.replace(" ", "_").lower()}_{nombre_plantilla_sel.replace(" ", "_").lower()}.csv', mime='text/csv', key="btn_dl_csv_msg_v3")
        elif nombres_plantillas_para_categoria_sel_ui: # Si hay nombres de plantillas pero ninguna cadena de plantilla (improbable)
            st.info("Selecciona una plantilla para generar la vista previa.")


# ... (linkedin_col_nombre debe estar definido antes de este bloque, usualmente al inicio de la sección "else" del if df_mensajes_final_display.empty)
# Asumimos que linkedin_col_nombre = "LinkedIn"

if 'df_vista_previa_msg' in locals() and not df_vista_previa_msg.empty and 'Mensaje_Personalizado' in df_vista_previa_msg.columns:
    st.markdown("---")
    st.markdown("### ✨ Vista Profesional de los Mensajes Personalizados") # Cambié "Vista de los..." por "Vista Profesional de los..." para consistencia
    for i, row in df_vista_previa_msg.iterrows():
        nombre_display = str(row.get("Nombre_Completo_Display", "[Nombre]")).title()
        empresa_display = row.get("Empresa", "")
        puesto_display = row.get("Puesto", "")
        categoria_row_display = row.get("Categoría", "N/A")
        linkedin_url_display = row.get(linkedin_col_nombre, "") # Asegúrate que linkedin_col_nombre esté definido
        mensaje_display_original = row.get("Mensaje_Personalizado", "")

        # --- AJUSTE PARA EL SALTO DE LÍNEA ANTES DE LA LISTA ---
        mensaje_display_ajustado = mensaje_display_original
        
        # Patrones comunes que preceden a tus listas. Ajusta estos si es necesario.
        # Buscamos "palabra_clave_seguida_de_dos_puntos_y_un_salto_de_linea_y_luego_un_guion"
        # y lo reemplazamos por "palabra_clave_seguida_de_dos_puntos_y_DOS_saltos_de_linea_y_luego_un_guion"
        patrones_a_buscar = [
            "por ejemplo:\n-", 
            "en:\n-"
            # Puedes añadir más patrones si tienes otras introducciones a listas
        ]
        
        for patron in patrones_a_buscar:
            if patron in mensaje_display_ajustado:
                # Reemplazar el \n simple por \n\n en el patrón encontrado
                # El patrón es "texto:\n-", queremos "texto:\n\n-"
                # Entonces, reemplazamos ":\n-" por ":\n\n-"
                parte_a_reemplazar = patron.replace("\n-", "", 1) # Queda "por ejemplo:" o "en:"
                mensaje_display_ajustado = mensaje_display_ajustado.replace(
                    parte_a_reemplazar + "\n-", 
                    parte_a_reemplazar + "\n\n-", 
                    1 # Solo la primera ocurrencia, asumiendo una lista principal
                )
                break # Salir del bucle una vez que se hace un ajuste

        # --- FIN DEL AJUSTE ---

        linkedin_html_str = ""
        if linkedin_url_display and isinstance(linkedin_url_display, str) and linkedin_url_display.strip():
            if linkedin_url_display.startswith("http://") or linkedin_url_display.startswith("https://"):
                link_text_display = "Abrir Perfil"
                try:
                    path_parts_display = [part for part in linkedin_url_display.split('/') if part]
                    if path_parts_display: link_text_display = path_parts_display[-1]
                except: pass
                linkedin_html_str = f"🔗 *LinkedIn:* <a href='{linkedin_url_display}' target='_blank'>{link_text_display}</a>"
            else:
                linkedin_html_str = f"🔗 *LinkedIn:* {linkedin_url_display} (No es una URL válida)"
        
        info_header = f"""
**{nombre_display}{f" - {empresa_display}" if empresa_display else ""}**<br>
🧑‍💼 *Puesto:* {puesto_display if puesto_display else "No especificado"}<br>
🗂️ *Categoría:* {categoria_row_display if categoria_row_display else "No especificada"}
"""
        if linkedin_html_str: # Solo añadir la línea de LinkedIn si hay algo que mostrar
            info_header += f"<br>{linkedin_html_str}"

        st.markdown("---")
        st.markdown(info_header, unsafe_allow_html=True)
        st.markdown("📩 *Mensaje:*")
        st.code(mensaje_display_ajustado, language=None) # Usar la versión ajustada del mensaje

st.markdown("---")
st.info("Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊")
