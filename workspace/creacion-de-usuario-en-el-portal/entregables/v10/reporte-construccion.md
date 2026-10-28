# Reporte de construcción v10

Aplicaciones: portal, panel. Arquitectura v3, backlog v13.

## Validación (reglas, ejecución real en Docker y revisión)
- **advertencia** · agente_pruebas · CRITERIOS_SIN_PRUEBA: Criterios sin caso de prueba: HU-009-CA-01, HU-010-CA-01, HU-011-CA-01 
- **advertencia** · validador_artefactos · SEP-001: Las pantallas del empleado (portal) y del panel (aprobadores) están correctamente separadas en aplicaciones distintas, cumpliendo la arquitectura definida. 
- **advertencia** · desarrollador_backend · VAL-002: El backend valida correctamente las reglas de negocio de edad mínima (>23 años) y nivel de estudios mínimo (bachillerato) al crear solicitudes, conforme a RN-001, RES-001 y RES-002. `backend/app/main.py`
- **advertencia** · desarrollador_backend · VAL-003: El backend implementa control de acceso para rutas administrativas con token de administrador, asegurando que solo usuarios autorizados puedan aprobar o rechazar solicitudes. `backend/app/main.py`
- **advertencia** · agente_pruebas · PRB-004: Los casos de prueba cubren adecuadamente los criterios de aceptación de las historias, incluyendo validaciones de datos, control de acceso y acciones de aprobación/rechazo con notificaciones. `backend/tests/test_api.py`
- **advertencia** · desarrollador_portal · FOR-005: Los campos del formulario en la pantalla del portal coinciden con los campos definidos en la tabla de usuarios y solicitudes, incluyendo validaciones de tipo y obligatoriedad. `portal/src/app/app.ts`
- **advertencia** · desarrollador_panel · FOR-006: La pantalla del panel muestra correctamente los datos del solicitante y del líder de área, y permite registrar la decisión con motivo obligatorio en caso de rechazo, conforme a las historias HU-009, HU-010 y HU-011. `panel/src/app/app.ts`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_api.py` | Verifica que GET /api/health retorne 200 con {'estado': 'ok'} para comprobar salud del sistema. |
| PR-002 | HU-007-CA-01 | `backend/tests/test_api.py` | Permite crear solicitud con datos válidos y recibe id y estado Pendiente. |
| PR-003 | HU-007-CA-02 | `backend/tests/test_api.py` | No permite crear solicitud con datos incompletos, retorna error 422. |
| PR-004 | HU-007-CA-03 | `backend/tests/test_api.py` | Bloquea solicitud con nivel de estudios inferior a bachillerato, muestra mensaje de error. |
| PR-005 | HU-007-CA-03 | `backend/tests/test_api.py` | Bloquea solicitud con edad menor o igual a 23 años, muestra mensaje de error. |
| PR-006 | AC-003 | `backend/tests/test_api.py` | Verifica que rutas administrativas sin token devuelvan 401 o 403. |
| PR-007 | AC-003 | `backend/tests/test_api.py` | Verifica que rutas administrativas con token válido respondan 200 y permitan listar solicitudes. |
| PR-008 | HU-009-CA-01 | `backend/tests/test_api.py` | Permite obtener detalle de solicitud con datos del solicitante y líder de área para revisión. |
| PR-009 | HU-010-CA-01 | `backend/tests/test_api.py` | Permite aprobar solicitud, registra acción y notifica al administrador de AD. |
| PR-010 | HU-011-CA-01 | `backend/tests/test_api.py` | Permite rechazar solicitud con motivo obligatorio, registra acción, cambia estado y notifica al empleado. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 4876 | 1202 | 10.2 s |
| desarrollador_backend | 2 | 17557 | 8618 | 66.0 s |
| desarrollador_portal | 3 | 14888 | 5643 | 40.2 s |
| agente_pruebas | 2 | 13776 | 4155 | 29.8 s |
| agente_iac | 1 | 1238 | 1781 | 12.7 s |
| desarrollador_panel | 2 | 11106 | 5292 | 35.4 s |
| validador_artefactos | 1 | 6355 | 410 | 5.0 s |
