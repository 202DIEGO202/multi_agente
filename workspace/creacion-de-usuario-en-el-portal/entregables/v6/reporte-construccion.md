# Reporte de construcción v6

Aplicaciones: portal, panel. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_panel · PANEL_SIN_API_ADMIN: El panel no consume /api/admin `panel/src/app/app.ts`
- **error** · desarrollador_panel · APP_INCOMPLETA: app.ts debe exportar la clase App y la constante routes `panel/src/app/app.ts`
- **error** · desarrollador_panel · PANTALLA_INCOMPLETA: PA-002 · Aprobación de solicitud por líder de área: faltan campos o textos del mockup (cobertura 0%) 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Prueba creación de solicitud válida con datos completos y validaciones correctas. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_api.py` | Prueba envío de solicitud con datos incompletos que debe fallar validación. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba validación específica de nivel de estudios inferior a bachillerato. |
| PR-004 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba validación específica de edad menor o igual a 23 años. |
| PR-005 | HU-009-CA-01 | `backend/tests/test_api.py` | Prueba visualización de datos de solicitud y líder de área en panel administrativo con token. |
| PR-006 | HU-010-CA-01 | `backend/tests/test_api.py` | Prueba aprobación de solicitud por líder de área y notificación al administrador. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba rechazo de solicitud con motivo obligatorio y notificación al empleado. |
| PR-008 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba rechazo de solicitud sin motivo obligatorio debe fallar. |
| PR-009 | GET /api/health → 200 | `backend/tests/test_api.py` | Prueba endpoint público /api/health responde 200 con estado ok. |
| PR-010 | /api/admin/ sin token → 401 o 403 | `backend/tests/test_api.py` | Prueba que rutas administrativas sin token devuelven 401 o 403. |
| PR-011 | /api/admin/ con token correcto → 200 | `backend/tests/test_api.py` | Prueba que rutas administrativas con token válido devuelven 200. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4876 | 1022 | 9.2 s |
| desarrollador_backend | 1 | 6302 | 4251 | 28.7 s |
| desarrollador_portal | 1 | 3177 | 2253 | 14.8 s |
| agente_pruebas | 1 | 5787 | 2766 | 21.2 s |
| agente_iac | 1 | 1238 | 1833 | 13.9 s |
| desarrollador_panel | 3 | 17728 | 6639 | 52.9 s |
