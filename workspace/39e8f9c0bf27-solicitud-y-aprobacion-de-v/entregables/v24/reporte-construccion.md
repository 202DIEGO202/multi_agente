# Reporte de construcción v24

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PORTAL_REGISTRO_INOPERANTE: El selector de tipos y el botón de envío están deshabilitados permanentemente; enviarSolicitud() solo muestra un error y no registra datos. Esto impide ejecutar HU-001-CA-01, CA-02 y CA-03. Conectar el catálogo y el registro mediante la integración autenticada del empleado, habilitar la selección y enviar tipo, fechas, horas y motivo según las restricciones del tipo, mostrando el resultado o el error del servidor. `portal/src/app/solicitudes.ts`
- **error** · desarrollador_portal · PORTAL_HISTORIAL_INOPERANTE: La sección de historial solo muestra un mensaje estático y un enlace sin identificar una solicitud; nunca consulta ni presenta solicitudes o estados del empleado, impidiendo HU-001-CA-04. Implementar la consulta autenticada del historial propio, mostrar sus estados y proporcionar enlaces al detalle con el identificador de cada solicitud. `portal/src/app/solicitudes.ts`
- **error** · desarrollador_portal · PORTAL_SEGUIMIENTO_INOPERANTE: La pantalla no consulta notificaciones, detalle ni historial: únicamente lee solicitud_id del enlace y presenta mensajes estáticos. El empleado no puede consultar los avisos de cambio de estado ni seguir una solicitud conforme a HU-002-CA-01 y HU-001-CA-04. Conectar las consultas autenticadas del empleado y renderizar avisos, datos y cambios de estado, gestionando denegaciones de acceso sin exponer solicitudes ajenas. `portal/src/app/notificaciones.ts`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva registro autenticado para revisión, persistencia y rechazo de datos obligatorios ausentes. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva persistencia del motivo y validación centralizada cuando el tipo lo exige. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Conserva catálogo autenticado, tipo, fechas y horas; límites y tipos inactivos o incompatibles. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Conserva listado propio, detalle e historial auditados, estado actualizado y aislamiento entre empleados. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva avisos autenticados de cambio de estado, sin duplicados ni exposición de solicitudes ajenas. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva notificaciones al aprobador inicial y siguiente, validación de asignaciones y aislamiento. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva bandeja del jefe, campos de revisión y validación de paginación. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva aprobación y rechazo, estados y versiones inválidos, autorización y conflicto concurrente sin doble decisión. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Corrige la expectativa: rechazo con observación omitida o nula devuelve 200 y persiste la decisión sin crear observaciones. Conserva persistencia del texto proporcionado y rechazo de texto vacío o superior a 5000 caracteres. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Conserva auditoría de consultas y decisiones del jefe y denegación de recursos no asignados. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva validación y aprobación por Talento Humano y rechazo de decisiones incompatibles o etapas anticipadas. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Corrige la expectativa: Talento Humano puede rechazar con observación omitida o nula. Conserva observaciones asociadas a validación o rechazo y el límite de 5000 caracteres. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Conserva trazabilidad de accesos y modificaciones de Talento Humano y aislamiento de revisiones. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva CRUD autenticado, auditoría, nombres duplicados permitidos, límites, estados inválidos y protección de referencias. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva asociación de los tres flujos, versiones optimistas y validación de flujos inválidos o inactivos. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| validador_artefactos | 24 | 333985 | 6109 | 245.5 s |
| desarrollador_backend | 1 | 28349 | 855 | 28.3 s |
| desarrollador_portal | 3 | 54544 | 5884 | 529.2 s |
| desarrollador_panel | 1 | 26416 | 5872 | 510.0 s |
| agente_pruebas | 1 | 44648 | 15361 | 1046.1 s |
