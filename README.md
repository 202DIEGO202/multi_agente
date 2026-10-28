# Trama · Fábrica de Software Multiagente

Fases 1 a 5 implementadas: analista funcional con LangGraph, RAG híbrido, backlog, mockups, arquitectura y construcción de aplicaciones; Angular, FastAPI, PostgreSQL/pgvector, contratos Pydantic y trazabilidad mediante SSE. La especificación original está en [docs/ESPECIFICACION.md](docs/ESPECIFICACION.md).

La revisión integral de calidad, los cambios de seguridad y los pendientes de madurez empresarial están en [docs/REVISION_CALIDAD_20261026.md](docs/REVISION_CALIDAD_20261026.md).

El corpus entregado permanece en sus carpetas originales. La aplicación lo incorpora **por proyecto**, conservando documento, versión, página y fragmento. No precarga requisitos ni decisiones ficticios.

## Desarrollo por partes

| Parte | Componentes |
|---|---|
| 1. Infraestructura | Configuración, PostgreSQL con pgvector e inferencia mediante APIs externas |
| 2. Conocimiento | Extracción PDF/TXT/MD, fragmentación, embeddings, actualización y eliminación |
| 3. Recuperación | Reformulación → vectorial + BM25 en paralelo → RRF → selección final |
| 4. Analista | LangGraph, selección de herramientas, descubrimiento y consolidación |
| 5. Persistencia | Conversaciones, propuestas, elementos versionados, contradicciones, líneas base |
| 6. Interfaz | Angular, chat, proyectos, conocimiento, revisión y versiones |
| 7. Transparencia | Eventos reales, respuesta progresiva SSE, rankings y JSON |
| 8. Verificación | Pruebas unitarias, PostgreSQL aislado, APIs de modelos y compilación Angular |

## Requisitos

- Windows con PowerShell, Python 3.11 o superior (verificado con 3.12).
- Node.js compatible con Angular 21 (verificado con Node 24).
- Docker Desktop en ejecución para PostgreSQL.
- Un proveedor de IA por API y sus credenciales. No se descargan ni ejecutan modelos en el equipo.

La aplicación se sirve en `127.0.0.1`; está diseñada inicialmente para un operador local. No incluye gestión multiusuario, SSO ni roles empresariales.

## Instalación

Desde la carpeta raíz:

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
docker compose up -d postgres
Set-Location frontend
npm ci
```

Si se utiliza el Python incluido en Codex y no puede ejecutar `ensurepip`, el entorno puede prepararse así, usando su ruta real como `$pythonRuntime`:

```powershell
& $pythonRuntime -m venv --without-pip .venv
& $pythonRuntime -m pip --python .venv/Scripts/python.exe install pip
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-dev.txt
```

`backend/requirements.lock.txt` conserva las versiones exactas del entorno verificado, incluidas las herramientas de desarrollo. `frontend/package-lock.json` fija las dependencias de Angular. Para reproducir las versiones Python verificadas, sustituya `requirements-dev.txt` por `requirements.lock.txt`.

## Ejecución

Terminal 1, desde la raíz:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe run.py
```

`run.py` selecciona explícitamente el bucle de eventos compatible con psycopg en Windows; evita iniciar este backend mediante un comando de Uvicorn que seleccione Proactor.

Terminal 2, desde la raíz:

```powershell
Set-Location frontend
npm start
```

- Aplicación: [http://127.0.0.1:4200](http://127.0.0.1:4200)
- API interactiva: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- Esquema OpenAPI: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

Para detener los servidores use `Ctrl+C` en sus terminales. `docker compose stop` detiene PostgreSQL conservando el volumen. No elimine el volumen si desea conservar proyectos.

En Windows también puede usar `.\iniciar.ps1` y `.\detener.ps1` desde la raíz. El arranque ejecuta ambos servidores en segundo plano, registra sus identificadores y deja los logs en `tmp/`. El comando de parada comprueba la identidad y fecha de esos procesos antes de terminarlos. Estos comandos requieren que las dependencias estén instaladas. No inician servidores de modelos.

## Primer uso

1. Cree un proyecto desde Vista general; el modo predeterminado es supervisado.
2. En Conocimiento, seleccione **Importar base TechRetail** para indexar los PDF de las tres carpetas entregadas. También puede cargar PDF, TXT o Markdown.
3. Consulte el progreso en Actividad de IA. Los fallos quedan registrados; un PDF escaneado sin texto requiere OCR previo.
4. Use Trazabilidad RAG para probar la recuperación de forma independiente.
5. Converse con el analista. Las preguntas documentales recuperan evidencia; los saludos, consultas sobre el estado y cambios explícitos de requisitos pueden resolverse sin RAG.
6. Revise las propuestas en Estado del proyecto. Puede editar su descripción antes de aprobarlas o rechazarlas.
7. Resuelva las contradicciones críticas y publique una línea base. Cada publicación es una versión inmutable.

También se puede cargar el corpus y ejecutar una consulta de verificación mediante:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -X utf8 scripts/prepare_techretail.py
```

Este comando crea o reutiliza el proyecto **TechRetail** y escribe los resultados reales en `output/verificacion_real.json`. No instala decisiones de negocio. Si usa `API_TOKEN`, expórtelo en esa terminal.

## Trabajo manual y automático

Cada proyecto puede trabajar en modo supervisado o automático. En modo supervisado, las versiones
de diseño, arquitectura y construcción esperan aprobación humana. En modo automático, una versión
solo se aprueba cuando supera los controles de su fase; preguntas, bloqueos, arquitectura incompleta
o ausencia de verificación real en Docker detienen el proceso para revisión. Las decisiones quedan
versionadas y registradas en Actividad de IA. En **Desarrollo completo** (`/workflow`), una sola
solicitud encadena análisis, línea base, backlog, diseño, arquitectura, construcción y pruebas.
El modo manual espera la revisión de cada etapa; el automático avanza solo al superar sus controles.
Puede solicitarse al inicio una instancia local. No se despliega infraestructura corporativa automáticamente.
Los pasos y ejecuciones hijas se conservan para pausar y continuar. Reintentar una etapa fallida es
una acción explícita que consume API y conserva los intentos anteriores; no repite las fases terminadas.

Las fases aplican a dominios distintos mediante requisitos, historias, reglas y contratos trazables.
La plantilla de código actual tiene un alcance tecnológico definido (FastAPI, PostgreSQL, Angular,
Docker y Terraform para AWS); una solución que requiera un stack diferente necesita una plantilla
validada para ese stack. La plataforma no afirma generar software perfecto ni soportar de forma
automática cualquier integración empresarial sin configurar sus capacidades.

## Configuración de modelos

Las variables se leen desde `.env` en la raíz y, si existe, `backend/.env` (este último tiene prioridad). Reinicie el backend al cambiarlas.

| Grupo | Variables principales |
|---|---|
| Analista | `LLM_PROVIDER`, `LLM_BASE_URL`, `LLM_MODEL`, `LLM_API_KEY`, `LLM_TEMPERATURE`, `LLM_MAX_TOKENS`, `LLM_TIMEOUT` |
| Reformulación | `REWRITE_PROVIDER`, `REWRITE_BASE_URL`, `REWRITE_MODEL`, `REWRITE_API_KEY` |
| Embeddings | `EMBEDDING_PROVIDER`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS`, `EMBEDDING_API_KEY` |
| Recuperación | `RETRIEVAL_K`, `FINAL_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP` |
| Servicios | `DATABASE_URL`, `API_HOST`, `API_PORT`, `CORS_ORIGINS`, `API_TOKEN`, `STORAGE_DIR`, `MAX_UPLOAD_MB` |

El adaptador conversacional implementado es `openai_compatible`, con `LLM_API_STYLE=responses` o `chat_completions`. En Azure se está usando Responses API: configure la base `https://RECURSO.services.ai.azure.com/openai/v1`, el nombre de implementación en `LLM_MODEL` y `LLM_AUTH_STYLE=api-key`. No añada `/responses` a la URL base; el adaptador lo incorpora. Responses usa JSON Schema estricto y streaming `response.output_text.delta`. Las variables de reformulación vacías reutilizan el modelo, URL y clave del analista. La API de embeddings puede usar otra URL y clave; si están vacías, reutiliza las del analista, pero `EMBEDDING_MODEL` debe configurarse expresamente.

Por decisión del usuario, se retiró el Neural Reranker del alcance. RRF determina el orden final y se seleccionan los primeros `FINAL_K` fragmentos. No se realiza otra llamada de IA para reordenarlos. El cambio está registrado en `docs/ALCANCE.md`.

El `.env.example` deja la URL y las credenciales vacías para evitar solicitudes accidentales y propone `text-embedding-3-small` como modelo de embeddings. La configuración privada actual conecta el analista a Azure `gpt-4.1-mini` y los embeddings a Azure `text-embedding-3-small`; la clave solo está en `.env`, ignorado por Git. Con autorización expresa del usuario se reindexaron los 98 documentos (401 fragmentos) con el modelo por API. La recuperación y la respuesta con fuentes fueron verificadas sin reranker. Los PDF originales se conservan.

Para comprobar la API configurada con dos solicitudes breves: desde `backend/`, ejecute `..\.venv\Scripts\python.exe -m scripts.check_api`. Consume tokens y guarda un resultado sin credenciales en `output/verificacion_api.json`.

Cambiar modelo o dimensión de embeddings bloquea la recuperación hasta reindexar todos los documentos del proyecto. La interfaz ofrece **Reindexar con el modelo actual**. Cambiar fragmentación requiere igualmente reindexar.

Las claves nunca se devuelven en la API de configuración. `API_TOKEN` habilita una clave de acceso al servidor, que se introduce en Configuración del espacio y permanece en `sessionStorage`. Esta clave no sustituye OIDC ni una solución multiusuario. El backend escucha en `127.0.0.1:8000` por defecto. Si `API_HOST` deja de ser loopback, el arranque exige `API_TOKEN` y que todos los orígenes CORS externos usen HTTPS; el token compartido sirve solo como barrera básica para una instalación controlada, no como identidad corporativa.

## Flujo y responsabilidades

```mermaid
flowchart TD
  U[Angular: mensaje del usuario] --> API[FastAPI: conversación y ejecución]
  API --> G[LangGraph: cargar estado e interpretar]
  G -->|Necesita documentación| T[search_knowledge]
  T --> Q[Reformulación con IA]
  Q --> V[pgvector]
  Q --> B[BM25]
  V --> R[RRF]
  B --> R
  R --> E[Evidencia con fuentes]
  E --> A[Analista]
  G -->|Consulta del estado o cambio explícito| A
  A -->|Información funcional nueva| P[Pydantic y reglas funcionales]
  P --> DB[(Propuestas, requisitos y versiones)]
  A --> S[Respuesta progresiva SSE]
  DB --> S
  S --> U
```

El RAG **solo devuelve evidencia**. No genera una respuesta conversacional adicional. El analista responde usando el estado funcional, la conversación reciente y los fragmentos recuperados. Las preguntas informativas no pasan por consolidación de requisitos.

Las búsquedas se ejecutan sobre una misma instantánea transaccional de documentos. BM25 se reconstruye cuando cambia la revisión documental del proyecto, incluyendo altas, modificaciones y borrados. Se limita la caché a 16 revisiones/proyectos. pgvector utiliza búsqueda exacta por coseno, apropiada para el corpus inicial de 401 fragmentos; no hay un índice aproximado HNSW que pueda esconder incompatibilidades de dimensión.

Si falla la reformulación, se utiliza la consulta original y se registra la degradación. RRF produce siempre el ranking final. Un fallo de embeddings o de PostgreSQL detiene la ejecución; no se sustituye con resultados inventados.

## Persistencia y contratos

- `messages` y `conversations`: historial recuperable.
- Tablas de checkpoints de LangGraph: estado y reanudación por ejecución.
- `functional_items`: cada versión aceptada del elemento, sin sobrescritura.
- `proposals` y `conflicts`: revisión, bloqueos y aclaraciones.
- `baselines`: contratos Pydantic en español, con `version_esquema = 1.0`.
- `documents`, `document_versions` y `chunks`: fuentes, versiones y vectores.
- `executions` y `events`: operaciones reales y resultados observables.

Los requisitos conservan `RF-001`, `RNF-001`, etc. al modificarse e incrementan `version`. Se separan `estado` de validación y `vigencia`. Las propuestas pendientes no se mezclan con elementos consolidados. Una validación automática nunca se etiqueta como aprobación humana.

Las modificaciones utilizan la versión esperada y se serializan por proyecto. La aprobación de una propuesta obsoleta se rechaza. Las líneas base requieren al menos un requisito, referencias válidas y ausencia de propuestas o contradicciones críticas pendientes. Los disparadores de PostgreSQL impiden actualizar o borrar versiones funcionales y líneas base.

El estado estructurado se consulta en cada análisis; el historial conversacional enviado al modelo se limita a los últimos 12 mensajes y 12.000 caracteres. No se envía indiscriminadamente toda la conversación. Los modelos no se reentrenan.

## Endpoints principales

Todos los siguientes están bajo `/api`; los recursos anidados comprueban su pertenencia al proyecto.

| Método | Ruta | Resultado |
|---|---|---|
| GET / POST | `/projects` | Listar / crear proyectos |
| GET | `/projects/{p}/state` | Estado vigente y propuestas |
| GET | `/projects/{p}/items/{id}/history` | Historial de un elemento |
| POST | `/projects/{p}/proposals/{id}/review` | Aprobar, editar o rechazar |
| POST | `/projects/{p}/conflicts/{id}/resolve` | Registrar aclaración humana |
| POST | `/projects/{p}/baselines` | Publicar versión inmutable |
| GET | `/projects/{p}/baselines/{version}` | Recuperar contrato publicado |
| GET / POST | `/projects/{p}/conversations` | Listar / crear conversaciones |
| GET / POST | `/projects/{p}/conversations/{c}/messages` | Historial / iniciar análisis |
| GET / POST | `/projects/{p}/documents` | Documentos / cargar archivo |
| GET | `/projects/{p}/documents/{d}/file?version=1` | Fuente original de esa versión |
| DELETE | `/projects/{p}/documents/{d}` | Retirar documento de ambos índices |
| POST | `/projects/{p}/knowledge/import` | Incorporar corpus inicial |
| POST | `/projects/{p}/knowledge/reindex` | Reindexar fuentes vigentes |
| POST | `/projects/{p}/knowledge/search` | Recuperación independiente |
| GET | `/projects/{p}/executions` | Historial de ejecuciones |
| GET | `/projects/{p}/executions/{e}` | Estado, resultado y primeros eventos |
| GET | `/projects/{p}/executions/{e}/events?after=0` | SSE con reproducción de eventos |
| POST | `/projects/{p}/executions/{e}/resume` | Reanudar análisis detenido |

El envío de mensajes exige `id_solicitud` UUID para evitar duplicados al reenviar la misma solicitud. Una conversación solo admite un análisis activo. SSE acepta `Last-Event-ID` o `after`, reproduce eventos persistidos y termina con `event: fin`. `actividad` contiene eventos observables; `texto_delta` contiene fragmentos reales del texto generado. Nunca se transmiten razonamientos internos del modelo.

Tras reiniciar el servidor, una ejecución activa se marca `interrumpido`. Los análisis pueden reanudarse desde el monitor; la consolidación y el guardado de mensajes son idempotentes. Una respuesta parcial se reinicia al reanudarla. La ingesta se puede volver a ejecutar y omite documentos idénticos. Ejecute una única instancia del backend en esta fase.

## Pruebas

Pruebas unitarias y del adaptador de proveedores:

```powershell
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

Para integración real con PostgreSQL, cree **una base separada**:

```powershell
docker compose exec postgres psql -U fabrica -d postgres -c "CREATE DATABASE fabrica_test;"
$env:TEST_DATABASE_URL='postgresql://fabrica:fabrica_local@127.0.0.1:5543/fabrica_test?connect_timeout=5'
Set-Location backend
..\.venv\Scripts\python.exe -m pytest -q
```

Los casos de integración se omiten si no se configura esa base. Las pruebas no utilizan el proyecto TechRetail. Sus filas de verificación permanecen en `fabrica_test` para inspección.

Para la prueba adicional de conversación con la API real, configure primero URL, modelo y clave. Esta prueba consume tokens del proveedor:

```powershell
$env:RUN_LIVE_TESTS='1'
..\.venv\Scripts\python.exe -m pytest -q
```

Frontend:

```powershell
Set-Location frontend
npm test
npm run build
```

Las pruebas comprueban RRF, fragmentos estables, validación, duplicados, versiones obsoletas, aprobación humana/automática, contradicciones, persistencia entre conexiones, ámbito de proyecto, pgvector, invalidación BM25, fallbacks RAG, autorización y reproducción SSE. La prueba de modelos externos utiliza un transporte HTTP controlado; no afirma conectividad real con un proveedor sin credenciales.

## Estructura

```text
backend/app/api/           Endpoints HTTP, tareas y SSE
backend/app/agents/        Grafo del analista funcional
backend/app/database/      Pool PostgreSQL y esquema versionado
backend/app/models/        Contratos Pydantic en español
backend/app/rag/           Ingesta y recuperación híbrida
backend/app/services/      Estado funcional y eventos
backend/app/providers.py  Adaptadores configurables de IA
backend/tests/             Pruebas críticas y de integración
frontend/src/core/         API, SSE, estado y tipos
frontend/src/features/     Vistas funcionales
frontend/src/shared/       Iconos y visor JSON
docs/                      Especificación y verificación
storage/                   Copias documentales por hash (ignorado por Git)
```

No hay agentes posteriores implementados. Los contratos publicados y `search_knowledge` son los puntos de integración para futuras etapas.

Referencias técnicas consultadas: [persistencia de LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence), [checkpoints PostgreSQL](https://github.com/langchain-ai/langgraph/tree/main/libs/checkpoint-postgres), [compilación de Angular](https://angular.dev/tools/cli/build) y [API compatible de chat](https://developers.openai.com/api/reference/resources/chat).

## Fase 2: backlog funcional

Organización en épicas y funcionalidades, historias con criterios de aceptación y validación mediante tres agentes coordinados con LangGraph. Consulte [la guía de fase 2](docs/FASE_2.md) para generación, revisión, publicación y trazabilidad.


## Fase 3: diseño y mockups

Dos agentes por API (diseñador y validador), visor Angular declarativo y una corrección automática como máximo. Versiones, decisiones y registros persistentes. Consulte [la guía de fase 3](docs/FASE_3.md).

## Eliminar y restaurar proyectos

En Vista general, el botón de papelera de cada tarjeta permite eliminar un proyecto tras confirmar la operación en el diálogo. Se trata de una eliminación recuperable: desaparece de los proyectos activos, pero conserva documentos, conversaciones, versiones, publicaciones y registros. El botón Papelera permite restaurarlo. No hay borrado definitivo en esta interfaz.

La eliminación se bloquea si hay tareas pendientes o en ejecución. El servidor impide acceder a recursos y reactivar ejecuciones mientras el proyecto está eliminado. Si se elimina el proyecto activo, la interfaz selecciona otro disponible o queda sin proyecto. Las operaciones de eliminación y restauración se registran en project_lifecycle_events. No requieren llamadas al modelo.

## Reutilizar conocimiento indexado

En Conocimiento y actividad → Conocimiento, la sección Reutilizar una base indexada permite seleccionar otro proyecto y pulsar Usar base existente. Se vinculan sus documentos indexados compatibles con el modelo actual, sin copiar archivos, fragmentos o vectores y sin llamar a Azure. La operación se registra en Actividad de IA.

Cada documento conserva su ID, versión, páginas y fragmentos originales. Las búsquedas vectorial y BM25, las fuentes y el visor de archivos usan la misma colección de documentos propios y vinculados. Los chats, requisitos, líneas base, backlog y mockups siguen separados por proyecto.

Los documentos vinculados se identifican con su origen y pueden Desvincularse sin eliminar el original. La reindexación desde el consumidor solo procesa documentos propios. Un original en uso por otros proyectos no puede eliminarse hasta desvincularlo de ellos. Enviar el proyecto de origen a la Papelera no rompe vínculos existentes.

Las actualizaciones de los documentos de origen se reflejan en los consumidores e invalidan su caché BM25. Los archivos nuevos del origen se incorporan pulsando de nuevo Usar base existente; los ya disponibles no se duplican. El contador del proyecto incluye los documentos vinculados. Reimportar el mismo nombre y contenido ya disponible reutiliza la indexación; Reindexar sigue siendo una acción explícita que puede consumir tokens.

Vincular y desvincular no consume tokens. Consultar con RAG sigue usando el modelo y el embedding de la pregunta. Las verificaciones de esta función usan modelos simulados en fabrica_test.

## Compatibilidad de requisitos con procedimientos

El analista conserva hasta ocho fragmentos de las últimas tres recuperaciones de la conversación y comprueba que sigan disponibles en la base vigente. Así, las respuestas de seguimiento no pierden las aprobaciones, roles o restricciones documentales del turno anterior. Si hay documentos indexados y no hay evidencia conservada, los cambios funcionales requieren una consulta documental actual.

El contrato de extracción incluye una revisión explícita de compatibilidad: compatible, requiere aclaración, contradice, sin evidencia o no aplica. El servidor verifica las citas contra los fragmentos recuperados, registra documento, página y versión, y convierte los conflictos/ambigüedades en bloqueos de consolidación y publicación. No se añade otra llamada al modelo para esta revisión: forma parte de la extracción ya existente. La compatibilidad semántica sigue dependiendo del análisis del modelo y del alcance de la evidencia; no equivale a una certificación completa de cumplimiento.

La aprobación de un requisito no constituye autorización de la entidad para derogar un procedimiento. El autorregistro de un portal se distingue de la provisión de una cuenta corporativa. Los cambios deliberados de procedimiento se mantienen pendientes de aclaración/autorización, sin convertirlos en políticas vigentes. Antes de aprobar también se verifica que las fuentes del dictamen no hayan cambiado de versión. Una aclaración libre del conflicto no vuelve compatible automáticamente una propuesta cuyo dictamen documental sigue bloqueado: debe revisarse la propuesta ajustada.

La recuperación de evidencia y los dictámenes quedan en Actividad de IA. Las revisiones anteriores y aprobaciones humanas se conservan. Las pruebas de esta funcionalidad son simuladas y no llaman a Azure.

Un fallo de formato o verificación de citas se distingue de una contradicción de negocio. La cita admite un único intento técnico de corrección, con salida y evidencia registradas. Si no se verifica, la aprobación sigue bloqueada por revisión técnica, pero no se crea una contradicción para que el usuario la resuelva mediante una nota. La corrección utiliza solo el dictamen de compatibilidad; no regenera ni aprueba requisitos.
