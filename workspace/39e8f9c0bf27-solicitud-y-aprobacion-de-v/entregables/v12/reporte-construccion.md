# Reporte de construcción v12

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · EJECUCION_CONSTRUCCION: 743.2 npm notice
#29 743.2 npm error A complete log of this run can be found in: /root/.npm/_logs/2026-10-29T15_01_53_564Z-debug-0.log
#29 ERROR: process "/bin/sh -c npm install --no-audit --no-fund --legacy-peer-deps" did not complete successfully: exit code: 1

#30 [panel build 4/6] RUN npm install --no-audit --no-fund --legacy-peer-deps
#30 CANCELED
------
 > [portal build 4/6] RUN npm install --no-audit --no-fund --legacy-peer-deps:
743.2 npm error   stderr: undefined
743.2 npm error }
743.2 npm error
743.2 npm error Node.js v22.23.4
743.2 npm notice
743.2 npm notice New major version of npm available! 10.9.9 -> 12.2.1
743.2 npm notice Changelog: https://github.com/npm/cli/releases/tag/v12.2.1
743.2 npm notice To update run: npm install -g npm@12.2.1
743.2 npm notice
743.2 npm error A complete log of this run can be found in: /root/.npm/_logs/2026-10-29T15_01_53_564Z-debug-0.log
------
 Image chk-262ae561db-backend Building 
 Image chk-262ae561db-portal Building 
 Image chk-262ae561db-panel Building 
Dockerfile:4

--------------------

   2 |     WORKDIR /app

   3 |     COPY package.json ./

   4 | >>> RUN npm install --no-audit --no-fund --legacy-peer-deps

   5 |     COPY . .

   6 |     RUN npx ng build

--------------------

target portal: failed to solve: process "/bin/sh -c npm install --no-audit --no-fund --legacy-peer-deps" did not complete successfully: exit code: 1



View build details: docker-desktop://dashboard/build/default/default/p7ap298rir27i0aru1rty2pyl 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Se conserva la prueba de registro público, persistencia del flujo y rechazo de datos incompletos. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Se conserva la persistencia del motivo y la validación de motivo ausente, vacío o compuesto por espacios. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan fechas, horas, límites temporales, tipo inactivo y prohibición de horas según configuración. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan seguimiento del estado, historial ordenado, auditoría de consulta y aislamiento entre empleados. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan notificaciones persistidas para aprobación y rechazo, y ausencia de duplicados tras repetir una decisión. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan notificación al siguiente aprobador, validación de su elegibilidad y aislamiento de notificaciones. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan campos de la bandeja PA-003 en la API, asignación al jefe, exclusión de solicitudes ajenas y validación de paginación. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan aprobación, rechazo, estados inválidos, versiones, entradas inválidas y conflicto concurrente sin doble decisión. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan observaciones asociadas a la decisión, obligatoriedad al rechazar y límite de longitud. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan auditorías de detalle, historial y modificaciones, y denegación a actores no asignados. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan validación y aprobación por Talento Humano, restricciones de rol y bloqueo de etapas anteriores pendientes. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan observaciones de validación y rechazo por Talento Humano y errores de validación. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan trazabilidad de Talento Humano y aislamiento de solicitudes. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan éxitos autenticados de CRUD, duplicados, referencias, auditoría, estados inválidos y límites de nombre y versión. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Se conservan asociación de los tres flujos, etapas ordenadas, configuración preservada, conflictos y rechazo de flujos inválidos o inactivos. |
| PR-016 | HU-005-CA-01 | `backend/tests/test_autorizacion_regresion.py` | Regresión de catálogo interno: no expone copias anónimas; operaciones administrativas rechazan ausencia de credenciales, esquema incorrecto y Bearer incorrecto. Salud pública devuelve 200. |
| PR-017 | HU-005-CA-02 | `backend/tests/test_autorizacion_regresion.py` | Consulta y asignación de flujos rechazan credenciales ausentes o inválidas. |
| PR-018 | HU-003-CA-01 | `backend/tests/test_autorizacion_regresion.py` | La bandeja administrativa rechaza acceso sin token o con credenciales inválidas. |
| PR-019 | HU-003-CA-02 | `backend/tests/test_autorizacion_regresion.py` | La decisión administrativa exige Bearer válido incluso con un cuerpo válido. |
| PR-020 | HU-003-CA-04 | `backend/tests/test_autorizacion_regresion.py` | El detalle administrativo no permite acceso anónimo ni con credenciales inválidas. |
| PR-021 | HU-004-CA-03 | `backend/tests/test_autorizacion_regresion.py` | El historial administrativo rechaza accesos sin autenticación válida. |
| PR-022 | HU-002-CA-02 | `backend/tests/test_autorizacion_regresion.py` | Las notificaciones administrativas exigen autenticación válida. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_portal | 1 | 12195 | 1689 | 30.9 s |
| desarrollador_panel | 1 | 20281 | 3163 | 65.6 s |
