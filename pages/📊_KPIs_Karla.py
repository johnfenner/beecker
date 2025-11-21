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
st.markdown("Análisis detallado de métricas y embudo de conversión United States - Karla.")

# --- Gestión de Estado ---
DETAILED_VIEW_WEEKS_KEY = "karla_detailed_view_weeks_v2"
if DETAILED_VIEW_WEEKS_KEY not in st.session_state:
    st.session_state[DETAILED_VIEW_WEEKS_KEY] = []

# --- Funciones de Procesamiento (VALIDACIÓN ORIGINAL) ---
def parse_kpi_value(value_str, column_name=""):
    """
    Limpia valores asegurando que si no hay dato se tome como 0.
    Misma lógica que en el archivo original de KPIs.
    """
    cleaned_val = str(value_str).strip().lower()
    if not cleaned_val: return 0.0
    try:
        num_val = pd.to_numeric(cleaned_val, errors='raise')
        return 0.0 if pd.isna(num_val) else float(num_val)
    except ValueError:
        pass
    
    # Lógica específica para columnas booleanas o texto mixto
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
    """Calcula tasa de conversión manejando división por cero."""
    if denominator == 0: return 0.0
    return round((numerator / denominator) * 100, round_to)

@st.cache_data(ttl=300)
def load_karla_data():
    try:
        creds_from_secrets = st.secrets["gcp_service_account"] 
        client = gspread.service_account_from_dict(creds_from_secrets)
    except Exception as e:
        st.error(f"Error de credenciales: {e}")
        st.stop()

    sheet_url = st.secrets.get("karla_sheet_url")
    if not sheet_url:
        st.error("Falta 'karla_sheet_url' en secrets.")
        st.stop()

    try:
        sheet = client.open_by_url(sheet_url).worksheet("Kpis")
        raw_data = sheet.get_all_values()
        if len(raw_data) <= 1:
            return pd.DataFrame() 
        headers = raw_data[0]
        rows = raw_data[1:]
        df = pd.DataFrame(rows, columns=[str(h).strip() for h in headers])
    except Exception as e:
        st.error(f"Error leyendo hoja Karla: {e}")
        st.stop()

    # Procesar Fecha
    if "Fecha" in df.columns:
        df["Fecha"] = pd.to_datetime(df["Fecha"], format='%d/%m/%Y', errors='coerce')
        df.dropna(subset=["Fecha"], inplace=True)
        if not df.empty:
            df['Año'] = df['Fecha'].dt.year
            df['NumSemana'] = df['Fecha'].dt.isocalendar().week.astype(int)
            df['MesNum'] = df['Fecha'].dt.month
            df['AñoMes'] = df['Fecha'].dt.strftime('%Y-%m')
    else:
        st.warning("Falta columna 'Fecha'.")

    # Procesar Columnas Numéricas con la validación original
    kpi_columns_ordered = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    for col_name in kpi_columns_ordered:
        if col_name not in df.columns:
            df[col_name] = 0
        else:
            df[col_name] = df[col_name].apply(lambda x: parse_kpi_value(x, column_name=col_name)).astype(int)

    # Limpieza Textos
    for col in ["Mes", "Semana"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip().replace('', 'N/D')
    
    # Forzar Analista
    df["Analista"] = "Karla Hernandez"

    return df

# --- Carga ---
df_raw = load_karla_data()
if df_raw.empty: st.stop()

# --- Sidebar Filtros ---
st.sidebar.header("🔍 Filtros Karla")
min_date = df_raw["Fecha"].min().date() if "Fecha" in df_raw.columns else None
max_date = df_raw["Fecha"].max().date() if "Fecha" in df_raw.columns else None

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Desde", value=min_date, min_value=min_date, max_value=max_date, key="k_start")
end_date = col2.date_input("Hasta", value=max_date, min_value=min_date, max_value=max_date, key="k_end")

st.sidebar.markdown("---")
year_opts = ["Todos"] + sorted([int(x) for x in df_raw["Año"].unique() if pd.notna(x)], reverse=True)
sel_year = st.sidebar.selectbox("Año", year_opts, key="k_year")

week_opts = ["Todas"]
df_year = df_raw[df_raw["Año"] == sel_year] if sel_year != "Todos" else df_raw
if "NumSemana" in df_year.columns:
    week_opts.extend(sorted(df_year["NumSemana"].unique()))
sel_weeks = st.sidebar.multiselect("Semanas", week_opts, default=["Todas"], key="k_weeks")

# --- Aplicar Filtros ---
df_filtered = df_raw.copy()

if start_date and end_date and "Fecha" in df_filtered.columns:
    df_filtered = df_filtered[(df_filtered["Fecha"].dt.date >= start_date) & (df_filtered["Fecha"].dt.date <= end_date)]

if sel_year != "Todos":
    df_filtered = df_filtered[df_filtered["Año"] == sel_year]

if "Todas" not in sel_weeks:
    df_filtered = df_filtered[df_filtered["NumSemana"].isin(sel_weeks)]

# --- DASHBOARD ---

# 1. Resumen KPIs
st.markdown("### 🧮 Resumen de KPIs Totales (Periodo Filtrado)")
kpi_cols = ["Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
icons = ["📧", "📤", "💬", "🤝"]
metrics = {c: df_filtered[c].sum() for c in kpi_cols}

c1, c2, c3, c4 = st.columns(4)
for i, col in enumerate(kpi_cols):
    c = [c1, c2, c3, c4][i]
    c.metric(f"{icons[i]} {col}", f"{metrics[col]:,}")

st.markdown("---")
# Tasas Totales
t_msj = calculate_rate(metrics["Mensajes Enviados"], metrics["Invites enviadas"])
t_resp = calculate_rate(metrics["Respuestas"], metrics["Mensajes Enviados"])
t_cita = calculate_rate(metrics["Sesiones agendadas"], metrics["Respuestas"])
t_glob = calculate_rate(metrics["Sesiones agendadas"], metrics["Invites enviadas"])

ct1, ct2, ct3, ct4 = st.columns(4)
ct1.metric("📨 Tasa Mens./Invite", f"{t_msj:.1f}%")
ct2.metric("📤 Tasa Resp./Msj", f"{t_resp:.1f}%")
ct3.metric("💬 Tasa Agend./Resp.", f"{t_cita:.1f}%")
ct4.metric("🤝 Tasa Global (Agend./Inv.)", f"{t_glob:.1f}%")

st.markdown("---")

# 2. Tabla General
with st.expander("📝 Datos Detallados Filtrados (Vista General)", expanded=True):
    cols_show = ["Fecha", "Mes", "Semana", "Invites enviadas", "Mensajes Enviados", "Respuestas", "Sesiones agendadas"]
    cols_final = [c for c in cols_show if c in df_filtered.columns]
    
    df_show = df_filtered.copy()
    if "Fecha" in df_show.columns: df_show["Fecha"] = df_show["Fecha"].dt.strftime('%d/%m/%Y')
    st.dataframe(df_show[cols_final], use_container_width=True, height=250)

st.markdown("---")

# 3. CONTROL DE VISTA DETALLADA SEMANAL (CORREGIDO EL ERROR Y NOMENCLATURA IGUAL AL ORIGINAL)
st.markdown("### 🔬 Control de Vista Detallada Semanal")
st.caption("Selecciona semanas específicas para ver el embudo completo y todas las tasas de conversión intermedias.")

if not df_filtered.empty:
    unique_weeks = df_filtered[['Año', 'NumSemana']].drop_duplicates().sort_values(['Año', 'NumSemana'], ascending=False)
    week_labels = [f"{r['Año']}-S{str(r['NumSemana']).zfill(2)}" for _, r in unique_weeks.iterrows()]
    
    selected_weeks_view = st.multiselect(
        "Selecciona las semanas para ver en detalle:",
        options=week_labels,
        key=DETAILED_VIEW_WEEKS_KEY
    )

    if selected_weeks_view:
        df_filtered['WeekLabel'] = df_filtered['Año'].astype(str) + "-S" + df_filtered['NumSemana'].astype(str).str.zfill(2)
        df_detail = df_filtered[df_filtered['WeekLabel'].isin(selected_weeks_view)].copy()
        
        # Agrupar
        df_weekly_agg = df_detail.groupby(['WeekLabel', 'Analista'])[kpi_cols].sum().reset_index()
        
        # Nombres exactos del original para las columnas calculadas
        df_weekly_agg['1. Invites enviadas'] = df_weekly_agg['Invites enviadas']
        df_weekly_agg['2. Mensajes Enviados'] = df_weekly_agg['Mensajes Enviados']
        df_weekly_agg['% Mens. / Invite'] = df_weekly_agg.apply(lambda x: calculate_rate(x['Mensajes Enviados'], x['Invites enviadas']), axis=1)
        df_weekly_agg['3. Respuestas'] = df_weekly_agg['Respuestas']
        df_weekly_agg['% Resp. / Mensaje'] = df_weekly_agg.apply(lambda x: calculate_rate(x['Respuestas'], x['Mensajes Enviados']), axis=1)
        df_weekly_agg['4. Sesiones agendadas'] = df_weekly_agg['Sesiones agendadas']
        df_weekly_agg['% Agend. / Respuesta'] = df_weekly_agg.apply(lambda x: calculate_rate(x['Sesiones agendadas'], x['Respuestas']), axis=1)
        df_weekly_agg['% Agend. / Invite (Global)'] = df_weekly_agg.apply(lambda x: calculate_rate(x['Sesiones agendadas'], x['Invites enviadas']), axis=1)
        
        for week in selected_weeks_view:
            st.markdown(f"#### {week}")
            week_data = df_weekly_agg[df_weekly_agg['WeekLabel'] == week].copy()
            
            if not week_data.empty:
                final_cols = [
                    'Analista', 
                    '1. Invites enviadas', '2. Mensajes Enviados', '% Mens. / Invite',
                    '3. Respuestas', '% Resp. / Mensaje',
                    '4. Sesiones agendadas', '% Agend. / Respuesta', '% Agend. / Invite (Global)'
                ]
                
                # --- CORRECCIÓN DEL ERROR (Cálculo con escalares) ---
                t_invites = week_data['1. Invites enviadas'].sum()
                t_mensajes = week_data['2. Mensajes Enviados'].sum()
                t_respuestas = week_data['3. Respuestas'].sum()
                t_sesiones = week_data['4. Sesiones agendadas'].sum()

                r_mens_inv = calculate_rate(t_mensajes, t_invites, round_to=2)
                r_resp_msj = calculate_rate(t_respuestas, t_mensajes, round_to=2)
                r_cita_resp = calculate_rate(t_sesiones, t_respuestas, round_to=2)
                r_global = calculate_rate(t_sesiones, t_invites, round_to=2)

                total_row = pd.DataFrame([{
                    'Analista': 'Total Semana',
                    '1. Invites enviadas': t_invites,
                    '2. Mensajes Enviados': t_mensajes,
                    '% Mens. / Invite': r_mens_inv,
                    '3. Respuestas': t_respuestas,
                    '% Resp. / Mensaje': r_resp_msj,
                    '4. Sesiones agendadas': t_sesiones,
                    '% Agend. / Respuesta': r_cita_resp,
                    '% Agend. / Invite (Global)': r_global
                }])
                
                display_table = pd.concat([week_data[final_cols], total_row[final_cols]], ignore_index=True)
                
                # Formato visual %
                pct_cols = ['% Mens. / Invite', '% Resp. / Mensaje', '% Agend. / Respuesta', '% Agend. / Invite (Global)']
                for c in pct_cols: 
                    display_table[c] = pd.to_numeric(display_table[c], errors='coerce').fillna(0)
                    display_table[c] = display_table[c].apply(lambda x: f"{x:.2f}%")
                
                st.dataframe(display_table.set_index('Analista'), use_container_width=True)
            else:
                st.info(f"Sin datos para {week}")
    else:
        st.info("👆 Selecciona semanas arriba para ver el desglose detallado.")

st.markdown("---")

# 4. Evolución Temporal
st.markdown("### 📈 Evolución Temporal de KPIs")
if not df_filtered.empty:
    tab_w, tab_m = st.tabs(["Semanas", "Meses"])
    
    with tab_w:
        df_w = df_filtered.groupby(["Año", "NumSemana"])[kpi_cols].sum().reset_index()
        df_w["Semana"] = df_w["Año"].astype(str) + "-S" + df_w["NumSemana"].astype(str).str.zfill(2)
        df_w = df_w.sort_values(["Año", "NumSemana"])
        fig_w = px.line(df_w, x="Semana", y=kpi_cols, markers=True, title="Evolución Semanal")
        st.plotly_chart(fig_w, use_container_width=True)
        
    with tab_m:
        df_m = df_filtered.groupby("AñoMes")[kpi_cols].sum().reset_index().sort_values("AñoMes")
        fig_m = px.line(df_m, x="AñoMes", y=kpi_cols, markers=True, title="Evolución Mensual")
        st.plotly_chart(fig_m, use_container_width=True)
