# componentes/analisis_prospectadores.py
import streamlit as st
from utils.limpieza import limpiar_valor_kpi
import pandas as pd
import plotly.express as px

def mostrar_analisis_por_prospectador(df):
    """
    Muestra una tabla y gráficos de rendimiento agrupados por la columna '¿Quién Prospecto?'.
    Es una adaptación directa del análisis por Avatar.
    """
    st.markdown("---")
    st.markdown("### 👤 Análisis de Rendimiento por Prospectador")

    required_cols = [
        "¿Quién Prospecto?", "¿Invite Aceptada?", "Respuesta Primer Mensaje", "Sesion Agendada?"
    ]
    if not all(col in df.columns for col in required_cols):
        missing = [col for col in required_cols if col not in df.columns]
        st.warning(f"Faltan columnas necesarias para el análisis de Prospectador: {', '.join(missing)}.")
        return

    df_analisis = df.copy()
    
    # A diferencia del Avatar, no se necesita estandarización para '¿Quién Prospecto?'.

    resumen_prospectador = df_analisis.groupby("¿Quién Prospecto?").agg(
        Prospectados=("¿Quién Prospecto?", "count"),
        Invites_Aceptadas=("¿Invite Aceptada?", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum()),
        Respuestas_1er_Msj=("Respuesta Primer Mensaje", lambda col: (col.apply(lambda x: limpiar_valor_kpi(x) not in ["no", "", "nan"])).sum()),
        Sesiones_Agendadas=("Sesion Agendada?", lambda col: (col.apply(limpiar_valor_kpi) == "si").sum())
    ).reset_index()

    # Calcular Tasas Clave
    resumen_prospectador["Tasa Aceptación (%)"] = (resumen_prospectador["Invites_Aceptadas"] / resumen_prospectador["Prospectados"] * 100).round(1).fillna(0)
    resumen_prospectador["Tasa Respuesta (vs Acept.) (%)"] = (resumen_prospectador["Respuestas_1er_Msj"] / resumen_prospectador["Invites_Aceptadas"] * 100).round(1).fillna(0)
    resumen_prospectador["Tasa Sesiones (vs Resp.) (%)"] = (resumen_prospectador["Sesiones_Agendadas"] / resumen_prospectador["Respuestas_1er_Msj"] * 100).round(1).fillna(0)
    resumen_prospectador["Tasa Sesiones Global (vs Prosp.) (%)"] = (resumen_prospectador["Sesiones_Agendadas"] / resumen_prospectador["Prospectados"] * 100).round(1).fillna(0)

    resumen_prospectador.replace([float('inf'), -float('inf')], 0, inplace=True)

    if resumen_prospectador.empty:
        st.info("No hay datos de Prospectador para analizar con los filtros actuales.")
        return

    st.markdown("#### Tabla de Rendimiento por Prospectador:")
    st.dataframe(resumen_prospectador[[
        "¿Quién Prospecto?", "Prospectados", "Invites_Aceptadas", "Respuestas_1er_Msj", "Sesiones_Agendadas",
        "Tasa Aceptación (%)", "Tasa Respuesta (vs Acept.) (%)", "Tasa Sesiones (vs Resp.) (%)", "Tasa Sesiones Global (vs Prosp.) (%)"
    ]].style.format({
        "Tasa Aceptación (%)": "{:.1f}%",
        "Tasa Respuesta (vs Acept.) (%)": "{:.1f}%",
        "Tasa Sesiones (vs Resp.) (%)": "{:.1f}%",
        "Tasa Sesiones Global (vs Prosp.) (%)": "{:.1f}%"
    }), use_container_width=True)

    # Gráfico de Tasa de Sesiones Global
    if not resumen_prospectador[resumen_prospectador["Prospectados"] > 0].empty:
        fig_tasa_sesion_global = px.bar(
            resumen_prospectador[resumen_prospectador["Prospectados"] > 0].sort_values(by="Tasa Sesiones Global (vs Prosp.) (%)", ascending=False),
            x="¿Quién Prospecto?",
            y="Tasa Sesiones Global (vs Prosp.) (%)",
            title="Tasa de Agendamiento Global por Prospectador",
            color="Tasa Sesiones Global (vs Prosp.) (%)",
            text="Tasa Sesiones Global (vs Prosp.) (%)",
            color_continuous_scale=px.colors.sequential.Plasma # Un color diferente para distinguirlo
        )
        fig_tasa_sesion_global.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig_tasa_sesion_global.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig_tasa_sesion_global, use_container_width=True)
    else:
        st.info("No hay suficientes datos para graficar la 'Tasa de Sesiones Global' por Prospectador.")
