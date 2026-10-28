# Reporte de construcción v8

Aplicaciones: portal, panel. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · EJECUCION_CONSTRUCCION: olume chk-6bf2c4337d_db-data Creating 
 Volume chk-6bf2c4337d_db-data Creating 
 Network chk-6bf2c4337d_default Creating 
 Volume chk-6bf2c4337d_db-data Created 
 Volume chk-6bf2c4337d_db-data Created 
 Network chk-6bf2c4337d_default Created 
 Network chk-6bf2c4337d_default Created 
 Container chk-6bf2c4337d-db-1 Creating 
 Container chk-6bf2c4337d-panel-1 Creating 
 Container chk-6bf2c4337d-portal-1 Creating 
 Container chk-6bf2c4337d-portal-1 Created 
 Container chk-6bf2c4337d-panel-1 Created 
 Container chk-6bf2c4337d-db-1 Created 
 Container chk-6bf2c4337d-backend-1 Creating 
 Container chk-6bf2c4337d-backend-1 Created 
 Container chk-6bf2c4337d-edge-1 Creating 
 Container chk-6bf2c4337d-edge-1 Created 
 Container chk-6bf2c4337d-db-1 Starting 
 Container chk-6bf2c4337d-portal-1 Starting 
 Container chk-6bf2c4337d-panel-1 Starting 
 Container chk-6bf2c4337d-db-1 Started 
 Container chk-6bf2c4337d-db-1 Waiting 
 Container chk-6bf2c4337d-portal-1 Started 
 Container chk-6bf2c4337d-panel-1 Started 
 Container chk-6bf2c4337d-db-1 Healthy 
 Container chk-6bf2c4337d-backend-1 Starting 
 Container chk-6bf2c4337d-backend-1 Started 
 Container chk-6bf2c4337d-portal-1 Waiting 
 Container chk-6bf2c4337d-panel-1 Waiting 
 Container chk-6bf2c4337d-backend-1 Waiting 
 Container chk-6bf2c4337d-backend-1 Error dependency backend failed to start
 Container chk-6bf2c4337d-panel-1 Error dependency panel failed to start
dependency failed to start: container chk-6bf2c4337d-backend-1 exited (1) 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Enviar solicitud con datos válidos y recibir id y estado Pendiente. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_api.py` | Intentar enviar solicitud con campos incompletos o inválidos y recibir error 422. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_api.py` | Enviar solicitud con nivel de estudios inferior a bachillerato o edad menor o igual a 23 años y recibir mensajes de error específicos. |
| PR-004 | HU-009-CA-01 | `backend/tests/test_api.py` | Líder de área visualiza datos del solicitante y del aprobador en la pantalla de aprobación. |
| PR-005 | HU-010-CA-01 | `backend/tests/test_api.py` | Líder de área aprueba solicitud y sistema registra acción y notifica al administrador. |
| PR-006 | HU-011-CA-01 | `backend/tests/test_api.py` | Líder de área rechaza solicitud con motivo obligatorio y sistema registra acción y notifica al empleado. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_api.py` | Intentar rechazar solicitud sin motivo obligatorio y recibir error de validación. |
| PR-008 | GET /api/health → 200 | `backend/tests/test_api.py` | Verificar que la ruta pública /api/health responde con estado 200 y contenido esperado. |
| PR-009 | /api/admin/ sin token → 401 o 403 | `backend/tests/test_api.py` | Verificar que las rutas administrativas sin token devuelven error 401 o 403. |
| PR-010 | /api/admin/ con token correcto → 200 | `backend/tests/test_api.py` | Verificar que las rutas administrativas con token válido responden con estado 200 o error esperado si recurso no existe. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4876 | 1196 | 10.4 s |
| desarrollador_backend | 1 | 6449 | 4299 | 28.9 s |
| desarrollador_portal | 3 | 14717 | 5696 | 33.0 s |
| agente_pruebas | 1 | 5789 | 4180 | 29.9 s |
| agente_iac | 1 | 1238 | 1784 | 14.7 s |
| desarrollador_panel | 1 | 3972 | 2825 | 19.8 s |
