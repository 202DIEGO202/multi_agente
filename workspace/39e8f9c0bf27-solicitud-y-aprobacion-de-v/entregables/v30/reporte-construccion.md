# Reporte de construcción v30

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **advertencia** · desarrollador_panel · PANEL_RECHAZO_SIN_MOTIVO: decidir('RECHAZAR') envía la petición aunque la observación esté vacía o contenga solo espacios, pese a que el contrato exige un motivo no vacío y devuelve 422 en ese caso. Antes de enviar, comprobar la observación normalizada con trim(), detener el rechazo si está vacía y mostrar que el motivo es obligatorio; mantenerlo opcional para las demás acciones. `panel/src/app/revision-store.ts`

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
| validador_artefactos | 12 | 165322 | 2649 | 119.7 s |
| desarrollador_portal | 1 | 19324 | 6756 | 98.0 s |
