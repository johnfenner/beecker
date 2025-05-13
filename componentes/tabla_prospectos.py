# componentes/tabla_prospectos.py
import streamlit as st
# Corregido: Eliminar ColumnsOptionsBuilder de la importación
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import pandas as pd # Asegurarse de importar pandas

def mostrar_tabla_filtrada(df_tabla):
    st.markdown("### 📄 Prospectos Filtrados")

    if df_tabla.empty:
        st.info("No hay prospectos para mostrar con los filtros actuales.")
        return

    # --- Inicio: Selección de Columnas ---
    todas_columnas = df_tabla.columns.tolist()

    # Usar session_state para guardar las columnas seleccionadas
    if 'columnas_seleccionadas_tabla' not in st.session_state:
        # Por defecto, seleccionar todas las columnas la primera vez
        st.session_state['columnas_seleccionadas_tabla'] = todas_columnas

    # Crear el multiselect, asegurando que los valores por defecto sean válidos
    columnas_disponibles_actualmente = st.session_state['columnas_seleccionadas_tabla']
    # Filtrar el default para que solo contenga columnas que realmente existen en el df actual
    default_seleccionado_valido = [col for col in columnas_disponibles_actualmente if col in todas_columnas]
    if not default_seleccionado_valido: # Si la selección guardada ya no es válida, volver a todas
        default_seleccionado_valido = todas_columnas
        st.session_state['columnas_seleccionadas_tabla'] = default_seleccionado_valido

    # Widget para seleccionar columnas
    with st.expander("Seleccionar Columnas para Mostrar", expanded=False):
      columnas_elegidas = st.multiselect(
          "Elige las columnas que quieres ver en la tabla:",
          options=todas_columnas,
          default=default_seleccionado_valido, # Usar el default validado
          key="multiselect_columnas_tabla" # Usar una key diferente para el widget
      )

    # Actualizar el session_state con la nueva selección
    if columnas_elegidas != st.session_state['columnas_seleccionadas_tabla']:
        st.session_state['columnas_seleccionadas_tabla'] = columnas_elegidas
        # No es necesario st.rerun() aquí, Streamlit lo maneja

    # Usar las columnas seleccionadas del estado de sesión
    columnas_para_mostrar = st.session_state['columnas_seleccionadas_tabla']

    # Si no se elige ninguna columna, mostrar todas como fallback o un mensaje
    if not columnas_para_mostrar:
        st.warning("No has seleccionado ninguna columna para mostrar. Mostrando todas por defecto.")
        columnas_para_mostrar = todas_columnas # Fallback a mostrar todas

    # Filtrar el DataFrame original para la tabla AgGrid
    tabla_filtrada_por_columnas = df_tabla[columnas_para_mostrar].copy()
    # --- Fin: Selección de Columnas ---


    # --- Configuración de AgGrid (usando tabla_filtrada_por_columnas) ---
    gb = GridOptionsBuilder.from_dataframe(tabla_filtrada_por_columnas)

    # Configuración por defecto (aplicada a las columnas que se mostrarán)
    gb.configure_default_column(resizable=True, sortable=True, filter='agTextColumnFilter', editable=False)

    # Configuración específica de columnas (solo si existen en columnas_para_mostrar)
    if "Fecha Primer Mensaje" in columnas_para_mostrar:
        gb.configure_column("Fecha Primer Mensaje", cellRenderer=f"""
            function(params) {{
                if (params.value == null || params.value == '' || String(params.value).toLowerCase() == 'no') {{
                    return '<span style="color: red;">Sin Respuesta Inicial</span>';
                }} else {{
                    // Intentar formatear si es fecha válida, sino mostrar como viene
                    try {{
                       const date = new Date(params.value);
                       // Verificar si es una fecha válida antes de formatear
                       if (!isNaN(date.getTime())) {{
                           return date.toLocaleDateString('es-ES', {{ day: '2-digit', month: '2-digit', year: 'numeric' }});
                       }}
                    }} catch (e) {{ /* Ignorar error de parseo */ }}
                    return params.value; // Devolver valor original si no es fecha o hay error
                }}
            }}
        """)

    if "Sesion Agendada?" in columnas_para_mostrar:
        gb.configure_column("Sesion Agendada?", cellRenderer=f"""
            function(params) {{
                if (params.value == null || String(params.value).toLowerCase() == 'no') {{
                    return '<span style="color: orange;">Sesión No Agendada</span>';
                }} else if (String(params.value).toLowerCase() == 'si') {{
                     return '<span style="color: green; font-weight: bold;">Sí Agendada</span>';
                }} else {{
                    return params.value; // Mostrar otros valores como vienen
                }}
            }}
        """)

    if "LinkedIn" in columnas_para_mostrar:
         gb.configure_column("LinkedIn", cellRenderer="""function(params) { if(params.value){ return '<a href="' + params.value + '" target="_blank">'+ 'Ver Perfil' +'</a>'} else { return ''}}""")


    # Puedes añadir más configuraciones específicas aquí si es necesario
    # Ejemplo: Ocultar el índice
    # gb.configure_grid_options(suppressRowTransform=True)

    gridOptions = gb.build()

    # --- Mostrar AgGrid ---
    st.write(f"Mostrando {len(columnas_para_mostrar)} de {len(todas_columnas)} columnas seleccionadas.")
    AgGrid(
        tabla_filtrada_por_columnas, # Usar el DataFrame con columnas seleccionadas
        gridOptions=gridOptions,
        height=400,
        width='100%', # Asegurar que use el ancho completo
        theme="alpine", # Puedes probar otros temas: "streamlit", "balham", "material"
        enable_enterprise_modules=False,
        # Permitir seleccionar texto en la tabla
        allow_unsafe_jscode=True, # Necesario para cellRenderer
        # Actualizar automáticamente si los datos cambian (útil con filtros)
        reload_data=True,
        key='aggrid_tabla_principal' # Añadir una key única para la tabla
    )

    # --- Descarga Excel (Descargará las columnas actualmente visibles en la tabla) ---
    output = io.BytesIO()
    # Usar tabla_filtrada_por_columnas para la descarga
    tabla_filtrada_por_columnas.to_excel(output, index=False, engine='openpyxl')
    st.download_button(
        "⬇️ Descargar Vista Actual (Excel)",
        output.getvalue(),
        "prospectos_filtrados_vista_actual.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_button_tabla_vista" # Key única para el botón de descarga
    )
