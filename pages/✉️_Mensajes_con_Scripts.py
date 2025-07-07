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
# --- Se importan los DOS sets de plantillas ---
from mensajes.mensajes import plantillas_john, plantillas_karen
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
    st.toast("Filtros de mensajes reiniciados ✅")

st.title("💌 Generador de Mensajes Personalizados")
st.markdown("Filtra prospectos que aceptaron tu invitación y genera mensajes personalizados.")

@st.cache_data
def get_base_data():
    df_base = cargar_y_limpiar_datos()
    col_fecha_ppal = "Fecha Primer Mensaje"
    if col_fecha_ppal in df_base.columns and not pd.api.types.is_datetime64_any_dtype(df_base[col_fecha_ppal]):
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
    if st.button("📬 Generar Vista de Mensajes", key="btn_cargar_filtrar_msg_page_v3"):
        st.session_state.mostrar_tabla_mensajes = True
with col_btn2:
    st.button("🧹 Limpiar Filtros", on_click=reset_mensaje_filtros_state, key="btn_limpiar_filtros_msg_page_v3")

if st.session_state.mostrar_tabla_mensajes:
    st.markdown("---")
    df_mensajes_filtrado_temp = df.copy()
    if "¿Invite Aceptada?" in df_mensajes_filtrado_temp.columns:
        df_mensajes_filtrado_temp = df_mensajes_filtrado_temp[df_mensajes_filtrado_temp["¿Invite Aceptada?"].apply(limpiar_valor_kpi).astype(str).str.lower() == str(st.session_state.mensaje_filtros["invite_aceptada"]).lower()]
    else:
        st.warning("Columna '¿Invite Aceptada?' no encontrada.")
        df_mensajes_filtrado_temp = pd.DataFrame()

    if not df_mensajes_filtrado_temp.empty:
        filtro_sesion_para_aplicar = st.session_state.mensaje_filtros.get("sesion_agendada", "– Todos –")
        if isinstance(filtro_sesion_para_aplicar, str):
            if filtro_sesion_para_aplicar.strip().lower() == "si": filtro_sesion_para_aplicar = "Si"
            elif filtro_sesion_para_aplicar.strip().lower() == "no": filtro_sesion_para_aplicar = "No"
            if filtro_sesion_para_aplicar not in ["Si", "No", "– Todos –"]: filtro_sesion_para_aplicar = "– Todos –"
        
        df_mensajes_filtrado_temp = aplicar_filtros_mensajes(
            df_mensajes_filtrado_temp, 
            st.session_state.mensaje_filtros.get("fuente_lista", ["– Todos –"]), 
            st.session_state.mensaje_filtros.get("proceso", ["– Todos –"]),
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
        st.warning("No se encontraron prospectos que cumplan todos los criterios de búsqueda y filtros.")
    else:
        linkedin_col_nombre = "LinkedIn"
        
        if "Proceso" not in df_mensajes_final_display.columns:
            df_mensajes_final_display["Proceso"] = "Desconocido"
        df_mensajes_final_display["Categoría"] = df_mensajes_final_display["Proceso"].apply(clasificar_por_proceso)
        
        st.markdown("### 📬️ Vista de Mensajes Automáticos")
        st.markdown("#### **Elige el Estilo del Mensaje**")
        set_plantillas_seleccionado = st.radio(
            "Selecciona el estilo:",
            ("Mensajes John", "Mensajes Karen CH"),
            key="set_plantillas_selector",
            horizontal=True
        )
        
        opciones_mensajes_base = {}
        nombre_set = ""
        if set_plantillas_seleccionado == "Mensajes John":
            opciones_mensajes_base = plantillas_john
            nombre_set = "John"
        else:
            opciones_mensajes_base = plantillas_karen
            nombre_set = "Karen"

        num_prospectos = len(df_mensajes_final_display)
        st.info(f"Se encontraron **{num_prospectos}** prospectos. A continuación se muestran los mensajes generados para cada uno.")
        
        def generar_mensaje_para_fila(row, plantilla_str):
            nombre_prospecto = str(row.get("Nombre", "")).split()[0] if pd.notna(row.get("Nombre")) and str(row.get("Nombre")).strip() else "[Nombre]"
            avatar_prospectador = str(row.get("Avatar", "Tu Nombre"))
            empresa_prospecto = str(row.get("Empresa", "[Empresa]"))
            
            mensaje = plantilla_str
            mensaje = mensaje.replace("{nombre}", nombre_prospecto).replace("#Lead", nombre_prospecto)
            mensaje = mensaje.replace("{empresa}", empresa_prospecto).replace("#Empresa", empresa_prospecto)
            mensaje = mensaje.replace("{avatar}", avatar_prospectador)
            
            return mensaje

        # En el archivo: pages/✉️_Mensajes_con_Scripts.py ...

for index, row in df_mensajes_final_display.iterrows():
    st.markdown("---")
    
    categoria_prospecto = row["Categoría"]
    nombre_completo = limpiar_nombre_completo(row.get("Nombre"), row.get("Apellido")).title()
    puesto = row.get("Puesto", "N/A")
    empresa = row.get("Empresa", "N/A")
    
    info_col, link_col = st.columns([4, 1])
    with info_col:
        st.markdown(f"**{nombre_completo}** | {puesto} en **{empresa}** | `Categoría: {categoria_prospecto}`")

    if linkedin_col_nombre in row and pd.notna(row[linkedin_col_nombre]) and str(row[linkedin_col_nombre]).startswith("http"):
         with link_col:
            # --- CORRECCIÓN APLICADA AQUÍ ---
            # Usamos el 'index' del DataFrame, que es un identificador único y estable para la fila.
            unique_key = f"link_{index}"
            st.link_button("🔗 Perfil LinkedIn", row[linkedin_col_nombre], key=unique_key)


            # ---- Lógica para Mensaje Principal ----
            key_plantilla_principal = f"Plantilla {nombre_set} {categoria_prospecto}"
            plantilla_principal_str = opciones_mensajes_base.get(key_plantilla_principal)
            
            if plantilla_principal_str:
                mensaje_principal = generar_mensaje_para_fila(row, plantilla_principal_str)
                st.markdown("**Mensaje Principal Sugerido:**")
                st.code(mensaje_principal, language=None)
            else:
                st.warning(f"No se encontró una plantilla principal para la categoría '{categoria_prospecto}' en el set de '{nombre_set}'.")

            # ---- Lógica para Mensaje Alternativo ---
            key_plantilla_alternativa = None
            nombre_alternativa = ""
            if categoria_prospecto == "General":
                key_plantilla_alternativa = f"Plantilla {nombre_set} TI (Alternativa)"
                nombre_alternativa = "TI"
            elif categoria_prospecto == "P2P":
                key_plantilla_alternativa = f"Plantilla {nombre_set} Aduanas (Alternativa)"
                nombre_alternativa = "Aduanas"
            
            if key_plantilla_alternativa:
                plantilla_alternativa_str = opciones_mensajes_base.get(key_plantilla_alternativa)
                if plantilla_alternativa_str:
                    mensaje_alternativo = generar_mensaje_para_fila(row, plantilla_alternativa_str)
                    expander_title = f"Ver Mensaje Alternativo para '{nombre_alternativa}'"
                    with st.expander(expander_title):
                        st.code(mensaje_alternativo, language=None)

st.markdown("---")
st.info("Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊")
