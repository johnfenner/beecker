# Prospe/mensajes/mensajes.py

# --- Plantillas Existentes (sin cambios) ---
mensaje_1_h2r = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Quería contactarte porque sé que impulsar el crecimiento y la eficiencia en toda la organización es prioridad. En RRHH, muchas organizaciones destinan gran parte del tiempo operativo a actividades como contrataciones, onboarding o gestión de beneficios...

¿Te parecería bien agendar esta conversación esta semana?"""

mensaje_2_h2r = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. En el ciclo Hire-to-Retire suelen haber múltiples tareas manuales que se pueden automatizar con agentes de IA especializados en selección, onboarding, gestión del talento, etc.

¿Crees que tendría sentido explorarlo juntos esta semana?"""

mensaje_3_h2r = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Desde RRHH hemos visto casos donde automatizar procesos como contrataciones, onboarding y nómina libera mucho tiempo operativo y permite al equipo enfocarse en temas estratégicos.

¿Podemos agendar una rápida charla para compartirte algunos casos aplicados?"""

mensaje_1_p2p = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. En el ciclo de compras (Procure to Pay), muchos equipos enfrentan tareas repetitivas como validaciones, conciliaciones o trazabilidad de órdenes, que ralentizan la operación y generan errores...

¿Te gustaría ver algunos enfoques que ya están funcionando en empresas similares?"""

mensaje_2_p2p = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Queríamos mostrarte cómo algunas compañías están automatizando tareas clave del proceso de compras, como validación de facturas, integración con ERPs o análisis de proveedores...

¿Tendrías disponibilidad esta semana para compartirte algunos casos útiles?"""

mensaje_1_o2c = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Muchas organizaciones enfrentan cuellos de botella en su ciclo Order to Cash: errores en pedidos, aprobaciones lentas o dificultades en conciliación y facturación...

Desde nuestro equipo podríamos mostrarte cómo lo están resolviendo otras compañías del sector. ¿Te parece si coordinamos un espacio breve esta semana?"""

mensaje_2_o2c = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. En Beecker hemos trabajado con empresas que necesitaban mejorar la eficiencia y trazabilidad de sus procesos Order to Cash: validación de pedidos, integración de canales de venta, control de facturación y cobranza...

¿Crees que podríamos platicarlo esta semana en una rápida reunión?"""

mensaje_1_general = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Desde nuestro equipo hemos acompañado a organizaciones de diferentes industrias en su transformación digital, usando agentes de IA que automatizan tareas clave y generan valor estratégico...

Si te interesa conocer algunos enfoques aplicados, ¿te parece si lo conversamos esta semana?"""

mensaje_2_general = """Hola {nombre}, Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Cada vez más organizaciones están incorporando automatización inteligente en sus procesos para reducir costos, errores y tiempos de ciclo...

¿Quieres que te muestre algunos ejemplos aplicados en tu sector?"""

# --- NUEVAS PLANTILLAS "PLANTILLA_JOHN" (CON AJUSTE PARA GÉNERO) ---

# Plantilla John para H2R
plantilla_john_h2r = """Hola {nombre}, un gusto saludarte. Espero que te encuentres excelente el día de hoy.
Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Nos especializamos en Intelligent Process Automation, desarrollamos agentes digitales de IA para optimizar procesos clave como los que gestionas en [Nombre de la empresa], en los procesos Hire-to-Retire (H2R), entre otros para diferentes áreas:
- Fer: Agente de publicación de vacantes
- Lucas: Agente de captación de talento
- Isa: Agente de onboarding y documentación del empleado
- Ben: Agente de evaluación de desempeño
- Lily: Agente de procesamiento de nómina
- Lisa: Agente de gestión de viáticos
- Cleo: Agente de procesos de jubilación
¿Qué día tienes disponible esta semana para mostrarte cómo otras empresas están resolviendo esto con muy buenos resultados?
Cualquier comentario, estoy {atencion_genero} a tu respuesta."""

# Plantilla John para P2P
plantilla_john_p2p = """Hola {nombre}, un gusto saludarte. Espero que te encuentres excelente el día de hoy.
Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Nos especializamos en Intelligent Process Automation, desarrollamos agentes digitales de IA para optimizar procesos clave como los que gestionas en [Nombre de la empresa], en los procesos Procure-to-Pay (P2P), entre otros para diferentes áreas:
- Jessica: Agente de selección de proveedor
- Elsa: Agente de alta de proveedores
- Olivia: Agente de procesamiento de órdenes de compra
- Daniel: Agente de procesamiento de facturas
- David: Agente de procesamiento de órdenes de pago
¿Qué día tienes disponible esta semana para mostrarte cómo otras empresas están resolviendo esto con muy buenos resultados?
Cualquier comentario, estoy {atencion_genero} a tu respuesta."""

# Plantilla John para O2C
plantilla_john_o2c = """Hola {nombre}, un gusto saludarte. Espero que te encuentres excelente el día de hoy.
Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Nos especializamos en Intelligent Process Automation, desarrollamos agentes digitales de IA para optimizar procesos clave como los que gestionas en [Nombre de la empresa], en los procesos Order-to-Cash (O2C), entre otros para diferentes áreas:
- Nico: Agente de procesamiento de pedidos
- Diana: Agente de planificación de entregas
- James: Agente de planificación del transporte
- Julia: Agente de logística de salida
- Ryan: Agente de gestión de devoluciones
- Alice: Agente de gestión de inventarios
- Nina: Agente de cuentas por cobrar
- Aaron: Agente de facturación
- Mia: Agente de gestión del crédito
¿Qué día tienes disponible esta semana para mostrarte cómo otras empresas están resolviendo esto con muy buenos resultados?
Cualquier comentario, estoy {atencion_genero} a tu respuesta."""

# Plantilla John para General (esta es la que proviene del DOCX)
plantilla_john_general = """Hola {nombre}, un gusto saludarte. Espero que te encuentres excelente el día de hoy.
Soy {avatar}, Digital Transformation Manager en https://beecker.ai/agentic-ai/. Nos especializamos en Intelligent Process Automation, desarrollamos agentes digitales de IA para optimizar procesos clave como los que gestionas en [Nombre de la empresa], en las áreas de Hire to Retire (H2R), Order to Cash (O2C) y Procure-to-Pay (P2P).
Me gustaría mostrarte cómo nuestras soluciones pueden mejorar la eficiencia en áreas de Trayecto, tales como:
- Procurement y Compras: Validación automática de facturas con órdenes de compra, detección de discrepancias en montos y autorizaciones, análisis de rendimiento de proveedores, y optimización del ciclo Procure-to-Pay (P2P).
- Finanzas y Contabilidad: Automatización de conciliaciones bancarias, procesamiento de facturas y seguimiento de pagos, todo respaldado por inteligencia artificial avanzada.
- Recursos Humanos: Gestión automatizada de nóminas, selección de personal mediante IA y manejo eficiente de beneficios para empleados.
- Atención al Cliente: Implementación de agentes virtuales inteligentes que mejoran la experiencia del cliente y reducen tiempos de respuesta.
- Cadena de Suministro: Optimización de inventarios, automatización de pedidos y gestión de la logística con mayor precisión y control.
¿Qué día tienes disponible esta semana para mostrarte cómo otras empresas están resolviendo esto con muy buenos resultados?
Cualquier comentario, estoy {atencion_genero} a tu respuesta."""
