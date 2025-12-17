import streamlit as st
import plotly.express as px
import pandas as pd
from utils.limpieza import limpiar_valor_kpi

def mostrar_analisis_dimension_agendamiento_flexible(
    df_filtrado,
    dimension_col,
    titulo_dimension,
    top_n_grafico=10,
    mostrar_tabla_completa=False,
    min_prospectados_para_significancia=3 
):
    st.markdown("---")
    titulo_seccion = f"Análisis de {titulo_dimension}: Volumen Prospectado y Tasa de Agendamiento"
    st.markdown(f"## 🏆 {titulo_seccion}")

    if dimension_col not in df_filtrado.columns: # Verificación temprana de columna de dimensión
        st.warning(f"La columna '{dimension_col}' no se encuentra en los datos para el análisis de {titulo_dimension.lower()}.")
        return

    # Calcular prospectados y sesiones agendadas por dimensión
    # Solo agrupar si la columna de sesión también existe
    if "Sesion Agendada?" in df_filtrado.columns:
        resumen_dimension_completo = df_filtrado.groupby(dimension_col, as_index=False).agg(
            Total_Prospectados=(dimension_col, 'count'),
            Sesiones_Agendadas=("Sesion Agendada?", lambda x: (x.apply(limpiar_valor_kpi) == "si").sum())
        )
        resumen_dimension_completo["Tasa Agendamiento (%)"] = (
            (resumen_dimension_completo["Sesiones_Agendadas"] / resumen_dimension_completo["Total_Prospectados"]) * 100
        ).fillna(0).round(1)
    else: # Si no hay datos de sesión, solo podemos mostrar volumen
        st.warning(f"Columna 'Sesion Agendada?' no encontrada. Solo se mostrará el volumen prospectado para {titulo_dimension.lower()}.")
        resumen_dimension_completo = df_filtrado.groupby(dimension_col, as_index=False).agg(
            Total_Prospectados=(dimension_col, 'count')
        )
        resumen_dimension_completo["Sesiones_Agendadas"] = 0 
        resumen_dimension_completo["Tasa Agendamiento (%)"] = 0.0 

    resumen_dimension_completo.rename(columns={resumen_dimension_completo.columns[0]: dimension_col}, inplace=True)


    if resumen_dimension_completo.empty:
        st.info(f"No hay datos de {titulo_dimension.lower()} para mostrar con los filtros actuales.")
        return

    # --- GRÁFICOS TOP N ---
    resumen_para_graficos = resumen_dimension_completo[resumen_dimension_completo["Total_Prospectados"] >= min_prospectados_para_significancia].copy()

    if resumen_para_graficos.empty:
        st.info(f"No hay suficientes datos (con al menos {min_prospectados_para_significancia} prospectados por categoría de {titulo_dimension.lower()}) para generar los gráficos.")
    else:
        col_graf_volumen, col_graf_tasa = st.columns(2) # Columnas para poner gráficos lado a lado

        # GRÁFICO TOP N POR VOLUMEN PROSPECTADO
        with col_graf_volumen:
            st.markdown(f"#### Top {top_n_grafico} por Volumen")
            df_grafico_volumen = resumen_para_graficos.sort_values(by="Total_Prospectados", ascending=False).head(top_n_grafico)
            if not df_grafico_volumen.empty:
                category_order_vol = df_grafico_volumen[dimension_col].tolist()
                fig_volumen = px.bar(
                    df_grafico_volumen, x="Total_Prospectados", y=dimension_col, orientation='h',
                    title=f'Mayor Volumen (Top {len(df_grafico_volumen)})', color="Total_Prospectados",
                    text="Total_Prospectados", color_continuous_scale='Blues', 
                    category_orders={dimension_col: category_order_vol}
                )
                fig_volumen.update_traces(texttemplate='%{text:,}', textposition='outside')
                fig_volumen.update_layout(yaxis_title=None, title_x=0.5, margin=dict(l=0, r=0, t=30, b=0))
                st.plotly_chart(fig_volumen, use_container_width=True)
            else:
                st.caption(f"No hay {titulo_dimension.lower()} con suficiente volumen para el gráfico.")

        # GRÁFICO TOP N POR TASA DE AGENDAMIENTO
        if "Tasa Agendamiento (%)" in resumen_para_graficos.columns: 
            with col_graf_tasa:
                st.markdown(f"#### Top {top_n_grafico} por Tasa Agendamiento")
                df_grafico_tasa = resumen_para_graficos.sort_values(by="Tasa Agendamiento (%)", ascending=False).head(top_n_grafico)
                if not df_grafico_tasa.empty:
                    category_order_tasa = df_grafico_tasa[dimension_col].tolist()
                    fig_tasa = px.bar(
                        df_grafico_tasa, x="Tasa Agendamiento (%)", y=dimension_col, orientation='h',
                        title=f'Mejor Tasa (Top {len(df_grafico_tasa)})', color="Tasa Agendamiento (%)",
                        text="Tasa Agendamiento (%)", color_continuous_scale='Greens',
                        category_orders={dimension_col: category_order_tasa}
                    )
                    fig_tasa.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                    fig_tasa.update_layout(yaxis_title=None, title_x=0.5, margin=dict(l=0, r=0, t=30, b=0))
                    st.plotly_chart(fig_tasa, use_container_width=True)
                else:
                    st.caption(f"No hay {titulo_dimension.lower()} con suficiente volumen para el gráfico de tasas.")
        else:
            with col_graf_tasa: # Para mantener la estructura de columnas
                st.info("No se pudo calcular la tasa de agendamiento.")


    # --- TABLA PAGINADA COMPLETA (Condicional) ---
    if mostrar_tabla_completa:
     
        with st.expander(f"Ver Tabla Detallada Completa de {titulo_dimension} ({len(resumen_dimension_completo)} categorías)"):
            # Decide el ordenamiento para la tabla
            tabla_completa_ordenada = resumen_dimension_completo.sort_values(by="Total_Prospectados", ascending=False) # Ejemplo: Ordenar tabla por volumen
            # O si prefieres por tasa:
            # tabla_completa_ordenada = resumen_dimension_completo.sort_values(by="Tasa Agendamiento (%)", ascending=False)
            
            tabla_completa_ordenada.reset_index(drop=True, inplace=True)

            num_total_registros_tabla = len(tabla_completa_ordenada)
            
            opciones_por_pagina_tabla = [10, 25, 50, 100, num_total_registros_tabla]
            opciones_por_pagina_filtradas_tabla = [opt for opt in opciones_por_pagina_tabla if opt < num_total_registros_tabla]
            if num_total_registros_tabla not in opciones_por_pagina_filtradas_tabla :
                opciones_por_pagina_filtradas_tabla.append(num_total_registros_tabla)
            opciones_por_pagina_filtradas_tabla = sorted(list(set(opciones_por_pagina_filtradas_tabla)))
            
            key_registros_por_pagina_tabla = f"tabla_registros_por_pagina_{dimension_col}"
            key_pagina_actual_tabla = f"tabla_pagina_actual_{dimension_col}"

            if key_registros_por_pagina_tabla not in st.session_state:
                st.session_state[key_registros_por_pagina_tabla] = opciones_por_pagina_filtradas_tabla[0] if opciones_por_pagina_filtradas_tabla else 10
            if key_pagina_actual_tabla not in st.session_state:
                st.session_state[key_pagina_actual_tabla] = 1

            col_control_tabla1, col_control_tabla2 = st.columns([1, 3])

            with col_control_tabla1:
                default_rpp_tabla = st.session_state[key_registros_por_pagina_tabla]
                if default_rpp_tabla not in opciones_por_pagina_filtradas_tabla : 
                    default_rpp_tabla = opciones_por_pagina_filtradas_tabla[0] if opciones_por_pagina_filtradas_tabla else 10
                    st.session_state[key_registros_por_pagina_tabla] = default_rpp_tabla
                
                registros_por_pagina_tabla_sel = st.selectbox(
                    f"Registros por página (Tabla):",
                    options=opciones_por_pagina_filtradas_tabla,
                    index=opciones_por_pagina_filtradas_tabla.index(default_rpp_tabla),
                    key=f"sb_tabla_{key_registros_por_pagina_tabla}"
                )
                if registros_por_pagina_tabla_sel != st.session_state[key_registros_por_pagina_tabla]:
                    st.session_state[key_registros_por_pagina_tabla] = registros_por_pagina_tabla_sel
                    st.session_state[key_pagina_actual_tabla] = 1
                    st.rerun()

            registros_por_pagina_actual_tabla = st.session_state[key_registros_por_pagina_tabla]
            num_paginas_total_tabla = (num_total_registros_tabla + registros_por_pagina_actual_tabla - 1) // registros_por_pagina_actual_tabla if registros_por_pagina_actual_tabla > 0 else 1

            with col_control_tabla2:
                if num_paginas_total_tabla > 1:
                    st.session_state[key_pagina_actual_tabla] = st.number_input(
                        f"Página (Tabla - de 1 a {num_paginas_total_tabla}):",
                        min_value=1,
                        max_value=num_paginas_total_tabla,
                        value=min(st.session_state[key_pagina_actual_tabla], num_paginas_total_tabla),
                        step=1,
                        key=f"ni_tabla_{key_pagina_actual_tabla}"
                    )
                elif num_total_registros_tabla > 0:
                     st.markdown(f"Mostrando **{num_total_registros_tabla}** de **{num_total_registros_tabla}** {titulo_dimension.lower()} en la tabla.")

            pagina_seleccionada_tabla = st.session_state[key_pagina_actual_tabla]
            inicio_idx_tabla = (pagina_seleccionada_tabla - 1) * registros_por_pagina_actual_tabla
            fin_idx_tabla = inicio_idx_tabla + registros_por_pagina_actual_tabla
            df_pagina_tabla = tabla_completa_ordenada.iloc[inicio_idx_tabla:fin_idx_tabla]

            columnas_tabla_display = [dimension_col, "Total_Prospectados", "Sesiones_Agendadas", "Tasa Agendamiento (%)"]
            st.dataframe(
                df_pagina_tabla[columnas_tabla_display].style.format({"Tasa Agendamiento (%)": "{:.1f}%", "Total_Prospectados": "{:,}", "Sesiones_Agendadas": "{:,}"}),
                use_container_width=True
            )

            if num_paginas_total_tabla > 1:
                st.caption(f"Mostrando registros del {inicio_idx_tabla + 1} al {min(fin_idx_tabla, num_total_registros_tabla)} de un total de {num_total_registros_tabla} {titulo_dimension.lower()} en la tabla.")

