# Avance de implementación

## Verificado

- Angular compila y está conectado a FastAPI.
- Analista con LangGraph, persistencia PostgreSQL y checkpoints.
- Conexión real a `gpt-4.1-mini` de Azure mediante Responses API.
- JSON Schema estricto, respuesta progresiva y conversación de dos turnos con modificación de requisitos.
- 16 pruebas Python sin inferencia aprobadas en la configuración sin reranker; también se verificaron conversaciones reales con Azure y checkpoints sobre la base separada `fabrica_test`.
- 3 pruebas del lector SSE del frontend aprobadas.
- Revisado el chat en el navegador: una respuesta real de Azure aparece y persiste.
- Corpus actual reindexado mediante Azure `text-embedding-3-small`: 98 documentos y 401 fragmentos, sin fallos. Vectores de 1536 dimensiones almacenados en PostgreSQL/pgvector.
- Búsqueda híbrida por API verificada: reformulación Azure, embeddings Azure, pgvector + BM25 y RRF. Contrato de recuperación 1.1, sin reranker ni degradaciones.
- Conversación documental completa verificada con GPT-4.1 mini: recuperó cinco fragmentos, respondió con documentos y páginas, y no creó propuestas de requisitos a partir de la consulta informativa.
- Inferencia local retirada del código, dependencias y arranque. Ollama detenido y su contenedor de este proyecto retirado.

## Verificación del RAG mediante APIs completada

El usuario autorizó expresamente enviar el texto de los 98 PDF al recurso Azure suministrado para generar y guardar sus embeddings. Después de esa autorización se completó la actualización de todos los documentos y se verificó la recuperación y la respuesta del analista.

Los resultados reales, sin credenciales, están en `output/verificacion_real.json` y `output/verificacion_chat_rag_azure.json`. No contienen datos simulados; la carpeta de resultados está ignorada por Git.

Las búsquedas BM25/pgvector, RRF, actualizaciones, borrados y degradaciones tienen pruebas. La configuración actual completa utiliza Azure para toda inferencia y se verificó de extremo a extremo. El reranker fue retirado del alcance por decisión del usuario; no es una integración pendiente.

La aplicación conserva eventos reales de las verificaciones, incluidos errores y correcciones. Ningún resultado de prueba se presenta como aprobación humana de requisitos del usuario.

## Fase 2 implementada

Backlog funcional con organizador, agente de historias y validador por Azure; revisiones y publicaciones inmutables, edición, decisiones e historial. Ver guía FASE_2.md. Verificación final: 36 pruebas sin inferencia aprobadas y prueba real de los tres agentes en Azure aprobada con datos sintéticos en fabrica_test. Mockups pendientes de una fase posterior.

## Fase 3 implementada

Diseñador y validador con LangGraph, visor declarativo, navegación simulada, revisión por pantalla, versiones inmutables y decisiones humanas. Pruebas sin llamadas al modelo: 50 aprobadas, incluyendo API, auditoría y reanudación desde checkpoints. Detalles y límites en FASE_3.md.

Refuerzo preventivo de fase 3: normalización auditable, prevalidación antes del validador, límite compartido de corrección y rechazo de contratos técnicos inválidos sin crear propuestas rotas. Pruebas de resiliencia con modelos simulados y proveedor HTTP simulado; cero llamadas reales en esta verificación.

## Fase 4 implementada

Arquitectura con LangGraph: arquitecto de software (atributos de calidad, ADR con tradeoffs, monolito, C4), arquitecto de infraestructura (local con Docker Compose y nube en AWS EKS), reglas deterministas, validador semántico, una corrección dirigida al agente responsable y planificador de tareas técnicas. Diagramas (C4, despliegue, secuencia, flujo), `.drawio`, `docker-compose.yml`, `k8s.yaml` y guía del desarrollador generados con código, sin tokens ni bibliotecas nuevas. Consumo real de tokens y tiempo por agente visible en la interfaz. Pruebas sin red: 52 aprobadas. Detalles en FASE_4.md.

## Fase 5 implementada

Red de agentes de construcción con LangGraph: desarrolladores de datos, backend (FastAPI) y frontend (Angular 21), agente de pruebas (pytest trazado a criterios), agente IaC (Terraform para EKS, RDS, ECR) y validador de artefactos (sintaxis Python/TypeScript, YAML, `docker compose config`, dependencias, rutas por agente y secretos, más revisión semántica). Andamiaje por plantillas, producto en `workspace/<proyecto>/aplicacion/vN` y entregables en `workspace/<proyecto>/entregables/vN`. Montaje del entorno local desde la interfaz (Docker Compose, salud y pytest en contenedor) y notificaciones en la aplicación al terminar. Ejecución real sobre «Creación de Usuario en el Portal»: ~41 000 tokens, producto levantado con API y frontend en 200 y 6/7 pruebas aprobadas. Pruebas sin red: 59 aprobadas. Detalles en FASE_5.md.

## Auditoría técnica

Reintentos y esquema único en el proveedor de IA (−58 % de tokens de entrada medido en una llamada real), trazabilidad de fallos sin secretos, criterio de roles compartido con la regla ACTOR_INCOHERENTE, análisis estático y de seguridad del código generado con ruff y filtro de confirmaciones en las revisiones. La suite completa se ejecuta con la base aislada fabrica_test: 126 pruebas aprobadas, ninguna omitida. Detalle, evidencias y riesgos pendientes en INFORME_AUDITORIA.md.
