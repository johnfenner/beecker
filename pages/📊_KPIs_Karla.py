# pages/📊_KPIs_Karla.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import os
import sys

# --- Configuración Inicial ---
st.set_page_config(layout="wide", page_title="KPIs Karla (USA)")

st.title("📊 Dashboard de KPIs - Karla (USA)")
st.markdown("Análisis de métricas semanales basado en la hoja **'United States - Karla' > 'Kpis'**.")

# --- Funciones de Procesamiento (Reutilizadas de KPIs.py) ---
def parse_kpi_value(value_str, column_name=""):
    cleaned_val = str(value_str).strip().lower()
    if not cleaned_val: return 0.0
    try:
        num_val = pd.to_numeric(cleaned_val, errors='raise')
        return 0.0 if pd.isna(num_val) else float(num_val)
    except ValueError:
        pass
    
    if column_name == "Sesiones agendadas": 
        affirmative_session_texts = ['vc', 'si', 'sí', 'yes', 'true', '1', '1.0']
        if cleaned_val in affirmative_session_texts: return 1.0
        return 0.0
    else:
        first_part = cleaned_val.split('-')[0].strip()
        if not first_part: return 0.0
        try:
            num_val_from_part = pd.to_numeric(first_part, errors='raise')
            return 0.0 if pd.isna(num_val_from_part) else float(num_val_from_part)
        except ValueError:
            return 0.0

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

@st.cache_data(ttl=300)
def load_karla_kpis_data():
    try:
        creds_from_secrets = st.secrets["gcp_service_account"] 
        client = gspread.service_account_from_dict(creds_from_secrets)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        st.stop()

    # Usamos la URL específica de Karla definida en secrets
    sheet_url = st.secrets.get("karla_sheet_url")
    
    if not sheet_url:
        st.error("No se encontró 'karla_sheet_url' en los secrets.")
        st.stop()

    try:
        workbook = client.open_by_url(sheet_url)
        # Cargamos específicamente la pestaña "Kpis"
        sheet = workbook.worksheet("Kpis")
        raw_data = sheet.get_all_values()
        
        if not raw_data or len(raw_data) <= 1:
            st.error(f"La hoja 'Kpis' parece estar vacía.")
            return pd.DataFrame() 
            
        headers = raw_data[0]
        rows = raw_data[1:]
    except Exception as e:
        st.error(f"Error al leer la hoja de Karla: {e}")
        st.stop()

    cleaned_headers = [str(h).strip() for h in headers]
    df = pd.DataFrame(rows, columns=cleaned_headers)

    # Procesamiento de Fechas
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], format='%d/%m/%Y', errors='coerce')
        df.dropna(subset=["Fecha"], inplace=True)
        if not df.empty:
            df['Año'] = df['Fecha'].dt.year
            df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
            df['MesNum'] = df['Fecha'].dt.month
            df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')
    else:
        st.warning("Columna 'Fecha' no encontrada.")

    # Procesamiento de Columnas Numéricas (Misma estructura que KPIs general)
    kpi_columns_ordered = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    for col_name in kpi_columns_ordered:
        if col_name not in df.columns:
            # Si por alguna razón falta una columna, la creamos en 0 para no romper el código
            df[col_name] = 0
        else:
            df[col_name] = df[col_name].apply(lambda x: parse_kpi_value(x, column_name=col_name)).astype(int)

    # Limpieza de columnas de texto
    string_cols_kpis = ["Mes", "Semana", "Analista", "Región"]
    for col_str in string_cols_kpis:
        if col_str in df.columns:
            df[col_str] = df[col_str].astype(str).str.strip().fillna("N/D")
            
    return df

# --- Carga de Datos ---
df_raw = load_karla_kpis_data()

if df_raw.empty:
    st.stop()

# --- Filtros (Adaptado: Sin filtro de Analista) ---
st.sidebar.header("🔍 Filtros")

# 1. Filtro Fecha
min_date = df_raw["Fecha"].min().date() if "Fecha" in df_raw.columns and not df_raw["Fecha"].empty else None
max_date = df_raw["Fecha"].max().date() if "Fecha" in df_raw.columns and not df_raw["Fecha"].empty else None

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Desde", value=min_date, min_value=min_date, max_value=max_date)
end_date = col2.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date)

# 2. Filtro Año y Semana
st.sidebar.markdown("---")
year_opts = ["Todos"] + sorted([int(x) for x in df_raw["Año"].unique()]) if "Año" in df_raw.columns else ["Todos"]
sel_year = st.sidebar.selectbox("Año", year_opts)

# Lógica de Filtrado
df_filtered = df_raw.copy()

if start_date and end_date and "Fecha" in df_filtered.columns:
    df_filtered = df_filtered[
        (df_filtered["Fecha"].dt.date >= start_date) & 
        (df_filtered["Fecha"].dt.date <= end_date)
    ]

if sel_year != "Todos":
    df_filtered = df_filtered[df_filtered["Año"] == sel_year]

# --- Visualización (Componentes reutilizados y simplificados) ---

def display_kpi_summary(df):
    st.markdown("### 🧮 Resumen de KPIs Totales")
    
    kpi_cols = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    icons = ["📧", "📤", "💬", "🤝"]
    
    metrics = {col: df[col].sum() for col in kpi_cols if col in df.columns}
    
    # Fila 1: Absolutos
    cols = st.columns(4)
    for i, col in enumerate(kpi_cols):
        cols[i].metric(f"{icons[i]} {col}", f"{metrics.get(col, 0):,}")
        
    st.markdown("---")
    
    # Fila 2: Tasas
    invites = metrics.get("Invites enviadas", 0)
    mensajes = metrics.get("Mensajes Enviados", 0)
    respuestas = metrics.get("Respuestas", 0)
    sesiones = metrics.get("Sesiones agendadas", 0)
    
    tasa_msj = calculate_rate(mensajes, invites)
    tasa_resp = calculate_rate(respuestas, mensajes)
    tasa_cita = calculate_rate(sesiones, respuestas)
    tasa_global = calculate_rate(sesiones, invites)
    
    cols_tasas = st.columns(4)
    cols_tasas[0].metric("📨 Tasa Msj/Invite", f"{tasa_msj:.1f}%")
    cols_tasas[1].metric("📤 Tasa Resp/Msj", f"{tasa_resp:.1f}%")
    cols_tasas[2].metric("💬 Tasa Cita/Resp", f"{tasa_cita:.1f}%")
    cols_tasas[3].metric("🤝 Tasa Global (Cita/Inv)", f"{tasa_global:.1f}%")

def display_time_evolution(df, time_col, label, title):
    st.markdown(f"### 📈 {title}")
    
    kpis = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    present_kpis = [k for k in kpis if k in df.columns]
    
    if not present_kpis: return

    # Agrupación
    if time_col == "NumSemana":
        df_agg = df.groupby(["Año", "NumSemana"]).sum(numeric_only=True).reset_index()
        df_agg["Periodo"] = df_agg["Año"].astype(str) + "-S" + df_agg["NumSemana"].astype(str).str.zfill(2)
        df_agg = df_agg.sort_values(["Año", "NumSemana"])
    else:
        df_agg = df.groupby(time_col).sum(numeric_only=True).reset_index()
        df_agg["Periodo"] = df_agg[time_col]
        df_agg = df_agg.sort_values(time_col)
        
    fig = px.line(df_agg, x="Periodo", y=present_kpis, markers=True, title=title)
    st.plotly_chart(fig, use_container_width=True)

# --- Renderizado Principal ---

if not df_filtered.empty:
    display_kpi_summary(df_filtered)
    
    st.markdown("---")
    
    # Gráfico de Barras por Región (si hay datos de región distintos)
    if "Región" in df_filtered.columns and df_filtered["Región"].nunique() > 1:
        st.subheader("🌎 Desglose por Región")
        df_region = df_filtered.groupby("Región")[["Invites enviadas", "Sesiones agendadas"]].sum().reset_index()
        fig_reg = px.bar(df_region, x="Región", y=["Invites enviadas", "Sesiones agendadas"], barmode="group", text_auto=True)
        st.plotly_chart(fig_reg, use_container_width=True)
        st.markdown("---")

    display_time_evolution(df_filtered, "NumSemana", "Semana", "Evolución Semanal")
    st.markdown("---")
    display_time_evolution(df_filtered, "AñoMes", "Mes", "Evolución Mensual")
    
    st.markdown("---")
    with st.expander("📝 Ver Tabla de Datos Detallada"):
        cols_show = ["Fecha", "Mes", "Semana", "Región", "Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
        # Filtramos para mostrar solo las que existen
        cols_final = [c for c in cols_show if c in df_filtered.columns]
        
        # Formato de fecha para la tabla
        df_table = df_filtered.copy()
        if "Fecha" in df_table.columns:
            df_table["Fecha"] = df_table["Fecha"].dt.strftime('%d/%m/%Y')
            
        st.dataframe(df_table[cols_final], use_container_width=True)

else:
    st.info("No hay datos para mostrar con los filtros seleccionados.")
