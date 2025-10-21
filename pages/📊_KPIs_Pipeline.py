import streamlit as st
import pandas as pd
import gspread  # Usando gspread, como en tu ejemplo
import plotly.express as px
import datetime

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Dashboard de Prospección (Pipeline)",
    page_icon="📊",
    layout="wide"
)

# --- Carga de Datos (Método gspread) ---
@st.cache_data(ttl=600) # Cache de 10 minutos
def load_data():
    
    # Define el nombre de la hoja ANTES del try para evitar UnboundLocalError
    WORKSHEET_NAME = "Prospects" 
    
    # 1. Autenticar (Exactamente como en tu archivo _KPIs_SDR.py)
    try:
        creds_from_secrets = st.secrets["gcp_service_account"]
        client = gspread.service_account_from_dict(creds_from_secrets)
    except KeyError:
        st.error("Error de Configuración: Falta [gcp_service_account] en los 'Secrets'.")
        st.stop()
    except Exception as e:
        st.error(f"Error al autenticar con Google (gcp_service_account): {e}")
        st.stop()

    # 2. Abrir la hoja de Prospects
    try:
        # Lee la URL de la nueva hoja desde el secret que acabamos de agregar
        sheet_url = st.secrets["prospects_sheet_url"]
        
        workbook = client.open_by_url(sheet_url)
        sheet = workbook.worksheet(WORKSHEET_NAME)
    
        # 3. Obtener datos y convertir a DataFrame
        raw_data = sheet.get_all_values()
        if not raw_data or len(raw_data) <= 1:
            st.error(f"No se pudieron obtener datos de la hoja '{WORKSHEET_NAME}'.")
            return pd.DataFrame()
            
        headers = raw_data[0]
        rows = raw_data[1:]
        
        # Filtra filas vacías
        cleaned_rows = [row for row in rows if any(cell.strip() for cell in row)]
        
        # Asegurar que todas las filas tengan la misma longitud que los encabezados
        num_cols = len(headers)
        cleaned_rows_padded = []
        for row in cleaned_rows:
            row_len = len(row)
            if row_len < num_cols:
                row.extend([''] * (num_cols - row_len)) # Añade celdas vacías si falta
            cleaned_rows_padded.append(row[:num_cols]) # Recorta si sobra

        df = pd.DataFrame(cleaned_rows_padded, columns=headers)

    except KeyError:
        st.error(f"Error de Configuración: No se encontró 'prospects_sheet_url' en tus secrets. Por favor, añádelo a .streamlit/secrets.toml")
        st.stop()
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Error: No se encontró la hoja de cálculo llamada '{WORKSHEET_NAME}' en el Google Sheet.")
        st.stop()
    except Exception as e:
        st.error(f"Error al leer la hoja '{WORKSHEET_NAME}': {e}")
        st.stop()

    # --- Limpieza de Datos Esencial (Basado en tus columnas) ---
    
    # 1. Convertir columnas de Falso/Verdadero (ej. 'TRUE', 'FALSE', '')
    # Tus datos de ejemplo usan 'TRUE' y 'FALSE' en mayúsculas
    bool_cols = ['Contacted?', 'Responded?']
    for col in bool_cols:
        if col in df.columns:
            # Convierte 'TRUE' (string) a True (Bool), y cualquier otra cosa (vacío, 'FALSE', etc.) a False
            df[col] = df[col].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)

    # 2. Limpiar columna 'Meeting?' (para contar 'Yes')
    if 'Meeting?' in df.columns:
        df['Meeting?'] = df['Meeting?'].apply(lambda x: 'Yes' if str(x).strip().upper() == 'YES' else 'No')

    # 3. Convertir columnas de fecha (tus datos usan D/M/YYYY)
    date_cols = ['Lead Generated (Date)', 'First Contact Date', 'Next Follow-Up Date', 'Meeting Date']
    for col in date_cols:
        if col in df.columns:
            # 'dayfirst=True' interpreta '2/10/2025' como 2 de Octubre
            # 'coerce' convierte errores (ej. celdas vacías) en NaT (Not a Time)
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            
    return df

# --- Cuerpo Principal de la App ---

st.title("📊 Dashboard de Métricas de Prospección (Pipeline)")
st.markdown("Mostrando los KPIs más importantes del embudo de ventas.")

# Cargar los datos
try:
    df = load_data()

    if df.empty:
        st.warning("No se pudieron cargar datos o la hoja está vacía. Revisa la hoja 'Prospects' o la configuración.")
        st.stop()

    # --- Cálculo de KPIs ---
    total_leads = len(df)
    total_contacted = df['Contacted?'].sum()
    total_responded = df['Responded?'].sum()
    # Contamos solo las filas donde la columna 'Meeting?' es 'Yes'
    total_meetings = df[df['Meeting?'] == 'Yes'].shape[0]

    # Tasas (con protección contra división por cero)
    contact_rate = (total_contacted / total_leads) * 100 if total_leads > 0 else 0
    # Tasa de respuesta sobre los contactados
    response_rate = (total_responded / total_contacted) * 100 if total_contacted > 0 else 0
    # Tasa de reunión sobre los que respondieron
    meeting_rate = (total_meetings / total_responded) * 100 if total_responded > 0 else 0
    
    # Tasa de conversión general (Reuniones / Leads Totales)
    overall_conversion = (total_meetings / total_leads) * 100 if total_leads > 0 else 0

    # --- Mostrar KPIs (Métricas Principales) ---
    st.header("KPIs del Embudo de Ventas 📈")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="Total Leads (Prospectos)", value=f"{total_leads:,.0f}")
    
    with col2:
        st.metric(label="Tasa de Contacto", value=f"{contact_rate:.1f}%",
                    help=f"{total_contacted:,.0f} de {total_leads:,.0f} leads han sido contactados.")
    
    with col3:
        st.metric(label="Tasa de Respuesta (s/ Contactados)", value=f"{response_rate:.1f}%",
                    help=f"{total_responded:,.0f} respondieron de {total_contacted:,.0f} contactados.")
        
    with col4:
        st.metric(label="Tasa de Reunión (s/ Respondidos)", value=f"{meeting_rate:.1f}%",
                    help=f"{total_meetings:,.0f} reuniones de {total_responded:,.0f} respuestas.")

    st.divider()

    # --- Visualizaciones (Gráficos) ---
    st.header("Análisis de Leads y Canales")
    
    viz1, viz2 = st.columns(2)

    with viz1:
        # 1. Gráfico: Canales de Respuesta
        st.subheader("Canales de Respuesta Más Efectivos")
        # Filtramos por los que SÍ respondieron y contamos los canales
        channel_data = df[df['Responded?'] == True]['Response Channel'].value_counts().reset_index()
        channel_data.columns = ['Canal', 'Cantidad']
        
        if not channel_data.empty:
            fig_pie = px.pie(channel_data, 
                                names='Canal', 
                                values='Cantidad', 
                                title="Distribución de Respuestas por Canal")
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Aún no hay datos de canales de respuesta.")

    with viz2:
        # 2. Gráfico: Industrias
        st.subheader("Leads por Industria")
        # Reemplaza valores vacíos o nulos en 'Industry' con 'N/D' antes de contar
        industry_counts = df['Industry'].fillna('N/D').replace('', 'N/D').value_counts().reset_index()
        industry_counts.columns = ['Industria', 'Cantidad']
        
        if not industry_counts.empty:
            fig_bar = px.bar(industry_counts.head(15), # Muestra top 15
                                x='Industria', 
                                y='Cantidad', 
                                title="Volumen de Leads por Industria")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("No hay datos de industria.")

    # 3. Gráfico: Leads generados a lo largo del tiempo
    if 'Lead Generated (Date)' in df.columns:
        st.subheader("Leads Generados por Día")
        df_time = df.dropna(subset=['Lead Generated (Date)'])
        
        if not df_time.empty:
            # Agrupar por día
            leads_over_time = df_time.set_index('Lead Generated (Date)').resample('D').size().reset_index(name='Nuevos Leads')
            
            fig_line = px.line(leads_over_time, 
                                x='Lead Generated (Date)', 
                                y='Nuevos Leads', 
                                title='Tendencia de Generación de Leads')
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("No hay fechas válidas en 'Lead Generated (Date)' para mostrar la tendencia.")


    # --- Mostrar Datos Crudos (Opcional) ---
    st.divider()
    with st.expander("Ver Tabla de Datos Completa"):
        st.dataframe(df)

except Exception as e:
    st.error(f"Ocurrió un error inesperado en la aplicación: {e}")
    st.exception(e) # Muestra el traceback completo para debugging
