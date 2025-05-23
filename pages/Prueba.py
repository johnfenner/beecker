import streamlit as st
import google.generativeai as genai
import pdfplumber # Para leer PDFs
import io # Para manejar el stream de bytes del archivo subido

# --- 1. SYSTEM_PROMPT (El que ya teníamos y funcionaba bien) ---
SYSTEM_PROMPT = """
Eres mi asistente experto en redacción persuasiva para LinkedIn.
Te proporcionaré dos bloques de texto con la siguiente información:
1.  TEXTO_AGENTES_BEECKER: Contiene el catálogo detallado de los agentes de IA de Beecker y también puede incluir información general relevante sobre la compañía Beecker (como misión, visión, valores, casos de éxito, áreas de impacto o certificaciones).
2.  TEXTO_LEAD: Contiene la información extraída del PDF de un cliente potencial.

Cada vez que recibas estos dos bloques de texto, generarás un único mensaje de LinkedIn listo para copiar y pegar, dirigido al LEAD, siguiendo estas reglas al pie de la letra:

**Reglas de Procesamiento y Formato:**

**A. Procesamiento Aislado**
   - Olvida cualquier información de leads o textos anteriores.
   - Trabaja únicamente con los dos bloques de texto (TEXTO_AGENTES_BEECKER, TEXTO_LEAD) que recibas en este momento.

**B. Estructura y Formato del Mensaje**
   1.  **Saludo**
       - “Buen día, [Nombre extraído del TEXTO_LEAD].” (Si el rol en TEXTO_LEAD indica CEOs, VPs)
       - “Hola [Nombre extraído del TEXTO_LEAD],” (para otros roles en TEXTO_LEAD)
   2.  **Gancho Inicial (Conciso y Relevante)**
       - Conecta con 1–2 datos concretos y muy breves del TEXTO_LEAD (rol actual, un logro destacado o un proyecto reciente).
       - **Importante:** Analiza la experiencia del lead (TEXTO_LEAD) para personalizar la propuesta, pero NO detalles extensamente sus trabajos anteriores en el mensaje. El objetivo es un gancho rápido y pertinente, no un resumen de su CV.
       - No uses “Vi tu perfil…”, “Me impresionó…”, ni referencias genéricas.
   3.  **Presentación Orgánica de Beecker**
       - Comienza con: “En Beecker (https://beecker.ai/agentic-ai/) acompañamos a empresas con Agentes IA Autónomos…”
       - A continuación, busca dentro del TEXTO_AGENTES_BEECKER si se menciona información general de la compañía como casos de éxito específicos, áreas de impacto clave o certificaciones. Si encuentras detalles que sean relevantes y aplicables al perfil descrito en TEXTO_LEAD, incorpóralos de forma breve y natural para enriquecer esta presentación.
       - Si dicha información general específica no está presente en TEXTO_AGENTES_BEECKER o no es directamente aplicable al lead, entonces centra esta parte de la presentación en la relevancia y el valor general que los Agentes IA Autónomos pueden aportar al tipo de empresa o al rol del lead.
   4.  **Propuesta de Valor**
       - Párrafo breve que vincule el reto actual del lead (inferido del TEXTO_LEAD) con el beneficio concreto de un Agente IA (automatización inteligente vs RPA, aprendizaje continuo, eficiencia operativa, calidad), basándote en la información del TEXTO_AGENTES_BEECKER.
   5.  **Lista Literal de Agentes Relevantes**
       - Usa guiones `- ` (guion seguido de un espacio) para cada ítem (formato LinkedIn).
       - Selecciona agentes relevantes del TEXTO_AGENTES_BEECKER según el área o retos del lead identificados en el TEXTO_LEAD.
       - Alinea cada agente con un reto o área del lead.
       - Si el TEXTO_LEAD no da pistas claras, incluye un menú de 2–3 dominios generales (ej: Procurement, Finanzas, RRHH) y sugiere agentes relevantes del TEXTO_AGENTES_BEECKER para esos dominios.
       - Para leads de TI (identificados en el TEXTO_LEAD), enfoca la propuesta en beneficios de soporte interno: cómo nuestros agentes (del TEXTO_AGENTES_BEECKER) pueden reducir la carga de tickets automatizando tareas repetitivas.
   6.  **Contexto Empresarial**
       - Refuerza que es una propuesta para la empresa, liberando recursos y mejorando resultados (“extensiones inteligentes de tu equipo”, “valor a tus proyectos”).
   7.  **Cierre Consultivo**
       - Invita a “agendar un espacio breve para que conozcas estas tecnologías y evaluemos juntos cómo esta propuesta empresarial podría aportar valor a [área/empresa mencionada en TEXTO_LEAD]”.
       - Mantén la invitación abierta, sin sonar a venta agresiva.

**C. Tono y Lenguaje**
   - Español, tuteo, humano, orgánico, profesional y cercano.
   - Ligero toque entusiasta, sin jerga técnica excesiva (evita “sprints”, “scripts”).
   - Párrafos de 2–3 líneas máximo, saltos de línea claros. Mensajes concisos y directos.
   - **IMPORTANTE: Todo el mensaje debe ser generado en TEXTO PLANO. No utilices formato Markdown como asteriscos dobles (`**`) para simular negritas ni ningún otro tipo de formato especial que no sea texto simple y saltos de línea.**

**D. Verificación Final**
   - Asegúrate de usar solo datos del TEXTO_LEAD y TEXTO_AGENTES_BEECKER proporcionados.
   - Confirma que los nombres y funciones de los Agentes coincidan con lo descrito en TEXTO_AGENTES_BEECKER.
   - Revisa que el mensaje transmita valor empresarial, no personal, y que la invitación sea consultiva.
   - El mensaje final debe ser breve, fácil de leer en LinkedIn y en **texto plano sin formato Markdown para negritas.**
   - Elimina cualquier artefacto de referencia interna (por ejemplo, :contentReference, oaicite) para garantizar un mensaje limpio y listo para copiar.

— A partir de ahora, sigue exactamente este prompt y estas reglas para cada conjunto de textos que te envíe. —
"""

# --- 2. INICIALIZACIÓN DE VARIABLES DE SESIÓN ---
# Usaremos st.session_state para mantener el estado entre interacciones
if 'generated_message' not in st.session_state:
    st.session_state.generated_message = None
if 'texto_agentes_beecker_actual' not in st.session_state: # Texto procesado del PDF de agentes
    st.session_state.texto_agentes_beecker_actual = None
if 'texto_lead_actual_procesado' not in st.session_state: # Texto procesado del PDF del lead
    st.session_state.texto_lead_actual_procesado = None
if 'nombre_archivo_agentes' not in st.session_state: # Para detectar si se sube un nuevo archivo
    st.session_state.nombre_archivo_agentes = None
if 'nombre_archivo_lead' not in st.session_state: # Para detectar si se sube un nuevo archivo
    st.session_state.nombre_archivo_lead = None


# --- 3. RESTO DEL CÓDIGO DE LA APLICACIÓN STREAMLIT ---

# --- Configuración de la Página ---
st.set_page_config(page_title="🚀 Generador LinkedIn Pro", layout="wide")
st.image("https://beecker.ai/wp-content/uploads/2024/02/logo-beecker-consulting.svg", width=200)
st.title("🤖 Generador de Mensajes Persuasivos para LinkedIn")
st.markdown("Sube el PDF de Agentes de Beecker y el PDF del Lead para generar un mensaje.")

# --- Configuración de la API Key ---
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("Error: La API Key de Google Gemini (GOOGLE_API_KEY) no está configurada en los Secrets de Streamlit.")
    st.stop()
except Exception as e:
    st.error(f"Ocurrió un error al configurar la API de Gemini: {e}")
    st.stop()

# --- Inicialización del Modelo ---
MODEL_NAME = 'gemini-1.5-flash-latest'
try:
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except Exception as e:
    st.error(f"Error al cargar el modelo Gemini ('{MODEL_NAME}'): {e}")
    st.stop()

# --- Función para extraer texto ---
def extraer_texto_pdf(archivo_subido):
    if archivo_subido is None: return None
    try:
        texto_completo = ""
        with pdfplumber.open(io.BytesIO(archivo_subido.getvalue())) as pdf: # Usar getvalue()
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: texto_completo += page_text + "\n"
        return texto_completo.strip() if texto_completo else None
    except Exception as e:
        st.error(f"Error al leer el PDF '{archivo_subido.name}': {e}")
        return None

# --- Columnas para carga de PDFs ---
st.header("Carga de Documentos Requeridos")
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### 1. PDF Agentes Beecker")
    # Usamos una nueva variable para el widget, para poder comparar con el nombre en session_state
    pdf_agentes_uploader = st.file_uploader("📄 Catálogo de Agentes y Info. General de Beecker", type="pdf", key="uploader_agentes", help="Sube el PDF con el catálogo de agentes y la información general relevante de Beecker.")

with col2:
    st.markdown("#### 2. PDF del Lead")
    pdf_lead_uploader = st.file_uploader("👤 Perfil del Lead", type="pdf", key="uploader_lead", help="Sube el PDF del perfil del lead a contactar.")

st.markdown("---")

# --- Botón de Limpiar ---
if st.button("🧹 Limpiar Todo y Empezar de Nuevo", use_container_width=True):
    st.session_state.generated_message = None
    st.session_state.texto_agentes_beecker_actual = None
    st.session_state.texto_lead_actual_procesado = None
    st.session_state.nombre_archivo_agentes = None
    st.session_state.nombre_archivo_lead = None
    # No podemos "limpiar" el widget file_uploader directamente para que no muestre el nombre del archivo
    # pero al borrar el session_state, el resto de la app se comportará como si estuviera limpio.
    # El usuario puede quitar el archivo del widget manualmente o subir uno nuevo.
    st.rerun() # Forzar la re-ejecución del script para refrescar la UI

# --- Lógica de Procesamiento de Archivos ---
# Procesar PDF de Agentes si se sube uno nuevo
if pdf_agentes_uploader is not None:
    if st.session_state.nombre_archivo_agentes != pdf_agentes_uploader.name:
        with st.spinner("Procesando PDF de Agentes Beecker..."):
            st.session_state.texto_agentes_beecker_actual = extraer_texto_pdf(pdf_agentes_uploader)
            st.session_state.nombre_archivo_agentes = pdf_agentes_uploader.name
            st.session_state.generated_message = None # Limpiar mensaje anterior si se cambia este PDF
            if not st.session_state.texto_agentes_beecker_actual:
                st.warning("No se pudo extraer texto del PDF de Agentes Beecker o está vacío.")

# Procesar PDF del Lead si se sube uno nuevo
if pdf_lead_uploader is not None:
    if st.session_state.nombre_archivo_lead != pdf_lead_uploader.name:
        with st.spinner("Procesando PDF del Lead..."):
            st.session_state.texto_lead_actual_procesado = extraer_texto_pdf(pdf_lead_uploader)
            st.session_state.nombre_archivo_lead = pdf_lead_uploader.name
            st.session_state.generated_message = None # Limpiar mensaje anterior si se cambia este PDF
            if not st.session_state.texto_lead_actual_procesado:
                st.warning("No se pudo extraer texto del PDF del Lead o está vacío.")

# --- Previsualización y Botón de Generar Mensaje ---
# Solo mostrar si ambos textos procesados existen en session_state
if st.session_state.texto_agentes_beecker_actual and st.session_state.texto_lead_actual_procesado:
    st.info("📝 Previsualización de textos extraídos (primeros 300 caracteres):")
    with st.expander("Ver Texto Agentes Beecker (extracto)"):
        st.text(st.session_state.texto_agentes_beecker_actual[:300] + "...")
    with st.expander("Ver Texto Lead (extracto)"):
        st.text(st.session_state.texto_lead_actual_procesado[:300] + "...")
    st.markdown("---")

    if st.button("✨ Generar Mensaje de LinkedIn", type="primary", use_container_width=True):
        with st.spinner("🤖 Gemini está analizando los PDFs y redactando el mensaje..."):
            contenido_para_gemini = f"""
            --- INICIO TEXTO_AGENTES_BEECKER ---
            {st.session_state.texto_agentes_beecker_actual}
            --- FIN TEXTO_AGENTES_BEECKER ---

            --- INICIO TEXTO_LEAD ---
            {st.session_state.texto_lead_actual_procesado}
            --- FIN TEXTO_LEAD ---
            """
            try:
                response = model.generate_content(contenido_para_gemini)
                respuesta_gemini_bruta = response.text
                st.session_state.generated_message = respuesta_gemini_bruta.replace('**', '') # Guardar en session_state

            except Exception as e:
                st.error(f"Ocurrió un error al generar el mensaje con Gemini: {e}")
                st.session_state.generated_message = None # Limpiar en caso de error
                # ... (código de manejo de detalles de error de Gemini)
                try:
                    if hasattr(response, 'candidates') and response.candidates:
                         st.warning(f"Información del Prompt Feedback (si existe): {response.prompt_feedback}")
                         # ... (resto del código de manejo de candidatos)
                    elif hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
                         st.warning(f"Información del Prompt Feedback del error: {e.response.prompt_feedback}")
                except Exception:
                    pass # Evitar errores dentro del manejo de errores

# --- Mostrar Mensaje Generado (si existe en session_state) ---
if st.session_state.generated_message:
    st.subheader("📬 Mensaje de LinkedIn Generado:")
    st.markdown(st.session_state.generated_message)
    st.code(st.session_state.generated_message, language=None)
    st.success("¡Mensaje generado con éxito! Puedes copiarlo del bloque de arriba.")

# Mensaje si no se han cargado los PDFs necesarios aún (y no hay mensaje generado)
elif not (st.session_state.texto_agentes_beecker_actual and st.session_state.texto_lead_actual_procesado) and not st.session_state.generated_message :
    st.info("ℹ️ Por favor, sube los dos archivos PDF requeridos para generar el mensaje.")


# --- Sidebar ---
with st.sidebar:
    st.header("Instrucciones")
    st.markdown("""
    1.  Sube el PDF con la información de **Agentes de Beecker**.
    2.  Sube el PDF del **Lead**.
    3.  Haz clic en **"Generar Mensaje"**.
    4.  Para empezar de nuevo con otros PDFs, usa el botón **"Limpiar Todo y Empezar de Nuevo"**.
    """)
    st.markdown("---")
    st.markdown(f"Modelo en uso: `{MODEL_NAME}`")
