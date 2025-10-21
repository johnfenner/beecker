import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection

# --- Configuración de la Página ---
st.set_page_config(
    page_title="Dashboard de Prospección",
    page_icon="📊",
    layout="wide"
)

# --- Carga de Datos (con caché) ---
# Usamos st.cache_data para no recargar los datos de Google Sheets
# en cada interacción del usuario. Se actualiza cada 10 minutos (ttl=600).
@st.cache_data(ttl=600)
def load_data():
    # URL de la hoja de cálculo (tomada de secrets)
    SHEET_URL = st.secrets["connections"]["gsheets"]["spreadsheet"]
    
    # Nombre de la hoja
    WORKSHEET_NAME = "Prospects" 
    
    # Conectar y leer
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read(
        spreadsheet=SHEET_URL,
        worksheet=WORKSHEET_NAME,
        usecols=list(range(24)) # Basado en las 24 columnas que listaste
    )
    
    # --- Limpieza de Datos Esencial ---
    
    # 1. Convertir columnas de Falso/Verdadero (ej. 'TRUE', 'FALSE', '')
    # El sample usa 'TRUE' y 'FALSE' en mayúsculas, que deben ser convertidos a Booleanos.
    bool_cols = ['Contacted?', 'Responded?']
    for col in bool_cols:
        if col in df.columns:
            # Convierte 'TRUE' (string) a True (Bool), y cualquier otra cosa a False
            df[col] = df[col].apply(lambda x: True if str(x).strip().upper() == 'TRUE' else False)

    # 2. Limpiar columna 'Meeting?' (para contar 'Yes')
    if 'Meeting?' in df.columns:
        df['Meeting?'] = df['Meeting?'].apply(lambda x: 'Yes' if str(x).strip().upper() == 'YES' else 'No')

    # 3. Convertir columnas de fecha (el sample usa D/M/YYYY)
    date_cols = ['Lead Generated (Date)', 'First Contact Date', 'Next Follow-Up Date', 'Meeting Date']
    for col in date_cols:
        if col in df.columns:
            # 'dayfirst=True' le dice a pandas que interprete '2/10/2025' como 2 de Octubre
            df[col] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
            
    return df

# --- Cuerpo Principal de la App ---

st.title("📊 Dashboard de Métricas de Prospección")
st.markdown("Mostrando los KPIs más importantes del proceso de ventas.")

# Cargar los datos
try:
    df = load_data()

    if df.empty:
        st.error("No se pudieron cargar datos. Revisa la hoja 'Prospects' o la configuración.")
    else:
        # --- Cálculo de KPIs ---
        total_leads = len(df)
        total_contacted = df['Contacted?'].sum()
        total_responded = df['Responded?'].sum()
        total_meetings = df[df['Meeting?'] == 'Yes'].shape[0]

        # Tasas (con protección contra división por cero)
        contact_rate = (total_contacted / total_leads) * 100 if total_leads > 0 else 0
        response_rate = (total_responded / total_contacted) * 100 if total_contacted > 0 else 0
        meeting_rate = (total_meetings / total_responded) * 100 if total_responded > 0 else 0
        
        # Tasa de conversión general
        overall_conversion = (total_meetings / total_leads) * 100 if total_leads > 0 else 0

        # --- Mostrar KPIs (Métricas Principales) ---
        st.header("KPIs del Embudo de Ventas 📈")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(label="Total Leads (Prospectos)", value=total_leads)
        
        with col2:
            st.metric(label="Tasa de Contacto", value=f"{contact_rate:.1f}%",
                      help=f"{total_contacted} de {total_leads} leads han sido contactados.")
        
        with col3:
            st.metric(label="Tasa de Respuesta (s/ Contactados)", value=f"{response_rate:.1f}%",
                      help=f"{total_responded} respondieron de {total_contacted} contactados.")
            
        with col4:
            st.metric(label="Tasa de Reunión (s/ Respondidos)", value=f"{meeting_rate:.1f}%",
                      help=f"{total_meetings} reuniones de {total_responded} respuestas.")

        st.divider()

        # --- Visualizaciones (Gráficos) ---
        st.header("Análisis de Leads y Canales")
        
        viz1, viz2 = st.columns(2)

        with viz1:
            # 1. Gráfico: Canales de Respuesta
            st.subheader("Canales de Respuesta Más Efectivos")
            channel_data = df[df['Responded?'] == True]['Response Channel'].value_counts().reset_index()
            channel_data.columns = ['Canal', 'Cantidad']
            
            if not channel_data.empty:
                fig_pie = px.pie(channel_data, 
                                 names='Canal', 
                                 values='Cantidad', 
                                 title="Distribución de Respuestas por Canal")
                st.plotly_chart(fig_pie, use_container_width=True)
            else:
                st.info("Aún no hay datos de canales de respuesta.")

        with viz2:
            # 2. Gráfico: Industrias
            st.subheader("Leads por Industria")
            industry_data = df['Industry'].value_counts().reset_index()
            industry_data.columns = ['Industria', 'Cantidad']
            
            if not industry_data.empty:
                fig_bar = px.bar(industry_data, 
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
                st.info("No hay fechas válidas en 'Lead Generated (Date)'.")


        # --- Mostrar Datos Crudos (Opcional) ---
        st.divider()
        st.header("Datos Completos")
        st.dataframe(df)

except Exception as e:
    st.error(f"Ocurrió un error al cargar la aplicación: {e}")
    st.error("Por favor, verifica que la hoja de Google Sheets esté compartida con el email de la cuenta de servicio (service account) y que el nombre de la hoja ('Prospects') sea correcto.")

