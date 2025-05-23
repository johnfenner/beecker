import streamlit as st
import google.generativeai as genai
import pdfplumber # Para leer PDFs
import io # Para manejar el stream de bytes del archivo subido

# --- 1. SYSTEM_PROMPT COMPLETO Y CORRECTO ---
# Este SYSTEM_PROMPT contiene las INSTRUCCIONES para la IA, indicando que recibirá
# tres bloques de texto (de los 3 PDFs) y cómo debe usarlos.
SYSTEM_PROMPT = """
Eres mi asistente experto en redacción persuasiva para LinkedIn.
Te proporcionaré tres bloques de texto con la siguiente información:
1.  TEXTO_AGENTES_BEECKER: Contiene el catálogo detallado y las funciones de los agentes de IA de Beecker.
2.  TEXTO_QUIENES_SOMOS_BEECKER: Contiene información general sobre la compañía Beecker, como su misión, visión, valores, casos de éxito generales y áreas de impacto.
3.  TEXTO_LEAD: Contiene la información extraída del PDF de un cliente potencial.

Cada vez que recibas estos tres bloques de texto, generarás un único mensaje de LinkedIn listo para copiar y pegar, dirigido al LEAD, siguiendo estas reglas al pie de la letra:

**Reglas de Procesamiento y Formato:**

**A. Procesamiento Aislado**
   - Olvida cualquier información de leads o textos anteriores.
   - Trabaja únicamente con los tres bloques de texto (TEXTO_AGENTES_BEECKER, TEXTO_QUIENES_SOMOS_BEECKER, TEXTO_LEAD) que recibas en este momento.

**B. Estructura y Formato del Mensaje**
   1.  **Saludo**
       - “Buen día, [Nombre extraído del TEXTO_LEAD].” (Si el rol en TEXTO_LEAD indica CEOs, VPs)
       - “Hola [Nombre extraído del TEXTO_LEAD],” (para otros roles en TEXTO_LEAD)
   2.  **Gancho Inicial**
       - Conecta con 1–2 datos concretos del TEXTO_LEAD (rol actual, proyecto o logro mencionado allí).
       - No uses “Vi tu perfil…”, “Me impresionó…”, ni referencias genéricas.
   3.  **Presentación Orgánica de Beecker**
       - Comienza con: “En Beecker (https://beecker.ai/agentic-ai/) acompañamos a empresas con Agentes IA Autónomos…”
       - Destaca un aspecto relevante según el TEXTO_LEAD, utilizando información del TEXTO_QUIENES_SOMOS_BEECKER (casos de éxito, áreas de impacto o certificaciones).
   4.  **Propuesta de Valor**
       - Párrafo breve que vincule el reto actual del lead (inferido del TEXTO_LEAD) con el beneficio concreto de un Agente IA (automatización inteligente vs RPA, aprendizaje continuo, eficiencia operativa, calidad), basándote en la información del TEXTO_AGENTES_BEECKER y TEXTO_QUIENES_SOMOS_BEECKER.
   5.  **Lista Literal de Agentes Relevantes**
       - Usa guiones `-` para cada ítem (formato LinkedIn).
       - Selecciona agentes relevantes del TEXTO_AGENTES_BEECKER según el área o retos del lead identificados en el TEXTO_LEAD.
       - Alinea cada agente con un reto o área del lead.
       - Si el TEXTO_LEAD no da pistas claras, incluye un menú de 3–4 dominios generales (ej: Procurement, Finanzas, RRHH, Cadena de Suministro) y sugiere agentes relevantes del TEXTO_AGENTES_BEECKER para esos dominios.
       - Para leads de TI (identificados en el TEXTO_LEAD), enfoca la propuesta en beneficios de soporte interno: cómo nuestros agentes (del TEXTO_AGENTES_BEECKER) pueden reducir la carga de tickets automatizando tareas repetitivas (monitoreo proactivo de sistemas, detección temprana de anomalías, reportes automáticos).
   6.  **Contexto Empresarial**
       - Refuerza que es una propuesta para la empresa, liberando recursos y mejorando resultados (“extensiones inteligentes de tu equipo”, “valor a tus proyectos”).
   7.  **Cierre Consultivo**
       - Invita a “agendar un espacio breve para que conozcas estas tecnologías y evaluemos juntos cómo esta propuesta empresarial podría aportar valor a [área/empresa mencionada en TEXTO_LEAD]”.
       - Mantén la invitación abierta, sin sonar a venta agresiva.

**C. Tono y Lenguaje**
   - Español, tuteo, humano, orgánico, profesional y cercano.
   - Ligero toque entusiasta, sin jerga técnica excesiva (evita “sprints”, “scripts”).
   - Párrafos de 2–3 líneas, saltos de línea claros.

**D. Verificación Final**
   - Asegúrate de usar solo datos del TEXTO_LEAD, TEXTO_AGENTES_BEECKER y TEXTO_QUIENES_SOMOS_BEECKER proporcionados.
   - Confirma que los nombres y funciones de los Agentes coincidan con lo descrito en TEXTO_AGENTES_BEECKER.
   - Revisa que el mensaje transmita valor empresarial, no personal, y que la invitación sea consultiva.
   - Elimina cualquier artefacto de referencia interna (por ejemplo, :contentReference, oaicite) para garantizar un mensaje limpio y listo para copiar.

— A partir de ahora, sigue exactamente este prompt y estas reglas para cada conjunto de textos que te envíe. —
"""

# --- 2. RESTO DEL CÓDIGO DE LA APLICACIÓN STREAMLIT ---

# --- Configuración de la Página de Streamlit ---
st.set_page_config(page_title="🚀 Generador LinkedIn Pro", layout="wide")
st.image("https://beecker.ai/wp-content/uploads/2024/02/logo-beecker-consulting.svg", width=200) # Opcional: logo de Beecker
st.title("🤖 Generador Mensajes para LinkedIn")
st.markdown("Sube los PDFs de Beecker (Agentes y Quiénes Somos) y el PDF del Lead para generar un mensaje personalizado.")

# --- Configuración de la API Key de Gemini (desde Streamlit Secrets) ---
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
except KeyError:
    st.error("Error: La API Key de Google Gemini (GOOGLE_API_KEY) no está configurada en los Secrets de Streamlit.")
    st.info("Por favor, configura la variable 'GOOGLE_API_KEY' en los secrets de tu aplicación en Streamlit Community Cloud.")
    st.stop() # Detiene la ejecución si la key no está
except Exception as e:
    st.error(f"Ocurrió un error al configurar la API de Gemini: {e}")
    st.stop()

# --- Inicialización del Modelo con el System Prompt ---
MODEL_NAME = 'gemini-1.5-flash-latest' # O 'gemini-pro' si es tu preferencia
try:
    # Aplicamos el SYSTEM_PROMPT (que contiene las instrucciones) al inicializar el modelo
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except Exception as e:
    st.error(f"Error al cargar el modelo Gemini ('{MODEL_NAME}'): {e}")
    st.info("Asegúrate de que el nombre del modelo sea correcto y que tu API key tenga acceso a él.")
    st.stop()

# --- Función para extraer texto de un PDF subido ---
def extraer_texto_pdf(archivo_subido):
    if archivo_subido is None:
        # st.warning(f"Se intentó procesar un archivo nulo.") # Comentado para no ser muy verboso si no hay archivo
        return None
    try:
        texto_completo = ""
        # Usamos io.BytesIO para manejar el stream de bytes del archivo subido
        with pdfplumber.open(io.BytesIO(archivo_subido.read())) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: # Asegurarse de que se extrajo texto
                    texto_completo += page_text + "\n"
        return texto_completo.strip() if texto_completo else None # Retorna None si no hay texto
    except Exception as e:
        st.error(f"Error al leer el PDF '{archivo_subido.name}': {e}")
        return None

# --- Columnas para la carga de PDFs ---
st.header("Carga de Documentos")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("#### 1. Info Agentes Beecker")
    pdf_agentes_beecker = st.file_uploader("📄 PDF Catálogo de Agentes", type="pdf", key="agentes", help="Sube el PDF con la información detallada de los agentes de Beecker.")

with col2:
    st.markdown("#### 2. Info 'Quiénes Somos' Beecker")
    pdf_quienes_somos_beecker = st.file_uploader("📄 PDF 'Quiénes Somos'", type="pdf", key="quienes_somos", help="Sube el PDF con la información general de la compañía Beecker.")

with col3:
    st.markdown("#### 3. Info del Lead")
    pdf_lead = st.file_uploader("👤 PDF del Lead", type="pdf", key="lead", help="Sube el PDF del perfil del lead a contactar.")

st.markdown("---") # Separador visual

# --- Procesamiento y Generación del Mensaje ---
# Solo proceder si los tres archivos han sido subidos
if pdf_agentes_beecker and pdf_quienes_somos_beecker and pdf_lead:
    
    # Extraer texto de cada PDF
    # Usamos variables de sesión para guardar el texto y no reprocesar innecesariamente si solo cambia uno (aunque aquí siempre se reprocesan los 3 si se presiona el botón)
    # Para una optimización más avanzada se podría usar st.cache_data para la extracción de los PDFs de Beecker si se asume que no cambian tan frecuentemente.
    
    texto_agentes = extraer_texto_pdf(pdf_agentes_beecker)
    texto_quienes_somos = extraer_texto_pdf(pdf_quienes_somos_beecker)
    texto_lead_actual = extraer_texto_pdf(pdf_lead)

    # Validar que se haya extraído texto de todos los PDFs
    valid_inputs = True
    if not texto_agentes:
        st.warning("⚠️ No se pudo extraer texto del PDF de Agentes Beecker o está vacío. Por favor, verifica el archivo.")
        valid_inputs = False
    if not texto_quienes_somos:
        st.warning("⚠️ No se pudo extraer texto del PDF 'Quiénes Somos' Beecker o está vacío. Por favor, verifica el archivo.")
        valid_inputs = False
    if not texto_lead_actual:
        st.warning("⚠️ No se pudo extraer texto del PDF del Lead o está vacío. Por favor, verifica el archivo.")
        valid_inputs = False

    if valid_inputs:
        st.info("📝 Previsualización de textos extraídos (primeros 300 caracteres de cada PDF):")
        with st.expander("Ver Texto Agentes Beecker (extracto)"):
            st.text(texto_agentes[:300] + "..." if texto_agentes else "No se extrajo texto.")
        with st.expander("Ver Texto 'Quiénes Somos' Beecker (extracto)"):
            st.text(texto_quienes_somos[:300] + "..." if texto_quienes_somos else "No se extrajo texto.")
        with st.expander("Ver Texto Lead (extracto)"):
            st.text(texto_lead_actual[:300] + "..." if texto_lead_actual else "No se extrajo texto.")
        
        st.markdown("---")

        if st.button("✨ Generar Mensaje de LinkedIn para este Lead", type="primary", use_container_width=True):
            with st.spinner("🤖 Gemini está analizando los 3 PDFs y redactando el mensaje... ¡Un momento!"):
                # Construir el contenido completo para enviar a Gemini
                # Este es el texto que la IA procesará, siguiendo las instrucciones del SYSTEM_PROMPT
                contenido_para_gemini = f"""
                --- INICIO TEXTO_AGENTES_BEECKER ---
                {texto_agentes}
                --- FIN TEXTO_AGENTES_BEECKER ---

                --- INICIO TEXTO_QUIENES_SOMOS_BEECKER ---
                {texto_quienes_somos}
                --- FIN TEXTO_QUIENES_SOMOS_BEECKER ---

                --- INICIO TEXTO_LEAD ---
                {texto_lead_actual}
                --- FIN TEXTO_LEAD ---
                """
                try:
                    # Llamada a la API de Gemini
                    response = model.generate_content(contenido_para_gemini)
                    respuesta_gemini = response.text

                    st.subheader("📬 Mensaje de LinkedIn Generado:")
                    st.markdown(respuesta_gemini) # Mostrar con formato Markdown
                    st.text_area("Para copiar fácilmente:", respuesta_gemini, height=200) # También en un text_area para copiar

                    st.success("¡Mensaje generado con éxito!")

                except Exception as e:
                    st.error(f"Ocurrió un error al generar el mensaje con Gemini: {e}")
                    # Intentar mostrar más detalles si están disponibles en el objeto de error o respuesta
                    # (Esto es una suposición, la estructura real del error/respuesta de Gemini puede variar)
                    try:
                        if hasattr(response, 'candidates') and response.candidates: # Chequeo más seguro
                             st.warning(f"Información del Prompt Feedback (si existe): {response.prompt_feedback}")
                             for candidate_idx, candidate in enumerate(response.candidates):
                                 st.caption(f"Candidato {candidate_idx+1} - Razón de finalización: {candidate.finish_reason}")
                                 if candidate.finish_message:
                                     st.caption(f"Candidato {candidate_idx+1} - Mensaje de finalización: {candidate.finish_message}")
                        elif hasattr(e, 'response') and hasattr(e.response, 'prompt_feedback'): # Para algunos tipos de errores de API
                             st.warning(f"Información del Prompt Feedback del error: {e.response.prompt_feedback}")
                    except Exception as inner_e:
                        st.warning(f"No se pudieron obtener detalles adicionales del error de Gemini: {inner_e}")
    else:
        if st.button("Reintentar Generación (si ya subiste los PDFs)", use_container_width=True): # Botón para reintentar si algo falló en la extracción pero los archivos están
            pass # Simplemente permite que el script se re-ejecute con los archivos ya cargados

else:
    st.info("ℹ️ Por favor, sube los tres archivos PDF requeridos en las secciones de arriba para poder generar el mensaje.")

# --- Sidebar para instrucciones y créditos ---
with st.sidebar:
    st.header("Instrucciones de Uso")
    st.markdown("""
    1.  Sube el PDF con la información detallada del **Catálogo de Agentes** de Beecker.
    2.  Sube el PDF con la información general de **"Quiénes Somos"** de Beecker (misión, visión, valores, etc.).
    3.  Sube el PDF del perfil del **Lead** al que deseas contactar.
    4.  Verifica las previsualizaciones de los textos extraídos (opcional).
    5.  Una vez cargados los 3 PDFs y si la extracción fue exitosa, haz clic en el botón **"Generar Mensaje de LinkedIn"**.
    6.  Copia el mensaje generado.
    """)
    st.markdown("---")
    st.markdown(
        "Desarrollado con [Streamlit](https://streamlit.io) y "
        "[Google Gemini](https://ai.google.dev/)."
    )
    st.markdown(f"Usando el modelo: `{MODEL_NAME}`")
