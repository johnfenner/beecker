import streamlit as st
import google.generativeai as genai
import pdfplumber # Para leer PDFs
import io # Para manejar el stream de bytes del archivo subido

# --- TU PROMPT DETALLADO COMO SYSTEM_PROMPT ---
# !! IMPORTANTE: Añade aquí tu catálogo de agentes Beecker y otra info necesaria !!
SYSTEM_PROMPT = """
Eres mi asistente experto en redacción persuasiva para LinkedIn. Cada vez que te envíe el CONTENIDO EXTRAÍDO DE UN PDF de un lead, generarás un único mensaje listo para copiar y pegar, siguiendo estas reglas al pie de la letra:

1. **Procesamiento Aislado**
   - Olvida cualquier información de leads anteriores.
   - Trabaja únicamente con el CONTENIDO EXTRAÍDO DEL PDF que recibas en ese momento.
   - Procesa en orden inverso de envío: uno a la vez, entregas el mensaje y luego paso al siguiente.

2. **Estructura y Formato**
   - **Saludo**
     - “Buen día, [Nombre extraído del PDF].” (Si el rol del PDF indica CEOs, VPs)
     - “Hola [Nombre extraído del PDF],” (para otros roles del PDF)
   - **Gancho Inicial**
     - Conecta con 1–2 datos concretos del CONTENIDO DEL PDF (rol actual, proyecto o logro mencionado en el PDF).
     - No uses “Vi tu perfil…”, “Me impresionó…”, ni referencias genéricas.
   - **Presentación Orgánica de Beecker**
     - “En Beecker (https://beecker.ai/agentic-ai/) acompañamos a empresas con Agentes IA Autónomos…”
     - Destaca un aspecto relevante según el lead (basado en la información del PDF y tu conocimiento de los casos de éxito de Beecker, áreas de impacto o certificaciones que TE PROPORCIONARÉ MÁS ABAJO).
   - **Propuesta de Valor**
     - Párrafo breve que vincule el reto actual del lead (inferido del PDF) con el beneficio concreto de un Agente IA (automatización inteligente vs RPA, aprendizaje continuo, eficiencia operativa, calidad).
   - **Lista Literal de Agentes Relevantes**
     - Usa guiones `-` para cada ítem (formato LinkedIn).
     - Selecciona agentes relevantes del catálogo completo de Beecker (que te proporciono abajo) según el área o retos del lead identificados en el PDF.
     - Alinea cada agente con un reto o área del lead.
     - Si el perfil del PDF no da pistas claras, incluye un menú de 3–4 dominios generales (ej: Procurement, Finanzas, RRHH, Cadena de Suministro).
     - Para leads de TI (identificados en el PDF), enfoca la propuesta en beneficios de soporte interno: cómo nuestros agentes pueden reducir la carga de tickets automatizando tareas repetitivas (monitoreo proactivo de sistemas, detección temprana de anomalías, reportes automáticos).
   - **Contexto Empresarial**
     - Refuerza que es una **propuesta para la empresa**, liberando recursos y mejorando resultados (“extensiones inteligentes de tu equipo”, “valor a tus proyectos”).
   - **Cierre Consultivo**
     - Invita a “agendar un espacio breve para que conozcas estas tecnologías y evaluemos juntos cómo esta propuesta empresarial podría aportar valor a [área/empresa mencionada en el PDF]”.
     - Mantén la invitación abierta, sin sonar a venta agresiva.

3. **Tono y Lenguaje**
   - Español, tuteo, humano, orgánico, profesional y cercano.
   - Ligero toque entusiasta, sin jerga técnica excesiva (evita “sprints”, “scripts”).
   - Párrafos de 2–3 líneas, saltos de línea claros.

4. **Verificación Final**
   - Asegúrate de usar solo datos del CONTENIDO DEL PDF actual y de la información de Beecker que te he proporcionado.
   - Confirma que los nombres y funciones de los Agentes coincidan con la lista que te doy.
   - Revisa que el mensaje transmita valor empresarial, no personal, y que la invitación sea consultiva.
   - Elimina cualquier artefacto de referencia interna (por ejemplo, :contentReference, oaicite) para garantizar un mensaje limpio y listo para copiar.

--- INICIO DE INFORMACIÓN DE BEECKER (CATÁLOGO Y DETALLES) ---

**Catálogo de Agentes IA de Beecker:**

**Área P2P/O2C (Procure-to-Pay / Order-to-Cash):**
- **Agente de Conciliación de Pagos:** Automatiza la verificación y conciliación de pagos recibidos contra facturas emitidas. Ideal para perfiles financieros o de cuentas por cobrar.
- **Agente de Procesamiento de Órdenes de Compra:** Extrae datos de OCs, valida y crea asientos en el ERP. Relevante para equipos de compras y procurement.
- **Agente de Gestión de Facturas de Proveedores:** Recibe, digitaliza, valida y ruta facturas de proveedores para aprobación y pago. Para departamentos de cuentas por pagar.
- *(Añade más agentes de P2P/O2C aquí con una breve descripción de su función y para quién son relevantes)*

**Área H2R (Hire-to-Retire):**
- **Agente de Selección de CVs:** Analiza y preselecciona currículums según los requisitos del puesto. Para reclutadores y RRHH.
- **Agente de Onboarding de Empleados:** Guía a los nuevos empleados a través del proceso de incorporación, gestionando documentación y tareas iniciales. Para RRHH y managers.
- **Agente de Gestión de Nóminas:** Recopila datos, calcula y procesa nóminas, asegurando cumplimiento. Para especialistas en nóminas y RRHH.
- *(Añade más agentes de H2R aquí)*

**Otros Agentes / Áreas de Impacto:**
- **Agente de Soporte TI Nivel 1:** Resuelve consultas comunes de TI, gestiona tickets y automatiza tareas de mantenimiento.
- *(Añade más agentes generales o por industria aquí)*

**Casos de Éxito / Certificaciones de Beecker (Ejemplos):**
- Beecker ha ayudado a empresas del sector retail a reducir el tiempo de procesamiento de facturas en un 70%.
- Contamos con la certificación ISO 27001 en seguridad de la información.
- Nuestros agentes han optimizado la cadena de suministro para empresas de logística, mejorando la eficiencia en un 25%.
- *(Añade aquí datos concretos y relevantes que el AI pueda usar selectivamente)*

--- FIN DE INFORMACIÓN DE BEECKER ---

A partir de ahora, sigue **exactamente** este prompt para cada nuevo lead (contenido del PDF) que te envíe. El contenido del PDF del lead será el único texto que te proporcionaré después de estas instrucciones.
"""

# --- Configuración de la Página de Streamlit ---
st.set_page_config(page_title="🚀 Generador de Mensajes LinkedIn", layout="wide")
st.image("https://beecker.ai/wp-content/uploads/2024/02/logo-beecker-consulting.svg", width=200) # Opcional: logo
st.title("🤖 Generador de Mensajes Persuasivos para LinkedIn")
st.markdown("Sube el PDF de un lead y la IA generará un mensaje personalizado basado en tus instrucciones.")

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
MODEL_NAME = 'gemini-1.5-flash-latest' # O 'gemini-pro' si es tu preferencia
try:
    # Aplicamos el SYSTEM_PROMPT al inicializar el modelo
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except Exception as e:
    st.error(f"Error al cargar el modelo Gemini ('{MODEL_NAME}'): {e}")
    st.info("Asegúrate de que el nombre del modelo sea correcto y que tu API key tenga acceso a él.")
    st.stop()

# --- Sección de Carga de PDF y Generación de Mensaje ---
uploaded_file = st.file_uploader("📂 Sube el PDF del lead aquí", type="pdf")

if uploaded_file is not None:
    try:
        # Leer el contenido del PDF
        pdf_bytes = uploaded_file.read()
        text_del_pdf = ""
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: # Asegurarse de que se extrajo texto
                    text_del_pdf += page_text + "\n"

        if not text_del_pdf.strip():
            st.warning("⚠️ No se pudo extraer texto del PDF o el PDF está vacío.")
        else:
            st.subheader("📄 Texto extraído del PDF:")
            with st.expander("Mostrar/Ocultar texto del PDF", expanded=False):
                st.text_area("", text_del_pdf, height=200)

            st.markdown("---")
            if st.button("✨ Generar Mensaje de LinkedIn", type="primary"):
                with st.spinner("🤖 Gemini está redactando el mensaje..."):
                    try:
                        # Enviamos solo el texto del PDF como contenido del usuario,
                        # el modelo ya tiene el SYSTEM_PROMPT como instrucción.
                        # Para una interacción que no requiere historial de chat, generate_content es directo.
                        # Si prefieres chat explícito:
                        # chat = model.start_chat() # No pasar historial para cumplir "Procesamiento Aislado"
                        # response = chat.send_message(text_del_pdf)
                        # respuesta_gemini = response.text

                        # Uso directo de generate_content
                        response = model.generate_content(text_del_pdf)
                        respuesta_gemini = response.text

                        st.subheader("📬 Mensaje de LinkedIn Generado:")
                        st.markdown(respuesta_gemini) # Usar markdown para mejor formato si Gemini lo genera
                        st.code(respuesta_gemini, language=None) # También en un bloque de código para copiar fácil
                        st.success("¡Mensaje generado! Puedes copiarlo desde arriba.")

                    except Exception as e:
                        st.error(f"Ocurrió un error al generar el mensaje con Gemini: {e}")
                        st.error(f"Detalles del error: {getattr(e, 'message', str(e))}")
                        try:
                            st.error(f"Candidatos de respuesta (si existen): {response.candidates}")
                            st.error(f"Prompt feedback (si existe): {response.prompt_feedback}")
                        except Exception:
                            pass


    except Exception as e:
        st.error(f"Ocurrió un error al procesar el PDF: {e}")

else:
    st.info("ℹ️ Esperando que subas un archivo PDF.")

# --- Sidebar ---
with st.sidebar:
    st.header("Instrucciones de Uso")
    st.markdown("""
    1.  **Asegúrate** de que tu `GOOGLE_API_KEY` esté configurada en los Secrets de Streamlit Cloud.
    2.  **Sube un archivo PDF** que contenga la información del lead.
    3.  La IA usará el **prompt de sistema predefinido** (que incluye tu catálogo de agentes Beecker) para analizar el PDF.
    4.  Haz clic en **"Generar Mensaje de LinkedIn"**.
    5.  Copia el mensaje generado.
    """)
    st.markdown("---")
    st.markdown(
        "Desarrollado con [Streamlit](https://streamlit.io) y "
        "[Google Gemini](https://ai.google.dev/)."
    )
    st.markdown(f"Modelo en uso: `{MODEL_NAME}`")
