# Reporte de construcción v22

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PORTAL_REGISTRO_INHABILITADO: PA-001 mantiene deshabilitados el selector de tipo y el botón de envío; enviarSolicitud() únicamente muestra un error y no registra datos. Esto impide crear solicitudes según HU-001-CA-01, CA-02 y CA-03. Sustituir el bloqueo permanente por la carga del catálogo autorizado para el empleado y el envío real del tipo, fechas, horas y motivo mediante la API del portal, con autenticación del empleado y sin utilizar operaciones administrativas. `portal/src/app/solicitudes.ts`
- **error** · desarrollador_portal · PORTAL_SEGUIMIENTO_SIN_CONSULTAS: El historial de PA-001 y las notificaciones y el detalle de PA-002 solo muestran mensajes de indisponibilidad. NotificacionesComponent lee solicitud_id del enlace, pero nunca consulta avisos, estado, detalle ni historial, por lo que el empleado no puede realizar el seguimiento exigido por HU-001-CA-04 ni consultar los avisos de HU-002-CA-01. Implementar las consultas autorizadas del empleado, mostrar sus resultados y enlazar cada solicitud o aviso con su detalle; mantener las notificaciones de aprobadores fuera del portal. `portal/src/app/notificaciones.ts`
- **advertencia** · agente_pruebas · PRUEBA_FLUJO_PRECONSTRUIDO: En test_hu_004_ca_01_validacion_th_y_orden_del_flujo, la revisión de Talento Humano se inserta directamente en la base de datos antes de aprobar la etapa del jefe. Así, la prueba puede finalizar aunque la aprobación del jefe no genere la siguiente revisión. Separar el escenario de revisión anticipada del recorrido normal: en este último, aprobar con siguiente_aprobador_id=qa.th y utilizar la siguiente_revision devuelta por la API para validar y aprobar como Talento Humano. `backend/tests/test_ausencias_aceptacion.py`

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
| desarrollador_backend | 1 | 27971 | 1227 | 31.3 s |
| desarrollador_portal | 3 | 58132 | 6353 | 230.6 s |
| desarrollador_panel | 1 | 26755 | 608 | 14.7 s |
| agente_pruebas | 1 | 44828 | 1826 | 43.5 s |
| validador_artefactos | 18 | 248463 | 4526 | 1514.3 s |
