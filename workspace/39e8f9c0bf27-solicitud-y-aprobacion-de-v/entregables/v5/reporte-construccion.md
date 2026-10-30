# Reporte de construcción v5

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/tipos-ausencia es público y expone los mismos datos que el administrativo /api/admin/tipos-ausencia `backend/app/main.py`
- **error** · desarrollador_panel · PANEL_SIN_API_ADMIN: El panel no consume /api/admin `panel/src/app/app.ts`
- **error** · desarrollador_panel · PANEL_SIN_TOKEN: El panel debe enviar Authorization: Bearer en sus llamadas `panel/src/app/app.ts`
- **error** · desarrollador_panel · PANTALLA_INCOMPLETA: PA-003 · Bandeja de revisión - Jefe inmediato: faltan campos o textos del mockup (cobertura 0%) 
- **error** · desarrollador_portal · PANTALLA_ADMIN_EN_EMPLEADO: PA-003 · Bandeja de revisión - Jefe inmediato es una pantalla de aprobadores y aparece en la aplicación del empleado 
- **advertencia** · agente_pruebas · CRITERIOS_SIN_PRUEBA: Criterios sin caso de prueba: HU-001-CA-01, HU-001-CA-02, HU-001-CA-03, HU-001-CA-04, HU-002-CA-01, HU-002-CA-02, HU-003-CA-03, HU-003-CA-04, HU-004-CA-01, HU-004-CA-02, HU-004-CA-03, HU-005-CA-02 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-005-CA-01 | `backend/tests/test_api_public_health.py` | Verifica GET /api/health con 200 y respuesta ok. |
| PR-002 | HU-005-CA-01 | `backend/tests/test_api_admin_tipos_ausencia.py` | Comprueba que /api/tipos-ausencia devuelve solo id y nombre para datos activos creados en la base real. |
| PR-003 | HU-005-CA-01 | `backend/tests/test_api_admin_tipos_ausencia.py` | Comprueba que /api/admin/tipos-ausencia sin token responde 401/403. |
| PR-004 | HU-005-CA-01 | `backend/tests/test_api_admin_tipos_ausencia.py` | Comprueba que /api/admin/tipos-ausencia con token correcto devuelve el registro completo. |
| PR-005 | HU-005-CA-01 | `backend/tests/test_api_admin_tipos_ausencia.py` | Comprueba que /api/admin/tipos-ausencia con token inválido deniega acceso. |
| PR-006 | HU-003-CA-01 | `backend/tests/test_api_admin_solicitudes.py` | Comprueba que GET /api/admin/solicitudes/{id} con token devuelve el detalle con historial. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_api_admin_solicitudes.py` | Comprueba que GET /api/admin/solicitudes/{id} sin token deniega acceso. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_api_admin_solicitudes.py` | Comprueba que POST /api/admin/solicitudes/{id}/aprobar con token y datos válidos devuelve 200 y marca APROBADA. |
| PR-009 | HU-003-CA-02 | `backend/tests/test_api_admin_solicitudes.py` | Comprueba que POST /api/admin/solicitudes/{id}/rechazar con token requiere observación y con dato válido devuelve 200 y RECHAZADA. |
| PR-010 | HU-003-CA-02 | `backend/tests/test_api_admin_solicitudes.py` | Comprueba que las rutas de decisión sin token responden 401/403 y que una segunda decisión sobre solicitud finalizada rechaza el conflicto. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 7086 | 2752 | 14.7 s |
| desarrollador_backend | 3 | 36096 | 8731 | 45.3 s |
| desarrollador_portal | 3 | 30545 | 11543 | 46.2 s |
| agente_pruebas | 3 | 41985 | 13906 | 51.1 s |
| agente_iac | 1 | 1285 | 2531 | 12.9 s |
| desarrollador_panel | 3 | 28163 | 4371 | 19.8 s |
