import streamlit as st
import google.generativeai as genai
import pdfplumber
import io

# --- 1. SYSTEM_PROMPT (El mismo que ya funcionaba bien) ---
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
if 'texto_agentes_beecker_actual' not in st.session_state:
    st.session_state.texto_agentes_beecker_actual = None
if 'nombre_archivo_agentes' not in st.session_state:
    st.session_state.nombre_archivo_agentes = None
if 'mensajes_generados_batch' not in st.session_state: # Para guardar los resultados del batch
    st.session_state.mensajes_generados_batch = []
if 'archivos_leads_procesados_nombres' not in st.session_state: # Para evitar reprocesar mismos archivos en un batch
    st.session_state.archivos_leads_procesados_nombres = []


# --- 3. CÓDIGO DE LA APLICACIÓN STREAMLIT ---
st.set_page_config(page_title="🚀 Generador LinkedIn Batch", layout="wide")
st.title("🤖 Generador de Mensajes para LinkedIn")
st.markdown("Sube el PDF de Agentes de Beecker una vez, y luego múltiples PDFs de Leads.")

# --- Configuración de API Key y Modelo (igual que antes) ---
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL_NAME = 'gemini-1.5-flash-latest'
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except KeyError:
    st.error("Error: GOOGLE_API_KEY no configurada en Secrets.")
    st.stop()
except Exception as e:
    st.error(f"Error configurando API o Modelo Gemini: {e}")
    st.stop()

def extraer_texto_pdf(archivo_subido):
    if archivo_subido is None: return None
    try:
        texto_completo = ""
        with pdfplumber.open(io.BytesIO(archivo_subido.getvalue())) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text: texto_completo += page_text + "\n"
        return texto_completo.strip() if texto_completo else None
    except Exception as e:
        st.error(f"Error al leer PDF '{archivo_subido.name}': {e}")
        return None

# --- Carga PDF Agentes Beecker ---
st.header("1. Cargar Información de Beecker")
pdf_agentes_uploader = st.file_uploader("📄 PDF Catálogo de Agentes y Info. General de Beecker", type="pdf", key="uploader_agentes_persistente")

if pdf_agentes_uploader is not None:
    if st.session_state.nombre_archivo_agentes != pdf_agentes_uploader.name or not st.session_state.texto_agentes_beecker_actual:
        with st.spinner("Procesando PDF de Agentes Beecker..."):
            st.session_state.texto_agentes_beecker_actual = extraer_texto_pdf(pdf_agentes_uploader)
            st.session_state.nombre_archivo_agentes = pdf_agentes_uploader.name
            if st.session_state.texto_agentes_beecker_actual:
                st.success(f"PDF de Agentes '{st.session_state.nombre_archivo_agentes}' cargado y procesado.")
            else:
                st.warning("No se pudo extraer texto del PDF de Agentes Beecker o está vacío.")

if st.session_state.texto_agentes_beecker_actual:
    with st.expander("Ver Texto de Agentes Beecker (extracto)"):
        st.text(st.session_state.texto_agentes_beecker_actual[:300] + "...")

st.markdown("---")

# --- Carga Múltiple PDFs Leads ---
st.header("2. Cargar PDFs de Leads")
lista_pdfs_leads_uploader = st.file_uploader("👤 Sube uno o varios PDFs de Leads", type="pdf", accept_multiple_files=True, key="uploader_leads_multiples")

# --- Botón de Limpiar ---
if st.button("🧹 Limpiar Todo (PDFs de Beecker, Leads y Resultados)", use_container_width=True):
    keys_to_reset = [
        'texto_agentes_beecker_actual', 'nombre_archivo_agentes',
        'mensajes_generados_batch', 'archivos_leads_procesados_nombres'
    ]
    for key in keys_to_reset:
        if key in st.session_state:
            st.session_state[key] = None if key.startswith('texto_') else [] if key.endswith('_batch') or key.endswith('_nombres') else None
    # Para "limpiar" los file_uploaders visualmente, cambiar su key y rerutear es una opción,
    # o simplemente confiar en que el usuario subirá nuevos archivos.
    # Por ahora, limpiamos el estado y reruteamos.
    st.success("Se han limpiado los datos. Puedes subir nuevos archivos.")
    st.rerun()

# --- Procesamiento Batch y Generación ---
if st.session_state.texto_agentes_beecker_actual and lista_pdfs_leads_uploader:
    if st.button(f"✨ Generar Mensajes para los {len(lista_pdfs_leads_uploader)} Leads Cargados", type="primary", use_container_width=True):
        st.session_state.mensajes_generados_batch = [] # Limpiar resultados anteriores de batch
        st.session_state.archivos_leads_procesados_nombres = [] # Limpiar nombres de archivos procesados

        progress_bar = st.progress(0, text="Iniciando proceso batch...")
        total_leads = len(lista_pdfs_leads_uploader)

        for i, pdf_lead_file in enumerate(lista_pdfs_leads_uploader):
            lead_filename = pdf_lead_file.name
            progress_text = f"Procesando Lead {i+1}/{total_leads}: {lead_filename}"
            progress_bar.progress((i+1)/total_leads, text=progress_text)
            
            with st.spinner(progress_text):
                texto_lead_actual = extraer_texto_pdf(pdf_lead_file)
                st.session_state.archivos_leads_procesados_nombres.append(lead_filename)

                if texto_lead_actual:
                    contenido_para_gemini = f"""
                    --- INICIO TEXTO_AGENTES_BEECKER ---
                    {st.session_state.texto_agentes_beecker_actual}
                    --- FIN TEXTO_AGENTES_BEECKER ---

                    --- INICIO TEXTO_LEAD ---
                    {texto_lead_actual}
                    --- FIN TEXTO_LEAD ---
                    """
                    try:
                        response = model.generate_content(contenido_para_gemini)
                        respuesta_bruta = response.text
                        respuesta_limpia = respuesta_bruta.replace('**', '')
                        st.session_state.mensajes_generados_batch.append({
                            'lead_filename': lead_filename,
                            'mensaje': respuesta_limpia,
                            'error': None
                        })
                    except Exception as e:
                        st.error(f"Error con Gemini para '{lead_filename}': {e}")
                        st.session_state.mensajes_generados_batch.append({
                            'lead_filename': lead_filename,
                            'mensaje': None,
                            'error': str(e)
                        })
                else:
                    st.warning(f"No se pudo extraer texto de '{lead_filename}'. Se omitirá.")
                    st.session_state.mensajes_generados_batch.append({
                        'lead_filename': lead_filename,
                        'mensaje': None,
                        'error': 'No se pudo extraer texto del PDF.'
                    })
        progress_bar.progress(1.0, text="¡Proceso batch completado!")
        st.success(f"Procesamiento batch finalizado para {total_leads} leads.")

# --- Mostrar Resultados del Batch ---
if st.session_state.mensajes_generados_batch:
    st.markdown("---")
    st.header("📬 Mensajes de LinkedIn Generados (Batch)")
    for resultado in st.session_state.mensajes_generados_batch:
        with st.expander(f"Lead: {resultado['lead_filename']}"):
            if resultado['mensaje']:
                st.markdown(resultado['mensaje'])
                st.code(resultado['mensaje'], language=None)
            elif resultado['error']:
                st.error(f"No se pudo generar mensaje: {resultado['error']}")
            else: # Caso improbable
                st.info("No hay mensaje ni error registrado para este lead.")

elif not lista_pdfs_leads_uploader and st.session_state.texto_agentes_beecker_actual:
    st.info("ℹ️ Sube uno o varios archivos PDF de Leads para generar mensajes.")
elif not st.session_state.texto_agentes_beecker_actual:
    st.info("ℹ️ Por favor, carga primero el PDF de Agentes Beecker.")


# --- Sidebar ---
with st.sidebar:
    st.header("Instrucciones")
    st.markdown("""
    1.  Carga el **PDF de Agentes Beecker** (se recordará mientras no lo limpies).
    2.  Sube **uno o varios PDFs de Leads**.
    3.  Haz clic en **"Generar Mensajes para los X Leads Cargados"**.
    4.  Los resultados aparecerán abajo.
    5.  Usa **"Limpiar Todo"** para reiniciar (esto borrará el PDF de Agentes cargado y los resultados).
    """)
    st.markdown("---")
    st.markdown(f"Modelo en uso: `{MODEL_NAME}`")
