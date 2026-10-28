# Fase 2: backlog funcional

La página **Backlog funcional** transforma una línea base publicada en una propuesta de épicas, funcionalidades e historias de usuario. No incluye todavía generación de mockups ni implementación de código.

## Agentes y transferencia

El organizador funcional recibe requisitos y actores de una línea base publicada, instrucciones y la revisión anterior. Propone épicas y funcionalidades con referencias a los requisitos. El agente de historias recibe esa organización y redacta historias con actor, objetivo, beneficio y criterios Dado/Cuando/Entonces. El validador recibe la propuesta completa y revisa coherencia y ambigüedades. Cada papel utiliza el modelo configurado mediante API de Azure; no hay inferencia local ni reranker.

LangGraph coordina los pasos y guarda checkpoints. La transferencia usa contratos JSON estructurados, no depende de que un agente recuerde el chat. El contrato de backlog es 2.0; el funcional permanece en 1.0 y el de recuperación en 1.1.

## Uso

1. Consolidar requisitos y actores en Estado del proyecto y publicar una línea base.
2. Abrir Backlog funcional, elegir esa línea base y generar la propuesta.
3. Revisar épicas, funcionalidades, historias, cobertura y observaciones.
4. Editar o regenerar cuando corresponda. Cada edición ejecuta validación y crea otra revisión.
5. Aprobar y publicar con una nota, o rechazar con el motivo. Las preguntas y errores de validación bloquean la publicación.

En proyectos de aprobación automática, una propuesta válida se publica con estado de aprobación automática explícito. Esto no representa una aprobación humana.

## Historia y trazabilidad

Cada elemento tiene identificador estable y versión. Conserva los requisitos de origen y sus versiones; las historias enlazan también con un actor y una funcionalidad. Las revisiones, decisiones y publicaciones son inmutables. El historial permite ver cambios por elemento y la ejecución que los produjo.

Los eventos registran agente, modelo, entradas y salidas estructuradas, tiempos y operaciones realizadas. La página de ejecuciones permite seguir el proceso y reanudar ejecuciones interrumpidas. No se almacena razonamiento privado del modelo.

Si cambia el estado funcional después de generar el backlog, la interfaz muestra que quedó desactualizado y señala elementos afectados. La publicación verifica nuevamente el origen. Las solicitudes son idempotentes y solo se permite una ejecución activa de backlog por proyecto.

## Verificación

Hay pruebas de contratos, cobertura, versiones, criterios, persistencia inmutable, concurrencia, aislamiento por proyecto y API con eventos. La prueba opcional `tests/test_backlog_live.py`, habilitada con `RUN_LIVE_BACKLOG=1`, comprueba los tres agentes contra Azure usando datos sintéticos en una base de pruebas separada.

## Recuperación de la revisión

El validador recibe los IDs vigentes y los elementos descartados, distinguiendo su alcance. Las referencias históricas solo se admiten en observaciones; no se convierten en fuentes vigentes de historias. Se normalizan formatos equivalentes de IDs y se registra la salida original. Una respuesta con referencias desconocidas puede corregirse una vez sin repetir organizador ni historias. Si sigue inválida, se conserva un borrador con validación semántica pendiente y publicación bloqueada. No se presenta como revisión completada. Cada intento queda en la ejecución.
