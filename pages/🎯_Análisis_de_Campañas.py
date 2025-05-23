# pages/🎯_Análisis_de_Campañas.py

import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io

# Asegúrate de que la ruta al proyecto raíz sea correcta para importar módulos
# Si este archivo está en /pages, y datos y utils están al mismo nivel que /pages
# o en un nivel superior accesible, los imports deberían funcionar.
# Si `datos` y `utils` están dentro de la carpeta principal del proyecto,
# y `pages` también, esta configuración de path es común.
import sys
import os

# Añadir la raíz del proyecto al path si es necesario (ajusta según tu estructura)
# Esto es más relevante si ejecutas el script directamente, Streamlit maneja los paths para páginas.
# project_root_campanas = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
# if project_root_campanas not in sys.path:
#     sys.path.insert(0, project_root_campanas)

from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar # estandarizar_avatar por si lo necesitas para el filtro de Avatar

# --- Configuración de la Página ---
st.set_page_config(layout="wide", page_title="Análisis de Campañas")
st.title("🎯 Análisis de Rendimiento de Campañas")
st.markdown("Selecciona una o varias campañas y aplica filtros para analizar su rendimiento detallado.")

# --- Funciones de Ayuda Específicas para esta Página ---

@st.cache_data
def obtener_datos_base_campanas():
    """
    Carga los datos completos y los filtra para obtener solo aquellos con información de campaña.
    """
    df_completo = cargar_y_limpiar_datos()
    if df_completo is None or df_completo.empty:
        return pd.DataFrame()

    if 'Campaña' not in df_completo.columns:
        st.error("La columna 'Campaña' no se encontró en los datos. Por favor, verifica la hoja de Google Sheets.")
        return pd.DataFrame()

    df_base_campanas = df_completo[df_completo['Campaña'].notna() & (df_completo['Campaña'] != '')].copy()

    # Asegurar que las columnas de fecha necesarias están en formato datetime
    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"]
    for col in date_cols_to_check:
        if col in df_base_campanas.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas[col]):
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
    if "Avatar" in df_base_campanas.columns: # Estandarizar avatar por si se usa en filtros
        df_base_campanas["Avatar"] = df_base_campanas["Avatar"].apply(estandarizar_avatar)

    return df_base_campanas

def inicializar_estado_filtros_campana():
    """Inicializa o resetea el estado de los filtros para la página de campañas."""
    default_filters = {
        "campana_seleccion_principal": [],
        "campana_filtro_prospectador": "– Todos –",
        "campana_filtro_pais": ["– Todos –"],
        "campana_filtro_fecha_ini": None,
        "campana_filtro_fecha_fin": None,
        # Añade aquí más claves para otros filtros (Industria, Avatar, etc.)
    }
    for key, value in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = value

def resetear_filtros_campana_callback():
    """Callback para el botón de resetear filtros."""
    # Reinicializa solo las claves de esta página
    keys_to_reset = [k for k in st.session_state.keys() if k.startswith("campana_filtro_") or k == "campana_seleccion_principal"]
    for key in keys_to_reset:
        if key == "campana_seleccion_principal":
            st.session_state[key] = [] # O el valor por defecto que definas para el multiselect de campañas
        elif key == "campana_filtro_prospectador":
            st.session_state[key] = "– Todos –"
        elif key == "campana_filtro_pais":
            st.session_state[key] = ["– Todos –"]
        elif key in ["campana_filtro_fecha_ini", "campana_filtro_fecha_fin"]:
            st.session_state[key] = None
        # Añade lógica de reseteo para otros filtros
    st.toast("Filtros de campaña reiniciados.", icon="🧹")


def calcular_kpis_df_campana(df_filtrado_campana):
    """Calcula los KPIs principales a partir de un DataFrame de campaña filtrado."""
    if df_filtrado_campana.empty:
        return {
            "total_prospectos": 0, "invites_aceptadas": 0,
            "primeros_mensajes_enviados": 0, "respuestas_primer_mensaje": 0,
            "sesiones_agendadas": 0, "tasa_aceptacion": 0,
            "tasa_respuesta_vs_aceptadas": 0, "tasa_sesion_vs_respuesta": 0,
            "tasa_sesion_global": 0
        }

    total_prospectos = len(df_filtrado_campana)
    invites_aceptadas = 0
    if "¿Invite Aceptada?" in df_filtrado_campana.columns:
        invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana["¿Invite Aceptada?"])

    primeros_mensajes_enviados = 0
    if "Fecha Primer Mensaje" in df_filtrado_campana.columns:
        primeros_mensajes_enviados = sum(
            pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
            for x in df_filtrado_campana["Fecha Primer Mensaje"]
        )

    respuestas_primer_mensaje = 0
    if "Respuesta Primer Mensaje" in df_filtrado_campana.columns:
        respuestas_primer_mensaje = sum(
            limpiar_valor_kpi(x) not in ["no", "", "nan"]
            for x in df_filtrado_campana["Respuesta Primer Mensaje"]
        )

    sesiones_agendadas = 0
    if "Sesion Agendada?" in df_filtrado_campana.columns:
        sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana["Sesion Agendada?"])

    # Tasas
    tasa_aceptacion = (invites_aceptadas / total_prospectos * 100) if total_prospectos > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0
    tasa_sesion_vs_respuesta = (sesiones_agendadas / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global = (sesiones_agendadas / total_prospectos * 100) if total_prospectos > 0 else 0

    return {
        "total_prospectos": total_prospectos,
        "invites_aceptadas": invites_aceptadas,
        "primeros_mensajes_enviados": primeros_mensajes_enviados,
        "respuestas_primer_mensaje": respuestas_primer_mensaje,
        "sesiones_agendadas": sesiones_agendadas,
        "tasa_aceptacion": tasa_aceptacion,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta": tasa_sesion_vs_respuesta,
        "tasa_sesion_global": tasa_sesion_global,
    }

def mostrar_embudo_para_campana(kpis_campana, titulo_embudo="Embudo de Conversión de Campaña"):
    """Muestra el embudo de conversión para los KPIs de una campaña."""
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

    # Calcular porcentajes vs etapa ANTERIOR
    porcentajes_vs_anterior = [100.0]
    for i in range(1, len(df_embudo)):
        if df_embudo['Cantidad'][i-1] > 0:
            porcentaje = (df_embudo['Cantidad'][i] / df_embudo['Cantidad'][i-1] * 100)
        else:
            porcentaje = 0.0
        porcentajes_vs_anterior.append(porcentaje)
    df_embudo['% vs Anterior'] = porcentajes_vs_anterior
    df_embudo['Texto'] = df_embudo.apply(lambda row: f"{row['Cantidad']:,} ({row['% vs Anterior']:.1f}%)", axis=1)


    fig_embudo = px.funnel(
        df_embudo,
        y='Etapa',
        x='Cantidad',
        title=titulo_embudo,
        text='Texto',
        category_orders={"Etapa": etapas_embudo}
    )
    fig_embudo.update_traces(textposition='inside', textinfo='text') # Muestra el texto personalizado
    st.plotly_chart(fig_embudo, use_container_width=True)
    st.caption(f"Embudo basado en {kpis_campana['total_prospectos']:,} prospectos iniciales para la selección actual.")

# --- Carga de Datos Base para la Página de Campañas ---
df_base_campanas_global = obtener_datos_base_campanas()
inicializar_estado_filtros_campana() # Asegura que las claves de sesión existen

if df_base_campanas_global.empty:
    # El mensaje de error ya se muestra en obtener_datos_base_campanas si falta la columna
    # o si después del filtro inicial no quedan datos.
    st.stop()

# --- Sección de Selección de Campaña Principal ---
st.markdown("---")
st.subheader("1. Selección de Campaña(s)")
lista_campanas_disponibles_global = sorted(df_base_campanas_global['Campaña'].unique())

if not lista_campanas_disponibles_global:
    st.warning("No se encontraron nombres de campañas en los datos cargados.")
    st.stop()

# Usar st.session_state para el multiselect de campañas
st.session_state.campana_seleccion_principal = st.multiselect(
    "Elige la(s) campaña(s) a analizar:",
    options=lista_campanas_disponibles_global,
    default=st.session_state.campana_seleccion_principal # Mantiene la selección entre reruns
)

if not st.session_state.campana_seleccion_principal:
    st.info("Por favor, selecciona al menos una campaña para visualizar los datos.")
    st.stop()

# Filtrar el DataFrame base por las campañas seleccionadas
df_campanas_filtradas_por_seleccion = df_base_campanas_global[
    df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)
].copy()

# --- Sección de Filtros Adicionales (en el cuerpo de la página) ---
st.markdown("---")
st.subheader("2. Filtros Adicionales")

with st.expander("Aplicar filtros detallados a la(s) campaña(s) seleccionada(s)", expanded=True):
    col_f1, col_f2 = st.columns(2)

    with col_f1:
        # Filtro: ¿Quién Prospectó?
        opciones_prospectador_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["¿Quién Prospecto?"].dropna().astype(str).unique()
        )
        st.session_state.campana_filtro_prospectador = st.selectbox(
            "¿Quién Prospectó?",
            options=opciones_prospectador_camp,
            index=opciones_prospectador_camp.index(st.session_state.campana_filtro_prospectador)
                  if st.session_state.campana_filtro_prospectador in opciones_prospectador_camp else 0,
            key="sb_campana_prospectador"
        )

        # Filtro: País
        opciones_pais_camp = ["– Todos –"] + sorted(
            df_campanas_filtradas_por_seleccion["Pais"].dropna().astype(str).unique()
        )
        st.session_state.campana_filtro_pais = st.multiselect(
            "País del Prospecto",
            options=opciones_pais_camp,
            default=[p for p in st.session_state.campana_filtro_pais if p in opciones_pais_camp] # Validar default
                   or (["– Todos –"] if "– Todos –" in opciones_pais_camp else []),
            key="ms_campana_pais"
        )

    with col_f2:
        # Filtro: Rango de Fechas (basado en Fecha de Invite)
        min_fecha_invite_camp, max_fecha_invite_camp = None, None
        if "Fecha de Invite" in df_campanas_filtradas_por_seleccion.columns and \
           pd.api.types.is_datetime64_any_dtype(df_campanas_filtradas_por_seleccion["Fecha de Invite"]):
            valid_dates = df_campanas_filtradas_por_seleccion["Fecha de Invite"].dropna()
            if not valid_dates.empty:
                min_fecha_invite_camp = valid_dates.min().date()
                max_fecha_invite_camp = valid_dates.max().date()

        st.session_state.campana_filtro_fecha_ini = st.date_input(
            "Fecha de Invite Desde:",
            value=st.session_state.campana_filtro_fecha_ini,
            min_value=min_fecha_invite_camp,
            max_value=max_fecha_invite_camp,
            format="DD/MM/YYYY",
            key="di_campana_fecha_ini"
        )
        st.session_state.campana_filtro_fecha_fin = st.date_input(
            "Fecha de Invite Hasta:",
            value=st.session_state.campana_filtro_fecha_fin,
            min_value=min_fecha_invite_camp, # o st.session_state.campana_filtro_fecha_ini si se quiere dependencia
            max_value=max_fecha_invite_camp,
            format="DD/MM/YYYY",
            key="di_campana_fecha_fin"
        )
    # Botón para resetear filtros específicos de esta página
    if st.button("Limpiar Filtros de Campaña", on_click=resetear_filtros_campana_callback, key="btn_reset_campana_filtros"):
        # La lógica de reseteo está en el callback, Streamlit re-ejecutará.
        # Podrías necesitar un st.rerun() aquí si los widgets no se actualizan inmediatamente
        # después del cambio de session_state en el callback en algunos escenarios complejos,
        # pero usualmente no es necesario con on_click.
        pass


# Aplicar filtros al DataFrame de campañas seleccionadas
df_aplicar_filtros = df_campanas_filtradas_por_seleccion.copy()

# Aplicar filtro ¿Quién Prospectó?
if st.session_state.campana_filtro_prospectador != "– Todos –":
    df_aplicar_filtros = df_aplicar_filtros[
        df_aplicar_filtros["¿Quién Prospecto?"] == st.session_state.campana_filtro_prospectador
    ]

# Aplicar filtro País
if st.session_state.campana_filtro_pais and "– Todos –" not in st.session_state.campana_filtro_pais:
    df_aplicar_filtros = df_aplicar_filtros[
        df_aplicar_filtros["Pais"].isin(st.session_state.campana_filtro_pais)
    ]

# Aplicar filtro de Fecha de Invite
if st.session_state.campana_filtro_fecha_ini and st.session_state.campana_filtro_fecha_fin and \
   "Fecha de Invite" in df_aplicar_filtros.columns and \
   pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    fecha_ini_dt = datetime.datetime.combine(st.session_state.campana_filtro_fecha_ini, datetime.time.min)
    fecha_fin_dt = datetime.datetime.combine(st.session_state.campana_filtro_fecha_fin, datetime.time.max)
    df_aplicar_filtros = df_aplicar_filtros[
        (df_aplicar_filtros["Fecha de Invite"] >= fecha_ini_dt) &
        (df_aplicar_filtros["Fecha de Invite"] <= fecha_fin_dt)
    ]
elif st.session_state.campana_filtro_fecha_ini and \
     "Fecha de Invite" in df_aplicar_filtros.columns and \
     pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    fecha_ini_dt = datetime.datetime.combine(st.session_state.campana_filtro_fecha_ini, datetime.time.min)
    df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros["Fecha de Invite"] >= fecha_ini_dt]
elif st.session_state.campana_filtro_fecha_fin and \
     "Fecha de Invite" in df_aplicar_filtros.columns and \
     pd.api.types.is_datetime64_any_dtype(df_aplicar_filtros["Fecha de Invite"]):
    fecha_fin_dt = datetime.datetime.combine(st.session_state.campana_filtro_fecha_fin, datetime.time.max)
    df_aplicar_filtros = df_aplicar_filtros[df_aplicar_filtros["Fecha de Invite"] <= fecha_fin_dt]


df_final_analisis_campana = df_aplicar_filtros.copy()

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")

if df_final_analisis_campana.empty:
    st.warning("No se encontraron prospectos que cumplan con todos los criterios de filtro para la(s) campaña(s) seleccionada(s).")
else:
    # --- KPIs Principales de la Campaña ---
    st.markdown("### Indicadores Clave (KPIs)")
    kpis_calculados_campana = calcular_kpis_df_campana(df_final_analisis_campana)

    kpi_cols = st.columns(4)
    kpi_cols[0].metric("Total Prospectos", f"{kpis_calculados_campana['total_prospectos']:,}")
    kpi_cols[1].metric("Invites Aceptadas", f"{kpis_calculados_campana['invites_aceptadas']:,}",
                       f"{kpis_calculados_campana['tasa_aceptacion']:.1f}% de Prospectos")
    kpi_cols[2].metric("Respuestas 1er Msj", f"{kpis_calculados_campana['respuestas_primer_mensaje']:,}",
                       f"{kpis_calculados_campana['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas")
    kpi_cols[3].metric("Sesiones Agendadas", f"{kpis_calculados_campana['sesiones_agendadas']:,}",
                       f"{kpis_calculados_campana['tasa_sesion_global']:.1f}% de Prospectos")
    
    if kpis_calculados_campana['sesiones_agendadas'] > 0 and kpis_calculados_campana['respuestas_primer_mensaje'] > 0 :
         st.caption(f"Tasa de Sesiones vs Respuestas: {kpis_calculados_campana['tasa_sesion_vs_respuesta']:.1f}%")


    # --- Embudo de Conversión ---
    st.markdown("### Embudo de Conversión")
    mostrar_embudo_para_campana(kpis_calculados_campana)

    # --- Análisis por Prospectador (Ejemplo) ---
    if st.session_state.campana_filtro_prospectador == "– Todos –" and "¿Quién Prospecto?" in df_final_analisis_campana.columns:
        st.markdown("### Rendimiento por Prospectador en la(s) Campaña(s)")
        df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?").apply(
            lambda x: pd.Series(calcular_kpis_df_campana(x))
        ).reset_index()
        
        df_prospectador_camp_display = df_prospectador_camp[
            (df_prospectador_camp['total_prospectos'] > 0) # Solo mostrar si tienen prospectos
        ][[
            "¿Quién Prospecto?", "total_prospectos", "invites_aceptadas", 
            "respuestas_primer_mensaje", "sesiones_agendadas", "tasa_sesion_global"
        ]].rename(columns={
            "total_prospectos": "Prospectos",
            "invites_aceptadas": "Aceptadas",
            "respuestas_primer_mensaje": "Respuestas",
            "sesiones_agendadas": "Sesiones",
            "tasa_sesion_global": "Tasa Sesión Global (%)"
        }).sort_values(by="Sesiones", ascending=False)

        if not df_prospectador_camp_display.empty:
            st.dataframe(
                df_prospectador_camp_display.style.format({"Tasa Sesión Global (%)": "{:.1f}%"}),
                use_container_width=True
            )
            
            fig_prosp_camp = px.bar(
                df_prospectador_camp_display.sort_values(by="Tasa Sesión Global (%)", ascending=False),
                x="¿Quién Prospecto?",
                y="Tasa Sesión Global (%)",
                title="Tasa de Sesión Global por Prospectador",
                text="Tasa Sesión Global (%)",
                color="Tasa Sesión Global (%)"
            )
            fig_prosp_camp.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
            fig_prosp_camp.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig_prosp_camp, use_container_width=True)
        else:
            st.caption("No hay suficientes datos para mostrar el rendimiento por prospectador para la selección actual.")


    # --- Tabla Detallada de Prospectos ---
    st.markdown("### Detalle de Prospectos en Campaña(s) Seleccionada(s)")
    columnas_a_mostrar_tabla = [
        "Campaña", "Nombre", "Apellido", "Empresa", "Puesto", "¿Quién Prospecto?",
        "Fecha de Invite", "¿Invite Aceptada?", "Fecha Primer Mensaje",
        "Respuesta Primer Mensaje", "Sesion Agendada?", "Fecha Sesion",
        "Pais", "Industria", "Avatar" # Añade o quita según necesites
    ]
    columnas_existentes_tabla = [col for col in columnas_a_mostrar_tabla if col in df_final_analisis_campana.columns]
    
    df_display_tabla_campana = df_final_analisis_campana[columnas_existentes_tabla].copy()
    
    # Formatear fechas para la tabla
    for col_fecha_tabla in ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"]:
        if col_fecha_tabla in df_display_tabla_campana.columns:
            df_display_tabla_campana[col_fecha_tabla] = pd.to_datetime(df_display_tabla_campana[col_fecha_tabla], errors='coerce').dt.strftime('%d/%m/%Y')

    st.dataframe(df_display_tabla_campana, height=400, use_container_width=True)

    # Descarga Excel
    @st.cache_data # Cachear la conversión para no rehacerla innecesariamente
    def convertir_df_a_excel_campana(df_conv):
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df_conv.to_excel(writer, index=False, sheet_name='Prospectos_Campaña')
        return output.getvalue()

    excel_data_campana = convertir_df_a_excel_campana(df_final_analisis_campana[columnas_existentes_tabla])
    nombre_archivo_excel = f"analisis_campañas_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
    st.download_button(
        label="⬇️ Descargar Datos de Campaña (Excel)",
        data=excel_data_campana,
        file_name=nombre_archivo_excel,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_excel_campana"
    )

st.markdown("---")
st.info(
    "Esta página de análisis de campañas ha sido desarrollada para ofrecer una vista dedicada y optimizada. ✨"
)
