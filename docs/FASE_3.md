# Fase 3: diseño y mockups

## Flujo

El diseñador de interfaces recibe un backlog publicado, los requisitos de su línea base y las instrucciones del usuario. Produce el contrato declarativo 3.0: paleta, pantallas, controles, navegación y relaciones con historias y criterios. El visor Angular utiliza HTML y CSS de la aplicación para representarlo. Nunca ejecuta HTML, JavaScript ni recursos remotos generados por el modelo.

El validador de diseño recibe el contrato completo y las fuentes. Comprueba coherencia, errores y cobertura semántica; el servidor comprueba identificadores, navegación, cobertura de historias y criterios y contraste de los tokens de texto (4.5:1). Esta comprobación de contraste no sustituye una auditoría completa de accesibilidad. El validador no inspecciona una captura de pantalla ni certifica la apariencia visual.

Si hay bloqueos se permite una corrección del diseñador y una segunda validación. Si persisten, la revisión se guarda bloqueada para intervención humana. Hay dos llamadas por generación válida sin correcciones y cuatro como máximo cuando se activa una corrección automática. Fallos de red pueden requerir reanudar desde un checkpoint; los pasos ya completados se conservan. Toda inferencia usa el modelo configurado por API, sin modelos locales ni generación de imágenes.

## Uso

1. Aprobar y publicar un backlog vigente.
2. Abrir Diseño y mockups y seleccionar el backlog publicado.
3. Escribir indicaciones opcionales y pulsar Generar mockups.
4. Explorar pantallas y navegación, en vista de escritorio o móvil. Los campos son de prueba: los botones no envían correos, SMS ni solicitudes reales.
5. Revisar bloqueos y advertencias. Para cambiar una pantalla, elegirla en Alcance, escribir el cambio y pulsar Refinar pantalla. La aplicación conserva las demás pantallas y la paleta global. Para cambios globales o historias nuevas, usar Diseño completo.
6. En modo manual, dejar una nota y aprobar/publicar o rechazar. En modo automático, la revisión se aprueba solo si cobertura, estructura, referencias y contraste pasan y no quedan preguntas. Una duda real deja la versión pendiente de revisión humana.

Consultar, visualizar y aprobar no llama al modelo. Generar y refinar sí lo hacen. El presupuesto de salida por llamada se configura con MOCKUP_MAX_TOKENS (6144 por defecto).

## Versiones y trazabilidad

Las revisiones y decisiones son inmutables. Cada revisión guarda su ejecución, fecha, instrucciones, versiones de backlog/línea base/historias, correcciones y diferencias. Las pantallas conservan su ID y versión si no cambiaron. Al cambiar la paleta global, las pantallas también aumentan de versión porque cambia su representación.

La revisión aprobada es la instantánea inmutable con decisión aprobado_por_humano o validado_automaticamente. Se conserva aunque se generen revisiones nuevas. Se exige la revisión más reciente y un origen vigente para aprobar. Si cambian los requisitos, el origen publicado o aparecen conflictos, se muestra la desactualización y se bloquea la aprobación.

Actividad de IA muestra carga de fuentes, agente/modelo, contratos de entrada y salida, duración de llamadas, validación, corrección, límite alcanzado, guardado, visualización y decisión humana. Las fallas también dejan un evento y estado de error. No se guarda razonamiento privado. LangGraph conserva checkpoints; las ejecuciones detenidas pueden reanudarse desde Actividad de IA.

Las solicitudes tienen clave idempotente y solo se permite una generación activa por proyecto. El guardado vuelve a comprobar origen y versión para evitar publicar resultados sobre un estado cambiado. El refinamiento puntual exige la última revisión para no editar accidentalmente otra versión.

## Límites

El visor admite texto, entradas, selectores, botones, avisos y casillas; es un prototipo estructural, no código de producción ni una herramienta libre de dibujo. Admite hasta 20 pantallas por diseño y 40 controles por pantalla. La representación incluye estados de error como avisos declarados, pero no implementa la lógica real del producto.

Las pruebas automatizadas usan respuestas controladas y una base fabrica_test separada: no consumen tokens de Azure. Incluyen cobertura, navegación, contraste, refinamiento puntual, versiones, publicación, aislamiento, concurrencia, límite de correcciones y eventos SSE. La conexión del proveedor Azure es la misma ya utilizada por las fases anteriores; no se ejecutó una generación real de esta fase durante la implementación para cuidar créditos.

## Prevención de fallos técnicos

Antes de invocar al validador, el servidor normaliza duplicados, mayúsculas y requisitos puestos en campos de criterios usando exclusivamente los IDs conocidos del backlog. No inventa relaciones ni borra referencias desconocidas. Cada normalización registra el contrato anterior y el resultado.

La prevalidación comprueba referencias, alcance del refinamiento, navegación, cobertura y contraste. Si encuentra errores técnicos, utiliza la única corrección permitida antes de pagar otra validación semántica. Si la respuesta del validador tiene un contrato inválido, corrige ese agente sin regenerar las pantallas. El mismo límite de una corrección se comparte entre todos los pasos. Los reintentos internos del adaptador están desactivados para esta fase; cada llamada del grafo queda registrada.

Si el contrato sigue siendo técnicamente inválido, no se guarda como propuesta para que el usuario repare IDs. Se conserva la ejecución con su error y las revisiones anteriores. Un diseño estructuralmente válido con una pregunta real se presenta para decisión humana, sin gastar una corrección en adivinar la respuesta. Los defectos semánticos del diseño se distinguen de los errores técnicos y de las decisiones pendientes.

## Vista limpia y aclaraciones

El interruptor Mostrar aclaraciones del visor alterna descripciones, ayudas y referencias de trazabilidad. La vista limpia es la predeterminada y la preferencia se guarda en el navegador. Los campos, botones y alertas funcionales se mantienen. La anotación visual explicativa de la primera generación también se oculta en vista limpia. No cambia el contrato guardado, no crea revisiones y no llama a Azure.
