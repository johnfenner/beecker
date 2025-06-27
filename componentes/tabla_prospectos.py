# Prospe/componentes/tabla_prospectos.py
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder
import io
import pandas as pd

def mostrar_tabla_filtrada(df_tabla, key_suffix=""):
    """
    Muestra una tabla AgGrid. Acepta un key_suffix para crear claves de widget únicas.
    """
    if df_tabla.empty:
        st.info("No hay prospectos para mostrar con los filtros actuales.")
        return

    session_state_key = f'columnas_seleccionadas_{key_suffix}'
    multiselect_key = f"multiselect_widget_{key_suffix}"
    aggrid_key = f'aggrid_tabla_{key_suffix}'
    download_button_key = f"download_button_{key_suffix}"
    
    todas_columnas = df_tabla.columns.tolist()

    if session_state_key not in st.session_state:
        st.session_state[session_state_key] = todas_columnas

    columnas_guardadas = st.session_state.get(session_state_key, todas_columnas)
    default_columnas_validas = [col for col in columnas_guardadas if col in todas_columnas]

    if not default_columnas_validas and todas_columnas:
        default_columnas_validas = todas_columnas
        st.session_state[session_state_key] = todas_columnas

    with st.expander("Seleccionar Columnas para Mostrar en esta Tabla"):
      columnas_elegidas = st.multiselect(
          "Elige las columnas:",
          options=todas_columnas,
          default=default_columnas_validas,
          key=multiselect_key
      )

    if columnas_elegidas != st.session_state[session_state_key]:
        st.session_state[session_state_key] = columnas_elegidas
        st.rerun()

    columnas_para_mostrar = st.session_state[session_state_key]

    if not columnas_para_mostrar:
        st.info("Selecciona al menos una columna para mostrar.")
        return

    tabla_a_mostrar = df_tabla[columnas_para_mostrar].copy()
    
    gb = GridOptionsBuilder.from_dataframe(tabla_a_mostrar)
    gb.configure_default_column(resizable=True, sortable=True, filter='agTextColumnFilter', editable=False)

    if "Fecha Primer Mensaje" in columnas_para_mostrar:
        gb.configure_column("Fecha Primer Mensaje", cellRenderer="""function(params) { if (!params.value || params.value.toLowerCase() === 'no' || params.value.toLowerCase() === 'nat') { return '<span style="color: red;">Sin Respuesta Inicial</span>'; } else { return params.value; }}""")

    if "Sesion Agendada?" in columnas_para_mostrar:
        gb.configure_column("Sesion Agendada?", cellRenderer="""function(params) { if (!params.value || params.value.toLowerCase() === 'no') { return '<span style="color: orange;">No</span>'; } else if (params.value.toLowerCase() === 'si') { return '<span style="color: green; font-weight: bold;">Sí</span>'; } else { return params.value; }}""")

    if "LinkedIn" in columnas_para_mostrar:
         gb.configure_column("LinkedIn", cellRenderer="""function(params) { if(params.value && String(params.value).trim()){ return '<a href="' + params.value + '" target="_blank">Ver Perfil</a>'} else { return ''}}""")

    gridOptions = gb.build()

    st.write(f"Mostrando {len(columnas_para_mostrar)} de {len(todas_columnas)} columnas para {len(tabla_a_mostrar)} prospectos.")
    AgGrid(tabla_a_mostrar, gridOptions=gridOptions, height=400, width='100%', theme="alpine", allow_unsafe_jscode=True, key=aggrid_key)

    output = io.BytesIO()
    tabla_a_mostrar.to_excel(output, index=False, engine='openpyxl')
    st.download_button( "⬇️ Descargar Vista (Excel)", output.getvalue(), f"prospectos_{key_suffix}.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=download_button_key)
