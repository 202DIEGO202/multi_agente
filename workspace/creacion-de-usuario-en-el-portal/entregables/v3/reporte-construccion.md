# Reporte de construcción v3

Aplicaciones: portal. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/solicitudes/{} es público y expone los mismos datos que el administrativo /api/admin/solicitudes/{solicitud_id} `backend/app/main.py`
- **advertencia** · agente_pruebas · CRITERIOS_SIN_PRUEBA: Criterios sin caso de prueba: HU-009-CA-01, HU-010-CA-01, HU-011-CA-01 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_solicitudes.py` | Verifica que un empleado puede crear una solicitud válida con todos los datos requeridos y que la solicitud queda en estado Pendiente. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_solicitudes.py` | Verifica que el sistema muestra mensajes de error claros y bloquea el envío cuando los datos están incompletos o no cumplen las validaciones de edad y nivel de estudios. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_solicitudes.py` | Verifica que el sistema muestra mensajes de error específicos para nivel de estudios inferior a bachillerato y edad menor o igual a 23 años, bloqueando el envío. |
| PR-004 | HU-007-CA-01 | `backend/tests/test_solicitudes.py` | Verifica que un empleado puede consultar su solicitud y recibe solo el id y estado. |
| PR-005 | Acceso a rutas administrativas sin token | `backend/tests/test_solicitudes.py` | Verifica que las rutas administrativas requieren token y sin él responden 401 o 403. |
| PR-006 | Acceso a rutas administrativas con token | `backend/tests/test_solicitudes.py` | Verifica que las rutas administrativas con token válido responden 200. |
| PR-007 | GET /api/health | `backend/tests/test_solicitudes.py` | Verifica que el endpoint de salud responde con estado ok y código 200. |
| PR-008 | HU-009, HU-010, HU-011 | `backend/tests/test_solicitudes.py` | Verifica que el administrador puede listar solicitudes con token válido. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4839 | 1737 | 15.5 s |
| desarrollador_backend | 3 | 25231 | 11058 | 77.2 s |
| desarrollador_portal | 3 | 21344 | 12153 | 80.5 s |
| agente_pruebas | 3 | 21028 | 5996 | 46.6 s |
| agente_iac | 1 | 1238 | 2267 | 17.7 s |
