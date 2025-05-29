import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import sys
import os
from datos.carga_datos import cargar_y_limpiar_datos
from utils.limpieza import limpiar_valor_kpi, estandarizar_avatar

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

    date_cols_to_check = ["Fecha de Invite", "Fecha Primer Mensaje", "Fecha Sesion"]
    for col in date_cols_to_check:
        if col in df_base_campanas.columns and not pd.api.types.is_datetime64_any_dtype(df_base_campanas[col]):
            df_base_campanas[col] = pd.to_datetime(df_base_campanas[col], errors='coerce')
        if col in df_completo.columns and not pd.api.types.is_datetime64_any_dtype(df_completo[col]):
            df_completo[col] = pd.to_datetime(df_completo[col], errors='coerce')

    for df_proc in [df_base_campanas, df_completo]:
        if "Avatar" in df_proc.columns:
            df_proc["Avatar"] = df_proc["Avatar"].apply(estandarizar_avatar)

    return df_base_campanas, df_completo


def inicializar_estado_filtros_campana():
    default_filters = {
        "campana_seleccion_principal": [],
        "campana_filtro_prospectador": ["– Todos –"],
        "campana_filtro_pais": ["– Todos –"],
        "campana_filtro_fecha_ini": None,
        "campana_filtro_fecha_fin": None,
    }
    for key, value in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = value
        elif key in ["campana_seleccion_principal", "campana_filtro_prospectador", "campana_filtro_pais"] and not isinstance(st.session_state[key], list):
            st.session_state[key] = value


def resetear_filtros_campana_callback():
    st.session_state.campana_seleccion_principal = []
    st.session_state.campana_filtro_prospectador = ["– Todos –"]
    st.session_state.campana_filtro_pais = ["– Todos –"]
    st.session_state.di_campana_fecha_ini = None
    st.session_state.di_campana_fecha_fin = None
    st.session_state.campana_filtro_fecha_ini = None
    st.session_state.campana_filtro_fecha_fin = None
    st.toast("Todos los filtros de la página de campañas han sido reiniciados.", icon="🧹")

# Funciones KPI y visualizaciones (sin cambios)
def calcular_kpis_df_campana(df_filtrado_campana):
    if df_filtrado_campana.empty:
        return {...}
    total_prospectos = len(df_filtrado_campana)
    invites_aceptadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("¿Invite Aceptada?", pd.Series(dtype=str)))
    primeros_mensajes_enviados = sum(
        pd.notna(x) and str(x).strip().lower() not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Fecha Primer Mensaje", pd.Series(dtype=str))
    )
    respuestas_primer_mensaje = sum(
        limpiar_valor_kpi(x) not in ["no", "", "nan"]
        for x in df_filtrado_campana.get("Respuesta Primer Mensaje", pd.Series(dtype=str))
    )
    sesiones_agendadas = sum(limpiar_valor_kpi(x) == "si" for x in df_filtrado_campana.get("Sesion Agendada?", pd.Series(dtype=str)))
    tasa_aceptacion = (invites_aceptadas / total_prospectos * 100) if total_prospectos > 0 else 0
    tasa_respuesta_vs_aceptadas = (respuestas_primer_mensaje / invites_aceptadas * 100) if invites_aceptadas > 0 else 0
    tasa_sesion_vs_respuesta = (sesiones_agendadas / respuestas_primer_mensaje * 100) if respuestas_primer_mensaje > 0 else 0
    tasa_sesion_global = (sesiones_agendadas / total_prospectos * 100) if total_prospectos > 0 else 0
    return {
        "total_prospectos": int(total_prospectos),
        "invites_aceptadas": int(invites_aceptadas),
        "primeros_mensajes_enviados": int(primeros_mensajes_enviados),
        "respuestas_primer_mensaje": int(respuestas_primer_mensaje),
        "sesiones_agendadas": int(sesiones_agendadas),
        "tasa_aceptacion": tasa_aceptacion,
        "tasa_respuesta_vs_aceptadas": tasa_respuesta_vs_aceptadas,
        "tasa_sesion_vs_respuesta": tasa_sesion_vs_respuesta,
        "tasa_sesion_global": tasa_sesion_global,
    }

def mostrar_embudo_para_campana(kpis_campana, titulo_embudo="Embudo de Conversión de Campaña"):
    # (sin cambios)
    pass

def generar_tabla_comparativa_campanas_filtrada(df_filtrado_con_filtros_pagina, lista_nombres_campanas_seleccionadas):
    # (sin cambios)
    pass

# Carga de datos y estado
df_base_campanas_global, df_original_completo = obtener_datos_base_campanas()
inicializar_estado_filtros_campana()
if df_base_campanas_global.empty:
    st.stop()

# Selección y filtros (sin cambios hasta df_final_analisis_campana)
# ... (código de selección y aplicación de filtros) ...

# Antes de mostrar resultados:
df_final_analisis_campana = df_aplicar_filtros.copy()

# --- Sección de Resultados y Visualizaciones ---
st.markdown("---")
st.header(f"📊 Resultados para: {', '.join(st.session_state.campana_seleccion_principal)}")

if not df_final_analisis_campana.empty:
    # NUEVA MÉTRICA: Datos totales en la campaña (sin filtrar por prospectos)
    df_datos_campana = df_base_campanas_global[df_base_campanas_global['Campaña'].isin(st.session_state.campana_seleccion_principal)]
    total_datos_campana = len(df_datos_campana)

    st.markdown("### Indicadores Clave (KPIs) - Agregado de Selección")
    kpis_agregado = calcular_kpis_df_campana(df_final_analisis_campana)
    # Crear 5 columnas para incluir la nueva métrica
    kpi_cols = st.columns(5)
    kpi_cols[0].metric("Datos en Campaña", f"{total_datos_campana:,}")
    kpi_cols[1].metric("Total Prospectos", f"{kpis_agregado['total_prospectos']:,}")
    kpi_cols[2].metric("Invites Aceptadas", f"{kpis_agregado['invites_aceptadas']:,}", f"{kpis_agregado['tasa_aceptacion']:.1f}% de Prospectos")
    kpi_cols[3].metric("Respuestas 1er Msj", f"{kpis_agregado['respuestas_primer_mensaje']:,}", f"{kpis_agregado['tasa_respuesta_vs_aceptadas']:.1f}% de Aceptadas")
    kpi_cols[4].metric("Sesiones Agendadas", f"{kpis_agregado['sesiones_agendadas']:,}", f"{kpis_agregado['tasa_sesion_global']:.1f}% de Prospectos")
    if kpis_agregado['sesiones_agendadas'] > 0 and kpis_agregado['respuestas_primer_mensaje'] > 0:
        st.caption(f"Tasa de Sesiones vs Respuestas (Agregado): {kpis_agregado['tasa_sesion_vs_respuesta']:.1f}%")

    # Resto de la visualización (embudo, comparativa, rendimientos, detalle) permanece igual
    st.markdown("### Embudo de Conversión - Agregado de Selección")
    mostrar_embudo_para_campana(kpis_calculados_campana_agregado, "Embudo de Conversión (Agregado de Selección y Filtros)")

    if len(st.session_state.campana_seleccion_principal) > 1:
        st.markdown("---")
        st.header(f"🔄 Comparativa Detallada entre Campañas (afectada por filtros de página)")
        st.caption("La siguiente tabla compara las campañas seleccionadas. 'Registros Originales' muestra el total de datos antes de filtros. Otros KPIs consideran los filtros de '¿Quién Prospectó?', 'País' y 'Fechas' aplicados arriba.")
        
        df_tabla_comp = generar_tabla_comparativa_campanas_filtrada(
            df_final_analisis_campana, # Este es el DF con filtros de página aplicados
            st.session_state.campana_seleccion_principal,
            df_base_campanas_global # <--- Pasar el DF base global para conteo original
        )
        
        if not df_tabla_comp.empty:
            st.subheader("Tabla Comparativa de KPIs (con filtros aplicados)")
            cols_enteros_comp = ["Registros Originales", "Prospectos (Tras Filtros)", "Aceptadas", "Respuestas", "Sesiones"] # Añadida nueva métrica y nombre cambiado
            format_dict_comp = {"Tasa Aceptación (%)": "{:.1f}%", "Tasa Respuesta (vs Acept.) (%)": "{:.1f}%", "Tasa Sesiones (vs Resp.) (%)": "{:.1f}%", "Tasa Sesión Global (%)": "{:.1f}%"}
            for col_int_comp in cols_enteros_comp:
                if col_int_comp in df_tabla_comp.columns:
                    df_tabla_comp[col_int_comp] = pd.to_numeric(df_tabla_comp[col_int_comp], errors='coerce').fillna(0).astype(int)
                    format_dict_comp[col_int_comp] = "{:,}"
            
            st.dataframe(df_tabla_comp.sort_values(by="Tasa Sesión Global (%)", ascending=False).style.format(format_dict_comp), use_container_width=True, hide_index=True)
            
            st.subheader("Gráfico: Tasa de Sesión Global por Campaña (con filtros aplicados)")
            # Usar 'Prospectos (Tras Filtros)' para la condición del gráfico
            df_graf_comp_tasa_global = df_tabla_comp[df_tabla_comp["Prospectos (Tras Filtros)"] > 0].sort_values(by="Tasa Sesión Global (%)", ascending=False)
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
        # Usar 'prospectos_tras_filtros' que es la salida de calcular_kpis_df_campana
        df_prospectador_camp = df_final_analisis_campana.groupby("¿Quién Prospecto?").apply(lambda x: pd.Series(calcular_kpis_df_campana(x))).reset_index()
        df_prospectador_camp_display = df_prospectador_camp[
            (df_prospectador_camp['prospectos_tras_filtros'] > 0) # Usar el nombre correcto
        ][["¿Quién Prospecto?", "prospectos_tras_filtros", "invites_aceptadas", "respuestas_primer_mensaje", "sesiones_agendadas", "tasa_sesion_global"]].rename(
            columns={"prospectos_tras_filtros": "Prospectos (Tras Filtros)", "invites_aceptadas": "Aceptadas", "respuestas_primer_mensaje": "Respuestas", "sesiones_agendadas": "Sesiones", "tasa_sesion_global": "Tasa Sesión Global (%)"}
        ).sort_values(by="Sesiones", ascending=False)
        
        cols_enteros_prosp = ["Prospectos (Tras Filtros)", "Aceptadas", "Respuestas", "Sesiones"] # Nombre cambiado
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
            elif isinstance(st.session_state.campana_filtro_prospectador, list) and len(st.session_state.campana_filtro_prospectador) > 1 and "– Todos –" not in st.session_state.campana_filtro_prospectador and len(df_prospectador_camp_display['¿Quién Prospecto?'].unique()) > 1:
                mostrar_grafico_prospectador = True
            
            if mostrar_grafico_prospectador:
                fig_prosp_camp_bar = px.bar(df_prospectador_camp_display.sort_values(by="Tasa Sesión Global (%)", ascending=False), x="¿Quién Prospecto?", y="Tasa Sesión Global (%)", title="Tasa de Sesión Global por Prospectador (Selección Actual)", text="Tasa Sesión Global (%)", color="Tasa Sesión Global (%)") # Considerar color por ¿Quién Prospecto?
                fig_prosp_camp_bar.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_prosp_camp_bar.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig_prosp_camp_bar, use_container_width=True)
        else: st.caption("No hay datos de rendimiento por prospectador para la selección actual.")
    else: st.caption("La columna '¿Quién Prospecto?' no está disponible.")

    st.markdown("### Detalle de Prospectos (para la selección actual)")
    # df_final_analisis_campana contiene los índices correctos DESPUÉS de todos los filtros
    # df_original_completo tiene todos los datos originales. Usamos los índices de df_final_analisis_campana para extraer de df_original_completo
    indices_filtrados = df_final_analisis_campana.index 
    # Asegurar que los índices existen en df_original_completo (si se hizo un reset_index en df_final_analisis_campana sin dropear)
    # O mejor, si df_final_analisis_campana es una copia directa con filtros, sus índices son los de df_original_completo
    df_detalle_original_filtrado = df_original_completo.loc[df_original_completo.index.isin(indices_filtrados)].copy()


    if not df_detalle_original_filtrado.empty:
        df_display_tabla_campana_detalle = pd.DataFrame()
        # Definir columnas a mostrar y su orden deseado
        cols_a_mostrar_detalle = [
            "Campaña", "Avatar", "¿Quién Prospecto?", "Pais", "Fecha de Invite", 
            "¿Invite Aceptada?", "Fecha Primer Mensaje", "Respuesta Primer Mensaje", 
            "Sesion Agendada?", "Fecha Sesion"
        ]
        # Tomar solo las columnas que existen en el dataframe
        cols_existentes_detalle = [col for col in cols_a_mostrar_detalle if col in df_detalle_original_filtrado.columns]
        
        for col_orig in cols_existentes_detalle: # Iterar solo sobre las columnas seleccionadas
            if pd.api.types.is_datetime64_any_dtype(df_detalle_original_filtrado[col_orig]):
                 df_display_tabla_campana_detalle[col_orig] = pd.to_datetime(df_detalle_original_filtrado[col_orig], errors='coerce').dt.strftime('%d/%m/%Y').fillna("N/A")
            elif pd.api.types.is_numeric_dtype(df_detalle_original_filtrado[col_orig]) and (df_detalle_original_filtrado[col_orig].dropna().apply(lambda x: isinstance(x, float) and x.is_integer()).all() or pd.api.types.is_integer_dtype(df_detalle_original_filtrado[col_orig].dropna())):
                 df_display_tabla_campana_detalle[col_orig] = df_detalle_original_filtrado[col_orig].fillna(0).astype(int).astype(str).replace('0', "N/A") # Considerar no reemplazar 0 con N/A si 0 es un valor válido
            else:
                 df_display_tabla_campana_detalle[col_orig] = df_detalle_original_filtrado[col_orig].astype(str).fillna("N/A")
        
        st.dataframe(df_display_tabla_campana_detalle, height=400, use_container_width=True)
        
        @st.cache_data
        def convertir_df_a_excel_campana_detalle(df_conv):
            output = io.BytesIO()
            # Seleccionar y ordenar columnas también para el Excel
            df_excel_export = df_conv[cols_existentes_detalle].copy()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_excel_export.to_excel(writer, index=False, sheet_name='Prospectos_Campaña_Detalle')
            return output.getvalue()
        
        excel_data_campana_detalle = convertir_df_a_excel_campana_detalle(df_detalle_original_filtrado) # Pasar el df con todas las columnas originales
        
        nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(st.session_state.campana_seleccion_principal)}.xlsx"
        if not st.session_state.campana_seleccion_principal: # Evitar nombre de archivo feo si no hay selección
            nombre_archivo_excel_detalle = "detalle_campañas_sin_seleccion.xlsx"
        else:
            nombre_archivo_excel_detalle = f"detalle_campañas_{'_'.join(s.replace(' ', '_') for s in st.session_state.campana_seleccion_principal)}.xlsx"


        st.download_button(label="⬇️ Descargar Detalle de Selección Actual (Excel)", data=excel_data_campana_detalle, file_name=nombre_archivo_excel_detalle, mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel_campana_detalle")
    else: st.caption("No hay prospectos detallados para mostrar con los filtros actuales.")

st.markdown("---")
st.info(
    "Esta maravillosa, caótica y probablemente sobrecafeinada plataforma ha sido realizada por Johnsito ✨ 😊"
)
