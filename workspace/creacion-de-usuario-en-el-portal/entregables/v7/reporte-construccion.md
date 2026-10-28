# Reporte de construcción v7

Aplicaciones: portal, panel. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_panel · ENDPOINT_INEXISTENTE: La interfaz llama a /api/admin/solicitudes/${this.solicitud(, que no existe en el backend 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Prueba que un empleado puede crear una solicitud válida con todos los datos requeridos y validaciones de edad y nivel de estudios. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_api.py` | Prueba que el sistema rechaza solicitudes con datos incompletos o inválidos y muestra mensajes de error. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_api.py` | Prueba que el sistema muestra mensajes de error específicos para nivel de estudios y edad cuando son inválidos. |
| PR-004 | HU-009-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área puede visualizar los datos del solicitante y sus propios datos en la pantalla de aprobación. |
| PR-005 | HU-010-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área puede aprobar una solicitud, registrando la acción y notificando al administrador de Active Directory. |
| PR-006 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba que el líder de área puede rechazar una solicitud con un motivo obligatorio, registrando la acción y notificando al empleado. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_api.py` | Prueba que el sistema no permite rechazar una solicitud sin un motivo obligatorio y devuelve error. |
| PR-008 | AC-003 | `backend/tests/test_api.py` | Prueba que las rutas administrativas sin token o con token inválido devuelven error 401 o 403. |
| PR-009 | AC-003 | `backend/tests/test_api.py` | Prueba que las rutas administrativas con token válido devuelven código 200. |
| PR-010 | GET /api/health → 200 | `backend/tests/test_api.py` | Prueba que la ruta /api/health responde con estado 200 y el contenido esperado. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4876 | 1179 | 10.7 s |
| desarrollador_backend | 1 | 6448 | 3845 | 27.6 s |
| desarrollador_portal | 1 | 3233 | 2043 | 13.1 s |
| agente_pruebas | 1 | 5771 | 4094 | 30.3 s |
| agente_iac | 1 | 1238 | 1645 | 12.1 s |
| desarrollador_panel | 3 | 17147 | 8011 | 52.5 s |
