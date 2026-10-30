# Reporte de construcción v28

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PORTAL_SESION_SIN_BEARER: Las consultas y el registro mediante fetch no envían Authorization: Bearer, exigido por el contrato de las rutas del empleado; credentials: 'same-origin' solo envía cookies y no sustituye ese encabezado. El mismo defecto aparece en detalle-solicitud.component.ts. Centralizar las peticiones e incorporar el token de la sesión verificada del empleado, sin reutilizar credenciales administrativas, para evitar el rechazo de las operaciones autenticadas. `portal/src/app/solicitudes.component.ts`
- **advertencia** · desarrollador_portal · AVISOS_FILTRADOS_TRAS_PAGINACION: El detalle obtiene únicamente los primeros 100 avisos del empleado y después los filtra por solicitud_id. Una solicitud cuyos avisos estén en páginas posteriores mostrará que no hay avisos aunque existan. Recorrer las páginas necesarias o incorporar un filtro autorizado por solicitud en la API y utilizarlo antes de paginar. `portal/src/app/detalle-solicitud.component.ts`
- **advertencia** · desarrollador_portal · SOLICITUDES_SIN_NAVEGACION_PAGINADA: El listado solicita siempre limit=100&offset=0 y no ofrece navegación a páginas posteriores, dejando inaccesibles desde esta pantalla las solicitudes fuera de ese primer bloque. Añadir controles de paginación y actualizar offset al navegar. `portal/src/app/solicitudes.component.ts`
- **advertencia** · agente_pruebas · PRUEBA_AUTOAPROBACION_NO_EJERCITADA: El test test_hu_003_ca_02_control_optimista_concurrente_y_autoaprobacion intenta decidir como usuarios que solo tienen el rol EMPLEADO; sus respuestas 404 no demuestran la prevención de autoaprobación para un usuario con permisos de aprobador. Añadir un escenario con un solicitante que también tenga el rol aprobador y una revisión propia asignada a él; comprobar que la decisión se deniega y que no cambian la revisión, el estado ni el historial de la solicitud. `backend/tests/test_aceptacion_ausencias.py`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_aceptacion_empleado.py` | Registro por portal y formato oficial con 201; rechazo de suplantación y referencia obligatoria ausente. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_aceptacion_empleado.py` | Persistencia del motivo y validación de obligatoriedad y contenido vacío en backend. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_aceptacion_empleado.py` | Catálogo de lectura, fechas y modalidades de horas; límites y rechazo de intervalos inválidos. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_aceptacion_empleado.py` | Estado e historial propios auditados, aislamiento por sesión y rechazo de estados e identificadores inválidos. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_aceptacion_empleado.py` | Avisos persistidos de cambio de estado, aislamiento entre empleados y validación de paginación. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_aceptacion_empleado.py` | Avisos únicamente al aprobador del paso activo, sin duplicados; rechazo del acceso de un actor sin rol de empleado. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Se conserva la prueba de bandeja asignada, orden del flujo, autorización y límites. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Se conservan aprobación y rechazo, validaciones, prevención de autoaprobación y conflicto concurrente 200/409. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Se conservan observaciones asociadas a revisión y decisión, rechazo de contenido vacío y conflictos de versión. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_aceptacion_ausencias.py` | Se conservan verificaciones de auditoría de accesos y modificaciones del jefe y rechazo de acciones sobre revisiones cerradas. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Se conservan validación y aprobación separadas o conjuntas por Talento Humano y rechazo de aprobación sin validación. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Se conservan observaciones de validación, aprobación y rechazo, con comprobación de autor y revisión y validación de contenido. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Se conserva auditoría persistida de Talento Humano y denegación de consulta de historial a otro empleado. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_aceptacion_empleado.py` | Se conserva la prohibición de administrar el catálogo desde rutas del empleado y de acceder sin token a administración; el ciclo administrativo permanece en test_aceptacion_ausencias.py. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_aceptacion_empleado.py` | Se conserva la prohibición de configurar flujos desde el empleado; las pruebas administrativas de asignación, flujo inválido y versiones permanecen en test_aceptacion_ausencias.py. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_portal | 2 | 33211 | 8766 | 134.3 s |
| validador_artefactos | 11 | 164165 | 3446 | 131.1 s |
| desarrollador_backend | 1 | 24992 | 4705 | 75.5 s |
| desarrollador_panel | 1 | 24889 | 558 | 13.9 s |
| agente_pruebas | 2 | 68985 | 9593 | 132.4 s |
