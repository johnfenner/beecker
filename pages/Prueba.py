import streamlit as st
import google.generativeai as genai
import pdfplumber # Para leer PDFs
import io # Para manejar el stream de bytes del archivo subido

# --- 1. SYSTEM_PROMPT (VERSIÓN MÁS RECIENTE Y COMPLETA) ---
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

   **Nota Clave para Analizar TEXTO_LEAD:** Para identificar el nombre del lead, su cargo actual y la empresa actual, debes buscar y dar **prioridad absoluta** a la información que encuentres bajo encabezados explícitos como "Experiencia", "Experience", "Experiencia Profesional" o "Professional Experience" dentro del TEXTO_LEAD. La información que aparece al inicio del PDF (como un titular o resumen) a veces puede no ser la más actualizada o precisa para estos detalles; la sección de 'Experiencia' es la fuente más confiable.

   1.  **Saludo**
       - “Buen día, [Nombre del lead, obtenido según la 'Nota Clave para Analizar TEXTO_LEAD']." (Si el rol actual del lead, obtenido según la 'Nota Clave', indica CEOs, VPs)
       - “Hola [Nombre del lead, obtenido según la 'Nota Clave para Analizar TEXTO_LEAD']." (para otros roles actuales del lead, obtenidos según la 'Nota Clave')
   2.  **Gancho Inicial (Conciso y Relevante)**
       - Conecta con 1–2 datos concretos y muy breves del TEXTO_LEAD (rol actual y empresa actual –obtenidos según la 'Nota Clave'– o un logro destacado/proyecto reciente mencionado en su sección de 'Experiencia').
       - **Importante:** Analiza la experiencia del lead (TEXTO_LEAD, especialmente la sección 'Experiencia') para personalizar la propuesta, pero NO detalles extensamente sus trabajos o proyectos anteriores en el mensaje. El objetivo es un gancho rápido y pertinente, no un resumen de su CV.
       - No uses “Vi tu perfil…”, “Me impresionó…”, ni referencias genéricas.
   3.  **Presentación Orgánica de Beecker**
       - Comienza con: “En Beecker (https://beecker.ai/agentic-ai/) acompañamos a empresas con Agentes IA Autónomos…”
       - A continuación, busca dentro del TEXTO_AGENTES_BEECKER si se menciona información general de la compañía como casos de éxito específicos, áreas de impacto clave o certificaciones. Si encuentras detalles que sean relevantes y aplicables al perfil descrito en TEXTO_LEAD, incorpóralos de forma breve y natural para enriquecer esta presentación.
       - Si dicha información general específica no está presente en TEXTO_AGENTES_BEECKER o no es directamente aplicable al lead, entonces centra esta parte de la presentación en la relevancia y el valor general que los Agentes IA Autónomos pueden aportar al tipo de empresa o al rol del lead.
   4.  **Propuesta de Valor**
       - Párrafo breve que vincule el reto actual del lead (inferido del TEXTO_LEAD, especialmente de su experiencia y rol actual) con el beneficio concreto de un Agente IA (automatización inteligente vs RPA, aprendizaje continuo, eficiencia operativa, calidad), basándote en la información del TEXTO_AGENTES_BEECKER.
   5.  **Lista Literal de Agentes Relevantes**
       - Usa guiones `- ` (guion seguido de un espacio) para cada ítem (formato LinkedIn).
       - Selecciona agentes relevantes del TEXTO_AGENTES_BEECKER según el área o retos del lead identificados en el TEXTO_LEAD (considerando su rol y empresa actual de la sección 'Experiencia').
       - Alinea cada agente con un reto o área del lead.
       - Si el TEXTO_LEAD no da pistas claras sobre retos específicos (incluso después de analizar su 'Experiencia'), incluye un menú de 2–3 dominios generales (ej: Procurement, Finanzas, RRHH) y sugiere agentes relevantes del TEXTO_AGENTES_BEECKER para esos dominios.
       - Para leads de TI (identificados en el TEXTO_LEAD, especialmente en su 'Experiencia'), enfoca la propuesta en beneficios de soporte interno: cómo nuestros agentes (del TEXTO_AGENTES_BEECKER) pueden reducir la carga de tickets automatizando tareas repetitivas.
   6.  **Contexto Empresarial**
       - Refuerza que es una propuesta para la empresa, liberando recursos y mejorando resultados (“extensiones inteligentes de tu equipo”, “valor a tus proyectos”).
   7.  **Cierre Consultivo**
       - Invita a “agendar un espacio breve para que conozcas estas tecnologías y evaluemos juntos cómo esta propuesta empresarial podría aportar valor a [área del lead o empresa actual del lead, obtenida del TEXTO_LEAD según la 'Nota Clave']”.
       - Mantén la invitación abierta, sin sonar a venta agresiva.

**C. Tono y Lenguaje**
   - Español, tuteo, humano, orgánico, profesional y cercano.
   - Ligero toque entusiasta, sin jerga técnica excesiva (evita “sprints”, “scripts”).
   - Párrafos de 2–3 líneas máximo, saltos de línea claros. Mensajes concisos y directos.
   - **IMPORTANTE: Todo el mensaje debe ser generado en TEXTO PLANO. No utilices formato Markdown como asteriscos dobles (`**`) para simular negritas ni ningún otro tipo de formato especial que no sea texto simple y saltos de línea.**

**D. Verificación Final**
   - Asegúrate de usar solo datos del TEXTO_LEAD y TEXTO_AGENTES_BEECKER proporcionados, dando prioridad a la sección 'Experiencia' del TEXTO_LEAD para datos del lead.
   - Confirma que los nombres y funciones de los Agentes coincidan con lo descrito en TEXTO_AGENTES_BEECKER.
   - Revisa que el mensaje transmita valor empresarial, no personal, y que la invitación sea consultiva.
   - El mensaje final debe ser breve, fácil de leer en LinkedIn y en **texto plano sin formato Markdown para negritas.**
   - Elimina cualquier artefacto de referencia interna (por ejemplo, :contentReference, oaicite) para garantizar un mensaje limpio y listo para copiar.

— A partir de ahora, sigue exactamente este prompt y estas reglas para cada conjunto de textos que te envíe. —
"""

# --- 2. INICIALIZACIÓN DE VARIABLES DE SESIÓN ---
if 'generated_message' not in st.session_state:
    st.session_state.generated_message = None
if 'texto_agentes_beecker_actual' not in st.session_state:
    st.session_state.texto_agentes_beecker_actual = None
if 'texto_lead_actual_procesado' not in st.session_state:
    st.session_state.texto_lead_actual_procesado = None
if 'nombre_archivo_agentes' not in st.session_state:
    st.session_state.nombre_archivo_agentes = None
if 'nombre_archivo_lead' not in st.session_state:
    st.session_state.nombre_archivo_lead = None

# --- 3. CÓDIGO DE LA APLICACIÓN STREAMLIT ---

# --- Configuración de la Página ---
st.set_page_config(page_title="🚀 Generador LinkedIn Pro", layout="wide")
st.title("🤖 Generador de Mensajes para LinkedIn")
st.markdown("Sube el PDF de Agentes de Beecker y el PDF del Lead para generar un mensaje.")

# --- Configuración de la API Key ---
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("Error: GOOGLE_API_KEY no configurada en Secrets.")
    st.stop()
except Exception as e:
    st.error(f"Error configurando API Gemini: {e}")
    st.stop()

# --- Inicialización del Modelo ---
MODEL_NAME = 'gemini-1.5-flash-latest'
try:
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except Exception as e:
    st.error(f"Error cargando modelo Gemini ('{MODEL_NAME}'): {e}")
    st.stop()

# --- Función para extraer texto ---
def extraer_texto_pdf(archivo_subido):
    if archivo_subido is None: return None
    try:
        texto_completo = ""
        # .getvalue() es necesario para que pdfplumber pueda leer el BytesIO de Streamlit
        with pdfplumber.open(io.BytesIO(archivo_subido.getvalue())) as pdf:
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
    pdf_agentes_uploader = st.file_uploader("📄 Catálogo de Agentes y Info. General de Beecker", type="pdf", key="uploader_agentes", help="Sube el PDF con el catálogo de agentes y la información general relevante de Beecker.")

with col2:
    st.markdown("#### 2. PDF del Lead")
    pdf_lead_uploader = st.file_uploader("👤 Perfil del Lead", type="pdf", key="uploader_lead", help="Sube el PDF del perfil del lead a contactar.")

st.markdown("---")

# --- Botón de Limpiar ---
# Colocado antes de la lógica de procesamiento para que esté siempre visible si hay algo que limpiar
if st.button("🧹 Limpiar Entradas y Resultados Anteriores", use_container_width=True):
    # Reiniciar las variables de sesión relevantes
    keys_to_reset = [
        'generated_message', 
        'texto_agentes_beecker_actual', 
        'texto_lead_actual_procesado',
        'nombre_archivo_agentes',
        'nombre_archivo_lead'
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            st.session_state[key] = None
    
    # Es importante usar st.rerun() para que la interfaz se refresque correctamente
    # y los file_uploaders también se comporten como si estuvieran "más limpios"
    # (aunque el navegador pueda recordar el último archivo, nuestra lógica lo ignorará hasta nueva carga)
    st.rerun()


# --- Lógica de Procesamiento de Archivos ---
# Se ejecuta si se sube un nuevo archivo de agentes
if pdf_agentes_uploader is not None:
    if st.session_state.nombre_archivo_agentes != pdf_agentes_uploader.name: # Solo procesa si es un archivo nuevo
        with st.spinner("Procesando PDF de Agentes Beecker..."):
            st.session_state.texto_agentes_beecker_actual = extraer_texto_pdf(pdf_agentes_uploader)
            st.session_state.nombre_archivo_agentes = pdf_agentes_uploader.name
            st.session_state.generated_message = None # Limpiar mensaje anterior si se cambia este PDF
            if not st.session_state.texto_agentes_beecker_actual:
                st.warning("No se pudo extraer texto del PDF de Agentes Beecker o está vacío.")
            # st.rerun() # Considerar un rerun aquí si queremos que la UI se actualice inmediatamente después de procesar este archivo

# Se ejecuta si se sube un nuevo archivo de lead
if pdf_lead_uploader is not None:
    if st.session_state.nombre_archivo_lead != pdf_lead_uploader.name: # Solo procesa si es un archivo nuevo
        with st.spinner("Procesando PDF del Lead..."):
            st.session_state.texto_lead_actual_procesado = extraer_texto_pdf(pdf_lead_uploader)
            st.session_state.nombre_archivo_lead = pdf_lead_uploader.name
            st.session_state.generated_message = None # Limpiar mensaje anterior si se cambia este PDF
            if not st.session_state.texto_lead_actual_procesado:
                st.warning("No se pudo extraer texto del PDF del Lead o está vacío.")
            # st.rerun() # Considerar un rerun aquí también

# --- Previsualización y Botón de Generar Mensaje ---
if st.session_state.texto_agentes_beecker_actual and st.session_state.texto_lead_actual_procesado:
    if not st.session_state.generated_message: # Mostrar previsualizaciones solo si no hay mensaje generado
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
                # Limpieza de asteriscos para negritas
                st.session_state.generated_message = respuesta_gemini_bruta.replace('**', '')
                st.rerun() # Rerun para mostrar el mensaje generado y limpiar previsualizaciones

            except Exception as e:
                st.error(f"Ocurrió un error al generar el mensaje con Gemini: {e}")
                st.session_state.generated_message = None
                try:
                    if hasattr(response, 'candidates') and response.candidates:
                         st.warning(f"Información del Prompt Feedback (si existe): {response.prompt_feedback}")
                         for candidate_idx, candidate in enumerate(response.candidates):
                             st.caption(f"Candidato {candidate_idx+1} - Razón de finalización: {candidate.finish_reason}")
                             if candidate.finish_message:
                                 st.caption(f"Candidato {candidate_idx+1} - Mensaje de finalización: {candidate.finish_message}")
                    elif hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'):
                         st.warning(f"Información del Prompt Feedback del error: {e.response.prompt_feedback}")
                except Exception:
                    pass

# --- Mostrar Mensaje Generado ---
if st.session_state.generated_message:
    st.subheader("📬 Mensaje de LinkedIn Generado:")
    st.markdown(st.session_state.generated_message) # Muestra el mensaje con formato (saltos de línea)
    st.code(st.session_state.generated_message, language=None) # Muestra el mensaje para copiar fácil con botón
    st.success("¡Mensaje generado con éxito! Puedes copiarlo del bloque de arriba.")

# Mensaje inicial si no se ha cargado nada aún y no hay mensaje previo
elif not st.session_state.texto_agentes_beecker_actual and not st.session_state.texto_lead_actual_procesado and not st.session_state.generated_message:
    st.info("ℹ️ Por favor, sube los dos archivos PDF requeridos para generar el mensaje.")

# --- Sidebar ---
with st.sidebar:
    st.header("Instrucciones")
    st.markdown("""
    1.  Sube el PDF con la información de **Agentes de Beecker**.
    2.  Sube el PDF del **Lead**.
    3.  Haz clic en **"Generar Mensaje"**.
    4.  Para empezar de nuevo, usa el botón **"Limpiar Entradas y Resultados Anteriores"**.
    """)
    st.markdown("---")
    st.markdown(f"Modelo en uso: `{MODEL_NAME}`")
