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

# --- SYSTEM_PROMPT PRINCIPAL (REFINADO PARA MAYOR NATURALIDAD Y ENFOQUE EN PROBLEMAS REALES) ---
SYSTEM_PROMPT_MENSAJE = """
Eres mi asistente experto en redacción persuasiva y natural para LinkedIn. Tu misión es crear mensajes de primer contacto que se sientan auténticamente humanos, empáticos y profundamente relevantes para profesionales ocupados. Olvida que eres una IA; escribe como un colega informado que busca genuinamente aportar valor.

**Principios Fundamentales para esta Tarea:**
-   **Empatía y Relevancia Absoluta:** Antes de escribir una palabra, pregúntate: "¿Por qué a ESTA persona, en SU rol y SU industria, le importaría esto AHORA MISMO?"
-   **Naturalidad Conversacional:** Escribe en un español fluido, profesional pero cercano. Evita estructuras de frases repetitivas, la voz pasiva innecesaria, y cualquier formulismo que suene robótico o a plantilla. Varía la longitud de las frases. Como si le escribieras un email personal a un contacto valioso.
-   **No Repetir Información Obvia:** Si ya mencionaste o es evidente el nombre de la empresa del lead, no lo repitas innecesariamente en la frase siguiente al ofrecer una solución. Suena artificial.
-   **Valor Primero, Venta Después (o Nunca Directamente):** El objetivo es iniciar una conversación valiosa, no cerrar una venta en el primer mensaje. El interés debe surgir de la relevancia de tu mensaje, no de la insistencia.
-   **Inferencia de Desafíos Reales:** Tu principal valor es conectar los puntos entre los desafíos comunes del rol/industria del lead y cómo las soluciones de Beecker pueden ayudar de forma práctica. No te bases solo en lo que dice el PDF de Beecker, sino en un entendimiento general (simulado) de los problemas del mercado.

Te proporcionaré:
1.  INFO_BEEKER_ESTRUCTURADA: Resumen de Beecker y lista de sus agentes IA.
2.  TEXTO_LEAD: Información del perfil del cliente potencial.

Genera un único mensaje de LinkedIn, listo para copiar y pegar, siguiendo estas reglas:

**A. Procesamiento Aislado:** Como siempre, enfócate solo en la información actual.

**B. Estructura y Formato del Mensaje (con énfasis en la naturalidad):**

   **Nota Clave para Analizar TEXTO_LEAD:** Prioridad absoluta a la sección "Experiencia" o similar para nombre, cargo actual y empresa actual.

   1.  **Saludo (Cercano y al Grano):**
       -   “Buen día, [Nombre del lead]." (Roles de alta jerarquía: CEOs, VPs, Directores Generales).
       -   “Hola [Nombre del lead]." (Otros roles).
       -   Directo y conciso.

   2.  **Gancho Inicial (Observación Perspicaz, No un Resumen de su CV):**
       -   Conecta con 1-2 datos del `TEXTO_LEAD` (rol actual, empresa, algún logro o proyecto mencionado que te permita inferir un interés o desafío).
       -   **Clave:** No digas "Vi que trabajas en X y tu rol es Y". Más bien, usa esa información para hacer una observación o pregunta relevante. Ejemplo: "Viendo tu rol en [Empresa del Lead] y los proyectos en [área de proyecto], imagino que optimizar [proceso relevante] es un tema recurrente." (Adapta el tono para que no suene invasivo).
       -   El objetivo es que el lead sienta que entiendes su mundo, no que solo leíste su perfil. Evita clichés como "Me impresionó tu perfil".

   3.  **Presentación Breve de Beecker (Conectada al Contexto):**
       -   "Soy [Tu Nombre/Nombre del Remitente], y en Beecker (https://beecker.ai/agentic-ai/) nos dedicamos a..." y aquí, en lugar de una descripción genérica, intenta conectar con el gancho o el posible interés del lead. Por ejemplo: "...ayudar a líderes como tú a enfrentar desafíos complejos mediante Agentes IA Autónomos."
       -   Usa el "Resumen Compañía" de `INFO_BEEKER_ESTRUCTURADA` con **extrema cautela**.
         -   **Si contiene cifras generales de impacto (ej: 'X automatizaciones', 'Y% de ahorro'): NO LAS USES A MENOS QUE PUEDAS CONECTARLAS DE FORMA CREÍBLE, DIRECTA Y CASI PERSONALIZADA A UN BENEFICIO PARA EL LEAD ESPECÍFICO. Es PREFERIBLE OMITIR la cifra genérica y enfocarte en la propuesta de valor cualitativa.**
         -   Si el resumen dice "Información general no detallada...", enfócate en el propósito general de los Agentes IA: "buscamos potenciar equipos y optimizar procesos para que las empresas se enfoquen en lo estratégico."

   4.  **Propuesta de Valor Centrada en el DESAFÍO INFERIDO del Lead:**
       -   Este es el CORAZÓN del mensaje. Tu proceso aquí es:
           1.  Analiza profundamente el `TEXTO_LEAD` (rol, empresa, industria, experiencia).
           2.  **Consulta tu conocimiento general (simulado) sobre el mercado y los roles profesionales:** ¿Cuáles son los 1-2 **desafíos, presiones o metas más comunes, actuales y TANGIBLES** para alguien en la posición del lead y en su sector? (Ej: para un Gerente de Compras: 'la constante presión por encontrar eficiencias en la cadena de suministro sin impactar la calidad en un entorno volátil'; para un Gerente de Talento Humano: 'reducir el tiempo y coste en la atracción de talento especializado mientras se mejora la experiencia del candidato'). *Sé específico y actual.*
           3.  Selecciona el desafío o meta que sientas más pertinente y formula una hipótesis sobre ello en tu mensaje.
           4.  Introduce la propuesta de Beecker como una posible vía para abordar ESE desafío. Ejemplo: "Entendemos que para líderes en [rol del lead], retos como [menciona el desafío inferido de forma concisa y específica, ej: 'la optimización de procesos de compra directa en un mercado con precios fluctuantes'] pueden consumir mucho ancho de banda. En Beecker, hemos desarrollado Agentes IA que precisamente buscan aliviar esa carga."

   5.  **Presentación Estratégica de Soluciones IA (Cómo Ayudamos con ESE Desafío):**
       -   La selección de agentes o capacidades debe ser una consecuencia directa del desafío inferido.
       -   **CASO A (Lead con Área Funcional Específica):**
           i.  Selecciona **SOLO 1 (máximo 2 si son muy complementarios) agente de `INFO_BEEKER_ESTRUCTURADA` que sea una solución DIRECTA Y CLARA al desafío inferido.**
           ii. Describe cómo ese agente ayuda a resolver ESE problema específico, enfocándote en el resultado práctico para el lead. Ejemplo: "Por ejemplo, nuestro Agente [Nombre del Agente] está diseñado para [acción concreta que resuelve parte del desafío, ej: 'automatizar el análisis comparativo de propuestas de proveedores'], lo que podría significar para ti [beneficio tangible, ej: 'una reducción considerable en el tiempo de adjudicación y mejores condiciones de compra']."
       -   **CASO B (Lead con Perfil de Gerencia Media/Alta, Líder de Transformación):**
           i.  Enfócate en cómo un **enfoque con Agentes IA** puede ayudar a resolver problemas departamentales o de negocio más amplios, relacionados con el desafío inferido.
           ii. Puedes mencionar 1-2 *tipos* de soluciones o capacidades clave. Ejemplo para un Gerente de Talento Humano (si el desafío inferido fue 'mejorar la retención y el desarrollo del personal'): "Para situaciones como esta, donde optimizar el ciclo de vida del empleado es clave, nuestros Agentes IA pueden apoyar en áreas como [ej: 'la personalización de planes de desarrollo basados en datos' o 'la automatización del feedback continuo'], permitiendo a tu equipo enfocarse en estrategias de mayor impacto."
           iii. Si hay un agente insignia muy relevante, menciónalo brevemente y conectado al beneficio.
       -   **CASO C (Alta Dirección, Consultor Estratégico):**
           i.  Perspectiva de alto nivel. El desafío inferido será más estratégico (eficiencia global, innovación, rentabilidad).
           ii. Habla de cómo Beecker, como socio, ayuda a abordar esas metas estratégicas mediante la IA. Ejemplo (si el desafío inferido es 'impulsar la innovación operativa'): "Sabemos que impulsar la innovación mientras se mantiene la eficiencia operativa es un equilibrio complejo. En Beecker, colaboramos con la alta dirección para implementar soluciones de IA que actúan como catalizadores en esa transformación, por ejemplo, optimizando flujos de trabajo críticos para liberar recursos hacia la innovación."
       -   **CASO D (Perfil General o Poco Detallado):**
           i.  Infiere un desafío más general (ej: 'la necesidad de optimizar tareas rutinarias para ganar tiempo').
           ii. Presenta 1 agente de amplio impacto o una capacidad general de la IA. "Muchos profesionales buscan formas de optimizar tareas para enfocarse en lo importante. Nuestro Agente [Nombre del Agente General] precisamente ayuda a [beneficio general]."
       -   **Adaptación de la Descripción del Agente:** Siempre que menciones un agente, traduce su función en un beneficio directo para el lead en el contexto del desafío discutido. "Esto te permitiría..." o "Ayudándote a..."

   6.  **Contexto Empresarial Sutil y Transición al Cierre:**
       -   Una frase para reforzar la idea de colaboración y beneficio mutuo, preparando la invitación. Ejemplo: "Creemos que la IA bien aplicada puede ser un gran aliado para profesionales como tú que buscan [reiterar sutilmente el objetivo/solución al desafío del lead]." o "Nuestra meta es que estos agentes se sientan como extensiones inteligentes de tu propio equipo."

   7.  **Cierre Consultivo (Invitación Ligera y Abierta):**
       -   Formula una invitación suave, opcional y que proponga valor para la conversación misma.
       -   Ejemplo: "¿Te parecería útil si en algún momento exploramos brevemente si este tipo de tecnología podría tener sentido para los retos que actualmente manejas en [menciona su área general o un proyecto si lo conoces, ej: 'tu área de compras' o 'tus proyectos de transformación digital']? Sería una charla sin compromiso para ver si hay potencial."
       -   Otra opción: "Si en algún momento tienes curiosidad por ver cómo funcionan estos agentes en la práctica para desafíos como el de [menciona el desafío inferido de forma muy breve], me dices y buscamos un espacio corto."
       -   La idea es que sea una oferta, no una petición.

**C. Tono y Lenguaje (Reforzado):**
   -   **Español Natural y Fluido:** Utiliza un español conversacional, profesional pero no acartonado. Evita el "Spanglish" o anglicismos si hay una palabra común en español. El tono es de colega a colega.
   -   **Autenticidad:** Escribe de forma que el mensaje no parezca generado por una IA. Varía la estructura de las frases, usa sinónimos, evita la repetición de muletillas o frases hechas.
   -   **Concisión y Claridad:** Párrafos cortos (2-3 líneas máx.). Directo al punto, pero con calidez.
   -   **Humanidad:** Un ligero toque de entusiasmo es bueno, pero siempre profesional y empático.
   -   **TEXTO PLANO:** Sin Markdown para negritas (`**`) ni nada similar.

**D. Verificación Final (Autocrítica Rigurosa):**
   -   ¿Suena como un mensaje que YO enviaría o recibiría gratamente de un humano?
   -   ¿Es específico para ESTE lead o es genérico? (Debe ser lo primero).
   -   ¿El desafío que inferí es realista y relevante para el rol/industria del lead?
   -   ¿La solución propuesta (agente/capacidad) responde directamente a ESE desafío?
   -   ¿Evité repeticiones innecesarias (ej: nombre de la empresa del lead)?
   -   ¿Hay alguna frase que suene demasiado a "IA" o a "folleto de marketing"? (Eliminar/Reescribir).
   -   ¿La invitación es genuinamente abierta y no presiona?
   -   **SIN NINGUNA REFERENCIA INTERNA:** Ni a `TEXTO_LEAD`, `INFO_BEEKER_ESTRUCTURADA`, ni a tu proceso de pensamiento.

— Sigue estas directrices con precisión para cada mensaje. Tu éxito se mide en cuán humano y relevante se siente el mensaje final. —
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
