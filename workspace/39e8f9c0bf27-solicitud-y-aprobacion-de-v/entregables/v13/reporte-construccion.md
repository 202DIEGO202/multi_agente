# Reporte de construcción v13

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/solicitudes/{} es público y expone los mismos datos que el administrativo /api/admin/solicitudes/{solicitud_id} `backend/app/main.py`
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/solicitudes/{}/historial es público y expone los mismos datos que el administrativo /api/admin/solicitudes/{solicitud_id}/historial `backend/app/main.py`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Registro autenticado por la ruta contractual: 201, identidad del empleado, flujo y estado EN_REVISION; rechazo de datos obligatorios ausentes y acceso sin token. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Persistencia del motivo y validación backend de motivo obligatorio nulo, vacío o compuesto por espacios. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Persistencia de fechas y horas; límites de intervalo, horas incompletas, fecha inválida, tipo inactivo y tipo sin horas. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Consulta autenticada de estado e historial ordenado con actor y fecha; auditoría de ambas consultas y aislamiento entre empleados. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Notificación persistida al empleado tras aprobación o rechazo; decisión repetida rechazada sin duplicar avisos. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Aviso al siguiente aprobador, aislamiento de notificaciones, rechazo de asignación inválida o ausente y límites de paginación. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Bandeja con solicitudes asignadas, datos de revisión y versiones; exclusión de otros aprobadores y validación de paginación. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Aprobación y rechazo registrados con actor, fecha y versiones; estados inválidos, versiones inválidas, repetición y conflicto concurrente sin doble decisión. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Observaciones vinculadas a la decisión; rechazo de observación vacía, exceso de longitud y rechazo sin motivo. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Auditoría persistida de consultas y decisiones del jefe; denegación de acceso y decisión a un actor no asignado. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Validación y aprobación de Talento Humano; rechazo de decisión incompatible con el rol y de revisión anterior a la etapa del jefe. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Observaciones de validación y rechazo visibles en el detalle y asociadas al actor; validación de longitud y motivo de rechazo. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Auditoría de consultas y modificaciones de Talento Humano, historial con actor y fecha y aislamiento frente a actores no asignados. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | CRUD autorizado y auditado; nombres repetidos sin unicidad inventada, límites de nombre, estados y versiones inválidos, conflictos y prohibición de eliminar tipos referenciados. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Consulta de flujos y asociación de JEFE, JEFE_TH y TH preservando configuración; rechazo de flujo inválido o inactivo y versión incompatible. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_panel | 2 | 50422 | 1590 | 39.0 s |
| desarrollador_datos | 1 | 16224 | 8424 | 130.1 s |
| desarrollador_backend | 1 | 24011 | 11148 | 201.5 s |
| desarrollador_portal | 1 | 17201 | 1560 | 31.5 s |
| agente_pruebas | 1 | 40075 | 10224 | 160.0 s |
