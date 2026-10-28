# Reporte de construcción v4

Aplicaciones: portal. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PANTALLA_INCOMPLETA: PA-002 · Aprobación de solicitud por líder de área: faltan campos o textos del mockup (cobertura 0%) 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Prueba de creación de solicitud con datos válidos y envío correcto. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_api.py` | Prueba de error al enviar solicitud con datos incompletos. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba de error por nivel de estudios inferior a bachillerato. |
| PR-004 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba de error por edad menor o igual a 23 años. |
| PR-005 | HU-009-CA-01 | `backend/tests/test_api.py` | Prueba de visualización de datos de solicitud y líder de área con token válido. |
| PR-006 | HU-010-CA-01 | `backend/tests/test_api.py` | Prueba de aprobación de solicitud por líder de área y notificación al administrador. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba de rechazo de solicitud con motivo obligatorio y notificación al empleado. |
| PR-008 | GET /api/health | `backend/tests/test_api.py` | Prueba de endpoint público /api/health responde 200 con estado ok. |
| PR-009 | Acceso sin token a rutas admin | `backend/tests/test_api.py` | Prueba que rutas /api/admin/ sin token devuelven 401 o 403. |
| PR-010 | Acceso con token a rutas admin | `backend/tests/test_api.py` | Prueba que rutas /api/admin/ con token correcto devuelven 200. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4853 | 1458 | 12.6 s |
| desarrollador_backend | 1 | 6694 | 4477 | 33.8 s |
| desarrollador_portal | 3 | 16672 | 5992 | 38.9 s |
| agente_pruebas | 1 | 5877 | 2819 | 18.7 s |
| agente_iac | 1 | 1238 | 1903 | 16.0 s |
