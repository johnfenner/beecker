# pages/📊_KPIs_Karla.py
import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
import datetime

# --- Configuración de la Página ---
st.set_page_config(
    page_title="KPIs Karla (USA)",
    page_icon="🇺🇸",
    layout="wide"
)

st.title("📊 Dashboard de KPIs - Karla (USA)")
st.markdown("Análisis de métricas semanales basado en la hoja **'United States - Karla' > pestaña 'Kpis'**.")

# --- Funciones de Carga y Limpieza ---

def parse_kpi_value(value):
    """Limpia y convierte valores numéricos de KPIs."""
    if pd.isna(value): return 0
    s_val = str(value).strip().lower()
    if s_val in ["", "nan", "none", "n/d"]: return 0
    # Eliminar posibles símbolos extraños
    try:
        return float(s_val)
    except ValueError:
        return 0

@st.cache_data(ttl=300)
def load_karla_data():
    """Carga los datos desde la hoja de Karla especificada en secrets."""
    try:
        creds = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds)
        
        sheet_url = st.secrets["karla_sheet_url"]
        workbook = client.open_by_url(sheet_url)
        
        # Intentamos cargar la pestaña "Kpis" (tal cual la imagen)
        sheet = workbook.worksheet("Kpis")
        
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error("La pestaña 'Kpis' parece estar vacía.")
            return pd.DataFrame()

        headers = [str(h).strip() for h in raw_data[0]]
        df = pd.DataFrame(raw_data[1:], columns=headers)
        
        return df

    except Exception as e:
        st.error(f"Error al cargar los datos de Karla: {e}")
        return pd.DataFrame()

def process_karla_df(df):
    """Procesa fechas y números."""
    if df.empty: return df
    
    # 1. Procesar Fecha
    if "Fecha" in df.columns:
        df["Fecha_Dt"] = pd.to_datetime(df["Fecha"], format="%d/%m/%Y", errors="coerce")
        # Eliminar filas sin fecha válida
        df.dropna(subset=["Fecha_Dt"], inplace=True)
        
        # Crear columnas derivadas
        df["Año"] = df["Fecha_Dt"].dt.year
        df["NumSemana"] = df["Fecha_Dt"].dt.isocalendar().week
        df["Mes_Año"] = df["Fecha_Dt"].dt.strftime("%Y-%m")
    else:
        st.error("No se encontró la columna 'Fecha'. Verifica la hoja.")
        return pd.DataFrame()

    # 2. Procesar Columnas Numéricas (KPIs)
    # Nombres exactos basados en tu imagen:
    # 'Mensajes Enviados', 'Respuestas', 'Invites enviadas', 'Sesiones agendadas'
    cols_numericas = ["Mensajes Enviados", "Respuestas", "Invites enviadas", "Sesiones agendadas"]
    
    for col in cols_numericas:
        if col in df.columns:
            df[col] = df[col].apply(parse_kpi_value)
        else:
            # Si no existe (ej. error de typo en el sheet), la creamos con 0
            df[col] = 0
            
    return df

def calculate_rate(num, den):
    return (num / den * 100) if den > 0 else 0

# --- Carga Principal ---
df_raw = load_karla_data()
df_kpis = process_karla_df(df_raw)

if df_kpis.empty:
    st.warning("No hay datos disponibles para mostrar.")
    st.stop()

# --- Filtros (Sidebar) ---
st.sidebar.header("🔍 Filtros Karla")

# Filtro de Fecha
min_date = df_kpis["Fecha_Dt"].min().date()
max_date = df_kpis["Fecha_Dt"].max().date()

start_date = st.sidebar.date_input("Desde", value=min_date, min_value=min_date, max_value=max_date, key="k_start")
end_date = st.sidebar.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date, key="k_end")

# Filtro de Año y Semana
all_years = sorted(df_kpis["Año"].unique(), reverse=True)
selected_year = st.sidebar.selectbox("Año", ["Todos"] + list(all_years), key="k_year")

# Lógica de filtrado
df_filtered = df_kpis.copy()

# 1. Filtro Rango Fechas
if start_date and end_date:
    df_filtered = df_filtered[
        (df_filtered["Fecha_Dt"].dt.date >= start_date) &
        (df_filtered["Fecha_Dt"].dt.date <= end_date)
    ]

# 2. Filtro Año
if selected_year != "Todos":
    df_filtered = df_filtered[df_filtered["Año"] == selected_year]


# --- Dashboard Visual ---

# 1. Métricas Totales (Sumas)
total_invites = df_filtered["Invites enviadas"].sum()
total_mensajes = df_filtered["Mensajes Enviados"].sum()
total_respuestas = df_filtered["Respuestas"].sum()
total_sesiones = df_filtered["Sesiones agendadas"].sum()

# 2. Tasas de Conversión
tasa_msj_inv = calculate_rate(total_mensajes, total_invites)
tasa_resp_msj = calculate_rate(total_respuestas, total_mensajes)
tasa_cita_resp = calculate_rate(total_sesiones, total_respuestas)
tasa_global = calculate_rate(total_sesiones, total_invites)

st.subheader("📈 Resumen de Rendimiento")

col1, col2, col3, col4 = st.columns(4)
col1.metric("📧 Invites Enviadas", f"{total_invites:,.0f}")
col2.metric("📤 Msj Enviados", f"{total_mensajes:,.0f}", f"{tasa_msj_inv:.1f}% de Inv.")
col3.metric("💬 Respuestas", f"{total_respuestas:,.0f}", f"{tasa_resp_msj:.1f}% de Msj")
col4.metric("🤝 Sesiones Agendadas", f"{total_sesiones:,.0f}", f"{tasa_cita_resp:.1f}% de Resp.")

# Métrica extra: Global
st.caption(f"**Tasa de Conversión Global (Sesiones / Invites): {tasa_global:.2f}%**")

st.markdown("---")

# 3. Gráficos de Evolución
st.subheader("📅 Evolución Temporal")

if not df_filtered.empty:
    # Agrupar por Semana para el gráfico
    # Creamos una columna ordenable Año-Semana
    df_filtered["Año-Semana"] = df_filtered["Año"].astype(str) + "-S" + df_filtered["NumSemana"].astype(str).str.zfill(2)
    
    df_grouped = df_filtered.groupby("Año-Semana")[["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]].sum().reset_index()
    df_grouped = df_grouped.sort_values("Año-Semana")

    tab_evol, tab_funnel = st.tabs(["📈 Tendencia Semanal", "🔻 Embudo del Periodo"])

    with tab_evol:
        # Gráfico de líneas
        fig_evol = px.line(
            df_grouped, 
            x="Año-Semana", 
            y=["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"],
            markers=True,
            title="Evolución de KPIs por Semana"
        )
        st.plotly_chart(fig_evol, use_container_width=True)

    with tab_funnel:
        # Gráfico de Embudo
        funnel_data = pd.DataFrame({
            "Etapa": ["Invites", "Mensajes", "Respuestas", "Sesiones"],
            "Valor": [total_invites, total_mensajes, total_respuestas, total_sesiones]
        })
        fig_funnel = px.funnel(funnel_data, x='Valor', y='Etapa', title="Embudo de Conversión Total")
        st.plotly_chart(fig_funnel, use_container_width=True)
else:
    st.info("No hay datos suficientes en el periodo seleccionado para graficar.")

st.markdown("---")

# 4. Tabla de Datos
with st.expander("📝 Ver Tabla de Datos Detallada"):
    # Formateamos la fecha para que se vea bonita
    df_display = df_filtered.copy()
    df_display["Fecha_Dt"] = df_display["Fecha_Dt"].dt.strftime("%d/%m/%Y")
    
    # Seleccionamos y ordenamos columnas clave
    cols_order = ["Fecha_Dt", "Mes", "Semana", "Analista", "Región", "Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    # Filtramos solo las que existen
    cols_final = [c for c in cols_order if c in df_display.columns]
    
    st.dataframe(df_display[cols_final], use_container_width=True)

