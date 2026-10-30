# Reporte de construcción v2

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/tipos-ausencia es público y expone los mismos datos que el administrativo /api/admin/tipos-ausencia `backend/app/main.py`
- **error** · desarrollador_panel · PANEL_SIN_API_ADMIN: El panel no consume /api/admin `panel/src/app/app.ts`
- **error** · desarrollador_panel · PANEL_SIN_TOKEN: El panel debe enviar Authorization: Bearer en sus llamadas `panel/src/app/app.ts`
- **error** · desarrollador_portal · PANTALLA_ADMIN_EN_EMPLEADO: PA-003 · Bandeja de revisión - Jefe inmediato es una pantalla de aprobadores y aparece en la aplicación del empleado 
- **advertencia** · agente_pruebas · CRITERIOS_SIN_PRUEBA: Criterios sin caso de prueba: HU-001-CA-02, HU-001-CA-04, HU-002-CA-01, HU-002-CA-02, HU-003-CA-01, HU-003-CA-02, HU-003-CA-03, HU-003-CA-04, HU-004-CA-01, HU-004-CA-02, HU-004-CA-03 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-005-CA-01 | `backend/tests/test_tipos_ausencia_api.py` | Verifica que /api/admin/tipos-ausencia exige token y que el listado público /api/tipos-ausencia no expone campos administrativos, además de validar alta y duplicado del catálogo. |
| PR-002 | HU-005-CA-02 | `backend/tests/test_tipos_ausencia_api.py` | Cubre la asignación válida de flujo de aprobación y los errores por lista vacía y rol aprobador inválido. |
| PR-003 | HU-001-CA-01 | `backend/tests/test_health_and_public_scope.py` | Confirma el estado sano del servicio con GET /api/health. |
| PR-004 | HU-001-CA-03 | `backend/tests/test_health_and_public_scope.py` | Comprueba que el listado público de tipos de ausencia siga restringido a campos no administrativos. |
| PR-005 | HU-001-CA-03 | `backend/app/main.py` | Corrige el endpoint público /api/tipos-ausencia para que responda con campos públicos separados de los administrativos. |
| PR-006 | HU-005-CA-01 | `panel/src/app/app.ts` | Corrige el panel para consumir /api/admin/tipos-ausencia con Authorization: Bearer. |
| PR-007 | HU-005-CA-01 | `panel/src/app/routes.ts` | Restituye la ruta del panel sin imports rotos, incluyendo el componente de bandeja si aplica. |
| PR-008 | HU-004-CA-01 | `portal/src/app/pa-004-validacion-talento-humano.component.ts` | Completa la pantalla PA-004 del portal del empleado con todos los campos y textos del mockup aprobado de Talento Humano. |
| PR-009 | HU-004-CA-01 | `portal/src/app/routes.ts` | Asegura que la pantalla PA-004 quede expuesta en el portal correcto y no en rutas del panel administrativo. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 7012 | 3551 | 15.0 s |
| desarrollador_backend | 3 | 37861 | 8813 | 34.0 s |
| desarrollador_portal | 3 | 30405 | 7159 | 27.9 s |
| agente_pruebas | 3 | 39625 | 9930 | 46.6 s |
| agente_iac | 1 | 1285 | 2150 | 11.4 s |
| desarrollador_panel | 3 | 19364 | 6587 | 27.6 s |
