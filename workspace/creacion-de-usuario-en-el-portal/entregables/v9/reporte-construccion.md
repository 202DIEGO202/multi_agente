# Reporte de construcción v9

Aplicaciones: portal, panel. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · EJECUCION_CONSTRUCCION: me chk-6bf2c4337d_db-data Creating 
 Network chk-6bf2c4337d_default Creating 
 Volume chk-6bf2c4337d_db-data Created 
 Volume chk-6bf2c4337d_db-data Created 
 Network chk-6bf2c4337d_default Created 
 Network chk-6bf2c4337d_default Created 
 Container chk-6bf2c4337d-panel-1 Creating 
 Container chk-6bf2c4337d-portal-1 Creating 
 Container chk-6bf2c4337d-db-1 Creating 
 Container chk-6bf2c4337d-panel-1 Created 
 Container chk-6bf2c4337d-portal-1 Created 
 Container chk-6bf2c4337d-db-1 Created 
 Container chk-6bf2c4337d-backend-1 Creating 
 Container chk-6bf2c4337d-backend-1 Created 
 Container chk-6bf2c4337d-edge-1 Creating 
 Container chk-6bf2c4337d-edge-1 Created 
 Container chk-6bf2c4337d-portal-1 Starting 
 Container chk-6bf2c4337d-panel-1 Starting 
 Container chk-6bf2c4337d-db-1 Starting 
 Container chk-6bf2c4337d-portal-1 Started 
 Container chk-6bf2c4337d-panel-1 Started 
 Container chk-6bf2c4337d-db-1 Started 
 Container chk-6bf2c4337d-db-1 Waiting 
 Container chk-6bf2c4337d-db-1 Healthy 
 Container chk-6bf2c4337d-backend-1 Starting 
 Container chk-6bf2c4337d-backend-1 Started 
 Container chk-6bf2c4337d-portal-1 Waiting 
 Container chk-6bf2c4337d-panel-1 Waiting 
 Container chk-6bf2c4337d-backend-1 Waiting 
 Container chk-6bf2c4337d-backend-1 Healthy 
 Container chk-6bf2c4337d-portal-1 Error dependency portal failed to start
 Container chk-6bf2c4337d-panel-1 Error dependency panel failed to start
dependency failed to start: container chk-6bf2c4337d-portal-1 is unhealthy 
- **error** · desarrollador_panel · EJECUCION_CONSTRUCCION: me chk-6bf2c4337d_db-data Creating 
 Network chk-6bf2c4337d_default Creating 
 Volume chk-6bf2c4337d_db-data Created 
 Volume chk-6bf2c4337d_db-data Created 
 Network chk-6bf2c4337d_default Created 
 Network chk-6bf2c4337d_default Created 
 Container chk-6bf2c4337d-panel-1 Creating 
 Container chk-6bf2c4337d-portal-1 Creating 
 Container chk-6bf2c4337d-db-1 Creating 
 Container chk-6bf2c4337d-panel-1 Created 
 Container chk-6bf2c4337d-portal-1 Created 
 Container chk-6bf2c4337d-db-1 Created 
 Container chk-6bf2c4337d-backend-1 Creating 
 Container chk-6bf2c4337d-backend-1 Created 
 Container chk-6bf2c4337d-edge-1 Creating 
 Container chk-6bf2c4337d-edge-1 Created 
 Container chk-6bf2c4337d-portal-1 Starting 
 Container chk-6bf2c4337d-panel-1 Starting 
 Container chk-6bf2c4337d-db-1 Starting 
 Container chk-6bf2c4337d-portal-1 Started 
 Container chk-6bf2c4337d-panel-1 Started 
 Container chk-6bf2c4337d-db-1 Started 
 Container chk-6bf2c4337d-db-1 Waiting 
 Container chk-6bf2c4337d-db-1 Healthy 
 Container chk-6bf2c4337d-backend-1 Starting 
 Container chk-6bf2c4337d-backend-1 Started 
 Container chk-6bf2c4337d-portal-1 Waiting 
 Container chk-6bf2c4337d-panel-1 Waiting 
 Container chk-6bf2c4337d-backend-1 Waiting 
 Container chk-6bf2c4337d-backend-1 Healthy 
 Container chk-6bf2c4337d-portal-1 Error dependency portal failed to start
 Container chk-6bf2c4337d-panel-1 Error dependency panel failed to start
dependency failed to start: container chk-6bf2c4337d-portal-1 is unhealthy 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Prueba creación de solicitud válida con datos completos, edad mayor a 23 y nivel de estudios mínimo bachillerato. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_api.py` | Prueba error de validación al enviar datos incompletos o inválidos en la solicitud. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba error específico cuando nivel de estudios es inferior a bachillerato o edad menor o igual a 23 años. |
| PR-004 | HU-009-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área visualiza correctamente los datos del solicitante y del aprobador en la pantalla de aprobación. |
| PR-005 | HU-010-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área puede aprobar una solicitud y que se registra la acción y notifica al administrador. |
| PR-006 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área puede rechazar una solicitud con motivo obligatorio y se notifica al empleado. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba error al intentar rechazar una solicitud sin proporcionar motivo obligatorio. |
| PR-008 | GET /api/health → 200 | `backend/tests/test_api.py` | Prueba que la ruta pública GET /api/health responde con estado 200 y el mensaje esperado. |
| PR-009 | /api/admin/ sin token → 401 o 403 | `backend/tests/test_api.py` | Prueba que las rutas administrativas sin token devuelven error 401 o 403. |
| PR-010 | /api/admin/ con token incorrecto → 401 o | `backend/tests/test_api.py` | Prueba que las rutas administrativas con token incorrecto devuelven error 401 o 403. |
| PR-011 | /api/admin/ con token correcto → 200 | `backend/tests/test_api.py` | Prueba que las rutas administrativas con token correcto devuelven estado 200. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4876 | 1139 | 9.3 s |
| desarrollador_backend | 1 | 6402 | 4030 | 29.0 s |
| desarrollador_portal | 2 | 9193 | 4326 | 30.1 s |
| agente_pruebas | 1 | 5759 | 2631 | 18.4 s |
| agente_iac | 1 | 1238 | 1648 | 12.7 s |
| desarrollador_panel | 2 | 10991 | 5158 | 37.2 s |
