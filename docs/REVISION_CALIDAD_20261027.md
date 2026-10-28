# Revisión de calidad — 27 de octubre de 2026

## Cambios de la plataforma

- Coordinador persistente para análisis, línea base, backlog, mockups, arquitectura,
  construcción y verificación. Interfaz `/workflow`, modos automático y supervisado,
  pausa, continuación, reintento explícito y enlaces a las ejecuciones de cada etapa.
- Idempotencia por solicitud, aislamiento por proyecto y bloqueo de modificaciones
  concurrentes mientras el flujo integral está activo.
- Reutilización del código candidato cuando sus fuentes no cambiaron. Las correcciones
  conservan archivos no mencionados; el frontend debe declarar las retiradas explícitamente.
- Los criterios internos de persistencia/auditoría se distinguen de los criterios visuales,
  sin excluirlos de la construcción ni de las pruebas. Se validan IDs y clasificación.
- Los agentes reciben el código real del backend y los criterios completos, sin cortar
  silenciosamente sus textos. El revisor inspecciona todos los archivos en lotes acotados.
- Detección de componentes importados pero no entregados y de estados SQL que exceden
  el tamaño de su columna. Los errores reales de PostgreSQL se devuelven al agente de datos.
- Las verificaciones reales se invalidan después de modificar código. Una suite omitida
  no acredita el producto. La aprobación automática exige revisión semántica y runtime.
- Candidatos de proyectos con igual nombre utilizan carpetas distintas. La escritura
  valida rutas y elimina únicamente archivos retirados del manifiesto de generación;
  conserva `.env` y archivos del usuario.

## Evaluaciones con Azure y documentación existente

Se usan bases separadas de los proyectos del usuario. Se copian vectores ya indexados,
sin volver a generar embeddings. No se ejecutan altas en AD, pagos, mensajes ni despliegues
corporativos. Los informes detallados quedan en `output/quality/`, excluido de Git.

| Escenario | Comportamiento comprobado |
| --- | --- |
| Alta inmediata en AD sin aprobación | Se detiene en requisitos por incompatibilidad documental; no inicia construcción. |
| Cálculo de días hábiles sin calendario definido | Formula preguntas sobre país, festivos y zona horaria; no inventa valores ni construye. También se observó que propone funciones documentales adicionales, que requieren revisión de alcance. |
| Helpdesk sin identidad, roles ni notificaciones definidos | Conserva las preguntas pendientes y detiene el flujo para hablar con el analista. |
| Orientador de devoluciones | Recorre análisis, backlog, diseño, arquitectura y construcción; las pruebas reales detectaron defectos que motivaron los cambios descritos. La aprobación final depende de la última verificación, no de un paso intermedio exitoso. |

La aplicación de devoluciones llegó a aprobar 22 pruebas de API antes de la revisión
semántica. Esa revisión detectó problemas adicionales y una corrección posterior introdujo
una incompatibilidad entre esquema y backend. Por tanto, ese resultado intermedio **no**
equivale a una entrega aprobada. La última ejecución autorizada produjo la versión 6,
compiló y aprobó 22 pruebas en Docker. El revisor marcó incumplimientos como advertencias:
se siguen guardando campos de entrada fuera del alcance solicitado y el formulario conserva
comprobaciones que rechazan condiciones negativas. La revisión manual confirmó que no basta
con el resultado verde de la API.

Se reforzó el control: una construcción con observaciones no puede aprobarse ni desplegarse
automáticamente. La auditoría sin modelo dejó el flujo en `esperando_revision`, conservando
el historial original. El producto de ejemplo **no está listo para producción**. No se
realizaron más correcciones por API después de las dos adicionales autorizadas.

## Verificaciones finales

- Suite completa del backend con PostgreSQL aislado: 147 aprobadas, dos pruebas marcadas
  `live` excluidas; las evaluaciones reales se ejecutaron por separado con su script.
- Frontend: tres pruebas aprobadas y compilación Angular satisfactoria.
- Ruff: sin errores.
- Código generado: 22 pruebas de API aprobadas, pero observaciones funcionales pendientes.
- Escenarios reales AD, calendario y Helpdesk: detención antes de construir, con decisiones
  pendientes conservadas. Los proyectos originales no se modificaron por estas evaluaciones.

## Límites pendientes para producción

Esta revisión no certifica cualquier escenario de negocio ni perfección del software generado.
La plantilla tecnológica sigue siendo FastAPI/PostgreSQL/Angular/Docker/Terraform AWS.
Persisten tareas de identidad corporativa por usuario y roles, validación del entorno de
despliegue, integraciones y comprobaciones de seguridad operativa de la organización.

Se recargaron los servidores registrados de Trama después de comprobar que no había trabajos
del usuario activos, conservando PostgreSQL. La carpeta de trabajo no contiene metadatos `.git`.

## Consumo y límites

Los modelos se invocaron por API; no hubo inferencia local. Se mantuvo el límite de dos
ciclos automáticos de corrección por ejecución. La revisión de permisos rechazó aumentarlo;
el usuario autorizó explícitamente dos correcciones adicionales para la última prueba,
sin modificar ese límite global. Las evaluaciones y contenedores sí consumen recursos locales
para ejecutar código y verificar resultados; no ejecutan un modelo local.
