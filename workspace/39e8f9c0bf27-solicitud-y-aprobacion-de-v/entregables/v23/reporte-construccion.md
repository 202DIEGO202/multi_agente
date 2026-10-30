# Reporte de construcción v23

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PORTAL_REGISTRO_INOPERANTE: El selector de tipo de ausencia y el botón de envío están deshabilitados permanentemente; enviarSolicitud() solo muestra un mensaje y no registra datos. Esto impide crear solicitudes con tipo, fechas, horas y motivo según HU-001-CA-01, HU-001-CA-02 y HU-001-CA-03. Corregir conectando el formulario al catálogo y al registro mediante acceso autenticado del empleado, habilitando los controles y enviando los datos; no es necesario convertir estas operaciones en acceso público. `portal/src/app/solicitudes.ts`
- **error** · desarrollador_portal · PORTAL_SEGUIMIENTO_INOPERANTE: La pantalla no consulta notificaciones, detalle ni historial: únicamente procesa solicitud_id y muestra mensajes de funcionalidad pendiente. Además, el historial de SolicitudesComponent tampoco carga solicitudes. Esto impide el seguimiento exigido por HU-001-CA-04 y la consulta de avisos de HU-002-CA-01. Corregir implementando consultas autenticadas de las solicitudes y notificaciones propias, enlaces con el identificador seleccionado y presentación del estado y su historial mediante operaciones que registren la trazabilidad requerida. `portal/src/app/notificaciones.ts`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva registro para revisión, rechazo de datos incompletos, autenticación y auditoría. La configuración automática elimina la dependencia de una variable de empleado no garantizada por Docker. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva persistencia del motivo y rechazo centralizado de motivos ausentes, vacíos o compuestos por espacios. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Conserva selección del tipo, persistencia de fechas y horas, límites temporales y rechazo de tipos inactivos o incompatibles con horas. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Conserva seguimiento e historial auditados, autenticación real del empleado, aislamiento por propietario y separación de las proyecciones administrativas. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva avisos de aprobación y rechazo, asociación al cambio de estado, prevención de duplicados y consulta exclusiva de notificaciones propias. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva notificación al aprobador inicial y siguiente, aislamiento de bandejas y rechazo de asignaciones inválidas. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva pendientes asignados al jefe, exclusión de revisiones ajenas y validación de límites de paginación. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva aprobación y rechazo, versiones optimistas, estados inválidos y conflicto concurrente sin doble decisión. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Conserva observaciones asociadas a la decisión, límite de longitud y obligatoriedad del motivo de rechazo. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Conserva auditoría de consultas y decisiones del jefe, identificación del actor y denegación de acceso no asignado. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva validación y aprobación de Talento Humano, rechazo de decisiones incompatibles y respeto del orden de etapas. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva persistencia de observaciones de validación y rechazo de Talento Humano y errores de validación de longitud y obligatoriedad. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Conserva trazabilidad de accesos y modificaciones de Talento Humano y aislamiento respecto de otros aprobadores. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Conserva administración del catálogo, estados de éxito, límites, nombres duplicados permitidos, conflictos de versión, referencias y permisos. También se mantienen las pruebas existentes de salud y protección de todas las operaciones administrativas. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Conserva asociación de los tres flujos, preservación de configuración, control de versión y rechazo de flujos inválidos o inactivos. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| validador_artefactos | 24 | 331233 | 5617 | 296.5 s |
| desarrollador_portal | 3 | 54558 | 6003 | 126.6 s |
