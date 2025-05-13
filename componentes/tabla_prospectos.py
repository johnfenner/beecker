# Prospe/componentes/tabla_prospectos.py
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder # ColumnsOptionsBuilder fue eliminado correctamente antes
import io
import pandas as pd

def mostrar_tabla_filtrada(df_tabla):
    st.markdown("### 📄 Prospectos Filtrados")

    if df_tabla.empty:
        st.info("No hay prospectos para mostrar con los filtros actuales.")
        return

    todas_columnas = df_tabla.columns.tolist()

    # Inicializar el estado de sesión para las columnas seleccionadas si no existe
    if 'columnas_seleccionadas_tabla_principal' not in st.session_state:
        st.session_state['columnas_seleccionadas_tabla_principal'] = todas_columnas

    # Validar que las columnas guardadas en session_state sigan existiendo en el df_tabla actual
    columnas_guardadas_en_estado = st.session_state['columnas_seleccionadas_tabla_principal']
    default_columnas_validas = [col for col in columnas_guardadas_en_estado if col in todas_columnas]

    if not default_columnas_validas and todas_columnas: # Si ninguna de las guardadas es válida, pero hay columnas
        default_columnas_validas = todas_columnas
        st.session_state['columnas_seleccionadas_tabla_principal'] = todas_columnas # Resetear el estado
    elif not default_columnas_validas and not todas_columnas: # No hay columnas ni en estado ni en df
         default_columnas_validas = []
         st.session_state['columnas_seleccionadas_tabla_principal'] = []


    with st.expander("Seleccionar Columnas para Mostrar en Tabla Principal", expanded=False):
      columnas_elegidas_widget = st.multiselect(
          "Elige las columnas:",
          options=todas_columnas,
          default=default_columnas_validas, # Usar las columnas validadas
          key="multiselect_widget_tabla_principal" # Key única para el widget
      )

    # Actualizar el estado de sesión con la nueva selección del widget
    # Esto es crucial para que la selección persista y se use correctamente
    if columnas_elegidas_widget != st.session_state['columnas_seleccionadas_tabla_principal']:
        st.session_state['columnas_seleccionadas_tabla_principal'] = columnas_elegidas_widget
        # st.rerun() # Podría ser necesario si la actualización no es inmediata en todos los casos, pero usualmente Streamlit lo maneja

    # Usar siempre las columnas del estado de sesión para la lógica de la tabla
    columnas_para_mostrar_en_tabla = st.session_state['columnas_seleccionadas_tabla_principal']


    if not columnas_para_mostrar_en_tabla and todas_columnas:
        # st.warning("No has seleccionado ninguna columna. Mostrando todas por defecto.") # Opcional
        columnas_para_mostrar_en_tabla = todas_columnas
    elif not columnas_para_mostrar_en_tabla and not todas_columnas:
        st.info("No hay columnas disponibles para mostrar.")
        return


    tabla_con_columnas_seleccionadas = df_tabla[columnas_para_mostrar_en_tabla].copy()
    
    gb = GridOptionsBuilder.from_dataframe(tabla_con_columnas_seleccionadas)
    gb.configure_default_column(resizable=True, sortable=True, filter='agTextColumnFilter', editable=False)

    # Configuraciones específicas de columnas (solo si están seleccionadas para mostrarse)
    if "Fecha Primer Mensaje" in columnas_para_mostrar_en_tabla:
        gb.configure_column("Fecha Primer Mensaje", cellRenderer=f"""
            function(params) {{
                if (params.value == null || params.value == '' || String(params.value).toLowerCase() == 'no' || String(params.value).toLowerCase() == 'nat') {{
                    return '<span style="color: red;">Sin Respuesta Inicial</span>';
                }} else {{
                    try {{ /* Intento de formatear como fecha */
                       const date = new Date(params.value);
                       if (!isNaN(date.getTime())) {{ /* Verificar si es fecha válida */
                           return date.toLocaleDateString('es-ES', {{ day: '2-digit', month: '2-digit', year: 'numeric' }});
                       }}
                    }} catch (e) {{ /* Ignorar error de parseo de fecha */ }}
                    return params.value; /* Devolver valor original si no es fecha o hay error */
                }}
            }}
        """)

    if "Sesion Agendada?" in columnas_para_mostrar_en_tabla:
        gb.configure_column("Sesion Agendada?", cellRenderer=f"""
            function(params) {{
                if (params.value == null || String(params.value).toLowerCase() == 'no') {{
                    return '<span style="color: orange;">Sesión No Agendada</span>';
                }} else if (String(params.value).toLowerCase() == 'si') {{
                     return '<span style="color: green; font-weight: bold;">Sí Agendada</span>';
                }} else {{
                    return params.value; /* Mostrar otros valores como vienen */
                }}
            }}
        """)

    if "LinkedIn" in columnas_para_mostrar_en_tabla:
         gb.configure_column("LinkedIn", cellRenderer="""function(params) { if(params.value && String(params.value).trim() !== '' && String(params.value).toLowerCase() !== 'no' && String(params.value).toLowerCase() !== 'na'){ return '<a href="' + params.value + '" target="_blank">'+ 'Ver Perfil' +'</a>'} else { return ''}}""")

    gridOptions = gb.build()

    st.write(f"Mostrando {len(columnas_para_mostrar_en_tabla)} de {len(todas_columnas)} columnas seleccionadas.")
    AgGrid(
        tabla_con_columnas_seleccionadas,
        gridOptions=gridOptions,
        height=400,
        width='100%',
        theme="alpine", # O "streamlit", "balham", "material"
        enable_enterprise_modules=False,
        allow_unsafe_jscode=True, # Necesario para cellRenderer
        reload_data=True, # Importante para que AgGrid reaccione a cambios en el DataFrame
        key='aggrid_tabla_prospectos_principal' # Key única
    )

    # Descarga Excel con las columnas actualmente visibles
    output = io.BytesIO()
    tabla_con_columnas_seleccionadas.to_excel(output, index=False, engine='openpyxl')
    st.download_button(
        "⬇️ Descargar Vista Actual (Excel)",
        output.getvalue(),
        "prospectos_filtrados_vista_actual.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="download_button_tabla_principal_vista" # Key única
    )
