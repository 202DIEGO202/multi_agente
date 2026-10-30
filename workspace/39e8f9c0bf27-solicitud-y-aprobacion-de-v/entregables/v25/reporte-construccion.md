# Reporte de construcción v25

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · DEPENDENCIA_NO_PERMITIDA: Módulo fuera de requirements.txt: cryptography `backend/app/security.py`
- **error** · desarrollador_backend · DEPENDENCIA_NO_PERMITIDA: Módulo fuera de requirements.txt: cryptography `backend/app/security.py`
- **error** · desarrollador_backend · DEPENDENCIA_NO_PERMITIDA: Módulo fuera de requirements.txt: cryptography `backend/app/security.py`
- **error** · desarrollador_panel · ENDPOINT_INEXISTENTE: La interfaz llama a /api/tipos-ausencia, que no existe en el backend 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_vacaciones_aceptacion.py` | Salud 200; registro 201 desde portal y formato oficial, asignación de revisión, persistencia y auditoría; duplicados 409 y entradas inválidas 422. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_vacaciones_aceptacion.py` | Persistencia del motivo obligatorio, límite válido de 4000 caracteres y rechazo de motivo ausente, vacío o de 4001 caracteres. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_vacaciones_aceptacion.py` | Catálogo interno autenticado en /api/empleado/tipos-ausencia sin campos administrativos; persistencia de fechas y horas, modalidades y períodos inválidos. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_vacaciones_aceptacion.py` | Estado e historial con auditoría, aislamiento entre empleados, autenticación y validación de filtros y límites de paginación. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_vacaciones_aceptacion.py` | Aviso al empleado ante aprobación o rechazo; estado informado, persistencia, lectura idempotente, aislamiento y validación del identificador. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_vacaciones_aceptacion.py` | Notificación única al aprobador de la etapa pendiente, sin aviso anticipado a Talento Humano ni exposición a otro jefe; paginación inválida 422. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_vacaciones_aceptacion.py` | Bandeja y alias administrativo 200 con credenciales completas, únicamente solicitudes asignadas; filtros inválidos y credenciales incompletas rechazados. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_vacaciones_aceptacion.py` | Aprobación y rechazo persistidos; decisiones inválidas 422, estado terminal y versión obsoleta 409; concurrencia con una única decisión válida. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_vacaciones_aceptacion.py` | Observaciones asociadas a revisión, decisión y autor; auditoría de inserción y rechazo de observación vacía al rechazar. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_vacaciones_aceptacion.py` | Auditoría de detalle, historial y modificaciones del jefe; acceso ajeno 403 auditado y desplazamiento inválido 422. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_vacaciones_aceptacion.py` | Validación y aprobación separadas o combinadas por Talento Humano; aprobación sin validación 422, repetición 409 y respeto de etapas y asignaciones. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_vacaciones_aceptacion.py` | Observaciones persistidas y auditadas en validación, aprobación combinada y rechazo; observación vacía 422 sin persistencia. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_vacaciones_aceptacion.py` | Accesos y modificaciones de Talento Humano auditados con actor, fecha y operación; acceso no asignado 403 y paginación inválida 422. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_vacaciones_aceptacion.py` | CRUD administrativo con estados de éxito definidos; todas las rutas administrativas sin token rechazadas; rol HR, duplicados, límites, estados inválidos, tipo utilizado e instantáneas. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_vacaciones_aceptacion.py` | Asociación 200 de cada flujo permitido y materialización de sus etapas y aprobadores; flujo inválido 422 sin alterar la configuración. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 6917 | 11266 | 178.5 s |
| desarrollador_backend | 4 | 96797 | 41171 | 548.5 s |
| desarrollador_portal | 4 | 77672 | 24318 | 329.5 s |
| agente_pruebas | 4 | 137713 | 60971 | 714.5 s |
| agente_iac | 1 | 1285 | 5962 | 112.3 s |
| desarrollador_panel | 4 | 82009 | 8810 | 135.4 s |
