import streamlit as st
import pandas as pd
import gspread # Mantener por si se vuelve a Hoja de Google
import datetime
import plotly.express as px
import plotly.graph_objects as go
from collections import Counter
import re

st.set_page_config(layout="wide", page_title="Pipeline de Prospección Detallado")
st.title("📈 Pipeline de Prospección Detallado (Oct 2025)")
st.markdown("Análisis avanzado del embudo, tiempos de conversión y segmentación.")

# --- Constantes ---
PIPELINE_SHEET_URL_KEY = "pipeline_october_2025"
DEFAULT_PIPELINE_URL = "https://docs.google.com/spreadsheets/d/..." # URL por defecto si no está en secrets
PIPELINE_SHEET_NAME = "Prospects" 

# Columnas Clave (asegúrate que los nombres coincidan EXACTAMENTE con tu hoja)
COL_LEAD_GEN_DATE = "Lead Generated (Date)"
COL_FIRST_CONTACT_DATE = "First Contact Date"
COL_MEETING_DATE = "Meeting Date"
COL_INDUSTRY = "Industry"
COL_MANAGEMENT = "Management Level"
COL_CHANNEL = "Response Channel"
COL_CONTACTED = "Contacted?" # ¿Se usa? First Contact Date podría ser mejor
COL_RESPONDED = "Responded?"
COL_MEETING = "Meeting?"

# Claves de Sesión (mantener las mismas para filtros)
SES_START_DATE_KEY = "pipeline_page_start_date_v1"
SES_END_DATE_KEY = "pipeline_page_end_date_v1"
SES_INDUSTRY_KEY = "pipeline_page_industry_v1"
SES_MANAGEMENT_KEY = "pipeline_page_management_v1"
SES_MEETING_KEY = "pipeline_page_meeting_v1"

# --- Funciones de Utilidad (sin cambios, excepto añadir parse_date) ---
def parse_date_robustly(date_val):
    if pd.isna(date_val) or str(date_val).strip() == "":
        return pd.NaT
    # Intentar con formatos comunes primero
    common_formats = ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d", "%d-%b-%Y", "%b %d, %Y"]
    for fmt in common_formats:
        try:
            return pd.to_datetime(date_val, format=fmt)
        except (ValueError, TypeError):
            pass
    # Intentar conversión genérica si los formatos comunes fallan
    try:
        return pd.to_datetime(date_val, errors='coerce')
    except Exception:
        return pd.NaT

def clean_yes_no(val):
    cleaned = str(val).strip().lower()
    if cleaned in ['yes', 'sí', 'si', '1', 'true', 'agendada', 'ok']: # Ampliar positivos
        return "Si"
    # Considerar vacíos y otros como 'No'
    if cleaned in ['no', '0', 'false', '', 'nan', 'na', '<na>', 'cancelada']:
        return "No"
    return "No" # Default a No

def calculate_rate(numerator, denominator, round_to=1):
    if denominator == 0 or pd.isna(denominator): return 0.0
    rate = (numerator / denominator) * 100
    return round(rate, round_to)

def calculate_time_diff(date1, date2):
    # Calcula diferencia en días solo si ambas fechas son válidas
    if pd.notna(date1) and pd.notna(date2) and date2 >= date1:
        return (date2 - date1).days
    return pd.NA # Devolver NA si no se puede calcular

# --- Carga y Procesamiento de Datos (MODIFICADO para más columnas y limpieza) ---
@st.cache_data(ttl=300)
def load_pipeline_data():
    sheet_url = st.secrets.get(PIPELINE_SHEET_URL_KEY, DEFAULT_PIPELINE_URL)
    
    try:
        # Intentar leer como Hoja de Google primero (si se convirtió)
        try:
            creds = st.secrets["gcp_service_account"]
            client = gspread.service_account_from_dict(creds)
            workbook = client.open_by_url(sheet_url)
            sheet = workbook.worksheet(PIPELINE_SHEET_NAME)
            raw_data = sheet.get_all_values()
            if not raw_data or len(raw_data) <= 1:
                raise ValueError("Hoja vacía o sin encabezados.")
            
            # Limpiar encabezados duplicados (copiado de tu código anterior)
            counts = Counter()
            headers = []
            for h in raw_data[0]:
                h_stripped = str(h).strip() if pd.notna(h) else "Columna_Vacia"
                if not h_stripped: h_stripped = "Columna_Vacia"
                counts[h_stripped] += 1
                if counts[h_stripped] == 1: headers.append(h_stripped)
                else: headers.append(f"{h_stripped}_{counts[h_stripped]-1}")
                
            df = pd.DataFrame(raw_data[1:], columns=headers)
            st.success(f"Datos cargados desde Google Sheet '{PIPELINE_SHEET_NAME}'.")

        except Exception as e_gspread:
            st.warning(f"Fallo al leer como Google Sheet ({e_gspread}). Intentando leer como Excel...")
            # Si falla como Hoja de Google, intentar como Excel
            file_id_match = re.search(r'/d/([a-zA-Z0-9_-]+)', sheet_url)
            if not file_id_match: raise ValueError("URL no parece ser de Google Drive.")
            file_id = file_id_match.group(1)
            download_url = f"https://drive.google.com/u/0/uc?id={file_id}&export=download&format=xlsx"
            
            df = pd.read_excel(download_url, sheet_name=PIPELINE_SHEET_NAME, engine="openpyxl")
            st.success(f"Datos cargados desde archivo Excel '{PIPELINE_SHEET_NAME}'.")

    except Exception as e:
        st.error(f"Error crítico al cargar datos desde '{sheet_url}': {e}")
        st.info("Verifica la URL, el nombre de la pestaña ('Prospects'), los permisos ('Cualquier persona con el enlace puede ver' si es Excel) y las credenciales si es Hoja de Google.")
        st.stop()

    # --- Procesamiento Post-Carga ---
    
    # 1. Parsear TODAS las fechas relevantes
    date_cols_to_parse = [COL_LEAD_GEN_DATE, COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]
    for col in date_cols_to_parse:
        if col in df.columns:
            df[col] = df[col].apply(parse_date_robustly)
        else:
            st.error(f"Columna de fecha esencial '{col}' NO encontrada. Verifica el nombre exacto.")
            # Podrías decidir parar st.stop() o continuar con datos parciales
            df[col] = pd.NaT # Crear columna vacía para evitar errores posteriores

    # Usar COL_LEAD_GEN_DATE como la fecha principal para filtros y tiempo
    df.rename(columns={COL_LEAD_GEN_DATE: 'Fecha_Principal'}, inplace=True)
    df.dropna(subset=['Fecha_Principal'], inplace=True) # Leads sin fecha de generación no son útiles aquí

    # 2. Limpiar columnas de estado (Sí/No)
    status_cols = [COL_CONTACTED, COL_RESPONDED, COL_MEETING] # Podrías quitar COL_CONTACTED si First Contact Date es más fiable
    for col in status_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_yes_no)
        else:
            st.warning(f"Columna de estado '{col}' no encontrada. Se asumirá 'No'.")
            df[col] = "No"
            
    # DERIVAR estado de 'Primer Contacto' si la fecha existe
    if COL_FIRST_CONTACT_DATE in df.columns:
        df['FirstContactStatus'] = df[COL_FIRST_CONTACT_DATE].apply(lambda x: 'Si' if pd.notna(x) else 'No')
    else:
        df['FirstContactStatus'] = 'No' # Si no hay columna de fecha, nadie fue contactado

    # 3. Limpiar columnas categóricas
    cat_cols = [COL_INDUSTRY, COL_MANAGEMENT, COL_CHANNEL]
    for col in cat_cols:
        if col in df.columns:
            df[col] = df[col].fillna('N/D')
            df[col] = df[col].astype(str).str.strip().replace('', 'N/D').str.title() # Poner en Title Case
            # Corregir casos comunes si es necesario, ej: "N/D" -> "No Definido"
            df[col] = df[col].replace({'N/D': 'No Definido'})
        else:
            df[col] = "No Definido"

    # 4. Crear columnas de tiempo para agrupar
    if not df.empty:
        df['Año'] = df['Fecha_Principal'].dt.year
        df['NumSemana'] = df['Fecha_Principal'].dt.isocalendar().week.astype('Int64', errors='ignore')
        df['AñoMes'] = df['Fecha_Principal'].dt.strftime('%Y-%m')
    else: # Crear columnas vacías si el df quedó vacío
        for col in ['Año', 'NumSemana', 'AñoMes']: df[col] = pd.NA

    # 5. Calcular diferencias de tiempo (¡NUEVO!)
    df['Dias_Gen_a_Contacto'] = df.apply(lambda row: calculate_time_diff(row['Fecha_Principal'], row[COL_FIRST_CONTACT_DATE]), axis=1)
    # Para calcular Contacto a Respuesta, necesitaríamos la fecha de respuesta. Usaremos Contacto a Reunión por ahora.
    df['Dias_Contacto_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row[COL_FIRST_CONTACT_DATE], row[COL_MEETING_DATE]), axis=1)
    df['Dias_Gen_a_Reunion'] = df.apply(lambda row: calculate_time_diff(row['Fecha_Principal'], row[COL_MEETING_DATE]), axis=1)
            
    return df

# --- Filtros de Barra Lateral (Sin cambios, ya son robustos) ---
def sidebar_filters_pipeline(df_options):
    st.sidebar.header("🔍 Filtros del Pipeline")
    
    default_filters = {
        SES_START_DATE_KEY: None, SES_END_DATE_KEY: None,
        SES_INDUSTRY_KEY: ["– Todos –"], SES_MANAGEMENT_KEY: ["– Todos –"],
        SES_MEETING_KEY: "– Todos –"
    }
    for key, val in default_filters.items():
        if key not in st.session_state:
            st.session_state[key] = val

    st.sidebar.subheader("🗓️ Por Fecha de Lead Generado")
    min_date, max_date = None, None
    if "Fecha_Principal" in df_options.columns and not df_options["Fecha_Principal"].dropna().empty:
        try: # Añadir try-except por si hay fechas inválidas residuales
            min_date = df_options["Fecha_Principal"].min().date()
            max_date = df_options["Fecha_Principal"].max().date()
        except:
            min_date, max_date = None, None # Resetear si hay error
    
    c1, c2 = st.sidebar.columns(2)
    c1.date_input("Desde", key=SES_START_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")
    c2.date_input("Hasta", key=SES_END_DATE_KEY, min_value=min_date, max_value=max_date, format="DD/MM/YYYY")

    st.sidebar.subheader("👥 Por Atributo de Lead")
    
    def create_multiselect(col_name, label, key):
        options = ["– Todos –"]
        if col_name in df_options.columns and not df_options[col_name].dropna().empty:
            # Usar .astype(str) para manejar posibles tipos mixtos antes de unique()
            unique_vals = sorted(df_options[col_name].astype(str).unique())
            # Asegurarse que 'No Definido' (nuevo valor limpio) esté al final si existe
            options.extend([val for val in unique_vals if val != "No Definido"])
            if "No Definido" in unique_vals:
                options.append("No Definido")
        st.sidebar.multiselect(label, options, key=key)

    create_multiselect(COL_INDUSTRY, "Industria", SES_INDUSTRY_KEY)
    create_multiselect(COL_MANAGEMENT, "Nivel de Management", SES_MANAGEMENT_KEY)

    st.sidebar.selectbox("¿Tiene Reunión?", ["– Todos –", "Si", "No"], key=SES_MEETING_KEY)

    def clear_pipeline_filters():
        for key, val in default_filters.items():
            st.session_state[key] = val
        st.toast("Filtros del Pipeline reiniciados ✅", icon="🧹")
        
    st.sidebar.button("🧹 Limpiar Filtros", on_click=clear_pipeline_filters, use_container_width=True)

    return (
        st.session_state[SES_START_DATE_KEY], st.session_state[SES_END_DATE_KEY],
        st.session_state[SES_INDUSTRY_KEY], st.session_state[SES_MANAGEMENT_KEY],
        st.session_state[SES_MEETING_KEY]
    )

# --- Aplicación de Filtros (Sin cambios, ya funciona bien) ---
def apply_pipeline_filters(df, start_dt, end_dt, industries, managements, meeting_status):
    df_f = df.copy()
    if df_f.empty: return df_f # Evitar errores si el df base ya estaba vacío

    # Filtro de Fecha
    if "Fecha_Principal" in df_f.columns and pd.api.types.is_datetime64_any_dtype(df_f['Fecha_Principal']):
        start_dt_date = pd.to_datetime(start_dt).normalize() if start_dt else None
        end_dt_date = pd.to_datetime(end_dt).normalize() if end_dt else None
        
        # Filtrar solo si las fechas son válidas
        if start_dt_date and end_dt_date:
            df_f = df_f[df_f['Fecha_Principal'].between(start_dt_date, end_dt_date, inclusive='both')]
        elif start_dt_date:
            df_f = df_f[df_f['Fecha_Principal'] >= start_dt_date]
        elif end_dt_date:
             df_f = df_f[df_f['Fecha_Principal'] <= end_dt_date]
    
    # Filtros Categóricos
    if industries and "– Todos –" not in industries:
        # Asegurarse que la columna existe antes de filtrar
        if COL_INDUSTRY in df_f.columns:
            df_f = df_f[df_f[COL_INDUSTRY].isin(industries)]
        
    if managements and "– Todos –" not in managements:
        if COL_MANAGEMENT in df_f.columns:
            df_f = df_f[df_f[COL_MANAGEMENT].isin(managements)]

    # Filtro de Estado
    if meeting_status != "– Todos –":
        if COL_MEETING in df_f.columns:
            df_f = df_f[df_f[COL_MEETING] == meeting_status]
            
    return df_f

# --- Componentes de Visualización (¡TODOS NUEVOS O MEJORADOS!) ---

def display_enhanced_funnel(df_filtered):
    st.markdown("###  funnel Embudo de Conversión Detallado")

    total_leads = len(df_filtered)
    # Usar el estado derivado de la fecha de primer contacto
    total_first_contact = len(df_filtered[df_filtered['FirstContactStatus'] == "Si"])
    total_responded = len(df_filtered[df_filtered[COL_RESPONDED] == "Si"])
    total_meetings = len(df_filtered[df_filtered[COL_MEETING] == "Si"])
    
    # Crear datos para el gráfico Plotly
    funnel_stages = ["Total Leads", "Primer Contacto", "Respondieron", "Reuniones"]
    funnel_values = [total_leads, total_first_contact, total_responded, total_meetings]

    fig = go.Figure(go.Funnel(
        y=funnel_stages,
        x=funnel_values,
        textposition="inside",
        textinfo="value+percent previous+percent initial", # Mostrar más info
        opacity=0.65,
        marker={"color": ["#8A2BE2", "#5A639C", "#7B8FA1", "#9BABB8"], # Colores violeta/azulados
               "line": {"width": [4, 2, 2, 1], "color": ["#6A1B9A", "#4A528A", "#6B7F91", "#8B9AAA"]}},
        connector={"line": {"color": "royalblue", "dash": "dot", "width": 3}}
        ))

    fig.update_layout(title="Embudo Detallado: Leads a Reuniones")
    st.plotly_chart(fig, use_container_width=True)

    # Mostrar Tasas de Conversión entre etapas
    st.markdown("#### Tasas de Conversión por Etapa")
    rate_lead_to_contact = calculate_rate(total_first_contact, total_leads)
    rate_contact_to_response = calculate_rate(total_responded, total_first_contact)
    rate_response_to_meeting = calculate_rate(total_meetings, total_responded)
    rate_global_lead_to_meeting = calculate_rate(total_meetings, total_leads)

    r1, r2, r3, r4 = st.columns(4)
    r1.metric("Lead -> Contacto", f"{rate_lead_to_contact:.1f}%", help="Primer Contacto / Total Leads")
    r2.metric("Contacto -> Respuesta", f"{rate_contact_to_response:.1f}%", help="Respondieron / Primer Contacto")
    r3.metric("Respuesta -> Reunión", f"{rate_response_to_meeting:.1f}%", help="Reuniones / Respondieron")
    r4.metric("Lead -> Reunión (Global)", f"{rate_global_lead_to_meeting:.1f}%", help="Reuniones / Total Leads")

def display_time_lag_analysis(df_filtered):
    st.markdown("---")
    st.markdown("### ⏱️ Tiempos Promedio del Ciclo")

    if df_filtered.empty:
        st.info("No hay datos suficientes para calcular los tiempos del ciclo.")
        return

    # Calcular promedios ignorando NA
    avg_gen_to_contact = df_filtered['Dias_Gen_a_Contacto'].mean()
    avg_contact_to_meeting = df_filtered['Dias_Contacto_a_Reunion'].mean()
    avg_gen_to_meeting = df_filtered['Dias_Gen_a_Reunion'].mean()

    # Contar cuántos tienen reunión para dar contexto
    count_meetings_for_time = len(df_filtered[df_filtered[COL_MEETING] == "Si"].dropna(subset=['Dias_Gen_a_Reunion']))

    t1, t2, t3 = st.columns(3)
    t1.metric("Lead Gen → 1er Contacto (días)",
              f"{avg_gen_to_contact:.1f}" if pd.notna(avg_gen_to_contact) else "N/A",
              help="Promedio de días desde la generación del lead hasta el primer contacto registrado.")
    t2.metric("1er Contacto → Reunión (días)",
              f"{avg_contact_to_meeting:.1f}" if pd.notna(avg_contact_to_meeting) else "N/A",
              help="Promedio de días desde el primer contacto hasta la reunión (para los que tuvieron reunión).")
    t3.metric("Lead Gen → Reunión (Total, días)",
              f"{avg_gen_to_meeting:.1f}" if pd.notna(avg_gen_to_meeting) else "N/A",
              help=f"Promedio de días desde la generación hasta la reunión (calculado sobre {count_meetings_for_time:,} reuniones con fechas válidas).")

    # Opcional: Mostrar distribución con histograma o boxplot si hay suficientes datos
    # fig_time_dist = px.histogram(df_filtered.dropna(subset=['Dias_Gen_a_Reunion']), x='Dias_Gen_a_Reunion', title="Distribución: Días de Lead a Reunión")
    # st.plotly_chart(fig_time_dist, use_container_width=True)

def display_segmentation_analysis(df_filtered):
    st.markdown("---")
    st.markdown("### 📊 Desempeño por Segmento (Industria y Nivel)")

    if df_filtered.empty:
        st.info("No hay datos para analizar por segmento.")
        return

    # Preparar función para reutilizar en Industria y Nivel
    def create_segment_chart(group_col, title_suffix):
        if group_col not in df_filtered.columns:
            st.caption(f"Columna '{group_col}' no encontrada para análisis.")
            return

        # Calcular totales y reuniones por segmento
        segment_summary = df_filtered.groupby(group_col).agg(
            Total_Leads=(group_col, 'count'),
            Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
        ).reset_index()

        # Calcular tasa de conversión global (Lead a Reunión) por segmento
        segment_summary['Tasa_Conversion_Global (%)'] = segment_summary.apply(
            lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Leads']), axis=1
        )

        # Filtrar segmentos con pocos leads para que las tasas sean más significativas
        segment_summary_filtered = segment_summary[segment_summary['Total_Leads'] >= 3].copy() # Umbral de 3 leads
        
        if segment_summary_filtered.empty:
             st.caption(f"No hay suficientes datos por '{group_col}' (mínimo 3 leads por grupo) para mostrar gráfico de tasas.")
             return

        segment_summary_filtered = segment_summary_filtered.sort_values('Tasa_Conversion_Global (%)', ascending=False)

        fig = px.bar(
            segment_summary_filtered.head(10), # Top 10 por tasa
            x=group_col,
            y='Tasa_Conversion_Global (%)',
            title=f"Top 10 {title_suffix} por Tasa de Conversión (Lead a Reunión)",
            text='Tasa_Conversion_Global (%)',
            color='Tasa_Conversion_Global (%)', # Colorear por la tasa
            color_continuous_scale=px.colors.sequential.YlGnBu # Escala de color
        )
        fig.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
        fig.update_layout(yaxis_title="Tasa de Conversión (%)", yaxis_ticksuffix="%")
        st.plotly_chart(fig, use_container_width=True)

        # Mostrar tabla con datos
        with st.expander(f"Ver datos detallados por {title_suffix}"):
            st.dataframe(
                segment_summary.sort_values('Total_Leads', ascending=False).style.format({
                    'Total_Leads': '{:,}',
                    'Total_Reuniones': '{:,}',
                    'Tasa_Conversion_Global (%)': '{:.1f}%'
                }),
                hide_index=True
            )

    # Crear gráficos para Industria y Nivel de Management
    col1, col2 = st.columns(2)
    with col1:
        create_segment_chart(COL_INDUSTRY, "Industrias")
    with col2:
        create_segment_chart(COL_MANAGEMENT, "Niveles de Management")


def display_channel_analysis(df_filtered):
    st.markdown("---")
    st.markdown(f"### 📣 Efectividad por Canal de Respuesta ({COL_CHANNEL})")

    if df_filtered.empty or COL_CHANNEL not in df_filtered.columns:
        st.info(f"No hay datos suficientes o falta la columna '{COL_CHANNEL}'.")
        return

    # Filtrar solo leads que respondieron para analizar el canal
    df_responded = df_filtered[df_filtered[COL_RESPONDED] == "Si"].copy()

    if df_responded.empty:
        st.info("No hay leads con respuesta registrada para analizar por canal.")
        return

    channel_summary = df_responded.groupby(COL_CHANNEL).agg(
        Total_Respuestas=(COL_CHANNEL, 'count'),
        Total_Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index()

    channel_summary['Tasa_Reunion_por_Respuesta (%)'] = channel_summary.apply(
        lambda row: calculate_rate(row['Total_Reuniones'], row['Total_Respuestas']), axis=1
    )

    channel_summary = channel_summary.sort_values('Total_Respuestas', ascending=False)

    # Gráfico de Volumen de Respuestas y Reuniones por Canal
    fig_volume = px.bar(
        channel_summary,
        x=COL_CHANNEL,
        y=['Total_Respuestas', 'Total_Reuniones'],
        title="Volumen de Respuestas y Reuniones por Canal",
        labels={"value": "Cantidad", "variable": "Métrica"},
        barmode='group', # Barras agrupadas
        text_auto=True
    )
    st.plotly_chart(fig_volume, use_container_width=True)

    # Gráfico de Tasa de Reunión por Canal (para los que respondieron)
    fig_rate = px.bar(
        channel_summary.sort_values('Tasa_Reunion_por_Respuesta (%)', ascending=False),
        x=COL_CHANNEL,
        y='Tasa_Reunion_por_Respuesta (%)',
        title="Tasa de Reunión por Canal (Reuniones / Respuestas)",
        text='Tasa_Reunion_por_Respuesta (%)',
        color='Tasa_Reunion_por_Respuesta (%)',
        color_continuous_scale=px.colors.sequential.Purples
    )
    fig_rate.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
    fig_rate.update_layout(yaxis_title="Tasa de Reunión (%)", yaxis_ticksuffix="%")
    st.plotly_chart(fig_rate, use_container_width=True)

    with st.expander("Ver datos detallados por Canal"):
        st.dataframe(
            channel_summary.style.format({
                'Total_Respuestas': '{:,}',
                'Total_Reuniones': '{:,}',
                'Tasa_Reunion_por_Respuesta (%)': '{:.1f}%'
            }),
            hide_index=True
        )

def display_enhanced_time_evolution(df_filtered):
    st.markdown("---")
    st.markdown("### 📈 Evolución Temporal Detallada (por Mes)")
    
    if df_filtered.empty or 'AñoMes' not in df_filtered.columns:
        st.info("No hay datos suficientes para mostrar la evolución temporal.")
        return

    # Agrupar por mes y contar leads, contactos, respuestas y reuniones
    time_summary = df_filtered.groupby('AñoMes').agg(
        Total_Leads=('AñoMes', 'count'),
        Primer_Contacto=( 'FirstContactStatus', lambda x: (x == 'Si').sum()),
        Respondieron=(COL_RESPONDED, lambda x: (x == 'Si').sum()),
        Reuniones=(COL_MEETING, lambda x: (x == 'Si').sum())
    ).reset_index().sort_values('AñoMes')
    
    if not time_summary.empty:
        # Usar melt para formato largo adecuado para plotly line chart con múltiples líneas
        time_summary_melted = time_summary.melt(
            id_vars=['AñoMes'],
            value_vars=['Total_Leads', 'Primer_Contacto', 'Respondieron', 'Reuniones'],
            var_name='Etapa',
            value_name='Cantidad'
        )
        
        fig = px.line(
            time_summary_melted,
            x='AñoMes',
            y='Cantidad',
            color='Etapa', # Una línea por cada etapa del embudo
            title="Evolución Mensual del Embudo",
            markers=True,
            labels={"Cantidad": "Número de Leads", "AñoMes": "Mes"}
        )
        # Ordenar leyenda
        fig.update_layout(legend_traceorder="reversed") 
        st.plotly_chart(fig, use_container_width=True)
        
        with st.expander("Ver datos de evolución mensual"):
            st.dataframe(time_summary.set_index('AñoMes'), use_container_width=True)
            
    else:
        st.caption("No hay datos agregados por mes.")


# --- Flujo Principal de la Página ---
df_pipeline_base = load_pipeline_data()

if df_pipeline_base.empty:
    st.error("Fallo crítico: El DataFrame del Pipeline está vacío tras la carga.")
    st.stop()

start_date, end_date, industries, managements, meeting_status = sidebar_filters_pipeline(df_pipeline_base.copy()) # Pasar copia para evitar modificar cache

df_pipeline_filtered = apply_pipeline_filters(
    df_pipeline_base, start_date, end_date, industries, managements, meeting_status
)

# --- Presentación del Dashboard Mejorado ---
if not df_pipeline_filtered.empty:
    
    display_enhanced_funnel(df_pipeline_filtered)
    
    display_time_lag_analysis(df_pipeline_filtered)
    
    display_segmentation_analysis(df_pipeline_filtered)
    
    display_channel_analysis(df_pipeline_filtered)

    display_enhanced_time_evolution(df_pipeline_filtered)

    # Tabla detallada (opcional, como antes)
    with st.expander("Ver tabla de datos detallados del pipeline (filtrada)"):
        cols_to_show = [
            "Full Name", "Company", "Role/Title", COL_INDUSTRY, COL_MANAGEMENT,
            'Fecha_Principal', # Usar la columna parseada
            COL_FIRST_CONTACT_DATE, COL_RESPONDED, COL_MEETING, COL_MEETING_DATE,
            COL_CHANNEL, "LinkedIn URL",
            # Columnas de tiempo calculado:
            'Dias_Gen_a_Contacto', 'Dias_Contacto_a_Reunion', 'Dias_Gen_a_Reunion'
        ]
        cols_exist = [col for col in cols_to_show if col in df_pipeline_filtered.columns]
        
        df_display = df_pipeline_filtered[cols_exist].copy()
        
        # Formatear fechas para display
        for date_col in ['Fecha_Principal', COL_FIRST_CONTACT_DATE, COL_MEETING_DATE]:
            if date_col in df_display.columns:
                 df_display[date_col] = df_display[date_col].dt.strftime('%Y-%m-%d').fillna('N/A')

        st.dataframe(df_display, hide_index=True)
else:
    st.info("No se encontraron datos que coincidan con los filtros seleccionados.")

