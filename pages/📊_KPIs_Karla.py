# pages/📊_KPIs_Karla.py
import streamlit as st
import pandas as pd
import gspread
import datetime
import plotly.express as px
import os
import sys

# --- Configuración Inicial del Proyecto y Título de la Página ---
st.set_page_config(layout="wide", page_title="KPIs Karla (USA)")

st.title("📊 Dashboard de KPIs - Karla (USA)") 
st.markdown(
    "Análisis de métricas absolutas y tasas de conversión (United States - Karla)." 
)

# --- Funciones de Procesamiento de Datos (Idénticas a KPIs Generales) ---
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

@st.cache_data(ttl=300)
def load_karla_data():
    try:
        creds_from_secrets = st.secrets["gcp_service_account"] 
        client = gspread.service_account_from_dict(creds_from_secrets)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        st.stop()

    # Usamos la variable karla_sheet_url que definiste en secrets
    sheet_url_kpis = st.secrets.get("karla_sheet_url")
    
    if not sheet_url_kpis:
        st.error("No se encontró la URL 'karla_sheet_url' en los secrets.")
        st.stop()

    try:
        # Carga la hoja específica "Kpis"
        sheet = client.open_by_url(sheet_url_kpis).worksheet("Kpis")
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos de la hoja 'Kpis'.")
            return pd.DataFrame() 
        headers = raw_data[0]
        rows = raw_data[1:]
    except Exception as e:
        st.error(f"Error al leer la hoja de Google Sheets: {e}")
        st.stop()

    cleaned_headers = [str(h).strip() for h in headers]
    df = pd.DataFrame(rows, columns=cleaned_headers)

    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], format='%d/%m/%Y', errors='coerce')
        df.dropna(subset=["Fecha"], inplace=True)
        if not df.empty:
            df['Año'] = df['Fecha'].dt.year
            df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
            df['MesNum'] = df['Fecha'].dt.month
            df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')
        else:
            for col_time in ['Año', 'NumSemana', 'MesNum']: df[col_time] = pd.Series(dtype='int')
            df['AñoMes'] = pd.Series(dtype='str')
    else:
        st.warning("Columna 'Fecha' no encontrada.")

    # MISMAS COLUMNAS QUE EN EL DASHBOARD GENERAL
    kpi_columns_ordered = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    for col_name in kpi_columns_ordered: 
        if col_name not in df.columns:
            # Si falta la columna, la creamos con 0 para no romper el código
            df[col_name] = 0
        else:
            df[col_name] = df[col_name].apply(lambda x: parse_kpi_value(x, column_name=col_name)).astype(int)

    string_cols_kpis = ["Mes", "Semana", "Región"] # Quitamos Analista de aquí porque es fijo
    for col_str in string_cols_kpis:
        if col_str in df.columns:
            df[col_str] = df[col_str].astype(str).str.strip().fillna("N/D")
            
    # Forzamos la columna Analista a "Karla" para consistencia visual si no viene
    df["Analista"] = "Karla Hernandez"
            
    return df

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

df_kpis_karla = load_karla_data()

if df_kpis_karla.empty:
    st.stop()

# --- FILTROS (Idénticos al original, menos Analista) ---

# Keys únicas para evitar conflicto con la otra página
START_DATE_KEY = "karla_start_date" 
END_DATE_KEY = "karla_end_date"
REGION_FILTER_KEY = "karla_region"
YEAR_FILTER_KEY = "karla_year" 
WEEK_FILTER_KEY = "karla_week" 

st.sidebar.header("🔍 Filtros")
st.sidebar.markdown("---")

# 1. Filtro Fecha
min_date = df_kpis_karla["Fecha"].min().date() if "Fecha" in df_kpis_karla.columns else None
max_date = df_kpis_karla["Fecha"].max().date() if "Fecha" in df_kpis_karla.columns else None

col1_date, col2_date = st.sidebar.columns(2)
start_date = col1_date.date_input("Desde", value=min_date, min_value=min_date, max_value=max_date, key=START_DATE_KEY)
end_date = col2_date.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date, key=END_DATE_KEY)

st.sidebar.markdown("---")

# 2. Filtro Año
year_options = ["– Todos –"] + sorted([str(y) for y in df_kpis_karla["Año"].unique() if pd.notna(y)], reverse=True)
sel_year_str = st.sidebar.selectbox("Año", year_options, key=YEAR_FILTER_KEY)
sel_year_int = int(sel_year_str) if sel_year_str != "– Todos –" else None

# 3. Filtro Semana
week_options = ["– Todas –"]
df_weeks = df_kpis_karla[df_kpis_karla["Año"] == sel_year_int] if sel_year_int else df_kpis_karla
if "NumSemana" in df_weeks.columns:
    week_options.extend([str(w) for w in sorted(df_weeks["NumSemana"].unique())])
    
sel_weeks = st.sidebar.multiselect("Semanas del Año", week_options, default=["– Todas –"], key=WEEK_FILTER_KEY)

st.sidebar.markdown("---")

# 4. Filtro Región (El único filtro categórico relevante aquí)
region_opts = ["– Todos –"]
if "Región" in df_kpis_karla.columns:
    region_opts.extend(sorted(df_kpis_karla["Región"].unique()))
sel_region = st.sidebar.multiselect("Región", region_opts, default=["– Todos –"], key=REGION_FILTER_KEY)

# --- Aplicar Filtros ---
df_filtered = df_kpis_karla.copy()

# Fecha
if start_date and end_date and "Fecha" in df_filtered.columns:
    df_filtered = df_filtered[
        (df_filtered["Fecha"].dt.date >= start_date) & 
        (df_filtered["Fecha"].dt.date <= end_date)
    ]

# Año
if sel_year_int:
    df_filtered = df_filtered[df_filtered["Año"] == sel_year_int]

# Semana
if "– Todas –" not in sel_weeks and "NumSemana" in df_filtered.columns:
    weeks_int = [int(w) for w in sel_weeks if w.isdigit()]
    df_filtered = df_filtered[df_filtered["NumSemana"].isin(weeks_int)]

# Región
if "– Todos –" not in sel_region and "Región" in df_filtered.columns:
    df_filtered = df_filtered[df_filtered["Región"].isin(sel_region)]


# --- VISUALIZACIÓN (Misma estructura que KPIs.py) ---

# 1. Resumen de KPIs Totales
st.markdown("### 🧮 Resumen de KPIs Totales")

kpi_cols = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
icons = ["📧", "📤", "💬", "🤝"]

metrics = {col: df_filtered[col].sum() for col in kpi_cols if col in df_filtered.columns}

# Fila Absolutos
cols_abs = st.columns(4)
for i, col in enumerate(kpi_cols):
    # Ajuste de nombre para visualización limpia
    label = col
    if col == "Invites enviadas": label = "Invites Enviadas"
    elif col == "Sesiones agendadas": label = "Sesiones Agendadas"
    
    cols_abs[i].metric(f"{icons[i]} Total {label}", f"{metrics.get(col, 0):,}")

st.markdown("---")
st.markdown("#### Tasas de Conversión")

# Cálculo de Tasas (Funnel)
invites = metrics.get("Invites enviadas", 0)
mensajes = metrics.get("Mensajes Enviados", 0)
respuestas = metrics.get("Respuestas", 0)
sesiones = metrics.get("Sesiones agendadas", 0)

tasa_msj = calculate_rate(mensajes, invites)
tasa_resp = calculate_rate(respuestas, mensajes)
tasa_cita = calculate_rate(sesiones, respuestas)
tasa_global = calculate_rate(sesiones, invites)

cols_tasas = st.columns(4)
rate_icons = ["📨➡️📤", "📤➡️💬", "💬➡️🤝", "📧➡️🤝"]

cols_tasas[0].metric(f"{rate_icons[0]} Tasa Mensajes / Invite", f"{tasa_msj:.1f}%")
cols_tasas[1].metric(f"{rate_icons[1]} Tasa Respuesta / Mensaje", f"{tasa_resp:.1f}%")
cols_tasas[2].metric(f"{rate_icons[2]} Tasa Agend. / Respuesta", f"{tasa_cita:.1f}%")
cols_tasas[3].metric(f"{rate_icons[3]} Tasa Agend. / Invite (Global)", f"{tasa_global:.1f}%")

st.markdown("---")

# 2. Desgloses y Gráficos
col_break1, col_break2 = st.columns(2)

with col_break1:
    # Desglose por Región
    st.markdown("### 🌎 Desglose por Región")
    if "Región" in df_filtered.columns and not df_filtered.empty:
        # Tabla simple
        df_reg = df_filtered.groupby("Región")[kpi_cols].sum().reset_index()
        st.dataframe(df_reg, use_container_width=True, hide_index=True)
        
        # Gráfico
        if df_reg["Sesiones agendadas"].sum() > 0:
            fig = px.bar(df_reg, x="Región", y="Sesiones agendadas", title="Sesiones por Región", text_auto=True)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sin datos de región.")

with col_break2:
    # Evolución Semanal
    st.markdown("### 🗓️ Evolución Semanal")
    if "NumSemana" in df_filtered.columns and not df_filtered.empty:
        df_time = df_filtered.groupby(["Año", "NumSemana"])[kpi_cols].sum().reset_index()
        df_time["Periodo"] = df_time["Año"].astype(str) + "-S" + df_time["NumSemana"].astype(str).str.zfill(2)
        df_time = df_time.sort_values(["Año", "NumSemana"])
        
        fig_time = px.line(df_time, x="Periodo", y="Sesiones agendadas", markers=True, title="Sesiones Agendadas por Semana")
        st.plotly_chart(fig_time, use_container_width=True)
    else:
        st.info("Sin datos para evolución semanal.")

st.markdown("---")

# 3. Tabla Detallada (Igual que en la página principal)
with st.expander("📝 Datos Detallados Filtrados (Vista General)", expanded=True):
    cols_display = ["Fecha", "Mes", "Semana", "Región", "Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    cols_final = [c for c in cols_display if c in df_filtered.columns]
    
    df_show = df_filtered[cols_final].copy()
    if "Fecha" in df_show.columns:
        df_show["Fecha"] = df_show["Fecha"].dt.strftime('%d/%m/%Y')
        
    st.dataframe(df_show, use_container_width=True)
