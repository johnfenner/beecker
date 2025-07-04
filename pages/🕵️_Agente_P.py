import streamlit as st
import google.generativeai as genai
import pdfplumber
import io
import sys
import os

# Añadir la raíz del proyecto al path
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)
       
# --- PROMPT DE EXTRACCIÓN DE AGENTES (NUEVO) ---
PROMPT_EXTRACCION_AGENTES = """
Eres un asistente de IA experto en analizar documentos técnicos y de marketing para extraer información clave de forma estructurada.
Voy a proporcionarte el contenido de un PDF que describe los agentes de IA de la compañía Beecker y posiblemente también información general sobre la empresa (TEXTO_DOCUMENTO_AGENTES).

Tu tarea es procesar este TEXTO_DOCUMENTO_AGENTES y generar un resumen estructurado que contenga dos secciones:

SECCIÓN 1: RESUMEN DE LA COMPAÑÍA BEECKER
Extrae de TEXTO_DOCUMENTO_AGENTES una breve descripción (2-3 frases) de la compañía Beecker, su propuesta de valor principal, o cualquier caso de éxito general o certificación destacada que se mencione. Si esta información no está claramente detallada o no es prominente, simplemente escribe: "Información general de la compañía no detallada en este documento."
Formato para esta sección:
Resumen Compañía: [Tu resumen extraído aquí, o la frase indicando que no hay detalle]

SECCIÓN 2: LISTA DETALLADA DE AGENTES DE IA
Identifica y lista TODOS los agentes de IA distintos mencionados en el TEXTO_DOCUMENTO_AGENTES. Para cada agente, proporciona la siguiente información en el formato exacto especificado a continuación. Separa la información de cada agente con una línea en blanco.

Formato para cada agente en la SECCIÓN 2:
Agente: [Nombre público y completo del agente, tal como debería verlo un cliente. Evita nombres de código internos si es posible.]
Descripción: [Una descripción concisa y clara, en 1-2 frases, de la función principal del agente y los beneficios clave que ofrece. Enfócate en el valor para el usuario final.]
Áreas Relevantes: [Una lista concisa separada por comas de las áreas funcionales, industrias o tipos de problemas para los que este agente es más adecuado (ej: Recursos Humanos, Reclutamiento, Finanzas, Automatización de Compras, Soporte TI, Cadena de Suministro).]

Consideraciones importantes para tu respuesta:
-   En la SECCIÓN 2, sé exhaustivo; incluye todos los agentes que puedas identificar.
-   Los nombres de los agentes deben ser los más orientados al cliente que encuentres.
-   Las descripciones deben ser concisas y enfocadas en beneficios.
-   No añadas ninguna introducción, conclusión, saludo o comentario tuyo fuera del formato estructurado solicitado. Tu respuesta debe comenzar directamente con "Resumen Compañía:" o con "Agente:" si no hay resumen de compañía.

Ahora, procesa el TEXTO_DOCUMENTO_AGENTES que te será proporcionado.
"""

# --- SYSTEM_PROMPT PRINCIPAL (RESTAURADO A LA BASE DEL ARCHIVO Y CON MEJORAS DE NATURALIDAD/ENFOQUE EN PROBLEMAS) ---
SYSTEM_PROMPT_MENSAJE = """
Eres mi asistente experto en redacción persuasiva para LinkedIn.
Te proporcionaré la siguiente información:
1.  INFO_BEEKER_ESTRUCTURADA: Contiene un breve resumen de la compañía Beecker y una lista estructurada de sus agentes de IA (con nombre, descripción y áreas relevantes). Esta es tu base de conocimiento sobre Beecker.
2.  TEXTO_LEAD: Contiene la información extraída del PDF de un cliente potencial.

Cada vez que recibas esta información, generarás un único mensaje de LinkedIn listo para copiar y pegar, dirigido al LEAD, siguiendo estas reglas al pie de la letra:

**Principios Adicionales para tu Redacción (Importante para evitar sonar a IA):**
-   **Naturalidad Ante Todo:** Escribe como un humano se dirigiría a otro en un contexto profesional pero cercano. Evita formulismos, la voz pasiva innecesaria y estructuras de frase repetitivas. Varía la longitud de tus frases.
-   **Evita la Redundancia:** No repitas información que el lead ya sabe o que es obvia (ej. su propia empresa si la acabas de mencionar para conectar la solución).
-   **Inferencia de Problemas del Lead:** Aunque te bases en `INFO_BEEKER_ESTRUCTURADA` para las soluciones, tu habilidad especial es inferir primero un posible desafío o necesidad del lead (basado en su rol, industria, y tu conocimiento general del mundo profesional) y LUEGO conectar cómo Beecker puede ayudar.
-   **Uso Criterioso de Datos de `INFO_BEEKER_ESTRUCTURADA`:** El resumen de la compañía y las descripciones de agentes son tu fuente, pero no los copies textualmente. Transfórmalos en un lenguaje persuasivo y adaptado al lead. Las cifras generales de Beecker úsalas solo si son impactantes Y directamente relevantes al problema inferido del lead; si no, es mejor omitirlas.

**Reglas de Procesamiento y Formato:**

**A. Procesamiento Aislado**
   - Olvida cualquier información de leads o textos anteriores.
   - Trabaja únicamente con la INFO_BEEKER_ESTRUCTURADA y el TEXTO_LEAD que recibas en este momento.

**B. Estructura y Formato del Mensaje**

   **Nota Clave para Analizar TEXTO_LEAD:** Para identificar el nombre del lead, su cargo actual y la empresa actual, debes buscar y dar **prioridad absoluta** a la información que encuentres bajo encabezados explícitos como "Experiencia", "Experience", "Experiencia Profesional" o "Professional Experience" dentro del TEXTO_LEAD. La información que aparece al inicio del PDF (como un titular o resumen) a veces puede no ser la más actualizada o precisa para estos detalles; la sección de 'Experiencia' es la fuente más confiable.

   1.  **Saludo**
       - “Buen día, [Nombre del lead, obtenido según la 'Nota Clave para Analizar TEXTO_LEAD']." (Si el rol actual del lead, obtenido según la 'Nota Clave', indica CEOs, VPs)
       - “Hola [Nombre del lead, obtenido según la 'Nota Clave para Analizar TEXTO_LEAD']." (para otros roles actuales del lead, obtenidos según la 'Nota Clave')

   2.  **Gancho Inicial (Conciso y Relevante)**
       - Conecta con 1–2 datos concretos y muy breves del TEXTO_LEAD (rol actual y empresa actual –obtenidos según la 'Nota Clave'– o un logro destacado/proyecto reciente mencionado en su sección de 'Experiencia').
       - **Importante:** Analiza la experiencia del lead (TEXTO_LEAD, especialmente la sección 'Experiencia') para personalizar la propuesta, pero NO detalles extensamente sus trabajos o proyectos anteriores en el mensaje. El objetivo es un gancho rápido y pertinente, no un resumen de su CV. Haz que se sienta como una observación inteligente, no como una repetición de su perfil.
       - No uses “Vi tu perfil…”, “Me impresionó…”, ni referencias genéricas.

   3.  **Presentación Orgánica de Beecker**
       - Comienza con: “En Beecker (https://beecker.ai/agentic-ai/) acompañamos a empresas con Agentes IA Autónomos…”
       - A continuación, utiliza el "Resumen Compañía" que se encuentra al inicio de INFO_BEEKER_ESTRUCTURADA.
         - Si este resumen contiene casos de éxito específicos, áreas de impacto clave o certificaciones que sean relevantes para el TEXTO_LEAD (considerando su rol e industria), incorpóralos de forma breve y natural.
         - **Precaución con cifras generales:** Si el "Resumen Compañía" incluye cifras de impacto muy generales (ej: "hemos realizado X automatizaciones"), úsalas solo si puedes conectarlas de forma MUY CREÍBLE y directa a un beneficio para el lead específico. De lo contrario, ES PREFERIBLE OMITIRLAS y enfocarte en la propuesta de valor cualitativa.
         - Si el "Resumen Compañía" en INFO_BEEKER_ESTRUCTURADA indica "Información general de la compañía no detallada...", entonces centra esta parte de la presentación en la relevancia y el valor general que los Agentes IA Autónomos pueden aportar al tipo de empresa o al rol del lead, basándote en la lista de agentes en INFO_BEEKER_ESTRUCTURADA.

   4.  **Propuesta de Valor (Conectando el Desafío Inferido del Lead con Beecker)**
       - Párrafo breve que vincule un **reto actual plausible del lead** (inferido de su `TEXTO_LEAD`, su rol, industria, y tu conocimiento general de los desafíos profesionales comunes para esos perfiles) con el **beneficio concreto** que una aproximación como la de Beecker con IA podría ofrecerle.
       - Ejemplo de Inferencia: Si es un Gerente de Compras, un reto podría ser "la optimización de costos en un mercado volátil". Si es de RRHH, "la agilización de procesos de reclutamiento para perfiles técnicos escasos".
       - Redacta esta conexión de forma natural, por ejemplo: "Entendemos que para profesionales en [rol del lead], desafíos como [desafío inferido específico y breve] suelen ser prioritarios. Es en este tipo de escenarios donde la IA puede ofrecer un apoyo significativo."

   5.  **Propuesta de Agentes IA Relevantes (Adaptada al Perfil del Lead y al Desafío Inferido):**
       - El objetivo es presentar una selección concisa y altamente relevante de cómo los Agentes IA de Beecker pueden ayudar, en lugar de una lista exhaustiva. Siempre conecta la presentación del agente con la solución a un problema o la consecución de un objetivo del lead.

       - **Paso 1: Análisis Detallado del Lead y su Contexto:** (Como ya lo tienes definido)
         - Examina el `TEXTO_LEAD`, prestando especial atención a la sección 'Experiencia' (y también al 'Extracto' o 'About') para determinar:
           a. El **área funcional principal** del lead.
           b. Sus **responsabilidades clave, logros y posibles desafíos** o áreas de enfoque.
           c. La **industria o tipo de empresa**, si es discernible.

       - **Paso 2: Estrategia de Presentación de Soluciones IA según el Perfil:**

         - **CASO A: Lead con Área Funcional Específica (ej: HR, Finanzas, Compras Directas, Ventas específicas, Cadena de Suministro detallada):**
           i.  Revisa la "LISTA DETALLADA DE AGENTES DE IA" en `INFO_BEEKER_ESTRUCTURADA`.
           ii. Selecciona **un máximo de 2-3 de los agentes MÁS RELEVANTES** cuyas 'Áreas Relevantes' coincidan directamente con el área funcional principal del lead y que aborden el desafío inferido en la "Propuesta de Valor" o necesidades evidentes de su rol.
           iii. Para cada agente seleccionado, usa el formato: `- [Nombre del Agente]: [Aquí, en lugar de solo copiar la descripción de INFO_BEEKER_ESTRUCTURADA, REDACTA una descripción adaptada (1-2 frases) de su función/beneficio enfocada en CÓMO resuelve un problema o aporta valor al ÁREA ESPECÍFICA del lead. Por ejemplo: 'que te ayudaría a optimizar [proceso clave del lead] al [acción principal del agente], liberando tiempo para [actividad estratégica del lead].']`

         - **CASO B: Lead con Perfil Amplio, Técnico, de Consultoría o Estratégico (ej: IT, Transformación Digital, Innovación, Project Manager en tecnología, Consultor, Business Development enfocado en tecnología):**
           i.  En lugar de listar múltiples agentes individuales, enfócate en presentar cómo la **aproximación general de Beecker con Agentes IA** puede abordar los desafíos típicos de estos roles (conectando con el desafío inferido en "Propuesta de Valor").
           ii. Menciona **1 o 2 ejemplos de *tipos* de soluciones o *capacidades clave* de los Agentes IA de Beecker** que resuenen con sus responsabilidades (ej: "la automatización inteligente de flujos de trabajo complejos en TI que vemos que gestionas", "la optimización de la gestión de datos para agilizar la toma de decisiones estratégicas en proyectos de innovación").
           iii. **Opcionalmente, y solo si hay 1 (máximo 2) agente insignia que sea EXCEPCIONALMENTE relevante y de amplio impacto para este tipo de perfil técnico/estratégico**, puedes mencionarlo brevemente: `- Por ejemplo, nuestro [Agente Insignia] está diseñado para ayudar a perfiles como el tuyo a [beneficio clave para un rol técnico/estratégico].` La preferencia es describir capacidades o enfoques generales.
           iv. La redacción aquí debe ser más sobre el "cómo Beecker ayuda a perfiles como el tuyo a..." en lugar de una lista de productos. Evita abrumar con una larga lista de agentes. El mensaje debe sonar técnico y estratégico, no como un catálogo.

         - **CASO C: Lead con Perfil Muy General o Poco Detallado (donde el área funcional o los desafíos no son claros tras el análisis):**
           i.  Selecciona **1-2 agentes de la `INFO_BEEKER_ESTRUCTURADA` que tengan 'Áreas Relevantes' amplias** o que representen soluciones de alto impacto general y fácil comprensión (ej: un agente de automatización de tareas comunes o uno de análisis de datos general).
           ii. Presenta estos agentes con el formato: `- [Nombre del Agente]: [REDACTA una descripción concisa de su beneficio general, idealmente conectada a un desafío universal como 'optimizar el tiempo' o 'mejorar la eficiencia en tareas X'. Ejemplo: 'que puede ser un gran aliado para simplificar [tipo de tarea general] y así permitir un mayor enfoque en [objetivo deseable].']`

       - **Paso 3: Adaptación de la Descripción del Agente (cuando se mencionan agentes por nombre):**
         - Para CADA agente que menciones por nombre (principalmente en CASO A y C, y opcionalmente en B):
           i.  Utiliza el **Nombre del Agente** exacto tal como aparece en la lista estructurada.
           ii. Toma su 'Descripción' de la lista estructurada como BASE y ADÁPTALA significativamente (1 frase concisa) para resaltar cómo específicamente podría ayudar al lead o a su departamento/empresa, conectándolo con el perfil del lead y los desafíos inferidos. **Enfócate en el resultado y el valor para el lead.**
           iii. **MUY IMPORTANTE:** La presentación debe ser limpia y profesional. No incluyas ninguna meta-referencia. Simplemente enuncia el nombre del agente y su valor adaptado.

       - **Consideración General para Todos los Casos:**
         - El objetivo no es vender cada agente, sino demostrar entendimiento del rol del lead y cómo Beecker puede aportar valor estratégico. La selección debe ser cualitativa y concisa.

   6.  **Contexto Empresarial y Transición al Cierre**
       - En un párrafo breve (idealmente 1-2 frases concisas), refuerza que la propuesta de Agentes IA es para la empresa del lead, enfocándote en cómo actúan como “extensiones inteligentes de su equipo” para liberar recursos y mejorar resultados en sus proyectos o área de responsabilidad.
       - Este párrafo debe fluir naturalmente hacia la invitación que vendrá inmediatamente después, idealmente preparando el terreno para ella.

   7.  **Cierre Consultivo (Invitación)**
       - En un nuevo párrafo corto, formula una invitación clara, completa y suave para una conversación. Esta debe ser una frase bien construida, típicamente una pregunta.
       - Ejemplo de estructura para la invitación: "¿Te parecería una buena idea si agendamos un espacio breve para que conozcas más sobre estas tecnologías? Podríamos evaluar juntos cómo esta propuesta podría aportar valor específicamente a [menciona aquí el área de responsabilidad del lead, los objetivos de su equipo, o un desafío/proyecto clave que se infiera del TEXTO_LEAD para su empresa actual. Por ejemplo: 'tus proyectos de transformación digital en [Empresa del Lead]', 'la eficiencia operativa de tu equipo en [Empresa del Lead]', o 'tus objetivos de [mencionar área específica] en [Empresa del Lead]'].”
       - **Crucial:** La invitación debe ser una pregunta completa o una propuesta formulada de manera que sea una oración gramaticalmente correcta. Evita imperativos directos o infinitivos sueltos como inicio de la invitación (ej. no empezar solo con "Agendar...").
       - El objetivo es sonar consultivo y abierto, no una venta agresiva.
       - **Consideración especial si el lead trabaja en Beecker (la misma compañía que el remitente):** Adapta el "aportar valor a..." para que se refiera a los objetivos específicos del lead o su departamento *dentro* de Beecker. Por ejemplo: "...aportar valor a tus iniciativas en el departamento de [Nombre del Dept.]" o "...a tus estrategias de crecimiento para Beecker desde tu rol."

**C. Tono y Lenguaje**
   - Español, tuteo, humano, orgánico, profesional y cercano.
   - Ligero toque entusiasta, sin jerga técnica excesiva (evita “sprints”, “scripts” a menos que el perfil del lead sea altamente técnico y sea su lenguaje común).
   - Párrafos de 2–3 líneas máximo, saltos de línea claros. Mensajes concisos y directos.
   - **IMPORTANTE: Todo el mensaje debe ser generado en TEXTO PLANO. No utilices formato Markdown como asteriscos dobles (`**`) para simular negritas ni ningún otro tipo de formato especial que no sea texto simple y saltos de línea.**
   - **Naturalidad Clave:** Evita construcciones que suenen artificiales o robóticas. Pregúntate: "¿Un humano escribiría esto así?". Varía la estructura de las frases.

**D. Verificación Final**
   - Asegúrate de usar solo datos del TEXTO_LEAD y de la INFO_BEEKER_ESTRUCTURADA (esta última como base para elaborar, no para copiar).
   - Confirma que los nombres de los Agentes en tu mensaje coincidan con la INFO_BEEKER_ESTRUCTURADA, pero que sus descripciones en el mensaje sean ADAPTADAS Y PERSUASIVAS.
   - Revisa que el mensaje transmita valor empresarial, no personal, y que la invitación sea consultiva.
   - ¿El mensaje suena natural y evita repeticiones innecesarias?
   - ¿Conecta claramente con un desafío inferido del lead?
   - El mensaje final debe ser breve, fácil de leer en LinkedIn y en **texto plano sin formato Markdown para negritas.**
   - **CRUCIAL: El mensaje final NO DEBE CONTENER ninguna nota interna, comentarios sobre tu proceso de pensamiento, referencias a los nombres de los bloques de texto de origen (como 'TEXTO_AGENTES_BEECKER', 'TEXTO_LEAD', 'INFO_BEEKER_ESTRUCTURADA'), ni frases como '(similar a X en el documento Y)'. La redacción debe ser fluida, natural y profesional, lista para ser sentada directamente al lead.**
   - Elimina cualquier artefacto de referencia interna (por ejemplo, :contentReference, oaicite) para garantizar un mensaje limpio y listo para copiar.

— A partir de ahora, sigue exactamente este prompt y estas reglas para cada conjunto de textos que te envíe. —
"""

# --- INICIALIZACIÓN DE VARIABLES DE SESIÓN ---
if 'info_beecker_estructurada' not in st.session_state: # NUEVO: para la info de Beecker pre-procesada
    st.session_state.info_beecker_estructurada = None
if 'nombre_archivo_agentes' not in st.session_state:
    st.session_state.nombre_archivo_agentes = None
if 'mensajes_generados_batch' not in st.session_state:
    st.session_state.mensajes_generados_batch = []

# --- CÓDIGO DE LA APLICACIÓN STREAMLIT ---

# Ruta de la imagen (asegúrate de que project_root esté definido)
FOTO_ORNITORRINCO_PATH = os.path.join(project_root, "ornitorrinco.png") # Recuerda que habíamos dicho que el nombre real era 'logo.jpeg'

# ─────────────────────────────────────────────
#  Imagen + título en línea
# ─────────────────────────────────────────────
# Tres columnas para equilibrar: pequeña – contenido – pequeña
col_left, col_mid, col_right = st.columns([1, 6, 1])

with col_mid:
    # Dentro del centro creamos dos columnas: imagen | títulos
    col_img, col_txt = st.columns([1, 4])

     # Imagen (columna izquierda)
    with col_img:
        try:
            st.image(FOTO_ORNITORRINCO_PATH, width=120)
            # Modificación para el texto "Agente P"
            st.markdown(
                "<p style='text-align: center; font-weight: bold;'>Agente P</p>",
                unsafe_allow_html=True
            )
        except FileNotFoundError:
            st.warning("⚠️ Foto del ornitorrinco no encontrada. Verifica la ruta.")
        except Exception as e:
            st.error(f"Error al cargar la foto: {e}")

    # Títulos (columna derecha)
    with col_txt:
        st.markdown(
            "## Generador IA de Mensajes para prospectos en LinkedIn 🤖",
            unsafe_allow_html=False,
        )
        st.markdown(
            "#### Sube el PDF de Agentes Beecker (se pre-procesará con IA) y luego múltiples PDFs de Leads.",
            unsafe_allow_html=False,
        )

# Separador
st.markdown("---")

# --- Configuración de API Key y Modelo ---
try:
    GEMINI_API_KEY = st.secrets["GOOGLE_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    MODEL_NAME = 'gemini-1.5-flash-latest'
    # Modelo para la generación principal de mensajes
    model_mensajes = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT_MENSAJE)
    # Modelo para la extracción de información de agentes (podría ser el mismo o uno más simple si se quisiera optimizar)
    # Usaremos el mismo modelo por simplicidad, pero con su propio prompt.
    # No se le pasa system_instruction aquí, se le pasará el PROMPT_EXTRACCION_AGENTES como parte del contenido.
    model_extraccion = genai.GenerativeModel(MODEL_NAME)

except KeyError:
    st.error("Error: GOOGLE_API_KEY no configurada en Secrets.")
    st.stop()
except Exception as e:
    st.error(f"Error configurando API o Modelo Gemini: {e}")
    st.stop()

def extraer_texto_pdf_crudo(archivo_subido): # Renombrado para claridad
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

# --- Etapa 1: Carga y Pre-procesamiento del PDF de Agentes Beecker ---
st.header("Etapa 1: Cargar y Procesar Información de Beecker")
pdf_agentes_uploader = st.file_uploader("📄 Sube aquí el PDF de Agentes Beecker", type="pdf", key="uploader_agentes_etapa1")

if pdf_agentes_uploader is not None:
    if st.session_state.nombre_archivo_agentes != pdf_agentes_uploader.name or not st.session_state.info_beecker_estructurada:
        st.session_state.nombre_archivo_agentes = pdf_agentes_uploader.name # Actualizar nombre antes de procesar
        st.session_state.info_beecker_estructurada = None # Limpiar info anterior
        st.session_state.mensajes_generados_batch = [] # Limpiar resultados de batch si el doc de agentes cambia

        with st.spinner(f"Analizando PDF de Agentes '{pdf_agentes_uploader.name}' con IA para extraer estructura... (esto puede tardar un momento)"):
            texto_agentes_bruto = extraer_texto_pdf_crudo(pdf_agentes_uploader)
            if texto_agentes_bruto:
                try:
                    # Llamada a Gemini para extraer y estructurar la info de agentes
                    prompt_completo_extraccion = PROMPT_EXTRACCION_AGENTES + "\n\nTEXTO_DOCUMENTO_AGENTES:\n" + texto_agentes_bruto
                    response_extraccion = model_extraccion.generate_content(prompt_completo_extraccion)
                    st.session_state.info_beecker_estructurada = response_extraccion.text.strip()
                    st.success(f"Información de Beecker procesada y estructurada desde '{pdf_agentes_uploader.name}'.")
                except Exception as e:
                    st.error(f"Error al extraer información del PDF de Agentes con IA: {e}")
                    st.session_state.info_beecker_estructurada = None # Asegurar que esté Nulo si falla
            else:
                st.warning("No se pudo extraer texto del PDF de Agentes para el pre-procesamiento.")
                st.session_state.info_beecker_estructurada = None

if st.session_state.info_beecker_estructurada:
    with st.expander("Ver Información Estructurada de Beecker (Resultado del Pre-procesamiento)", expanded=False):
        st.text_area("Info Estructurada:", st.session_state.info_beecker_estructurada, height=300)
else:
    st.info("Esperando el PDF de Agentes Beecker para el pre-procesamiento inicial con IA.")

st.markdown("---")

# --- Etapa 2: Carga Múltiple PDFs Leads y Generación de Mensajes ---
st.header("Etapa 2: Cargar PDFs de Leads y Generar Mensajes")
lista_pdfs_leads_uploader = st.file_uploader("👤 Sube uno o varios PDFs de Leads", type="pdf", accept_multiple_files=True, key="uploader_leads_etapa2", disabled=not st.session_state.info_beecker_estructurada)

# --- Botón de Limpiar ---
if st.button("🧹 Limpiar Todo (PDFs y Resultados)", use_container_width=True):
    keys_to_reset = ['info_beecker_estructurada', 'nombre_archivo_agentes', 'mensajes_generados_batch']
    for key_to_reset in keys_to_reset:
        if key_to_reset in st.session_state:
            st.session_state[key_to_reset] = [] if key_to_reset == 'mensajes_generados_batch' else None
    st.success("Se han limpiado los datos. Puedes subir nuevos archivos.")
    st.rerun()

# --- Procesamiento Batch y Generación ---
if st.session_state.info_beecker_estructurada and lista_pdfs_leads_uploader:
    if st.button(f"✨ Generar Mensajes para los {len(lista_pdfs_leads_uploader)} Leads Cargados", type="primary", use_container_width=True):
        st.session_state.mensajes_generados_batch = [] # Limpiar resultados anteriores de batch
        progress_bar = st.progress(0, text="Iniciando proceso batch...")
        total_leads = len(lista_pdfs_leads_uploader)
        resultados_actuales_batch = []

        for i, pdf_lead_file in enumerate(lista_pdfs_leads_uploader):
            lead_filename = pdf_lead_file.name
            progress_text = f"Procesando Lead {i+1}/{total_leads}: {lead_filename}"
            progress_bar.progress(float(i) / total_leads, text=progress_text)
            
            resultado_placeholder = st.empty()
            spinner_message = resultado_placeholder.info(f"🔄 Procesando: {lead_filename}...")

            texto_lead_actual = extraer_texto_pdf_crudo(pdf_lead_file)

            if texto_lead_actual:
                contenido_para_gemini = f"""
                --- INICIO INFO_BEEKER_ESTRUCTURADA ---
                {st.session_state.info_beecker_estructurada}
                --- FIN INFO_BEEKER_ESTRUCTURADA ---

                --- INICIO TEXTO_LEAD ---
                {texto_lead_actual}
                --- FIN TEXTO_LEAD ---
                """
                try:
                    # Usamos model_mensajes que tiene el SYSTEM_PROMPT_MENSAJE
                    response_mensaje = model_mensajes.generate_content(contenido_para_gemini)
                    respuesta_bruta = response_mensaje.text
                    respuesta_limpia = respuesta_bruta.replace('**', '')
                    resultados_actuales_batch.append({
                        'lead_filename': lead_filename,
                        'mensaje': respuesta_limpia,
                        'error': None
                    })
                    spinner_message.success(f"✅ Mensaje generado para: {lead_filename}")
                except Exception as e:
                    error_msg = f"Error con Gemini para '{lead_filename}': {e}"
                    st.error(error_msg)
                    resultados_actuales_batch.append({'lead_filename': lead_filename, 'mensaje': None, 'error': str(e)})
                    spinner_message.error(f"❌ Error al generar para: {lead_filename}")
            else:
                warning_msg = f"No se pudo extraer texto de '{lead_filename}'. Se omitirá."
                st.warning(warning_msg)
                resultados_actuales_batch.append({'lead_filename': lead_filename, 'mensaje': None, 'error': 'No se pudo extraer texto del PDF.'})
                spinner_message.warning(f"⚠️ Omitido (sin texto): {lead_filename}")
            
            progress_bar.progress(float(i+1) / total_leads, text=progress_text if i+1 < total_leads else "Finalizando...")

        st.session_state.mensajes_generados_batch = resultados_actuales_batch
        progress_bar.progress(1.0, text="¡Proceso batch completado!")
        st.success(f"Procesamiento batch finalizado.")
        st.balloons()

# --- CÓDIGO DE LA APLICACIÓN STREAMLIT ---
# ... (todo tu código anterior permanece igual hasta la sección de mostrar resultados) ...

# --- Mostrar Resultados del Batch ---
if st.session_state.mensajes_generados_batch:
    st.markdown("---")
    st.header("📬 Mensajes de LinkedIn Generados (Batch)")

    for i, resultado in enumerate(st.session_state.mensajes_generados_batch):
        st.subheader(f"Lead: {resultado['lead_filename']}")
        if resultado['mensaje']:
            st.markdown("**Mensaje Original Generado:**")
            st.code(resultado['mensaje'], language=None)

            # --- Funcionalidad de Replantear Mensaje ---
            st.markdown("---") 

            input_instruccion_key = f"input_instruccion_{resultado['lead_filename']}_{i}"
            boton_replantear_key = f"boton_replantear_{resultado['lead_filename']}_{i}"
            
            if input_instruccion_key not in st.session_state:
                st.session_state[input_instruccion_key] = ""

            # El widget st.text_input actualiza st.session_state[input_instruccion_key] automáticamente.
            # La variable instruccion_usuario recibe el valor actual del campo de texto.
            instruccion_usuario = st.text_input(
                "Si quieres, describe aquí cómo refinar el mensaje de arriba:",
                value=st.session_state[input_instruccion_key], 
                key=input_instruccion_key, 
                placeholder="Ej: Hazlo más corto y directo, enfatiza mi experiencia en IA."
            )
            
            # LA SIGUIENTE LÍNEA ERA EL PROBLEMA Y SE HA ELIMINADO:
            # st.session_state[input_instruccion_key] = instruccion_usuario <--- ELIMINADA

            if st.button("🔄 Replantear este Mensaje con IA", key=boton_replantear_key, use_container_width=True):
                # Ahora usamos 'instruccion_usuario' directamente, que ya tiene el valor del input.
                # O podríamos usar st.session_state[input_instruccion_key] si preferimos.
                if instruccion_usuario: 
                    mensaje_original_para_replantear = resultado['mensaje']
                    
                    prompt_refinamiento = f"""Eres un asistente de IA experto en redacción persuasiva para LinkedIn.
Aquí tienes un mensaje que necesita ser ajustado:
--- MENSAJE ORIGINAL ---
{mensaje_original_para_replantear}
--- FIN MENSAJE ORIGINAL ---

Por favor, modifica este MENSAJE ORIGINAL basándote en la siguiente instrucción del usuario:
--- INSTRUCCIÓN DEL USUARIO ---
{instruccion_usuario}
--- FIN INSTRUCCIÓN DEL USUARIO ---

Asegúrate de que el mensaje resultante siga siendo apropiado para LinkedIn, profesional, en texto plano y sin artefactos de Markdown para negritas.
Mantén el tuteo (tratar de "tú") y el tono general humano, orgánico, profesional y cercano que se te solicitó originalmente, a menos que la instrucción del usuario pida explícitamente un cambio de tono.
El mensaje debe ser conciso y directo, con párrafos de 2-3 líneas máximo si es posible.
No añadas introducciones o conclusiones tuyas como "Aquí está el mensaje modificado:", "Claro, aquí tienes el ajuste:", etc. Simplemente proporciona el mensaje replanteado y listo para copiar y pegar.
"""
                    with st.spinner(f"Replanteando mensaje para '{resultado['lead_filename']}'..."):
                        try:
                            response_refinamiento = model_mensajes.generate_content(prompt_refinamiento)
                            mensaje_refinado_bruto = response_refinamiento.text
                            mensaje_refinado_limpio = mensaje_refinado_bruto.replace('**', '').strip()

                            st.session_state.mensajes_generados_batch[i]['mensaje_refinado'] = mensaje_refinado_limpio
                            st.session_state.mensajes_generados_batch[i]['instruccion_refinamiento_usada'] = instruccion_usuario
                            
                            # Opcional: Limpiar el campo de instrucción después de usarlo.
                            # Si deseas que el campo se limpie, descomenta la siguiente línea:
                            # st.session_state[input_instruccion_key] = ""
                            
                            st.rerun()

                        except Exception as e:
                            st.error(f"Error al refinar el mensaje con IA para '{resultado['lead_filename']}': {e}")
                else:
                    st.warning("Por favor, escribe una instrucción para poder replantear el mensaje.")
                    if 'mensaje_refinado' in st.session_state.mensajes_generados_batch[i]:
                        del st.session_state.mensajes_generados_batch[i]['mensaje_refinado']
                    if 'instruccion_refinamiento_usada' in st.session_state.mensajes_generados_batch[i]:
                        del st.session_state.mensajes_generados_batch[i]['instruccion_refinamiento_usada']
                    st.rerun()

            if 'mensaje_refinado' in resultado and resultado.get('instruccion_refinamiento_usada'):
                st.markdown("**Mensaje Replanteado:**")
                st.caption(f"Basado en tu instrucción: \"{resultado['instruccion_refinamiento_usada']}\"")
                st.code(resultado['mensaje_refinado'], language=None)

        elif resultado['error']:
            st.error(f"No se pudo generar mensaje: {resultado['error']}")
        st.markdown("---")
# ... (resto del código)
# --- Sidebar ---
with st.sidebar:
    st.header("Instrucciones")
    st.markdown("""
    **Etapa 1:**
    1. Carga el **PDF de Agentes Beecker**. La IA lo analizará para extraer una lista estructurada de agentes y un resumen de la compañía. Esto puede tomar un momento.
    
    **Etapa 2:**

    2. Una vez procesada la información de Beecker, sube **uno o varios PDFs de Leads**.
    3. Haz clic en **"Generar Mensajes..."**.
    4. Los mensajes aparecerán en la página principal.
    
    Usa **"Limpiar Todo..."** para reiniciar el proceso completo (se borrará la información de Beecker procesada y los resultados).
    """)
    st.markdown("---")
    st.markdown(f"Modelo IA en uso: `{MODEL_NAME}`")
