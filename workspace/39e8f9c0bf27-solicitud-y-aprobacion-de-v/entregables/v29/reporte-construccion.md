# Reporte de construcción v29

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PORTAL_REGISTRO_INOPERANTE: cargar() deja siempre la identidad en null y el catálogo vacío, por lo que el selector no ofrece tipos y el botón de envío permanece deshabilitado. Además, enviar() solo muestra un error y nunca registra la solicitud. Esto impide crear solicitudes según HU-001-CA-01, CA-02 y CA-03. Sustituir estos bloqueos por la integración de sesión del empleado, la carga del catálogo y el envío de los datos del formulario mediante la API correspondiente, sin utilizar credenciales administrativas. `portal/src/app/solicitudes.component.ts`
- **error** · desarrollador_portal · PORTAL_HISTORIAL_INOPERANTE: cargar() no consulta solicitudes ni actualiza solicitudes(); únicamente establece un error de listado. El empleado no puede acceder a su historial ni navegar desde una solicitud a su detalle, lo que impide el seguimiento de HU-001-CA-04. Implementar la consulta del historial con la sesión del empleado y actualizar el listado, manteniendo el aislamiento de sus datos. `portal/src/app/solicitudes.component.ts`
- **error** · desarrollador_portal · PORTAL_DETALLE_AVISOS_INOPERANTES: Para cualquier identificador válido, cargar() vacía el detalle, el historial y las notificaciones y solo establece mensajes de error; no realiza consultas. La pantalla no permite consultar el seguimiento ni los avisos de cambio de estado exigidos por HU-001-CA-04 y HU-002-CA-01. Integrar las consultas del detalle, historial y notificaciones mediante la sesión del empleado, poblar sus señales y gestionar los errores de cada consulta. `portal/src/app/detalle-solicitud.component.ts`
- **advertencia** · agente_pruebas · PR-014-DUPLICADO-NO-IDENTICO: La prueba test_hu_005_ca_01_catalogo_ciclo_completo_duplicados_y_versiones transforma el nombre con upper() antes de crear el duplicado. Así no verifica la creación de dos tipos con el mismo nombre exacto y podría pasar aunque exista una restricción de unicidad sensible a mayúsculas. Crear el segundo tipo con tipo['nombre'] sin transformarlo y comprobar la respuesta 201 y los identificadores distintos; mantener la variante en mayúsculas como caso adicional. `backend/tests/test_aceptacion_ausencias.py`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Conserva registro por portal y formato oficial, envío a revisión, auditoría y rechazo de datos inválidos o suplantación. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Conserva persistencia del motivo y validación backend de obligatoriedad y contenido vacío. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Conserva fechas, horas, modalidades, límites temporales y rechazo sin creación de registros. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_aceptacion_ausencias.py` | Conserva seguimiento, historial auditado, aislamiento por empleado y validación de filtros y paginación. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Conserva notificaciones persistidas de cambios de estado, aislamiento de destinatarios y límites de consulta. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Conserva avisos al aprobador del paso activo, ausencia de duplicados y autorización del procesamiento. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Conserva bandeja asignada, orden del flujo y rechazo de acceso o revisión prematura. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Corrige rechazo sin observación a 422 según contrato; conserva decisiones válidas, versiones, estados cerrados y concurrencia 200/409. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Verifica motivo de rechazo obligatorio, límites vacío y 5001 inválidos, 5000 válido y persistencia asociada a revisión y autor. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_aceptacion_ausencias.py` | Conserva auditoría de consultas y decisiones e incorpora verificación de auditoría de la observación obligatoria. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Conserva validación y aprobación separadas o conjuntas, validación previa obligatoria y control de estados inválidos. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Corrige rechazo de Talento Humano sin motivo a 422 y comprueba persistencia del motivo válido en el límite superior. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Conserva trazabilidad de accesos, validaciones, decisiones y observaciones, con aislamiento de solicitudes ajenas. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Corrige nombres repetidos a creación 201 con identificadores distintos; conserva ciclo de catálogo, versiones, roles y restricciones de tipos utilizados. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Conserva asociación de los tres flujos, consulta posterior, conflicto optimista y validación de flujo y versión. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| validador_artefactos | 18 | 249209 | 4728 | 194.1 s |
| desarrollador_backend | 2 | 55075 | 2905 | 50.4 s |
| desarrollador_portal | 3 | 59572 | 13483 | 622.3 s |
| desarrollador_panel | 2 | 49502 | 4404 | 494.4 s |
| agente_pruebas | 2 | 73200 | 22491 | 742.7 s |
| desarrollador_datos | 1 | 16461 | 9324 | 131.6 s |
