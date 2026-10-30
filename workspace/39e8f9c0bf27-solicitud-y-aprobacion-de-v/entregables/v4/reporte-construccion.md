# Reporte de construcción v4

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/tipos-ausencia es público y expone los mismos datos que el administrativo /api/admin/tipos-ausencia `backend/app/main.py`
- **error** · desarrollador_panel · ENDPOINT_INEXISTENTE: La interfaz llama a /api/admin/solicitudes/1/aprobar, que no existe en el backend 
- **error** · desarrollador_panel · ENDPOINT_INEXISTENTE: La interfaz llama a /api/admin/solicitudes/1/rechazar, que no existe en el backend 
- **error** · desarrollador_portal · PANTALLA_ADMIN_EN_EMPLEADO: PA-003 · Bandeja de revisión - Jefe inmediato es una pantalla de aprobadores y aparece en la aplicación del empleado 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_vacaciones_api.py` | Crear solicitud válida desde el portal devuelve 201/200 y campos esperados. |
| PR-002 | HU-001-CA-01 | `backend/tests/test_vacaciones_api.py` | Validar fechas inválidas y horas parciales al crear solicitud devuelve 422. |
| PR-003 | HU-001-CA-02 | `backend/tests/test_vacaciones_api.py` | Cuando el tipo requiere motivo, crear sin motivo devuelve 422. |
| PR-004 | HU-001-CA-03 | `backend/tests/test_vacaciones_api.py` | Crear con tipo inexistente o con rango horario inválido devuelve 422. |
| PR-005 | HU-001-CA-04 | `backend/tests/test_vacaciones_api.py` | Consultar catálogo público devuelve 200 y lista sin datos administrativos; verifica trazabilidad por acceso público. |
| PR-006 | HU-002-CA-01 | `backend/tests/test_vacaciones_api.py` | /api/admin/tipos-ausencia sin token devuelve 401 o 403. |
| PR-007 | HU-002-CA-02 | `backend/tests/test_vacaciones_api.py` | /api/admin/solicitudes sin token devuelve 401 o 403. |
| PR-008 | HU-003-CA-01 | `backend/tests/test_vacaciones_api.py` | Con token correcto, listar solicitudes administrativas devuelve 200 y lista. |
| PR-009 | HU-003-CA-02 | `backend/tests/test_vacaciones_api.py` | Aprobar solicitud válida con observación devuelve éxito; observación vacía devuelve 422. |
| PR-010 | HU-003-CA-03 | `backend/tests/test_vacaciones_api.py` | Rechazar una solicitud ya decidida devuelve conflicto o validación adecuada. |
| PR-011 | HU-003-CA-04 | `backend/tests/test_vacaciones_api.py` | Acciones administrativas con token quedan cubiertas por consulta y decisión con control de estado. |
| PR-012 | HU-004-CA-01 | `backend/tests/test_vacaciones_api.py` | Rechazar como validación/decisión administrativa con token correcto responde según regla del flujo. |
| PR-013 | HU-004-CA-02 | `backend/tests/test_vacaciones_api.py` | La consulta administrativa verifica que las observaciones son obligatorias y valida respuestas 422. |
| PR-014 | HU-004-CA-03 | `backend/tests/test_vacaciones_api.py` | Consulta administrativa con token correcto cubre trazabilidad y acceso autorizado. |
| PR-015 | HU-005-CA-01 | `backend/tests/test_vacaciones_api.py` | El catálogo público y el administrativo devuelven datos distintos; el público no incluye estado ni flujo. |
| PR-016 | HU-005-CA-02 | `backend/tests/test_vacaciones_api.py` | El catálogo administrativo incluye estado y flujo de aprobación con token correcto. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 7089 | 3255 | 16.0 s |
| desarrollador_backend | 3 | 37965 | 9521 | 43.8 s |
| desarrollador_portal | 3 | 28867 | 10261 | 39.4 s |
| agente_pruebas | 3 | 45656 | 13380 | 56.2 s |
| agente_iac | 1 | 1285 | 2114 | 13.1 s |
| desarrollador_panel | 3 | 21560 | 2909 | 13.4 s |
