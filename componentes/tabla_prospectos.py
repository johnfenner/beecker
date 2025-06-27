# Prospe/componentes/tabla_prospectos.py
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import pandas as pd

def mostrar_tabla_filtrada(df_tabla, key_suffix=""):
    """
    Muestra una tabla AgGrid filtrada. Acepta un key_suffix para crear claves de widget únicas.
    """
    # El título general ya no es necesario aquí, lo pondremos en el dashboard principal.

    if df_tabla.empty:
        st.info("No hay prospectos para mostrar con los filtros actuales.")
        return

    # --- Creación de claves únicas usando el sufijo ---
    session_state_key = f'columnas_seleccionadas_tabla_{key_suffix}'
    multiselect_key = f"multiselect_widget_tabla_{key_suffix}"
    aggrid_key = f'aggrid_tabla_{key_suffix}'
    download_button_key = f"download_button_tabla_{key_suffix}"
    
    todas_columnas = df_tabla.columns.tolist()

    if session_state_key not in st.session_state:
        st.session_state[session_state_key] = todas_columnas

    columnas_guardadas_en_estado = st.session_state.get(session_state_key, todas_columnas)
    default_columnas_validas = [col for col in columnas_guardadas_en_estado if col in todas_columnas]

    if not default_columnas_validas and todas_columnas:
        default_columnas_validas = todas_columnas
        st.session_state[session_state_key] = todas_columnas

    with st.expander("Seleccionar Columnas para Mostrar en esta Tabla", expanded=False):
      columnas_elegidas_widget = st.multiselect(
          "Elige las columnas:",
          options=todas_columnas,
          default=default_columnas_validas,
          key=multiselect_key
      )

    if columnas_elegidas_widget != st.session_state[session_state_key]:
        st.session_state[session_state_key] = columnas_elegidas_widget
        st.rerun()

    columnas_para_mostrar_en_tabla = st.session_state[session_state_key]

    if not columnas_para_mostrar_en_tabla and todas_columnas:
        columnas_para_mostrar_en_tabla = todas_columnas
    
    tabla_con_columnas_seleccionadas = df_tabla[columnas_para_mostrar_en_tabla].copy()
    
    gb = GridOptionsBuilder.from_dataframe(tabla_con_columnas_seleccionadas)
    gb.configure_default_column(resizable=True, sortable=True, filter='agTextColumnFilter', editable=False)

    if "Fecha Primer Mensaje" in columnas_para_mostrar_en_tabla:
        gb.configure_column("Fecha Primer Mensaje", cellRenderer=f"""
            function(params) {{
                if (params.value == null || params.value == '' || String(params.value).toLowerCase() == 'no' || String(params.value).toLowerCase() == 'nat') {{ return '<span style="color: red;">Sin Respuesta Inicial</span>'; }}
                else {{ try {{ const date = new Date(params.value); if (!isNaN(date.getTime())) {{ return date.toLocaleDateString('es-ES', {{ day: '2-digit', month: '2-digit', year: 'numeric' }}); }} }} catch (e) {{}} return params.value; }}
            }}
        """)

    if "Sesion Agendada?" in columnas_para_mostrar_en_tabla:
        gb.configure_column("Sesion Agendada?", cellRenderer=f"""
            function(params) {{
                if (params.value == null || String(params.value).toLowerCase() == 'no') {{ return '<span style="color: orange;">Sesión No Agendada</span>'; }}
                else if (String(params.value).toLowerCase() == 'si') {{ return '<span style="color: green; font-weight: bold;">Sí Agendada</span>'; }}
                else {{ return params.value; }}
            }}
        """)

    if "LinkedIn" in columnas_para_mostrar_en_tabla:
         gb.configure_column("LinkedIn", cellRenderer="""function(params) { if(params.value && String(params.value).trim() !== '' && String(params.value).toLowerCase() !== 'no' && String(params.value).toLowerCase() !== 'na'){ return '<a href="' + params.value + '" target="_blank">'+ 'Ver Perfil' +'</a>'} else { return ''}}""")

    gridOptions = gb.build()

    st.write(f"Mostrando {len(columnas_para_mostrar_en_tabla)} de {len(todas_columnas)} columnas seleccionadas.")
    AgGrid(tabla_con_columnas_seleccionadas, gridOptions=gridOptions, height=400, width='100%', theme="alpine", enable_enterprise_modules=False, allow_unsafe_jscode=True, reload_data=True, key=aggrid_key)

    output = io.BytesIO()
    tabla_con_columnas_seleccionadas.to_excel(output, index=False, engine='openpyxl')
    st.download_button( "⬇️ Descargar Vista Actual (Excel)", output.getvalue(), f"prospectos_filtrados_{key_suffix}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=download_button_key)
