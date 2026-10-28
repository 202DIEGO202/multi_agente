# Reporte de construcción v5

Aplicaciones: portal, panel. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · EJECUCION_CONSTRUCCION: -27T02:07:31.280Z
#29 6.214 
#29 6.215 ✘ [ERROR] NG8002: Can't bind to 'ngModel' since it isn't a known property of 'input'. [plugin angular-compiler]
#29 6.215 
#29 6.215     src/app/app.ts:75:65:
#29 6.215       75 │ ... class="form-control" [(ngModel)]="token" name="token" autocomp...
#29 6.215          ╵                          ~~~~~~~~~~~~~~~~~~~
#29 6.215 
#29 6.215 
#29 ERROR: process "/bin/sh -c npx ng build" did not complete successfully: exit code: 1
------
 > [panel build 6/6] RUN npx ng build:
6.213 ✔ Building...
6.214 Application bundle generation failed. [4.726 seconds] - 2026-10-27T02:07:31.280Z
6.214 
6.215 ✘ [ERROR] NG8002: Can't bind to 'ngModel' since it isn't a known property of 'input'. [plugin angular-compiler]
6.215 
6.215     src/app/app.ts:75:65:
6.215       75 │ ... class="form-control" [(ngModel)]="token" name="token" autocomp...
6.215          ╵                          ~~~~~~~~~~~~~~~~~~~
6.215 
6.215 
------
 Image chk-6bf2c4337d-backend Building 
 Image chk-6bf2c4337d-portal Building 
 Image chk-6bf2c4337d-panel Building 
Dockerfile:6

--------------------

   4 |     RUN npm install --no-audit --no-fund --legacy-peer-deps

   5 |     COPY . .

   6 | >>> RUN npx ng build

   7 |     

   8 |     FROM nginx:1.27-alpine

--------------------

target panel: failed to solve: process "/bin/sh -c npx ng build" did not complete successfully: exit code: 1



View build details: docker-desktop://dashboard/build/default/default/kpkc21j6mvzkpdqzntwot9sae 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Prueba creación exitosa de solicitud con datos válidos, edad mayor a 23 y nivel de estudios mínimo bachillerato. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_api.py` | Prueba error al enviar solicitud con datos incompletos, validación de campos obligatorios. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba error al enviar solicitud con nivel de estudios inferior a bachillerato. |
| PR-004 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba error al enviar solicitud con edad menor o igual a 23 años. |
| PR-005 | HU-009-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área puede listar solicitudes y visualizar datos del solicitante y aprobador. |
| PR-006 | HU-010-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área aprueba una solicitud y el sistema registra la acción y notifica al administrador. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área rechaza una solicitud con motivo obligatorio y el sistema registra y notifica correctamente. |
| PR-008 | Acceso admin sin token | `backend/tests/test_api.py` | Prueba que las rutas administrativas sin token devuelven error 401 o 403. |
| PR-009 | Acceso admin con token | `backend/tests/test_api.py` | Prueba que las rutas administrativas con token válido devuelven 200. |
| PR-010 | GET /api/health | `backend/tests/test_api.py` | Prueba que la ruta /api/health responde con estado 200 y contenido esperado. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4876 | 1520 | 13.1 s |
| desarrollador_backend | 1 | 6819 | 3860 | 25.8 s |
| desarrollador_portal | 3 | 15400 | 7007 | 49.0 s |
| agente_pruebas | 1 | 5758 | 2744 | 19.0 s |
| agente_iac | 1 | 1238 | 1763 | 14.2 s |
| desarrollador_panel | 1 | 3848 | 3032 | 25.8 s |
