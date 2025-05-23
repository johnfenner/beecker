import streamlit as st
import google.generativeai as genai
import pdfplumber # Para leer PDFs
import io # Para manejar el stream de bytes del archivo subido

# --- 1. SYSTEM_PROMPT ACTUALIZADO (COPIAR EL DE ARRIBA AQUÍ) ---
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
       - Si el TEXTO_AGENTES_BEECKER contiene información general de la compañía (casos de éxito, áreas de impacto), destaca un aspecto brevemente relevante para el TEXTO_LEAD. Si no, céntrate en la conexión con los agentes.
   4.  **Propuesta de Valor**
       - Párrafo breve que vincule el reto actual del lead (inferido del TEXTO_LEAD) con el beneficio concreto de un Agente IA (automatización inteligente vs RPA, aprendizaje continuo, eficiencia operativa, calidad), basándote en la información del TEXTO_AGENTES_BEECKER.
   5.  **Lista Literal de Agentes Relevantes**
       - Usa guiones `-` para cada ítem (formato LinkedIn).
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

**D. Verificación Final**
   - Asegúrate de usar solo datos del TEXTO_LEAD y TEXTO_AGENTES_BEECKER proporcionados.
   - Confirma que los nombres y funciones de los Agentes coincidan con lo descrito en TEXTO_AGENTES_BEECKER.
   - Revisa que el mensaje transmita valor empresarial, no personal, y que la invitación sea consultiva.
   - El mensaje final debe ser breve y fácil de leer en LinkedIn.
   - Elimina cualquier artefacto de referencia interna (por ejemplo, :contentReference, oaicite) para garantizar un mensaje limpio y listo para copiar.

— A partir de ahora, sigue exactamente este prompt y estas reglas para cada conjunto de textos que te envíe. —
"""

# --- 2. RESTO DEL CÓDIGO DE LA APLICACIÓN STREAMLIT ---

# --- Configuración de la Página de Streamlit ---
st.set_page_config(page_title="🚀 Generador LinkedIn Pro", layout="wide")
st.image("https://beecker.ai/wp-content/uploads/2024/02/logo-beecker-consulting.svg", width=200) # Opcional: logo de Beecker
st.title("🤖 Generador de Mensajes para LinkedIn")
st.markdown("Sube el PDF de Agentes de Beecker y el PDF del Lead para generar un mensaje.")

# --- Configuración de la API Key de Gemini (desde Streamlit Secrets) ---
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("Error: La API Key de Google Gemini (GOOGLE_API_KEY) no está configurada en los Secrets de Streamlit.")
    st.stop()
except Exception as e:
    st.error(f"Ocurrió un error al configurar la API de Gemini: {e}")
    st.stop()

# --- Inicialización del Modelo con el System Prompt ---
MODEL_NAME = 'gemini-1.5-flash-latest'
try:
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except Exception as e:
    st.error(f"Error al cargar el modelo Gemini ('{MODEL_NAME}'): {e}")
    st.stop()

# --- Función para extraer texto de un PDF subido ---
def extraer_texto_pdf(archivo_subido):
    if archivo_subido is None:
        return None
    try:
        texto_completo = ""
        with pdfplumber.open(io.BytesIO(archivo_subido.read())) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    texto_completo += page_text + "\n"
        return texto_completo.strip() if texto_completo else None
    except Exception as e:
        st.error(f"Error al leer el PDF '{archivo_subido.name}': {e}")
        return None

# --- Columnas para la carga de PDFs ---
st.header("Carga de Documentos Requeridos")
col1, col2 = st.columns(2) # Ahora solo dos columnas

with col1:
    st.markdown("#### 1. PDF Agentes Beecker")
    pdf_agentes_beecker = st.file_uploader("📄 Catálogo de Agentes y Info. General de Beecker", type="pdf", key="agentes", help="Sube el PDF con el catálogo de agentes y la información general relevante de Beecker.")

with col2:
    st.markdown("#### 2. PDF del Lead")
    pdf_lead = st.file_uploader("👤 Perfil del Lead", type="pdf", key="lead", help="Sube el PDF del perfil del lead a contactar.")

st.markdown("---")

# --- Procesamiento y Generación del Mensaje ---
if pdf_agentes_beecker and pdf_lead:
    texto_agentes_beecker = extraer_texto_pdf(pdf_agentes_beecker)
    texto_lead_actual = extraer_texto_pdf(pdf_lead)

    valid_inputs = True
    if not texto_agentes_beecker:
        st.warning("⚠️ No se pudo extraer texto del PDF de Agentes Beecker o está vacío.")
        valid_inputs = False
    if not texto_lead_actual:
        st.warning("⚠️ No se pudo extraer texto del PDF del Lead o está vacío.")
        valid_inputs = False

    if valid_inputs:
        st.info("📝 Previsualización de textos extraídos (primeros 300 caracteres):")
        with st.expander("Ver Texto Agentes Beecker (extracto)"):
            st.text(texto_agentes_beecker[:300] + "..." if texto_agentes_beecker else "No se extrajo texto.")
        with st.expander("Ver Texto Lead (extracto)"):
            st.text(texto_lead_actual[:300] + "..." if texto_lead_actual else "No se extrajo texto.")
        st.markdown("---")

        if st.button("✨ Generar Mensaje de LinkedIn", type="primary", use_container_width=True):
            with st.spinner("🤖 Gemini está analizando los PDFs y redactando el mensaje..."):
                contenido_para_gemini = f"""
                --- INICIO TEXTO_AGENTES_BEECKER ---
                {texto_agentes_beecker}
                --- FIN TEXTO_AGENTES_BEECKER ---

                --- INICIO TEXTO_LEAD ---
                {texto_lead_actual}
                --- FIN TEXTO_LEAD ---
                """
                try:
                    response = model.generate_content(contenido_para_gemini)
                    respuesta_gemini = response.text

                    st.subheader("📬 Mensaje de LinkedIn Generado:")
                    st.markdown(respuesta_gemini)
                    st.text_area("Para copiar fácilmente:", respuesta_gemini, height=200)
                    st.success("¡Mensaje generado con éxito!")

                except Exception as e:
                    st.error(f"Ocurrió un error al generar el mensaje con Gemini: {e}")
                    try:
                        if hasattr(response, 'candidates') and response.candidates:
                             st.warning(f"Información del Prompt Feedback (si existe): {response.prompt_feedback}")
                             for candidate_idx, candidate in enumerate(response.candidates):
                                 st.caption(f"Candidato {candidate_idx+1} - Razón de finalización: {candidate.finish_reason}")
                                 if candidate.finish_message:
                                     st.caption(f"Candidato {candidate_idx+1} - Mensaje de finalización: {candidate.finish_message}")
                        elif hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
                             st.warning(f"Información del Prompt Feedback del error: {e.response.prompt_feedback}")
                    except Exception as inner_e:
                        st.warning(f"No se pudieron obtener detalles adicionales del error de Gemini: {inner_e}")
    else:
        if st.button("Reintentar Generación", use_container_width=True, disabled=not (pdf_agentes_beecker and pdf_lead)):
            pass

else:
    st.info("ℹ️ Por favor, sube los dos archivos PDF requeridos para generar el mensaje.")

# --- Sidebar ---
with st.sidebar:
    st.header("Instrucciones")
    st.markdown("""
    1.  Sube el PDF con la información de **Agentes de Beecker** (este PDF también puede contener información general de la empresa).
    2.  Sube el PDF del **Lead**.
    3.  Haz clic en **"Generar Mensaje"**.
    """)
    st.markdown("---")
    st.markdown(f"Modelo en uso: `{MODEL_NAME}`")
