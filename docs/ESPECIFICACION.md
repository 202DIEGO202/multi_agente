# ESPECIFICACIÓN TÉCNICA Y FUNCIONAL
# Fábrica de Software Multiagente basada en Inteligencia Artificial

**Fase 1:** Motor RAG híbrido mejorado, agente analista funcional, chatbot Angular, persistencia de requisitos y monitor visual de ejecución.

**Propósito del documento:** Servir como especificación de implementación para Codex.

**Principio general:** Construir una solución funcional, modular, mantenible y extensible, utilizando únicamente los componentes necesarios y evitando simulaciones que aparenten funcionalidades reales.

---

# 1. OBJETIVO GENERAL

Desarrollar la primera fase de una Fábrica de Software Multiagente basada en Inteligencia Artificial que permita a un analista funcional humano interactuar con un agente de IA para descubrir, comprender, estructurar, validar y consolidar requisitos de software.

La solución deberá integrar:

- Un agente analista funcional conversacional orquestado mediante LangGraph.
- Un motor RAG híbrido mejorado para consultar documentación.
- Memoria conversacional y estado funcional persistente.
- Contratos JSON estructurados y versionados.
- Un frontend Angular moderno, interactivo y responsivo.
- Un backend Python con FastAPI.
- Un monitor visual de ejecución y trazabilidad de agentes.
- Configuración de modelos locales mediante Ollama o proveedores externos de IA.

El sistema deberá permitir que el conocimiento funcional del proyecto se construya progresivamente a partir de conversaciones, conservando decisiones, modificaciones, requisitos, restricciones y preguntas pendientes.

La arquitectura deberá quedar preparada para integrar posteriormente agentes especializados en historias de usuario, BPMN, UX/UI, arquitectura de software, infraestructura, desarrollo, pruebas y DevOps.

**Importante:** Estos agentes posteriores no forman parte de la implementación inicial. La primera fase debe preparar los contratos y puntos de integración necesarios, sin desarrollar anticipadamente módulos que todavía no se utilizarán.

---

# 2. ARQUITECTURA DEL RAG HÍBRIDO MEJORADO

## 2.1. Objetivo

Implementar un motor de recuperación documental capaz de combinar búsqueda semántica y búsqueda léxica para recuperar información relevante, confiable y trazable.

El motor RAG será un componente reutilizable por los agentes de la fábrica de software.

Su responsabilidad será recuperar evidencia documental, no administrar requisitos ni generar por separado las respuestas conversacionales del agente analista.

## 2.2. Pipeline definido

El flujo obligatorio será:

**Consulta original → Reformulación con IA → Búsqueda vectorial y BM25 en paralelo → Fusión RRF → Neural Reranker → Fragmentos relevantes con fuentes.**

Posteriormente, el agente analista utilizará los fragmentos recuperados para generar la respuesta mediante su LLM.

## 2.3. Reformulación de consultas con IA

Un modelo LLM recibirá la consulta original y, cuando sea necesario, generará una versión optimizada para la recuperación documental.

Deberá:

- Conservar la intención original.
- Preservar nombres, códigos, identificadores y términos técnicos.
- Considerar el contexto conversacional relevante.
- Evitar introducir información inexistente.
- Permitir recuperar la consulta original si falla la reformulación.

Las consultas originales y reformuladas deberán quedar disponibles para el monitor visual.

## 2.4. Búsqueda vectorial

Utilizar PostgreSQL con la extensión pgvector.

El proceso deberá:

- Generar embeddings de los fragmentos documentales.
- Almacenar vectores asociados a identificadores de fragmentos.
- Recuperar documentos mediante similitud semántica.
- Permitir configurar la cantidad de resultados recuperados.
- Conservar los metadatos y la fuente documental.

El modelo de embeddings deberá admitir adecuadamente contenido en español.

## 2.5. Búsqueda léxica BM25

Implementar búsqueda basada en términos mediante `rank-bm25`.

Deberá:

- Recuperar coincidencias de palabras, expresiones e identificadores.
- Utilizar los mismos fragmentos que la búsqueda vectorial.
- Ejecutarse en paralelo con la recuperación semántica.
- Devolver identificadores, puntuaciones y posiciones de los resultados.

La indexación BM25 deberá mantenerse sincronizada con el conjunto documental vigente y utilizar un mecanismo apropiado para reconstruir o actualizar el índice cuando cambien los documentos.

## 2.6. Fusión Reciprocal Rank Fusion

Combinar los rankings vectorial y BM25 utilizando Reciprocal Rank Fusion (RRF).

La implementación deberá:

- Recibir los resultados de ambos recuperadores.
- Fusionar las posiciones mediante el algoritmo RRF.
- Eliminar resultados duplicados utilizando identificadores estables.
- Producir un ranking unificado.
- Conservar información suficiente para explicar la posición de cada resultado.

RRF es un algoritmo matemático y no requiere un LLM.

## 2.7. Neural Reranker

Utilizar un modelo Cross-Encoder multilingüe para evaluar la relevancia de los fragmentos candidatos.

El reranker deberá:

- Recibir la consulta y los fragmentos recuperados por RRF.
- Evaluar la relación entre cada fragmento y la consulta.
- Reordenar los candidatos según relevancia.
- Seleccionar los fragmentos finales que recibirá el agente analista.

El modelo de reranking deberá configurarse independientemente del modelo conversacional y del modelo de embeddings.

Si el reranker falla, el sistema podrá utilizar los resultados ordenados por RRF, registrando la degradación del proceso.

## 2.8. Resultado del RAG

El servicio RAG devolverá una estructura con:

- Consulta original.
- Consulta reformulada.
- Fragmentos recuperados.
- Identificadores de fragmentos.
- Documentos de origen.
- Metadatos.
- Puntuaciones y rankings disponibles.
- Fragmentos finalmente seleccionados.
- Información de trazabilidad de la recuperación.

**Regla arquitectónica obligatoria:** El RAG no deberá generar una segunda respuesta conversacional independiente. El agente analista será responsable de interpretar la evidencia y responder al usuario.

---

# 3. INTEGRACIÓN CON EL AGENTE ANALISTA FUNCIONAL

El agente analista funcional estará implementado mediante LangGraph.

La integración con el motor RAG se realizará mediante una herramienta denominada:

`search_knowledge`

## 3.1. Funcionamiento

1. El usuario envía un mensaje desde Angular.
2. El backend recupera el contexto conversacional y el estado vigente del proyecto.
3. El agente interpreta la solicitud.
4. Determina si necesita consultar conocimiento documental.
5. Si lo necesita, ejecuta `search_knowledge`.
6. El RAG ejecuta el pipeline de recuperación.
7. El agente recibe los fragmentos relevantes y sus fuentes.
8. El agente genera una respuesta contextualizada o solicita aclaraciones.
9. Se proponen y validan las actualizaciones del estado funcional.
10. Las actualizaciones aceptadas se persisten en PostgreSQL.
11. Los eventos relevantes se transmiten al monitor Angular.

No se deberá ejecutar el RAG para todos los mensajes.

Las consultas relacionadas únicamente con requisitos, decisiones o información previamente consolidada podrán resolverse consultando el estado estructurado del proyecto.

## 3.2. Separación de responsabilidades

El agente analista será responsable de:

- Comprender solicitudes.
- Conversar con el usuario.
- Identificar requisitos.
- Detectar contradicciones.
- Solicitar aclaraciones.
- Utilizar evidencia documental.
- Proponer cambios.
- Generar respuestas.

El motor RAG será responsable de:

- Reformular consultas.
- Recuperar fragmentos.
- Fusionar resultados.
- Reordenar candidatos.
- Entregar evidencia y fuentes.

La persistencia será responsable de almacenar las definiciones y versiones del proyecto.

---

# 4. TECNOLOGÍAS SELECCIONADAS

| Componente | Tecnología |
|---|---|
| Frontend | Angular |
| Backend | Python + FastAPI |
| Orquestación del agente | LangGraph |
| Integración de modelos y herramientas | LangChain cuando sea necesario |
| Validación estructural | Pydantic |
| Base de datos | PostgreSQL |
| Búsqueda vectorial | pgvector |
| Búsqueda léxica | BM25 mediante rank-bm25 |
| Fusión de resultados | RRF |
| Neural Reranker | Cross-Encoder multilingüe |
| Modelos LLM | Ollama o proveedor externo configurable |
| Embeddings | Modelo configurable compatible con español |
| Comunicación en tiempo real | Server-Sent Events (SSE) |
| Persistencia de ejecución | Checkpoints de LangGraph |
| Validación y pruebas | Herramientas de pruebas compatibles con Python y Angular |

## 4.1. Configuración de modelos de IA

El sistema deberá permitir seleccionar modelos locales o externos sin modificar la lógica principal de los agentes.

La configuración deberá contemplar:

- Proveedor.
- Nombre del modelo.
- URL del servicio.
- Credenciales.
- Temperatura.
- Límite de tokens.
- Timeout.
- Modelo para el agente analista.
- Modelo para reformulación.
- Modelo de embeddings.
- Modelo de reranking.

Las credenciales deberán almacenarse de forma segura y nunca exponerse en el frontend.

Se implementarán únicamente los conectores de proveedores que realmente se utilicen.

**LangChain no es obligatorio como capa adicional para todos los componentes.** Se utilizarán sus integraciones cuando aporten valor y sean necesarias para LangGraph o los proveedores seleccionados.

---

# 5. INGESTA DOCUMENTAL

El sistema deberá permitir incorporar documentación de conocimiento para alimentar el RAG híbrido.

## 5.1. Proceso

1. Cargar documentos.
2. Validar el tipo de archivo.
3. Extraer el contenido textual.
4. Normalizar el contenido.
5. Dividirlo en fragmentos.
6. Asignar identificadores estables.
7. Generar embeddings.
8. Almacenar fragmentos y vectores en PostgreSQL.
9. Incorporar los mismos fragmentos al índice BM25.
10. Registrar el estado de procesamiento.

## 5.2. Metadatos

Cada documento deberá conservar:

- Identificador.
- Nombre.
- Tipo.
- Proyecto o ámbito al que pertenece.
- Fecha de incorporación.
- Versión.
- Estado de indexación.

Cada fragmento deberá conservar su documento de origen y la información necesaria para citarlo.

## 5.3. Actualización documental

Cuando un documento se modifique o elimine, deberán actualizarse los índices vectorial y BM25 para evitar recuperar fragmentos obsoletos.

La solución deberá evitar duplicaciones innecesarias.

La recuperación deberá respetar el ámbito del proyecto y los permisos disponibles.

---

# 6. VISUALIZACIÓN DEL PROCESO RAG

La plataforma deberá permitir inspeccionar el recorrido de recuperación documental.

Se visualizarán:

- Consulta original.
- Consulta reformulada.
- Resultados vectoriales.
- Resultados BM25.
- Ranking RRF.
- Resultados del Neural Reranker.
- Fragmentos seleccionados.
- Documentos utilizados.
- Tiempos de ejecución.
- Errores o degradaciones.

El usuario podrá comparar los resultados de las distintas etapas mediante tablas, tarjetas y visualizaciones comprensibles.

La respuesta conversacional final se identificará como resultado del agente analista, no como una generación independiente del servicio RAG.

La interfaz deberá distinguir entre información documental recuperada y decisiones funcionales almacenadas en el proyecto.

---

# 7. RESULTADO ESPERADO DEL MOTOR RAG

Obtener un único motor de recuperación híbrida mejorada, reutilizable por los agentes de la fábrica de software.

**Arquitectura definitiva:**

Agente analista → `search_knowledge` → Reformulación IA → Búsqueda vectorial + BM25 → RRF → Neural Reranker → Evidencia documental con fuentes → Agente analista → Respuesta contextualizada.

El motor deberá poder probarse independientemente del chatbot.

---

# 8. CHATBOT CONVERSACIONAL Y AGENTE ANALISTA FUNCIONAL

## 8.1. Objetivo

Implementar un chatbot inteligente que permita la colaboración bidireccional entre un analista funcional humano y un agente de IA.

El agente deberá comprender necesidades de negocio, identificar requisitos, resolver ambigüedades y construir progresivamente el conocimiento funcional del proyecto.

## 8.2. Capacidades conversacionales

El agente deberá:

- Mantener conversaciones de múltiples turnos.
- Interpretar solicitudes expresadas en lenguaje natural.
- Comprender correcciones y aclaraciones.
- Conservar el contexto del proyecto.
- Evitar preguntas repetitivas.
- Formular preguntas relevantes cuando falte información.
- Distinguir hechos, propuestas, supuestos y decisiones.
- Mantener coherencia entre sesiones.

No deberá inventar decisiones de negocio que el usuario no haya proporcionado.

## 8.3. Descubrimiento de requisitos

El agente identificará progresivamente:

- Objetivos del proyecto.
- Actores.
- Requisitos funcionales.
- Requisitos no funcionales identificados.
- Reglas de negocio.
- Restricciones.
- Decisiones.
- Supuestos.
- Preguntas pendientes.

Los requisitos podrán registrarse inicialmente como propuestas y evolucionar conforme avance la conversación.

## 8.4. Estado estructurado del proyecto

El sistema mantendrá en PostgreSQL un estado funcional persistente por proyecto.

Este estado será independiente de:

- El historial de mensajes.
- Los checkpoints de LangGraph.
- Los documentos del RAG.

Los elementos deberán tener identificadores, estados y versiones cuando corresponda.

El agente consultará las definiciones vigentes antes de responder o modificar información.

## 8.5. Memoria conversacional

La memoria deberá permitir:

- Recuperar conversaciones anteriores.
- Continuar el análisis en distintas sesiones.
- Relacionar mensajes con decisiones y requisitos.
- Mantener contexto relevante sin enviar indiscriminadamente todo el historial al modelo.
- Conservar las definiciones funcionales en estructuras persistentes.

La memoria no implica reentrenar el modelo LLM.

## 8.6. Confirmación y actualización de requisitos

El sistema deberá admitir dos modos:

**Modo supervisado**

El usuario podrá revisar, aprobar, rechazar o modificar propuestas antes de consolidarlas.

**Modo automático**

El sistema podrá validar y consolidar propuestas cuando cumplan las reglas configuradas.

La validación automática no se presentará como aprobación humana.

Las contradicciones críticas deberán bloquear la consolidación automática y generar preguntas de aclaración.

## 8.7. Flujo conversacional

El flujo general será:

1. Recibir mensaje.
2. Recuperar estado vigente.
3. Interpretar intención.
4. Identificar información nueva o modificada.
5. Detectar contradicciones.
6. Consultar el RAG cuando sea necesario.
7. Generar respuesta o pregunta.
8. Proponer cambios estructurados.
9. Validar los cambios.
10. Persistir los cambios aceptados.
11. Emitir eventos de trazabilidad.
12. Actualizar Angular.

Este ciclo se repetirá durante el descubrimiento y refinamiento funcional.

## 8.8. Integración posterior con agentes especializados

La arquitectura deberá permitir incorporar posteriormente:

- Agente de historias de usuario.
- Agente BPMN.
- Agente UX/UI y mockups.
- Agente validador funcional.
- Agentes de arquitectura de software e infraestructura.
- Agentes de desarrollo, pruebas y DevOps.

Estos módulos consumirán información estructurada del proyecto y podrán utilizar el RAG cuando necesiten conocimiento documental.

No deberán depender exclusivamente del texto del historial conversacional.

**En esta fase no se implementarán esos agentes especializados.**

## 8.9. Consolidación progresiva del conocimiento funcional

En cada interacción, el agente deberá determinar si la información recibida representa:

1. Un requisito nuevo.
2. Una ampliación de un requisito existente.
3. Una modificación.
4. Una contradicción.
5. Una decisión.
6. Una pregunta pendiente.
7. Una aclaración sin cambio estructural.

El sistema deberá evitar requisitos duplicados y conservar el historial de modificaciones.

Cuando un requisito cambie, deberá identificarse qué decisiones o artefactos relacionados podrían resultar afectados.

## 8.10. Criterios de aceptación

- El chatbot permite conversaciones de múltiples turnos.
- Las conversaciones pueden recuperarse.
- Los requisitos se registran estructuradamente.
- El agente identifica ambigüedades.
- Las decisiones conservan trazabilidad.
- El RAG se consulta cuando corresponde.
- Los requisitos pueden corregirse.
- Los cambios no destruyen versiones anteriores.
- Se diferencian aprobaciones humanas y validaciones automáticas.
- Los datos pueden entregarse mediante contratos estructurados.

---

# 9. INTERFAZ WEB INTERACTIVA — ANGULAR

## 9.1. Objetivo

Desarrollar una interfaz moderna, intuitiva, profesional y responsiva que permita al usuario conversar con el agente, administrar proyectos, visualizar requisitos y observar el funcionamiento interno del sistema.

La experiencia deberá combinar facilidad de uso con transparencia técnica.

## 9.2. Diseño visual

Utilizar una identidad visual cálida con:

- Crema.
- Beige.
- Blanco cálido.
- Terracota.
- Verde suave.
- Sombras discretas.
- Bordes redondeados.
- Tipografía moderna y legible.
- Espaciado amplio.
- Animaciones suaves.

La aplicación deberá permitir modo claro y oscuro.

El diseño deberá ser accesible y adaptable a computadores, tabletas y dispositivos móviles.

## 9.3. Navegación principal

**Dashboard**

Mostrar proyectos, estado del análisis, requisitos, decisiones, pendientes y actividad reciente.

**Chat del analista**

Permitir conversar con el agente, revisar propuestas, consultar fuentes y visualizar respuestas progresivas.

**Estado del proyecto**

Mostrar requisitos, reglas, actores, restricciones, decisiones, pendientes y versiones.

**Explorador de conocimiento**

Permitir cargar documentos, revisar indexación y consultar fuentes documentales.

**Trazabilidad RAG**

Mostrar el recorrido completo de recuperación híbrida y sus rankings.

**Actividad de IA**

Mostrar los eventos reales de ejecución de LangGraph y las herramientas utilizadas.

## 9.4. Pantalla principal

La pantalla del chatbot tendrá tres zonas.

**Barra lateral izquierda**

- Navegación.
- Proyectos.
- Historial de conversaciones.
- Configuración.

**Área central**

- Mensajes del usuario.
- Respuestas del agente.
- Entrada de texto.
- Indicadores de ejecución.
- Preguntas de aclaración.
- Acciones de confirmación.
- Referencias documentales.

**Panel contextual derecho**

- Requisitos identificados.
- Decisiones vigentes.
- Pendientes.
- Actividad reciente.
- Estado del proyecto.

El panel derecho podrá contraerse u ocultarse.

En pantallas pequeñas, los paneles deberán adaptarse sin perjudicar la conversación.

## 9.5. Interacción en tiempo real

Angular se comunicará con FastAPI mediante endpoints HTTP y SSE para las respuestas progresivas y los eventos de ejecución.

El sistema deberá:

- Mostrar respuestas de manera progresiva.
- Indicar cuándo se ejecuta una herramienta.
- Actualizar el estado funcional sin recargar.
- Mostrar errores comprensibles.
- Recuperar información al recargar la aplicación.
- Mantener identificadores de conversación y ejecución.

## 9.6. Gestión visual de requisitos

Cada requisito deberá mostrar:

- Identificador.
- Descripción.
- Estado.
- Versión.
- Fecha de modificación.
- Origen.
- Decisiones relacionadas.

El usuario podrá consultar su historial y solicitar cambios mediante el chatbot.

## 9.7. Organización inicial del frontend

```text
frontend/
└── src/
    └── app/
        ├── core/
        │   ├── services/
        │   ├── models/
        │   └── interceptors/
        ├── layout/
        │   ├── sidebar/
        │   ├── header/
        │   └── contextual-panel/
        ├── features/
        │   ├── dashboard/
        │   ├── projects/
        │   ├── analyst-chat/
        │   ├── project-state/
        │   ├── knowledge-base/
        │   ├── rag-observability/
        │   └── agent-monitor/
        └── shared/
            ├── components/
            ├── directives/
            └── pipes/
```

Esta estructura es orientativa. Solo deberán crearse módulos y archivos que realmente se necesiten.

## 9.8. Criterios de aceptación

- Angular funciona con el backend real.
- El chatbot permite conversaciones persistentes.
- Los requisitos se visualizan y actualizan.
- El usuario puede cargar y consultar documentos.
- La trazabilidad RAG muestra resultados reales.
- El monitor refleja eventos reales.
- La interfaz es responsiva.
- La navegación es intuitiva.
- Los errores se presentan adecuadamente.
- No existen pantallas que aparenten integraciones inexistentes.

---

# 10. BACKEND PYTHON Y ESTÁNDARES DE CÓDIGO

## 10.1. Objetivo

Desarrollar el backend mediante Python y FastAPI, priorizando legibilidad, mantenibilidad, separación de responsabilidades y simplicidad.

## 10.2. Principios de desarrollo

- Seguir PEP 8.
- Utilizar nombres descriptivos.
- Aplicar anotaciones de tipos.
- Separar rutas, servicios, modelos, agentes y persistencia.
- Evitar archivos excesivamente grandes.
- Evitar duplicación.
- Implementar manejo adecuado de errores.
- Utilizar programación asíncrona cuando aporte beneficios.
- Incorporar comentarios útiles, no redundantes.
- Mantener una configuración centralizada.
- No almacenar credenciales en el código.
- Implementar pruebas de componentes críticos.

Los nombres técnicos de archivos, funciones y clases podrán mantenerse en inglés, aunque los contratos JSON de intercambio se definirán en español.

## 10.3. Gestión de dependencias

Instalar únicamente las bibliotecas necesarias.

No incorporar frameworks, motores, colas, microservicios o herramientas adicionales sin una necesidad concreta.

No instalar varias bibliotecas para resolver exactamente la misma responsabilidad sin justificación.

Documentar las dependencias principales y eliminar importaciones no utilizadas.

## 10.4. Estructura inicial recomendada

```text
backend/
├── app/
│   ├── main.py
│   ├── api/
│   │   ├── chat.py
│   │   ├── projects.py
│   │   └── knowledge.py
│   ├── agents/
│   │   └── functional_analyst.py
│   ├── rag/
│   │   ├── document_ingestion.py
│   │   ├── query_rewriting.py
│   │   ├── vector_search.py
│   │   ├── bm25_search.py
│   │   ├── rank_fusion.py
│   │   ├── neural_reranker.py
│   │   └── rag_service.py
│   ├── services/
│   │   ├── chat_service.py
│   │   └── project_service.py
│   ├── models/
│   │   └── schemas.py
│   ├── database/
│   │   └── connection.py
│   └── config.py
├── tests/
├── requirements.txt
├── .env.example
└── README.md
```

La estructura podrá ajustarse cuando aparezcan responsabilidades reales adicionales, como persistencia de eventos o contratos estructurados.

No deberán generarse archivos vacíos o capas artificiales únicamente para cumplir una estructura.

## 10.5. Documentación

El proyecto incluirá:

- README con instrucciones de instalación.
- Configuración del entorno.
- Variables de entorno de ejemplo.
- Instrucciones de ejecución.
- Documentación de endpoints.
- Instrucciones para ejecutar pruebas.
- Explicación de la estructura del proyecto.

## 10.6. Criterios de aceptación

El backend deberá:

- Ejecutarse correctamente.
- Integrarse con PostgreSQL.
- Integrarse con el proveedor de IA configurado.
- Ejecutar LangGraph.
- Permitir consultas RAG.
- Validar contratos con Pydantic.
- Exponer endpoints reales.
- Transmitir eventos mediante SSE.
- Conservar datos entre reinicios.
- Contar con pruebas de las funcionalidades críticas.

---

# 11. REFINAMIENTOS ARQUITECTÓNICOS Y OPERATIVOS

## 11.1. Configuración de proveedores

Los proveedores de IA deberán configurarse independientemente de la lógica del agente.

Cambiar de Ollama a una API externa compatible no deberá exigir reescribir el flujo funcional.

Los modelos de embeddings y reranking podrán tener proveedores distintos.

Si cambia el modelo de embeddings o su dimensionalidad, deberá verificarse la compatibilidad del índice y regenerarlo cuando corresponda.

## 11.2. Separación entre recuperación y generación

`search_knowledge` recuperará evidencia documental.

El agente analista será el responsable de generar la respuesta conversacional.

No implementar una segunda generación LLM dentro del servicio RAG para responder al mismo mensaje.

## 11.3. Persistencia y consistencia

Persistir por separado:

- Historial conversacional.
- Estado funcional del proyecto.
- Checkpoints de LangGraph.
- Documentación e índices del RAG.
- Eventos relevantes de ejecución.

Podrán compartir PostgreSQL, pero deberán conservar responsabilidades y estructuras diferenciadas.

Los checkpoints permitirán reanudar ejecuciones, mientras que el estado funcional será la fuente persistente de requisitos y decisiones.

## 11.4. Manejo de errores

El sistema deberá manejar:

- Errores de conexión con proveedores.
- Respuestas inválidas del LLM.
- Fallos de validación Pydantic.
- Fallos de recuperación.
- Problemas de persistencia.
- Pérdida temporal de conexión con el frontend.

Cuando falle la reformulación, podrá utilizarse la consulta original.

Cuando falle el reranker, podrán utilizarse los resultados RRF.

Las operaciones de persistencia deberán evitar dejar actualizaciones parciales inconsistentes.

## 11.5. Recuperación confiable

El sistema deberá:

- Conservar referencias documentales.
- Evitar utilizar fragmentos obsoletos.
- Informar cuando falte evidencia.
- Respetar el ámbito de los proyectos.
- Distinguir conocimiento documental de decisiones del usuario.

## 11.6. Orquestación mediante LangGraph

LangGraph administrará el flujo de ejecución del agente analista.

Los nodos deberán representar responsabilidades concretas, como interpretación, consulta documental, consolidación o validación.

No es necesario convertir cada función Python en un agente autónomo.

Los futuros equipos multiagente podrán implementarse mediante subgrafos especializados que consuman contratos estructurados.

---

# 12. CONTRATOS ESTRUCTURADOS PARA INTEGRACIÓN MULTIAGENTE

## 12.1. Objetivo

Definir contratos JSON estructurados, versionados y con atributos en español para intercambiar información entre las etapas de la fábrica de software.

Los contratos se definirán y validarán mediante Pydantic.

Su objetivo será permitir que los futuros agentes consuman información funcional sin depender de interpretar libremente el historial del chatbot.

## 12.2. Información obligatoria

Cada línea base funcional deberá contener:

- Identificador del proyecto.
- Versión del esquema.
- Versión de la línea base.
- Estado de validación o aprobación.
- Requisitos identificados.
- Decisiones.
- Reglas de negocio.
- Restricciones.
- Preguntas pendientes.
- Supuestos relevantes.
- Referencias a los artefactos disponibles.

Las features, historias de usuario, criterios de aceptación detallados, diagramas BPMN y mockups podrán incorporarse posteriormente.

**No será obligatorio que existan historias de usuario para generar la primera línea base funcional.**

## 12.3. Ejemplo de contrato JSON

```json
{
  "id_proyecto": "PRY-001",
  "nombre_proyecto": "Gestion de Seguros",
  "version_esquema": "1.0",
  "version_linea_base": 1,
  "estado": "validado_automaticamente",
  "requisitos": [
    {
      "id": "RF-001",
      "descripcion": "Registrar solicitudes de seguros",
      "version": 1,
      "estado": "vigente",
      "origen": "conversacion"
    }
  ],
  "decisiones": [],
  "reglas_negocio": [],
  "restricciones": [],
  "preguntas_pendientes": [],
  "supuestos": [],
  "caracteristicas": [],
  "historias_usuario": [],
  "artefactos": []
}
```

Este ejemplo representa un contrato inicial. Los modelos Pydantic deberán precisar tipos, valores permitidos y validaciones.

## 12.4. Identificadores estables

Los requisitos y artefactos deberán tener identificadores únicos y estables dentro de su ámbito.

Cuando cambie un requisito existente, deberá conservar su identificador e incrementar su versión.

Ejemplo:

- RF-001, versión 1.
- RF-001, versión 2.
- RF-001, versión 3.

No crear nuevos identificadores para modificaciones de un mismo requisito.

## 12.5. Versionamiento de líneas base

La información funcional podrá evolucionar durante el análisis.

Cuando se publique una línea base, deberá conservarse como una versión inmutable.

Las modificaciones posteriores producirán una nueva línea base.

Esto permitirá que los futuros agentes trabajen sobre una versión específica y reproducible de los requisitos.

## 12.6. Estados de validación

El sistema deberá distinguir, como mínimo:

- Propuesto.
- Pendiente de aclaración.
- Validado automáticamente.
- Aprobado por humano.
- Sustituido o descartado, cuando corresponda.

El estado de aprobación no deberá confundirse con la versión del requisito ni con su vigencia.

## 12.7. Validaciones

Pydantic verificará:

- Tipos de datos.
- Campos obligatorios.
- Formato de estructuras.
- Valores permitidos.

Las validaciones funcionales adicionales verificarán:

- Identificadores duplicados.
- Referencias inexistentes.
- Contradicciones críticas.
- Consistencia de versiones.
- Condiciones necesarias para publicar una línea base.

No se permitirá avanzar automáticamente cuando existan contradicciones críticas sin resolver.

## 12.8. Exposición mediante API

FastAPI permitirá consultar el estado vigente del proyecto y recuperar líneas base específicas.

Los futuros agentes podrán solicitar una línea base por identificador de proyecto y versión.

## 12.9. Resultado esperado

Contar con una estructura de intercambio confiable que permita incorporar posteriormente agentes de historias de usuario, arquitectura, desarrollo, pruebas y DevOps sin rediseñar la persistencia funcional.

---

# 13. MONITOR VISUAL DE EJECUCIÓN Y TRAZABILIDAD DE AGENTES

## 13.1. Objetivo

Implementar un monitor visual e interactivo en Angular que permita observar las operaciones reales ejecutadas por LangGraph, el agente analista y el RAG híbrido.

El monitor deberá proporcionar transparencia técnica sin complicar la experiencia principal del chatbot.

## 13.2. Capacidades

El monitor permitirá:

- Visualizar actividades en tiempo real.
- Identificar el agente o nodo activo.
- Mostrar herramientas utilizadas.
- Mostrar consultas al RAG.
- Visualizar JSON generados.
- Consultar resultados de Pydantic.
- Identificar requisitos creados o modificados.
- Mostrar errores y advertencias.
- Consultar ejecuciones anteriores.

## 13.3. Eventos reales

Los eventos deberán originarse en operaciones realmente ejecutadas por el backend.

No se utilizarán mensajes inventados por un LLM para simular que una herramienta fue ejecutada.

Cada evento deberá incluir:

- Identificador de ejecución.
- Identificador de evento.
- Fecha y hora.
- Agente o componente.
- Tipo de operación.
- Estado.
- Descripción.
- Referencia al artefacto, cuando corresponda.
- Duración, cuando esté disponible.
- Detalles de error, cuando corresponda.

## 13.4. Comunicación en tiempo real

FastAPI transmitirá los eventos a Angular mediante SSE.

El frontend deberá mostrar progresivamente las actividades sin esperar a que finalice toda la ejecución.

Los eventos relevantes deberán persistirse en PostgreSQL para consulta posterior.

## 13.5. Visualización de JSON

Cuando se genere o modifique un JSON, el monitor permitirá:

- Identificar el artefacto.
- Consultar su contenido.
- Ver su versión.
- Conocer el resultado de validación.
- Copiar el contenido.
- Comparar versiones cuando existan.

El JSON deberá presentarse con formato legible y resaltado de sintaxis.

## 13.6. Interfaz del monitor

La pantalla deberá incluir:

- Línea de tiempo.
- Indicadores de estado.
- Panel de detalle del evento.
- Visor JSON.
- Referencias documentales.
- Resultados de validación.
- Historial por proyecto y ejecución.

Los detalles técnicos avanzados deberán estar disponibles bajo demanda.

## 13.7. Seguridad

El monitor no deberá exponer:

- Credenciales.
- Tokens.
- Contraseñas.
- Información sensible innecesaria.
- Razonamientos internos privados de los modelos.

Se mostrarán acciones observables, entradas y salidas autorizadas, resultados de herramientas y decisiones estructuradas registradas.

## 13.8. Criterios de aceptación

- Los eventos corresponden a ejecuciones reales.
- Angular recibe eventos durante el procesamiento.
- Los JSON se visualizan correctamente.
- Se muestran resultados de validación.
- Los errores son comprensibles.
- El historial puede recuperarse.
- Cada ejecución está identificada.
- La información sensible está protegida.

---

# INSTRUCCIONES FINALES PARA CODEX

Implementa la primera fase de la Fábrica de Software Multiagente conforme a esta especificación.

## Reglas de implementación

1. Conserva el alcance definido. No agregues agentes de arquitectura, desarrollo, pruebas o DevOps en esta fase.
2. Utiliza LangGraph para el agente analista y su flujo de ejecución.
3. Implementa el RAG híbrido real con reformulación, pgvector, BM25, RRF y Cross-Encoder.
4. Separa estrictamente la recuperación documental de la generación conversacional.
5. Utiliza Pydantic para validar las estructuras de intercambio.
6. Persiste conversaciones, requisitos, decisiones, versiones y eventos relevantes en PostgreSQL.
7. Implementa Angular conectado a servicios reales FastAPI.
8. Utiliza SSE para transmitir respuestas progresivas y eventos.
9. Permite configurar Ollama o un proveedor externo de IA.
10. Mantén una estructura de código sencilla, modular y documentada.
11. No incorpores dependencias o servicios innecesarios.
12. No presentes datos simulados como resultados reales.
13. Incluye pruebas de las funcionalidades críticas.
14. Documenta la instalación, configuración y ejecución.
15. Mantén contratos JSON versionados en español, preparados para los agentes futuros.

## Estrategia de implementación

Desarrolla progresivamente, validando cada componente antes de integrar el siguiente.

**Orden recomendado:**

1. Configuración del backend, PostgreSQL y modelos de IA.
2. Ingesta documental y motor RAG híbrido.
3. Agente analista funcional mediante LangGraph.
4. Persistencia de conversaciones y estado funcional.
5. Contratos JSON y validaciones Pydantic.
6. Frontend Angular y chatbot.
7. Monitor visual de ejecución mediante SSE.
8. Pruebas de integración y verificación final.

No declares una funcionalidad como completada si todavía no está implementada y verificada.

## Resultado final esperado

Una aplicación funcional que permita:

- Crear proyectos.
- Conversar con un agente analista de IA.
- Incorporar y consultar documentación mediante RAG híbrido.
- Descubrir y consolidar requisitos.
- Conservar el conocimiento funcional entre sesiones.
- Generar y validar contratos JSON versionados.
- Visualizar los requisitos y decisiones en Angular.
- Observar en tiempo real las operaciones internas ejecutadas.
- Consultar la trazabilidad del RAG y de los agentes.
- Continuar posteriormente hacia equipos multiagente especializados.

**Prioridad:** funcionamiento real, calidad técnica, trazabilidad, facilidad de uso y extensibilidad controlada.

**No desarrollar funcionalidades adicionales fuera de esta especificación sin una justificación técnica clara.**