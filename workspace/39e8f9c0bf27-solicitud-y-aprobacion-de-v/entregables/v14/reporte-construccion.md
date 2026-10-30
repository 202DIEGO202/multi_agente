# Reporte de construcción v14

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PORTAL_REGISTRO_SIN_PERSISTENCIA: Enviar solicitud solo revisa campos locales y muestra un aviso; nunca registra la solicitud, bloqueando HU-001-CA-01 a CA-03. Conectar el formulario al POST /api/solicitudes con la credencial del empleado, enviar tipo_ausencia_id, fecha_inicio, fecha_fin, hora_inicio, hora_fin y motivo, y gestionar la respuesta y los errores. Sustituir los nombres fijos del selector por identificadores del catálogo obtenido mediante acceso autorizado del empleado, sin utilizar credenciales administrativas. `portal/src/app/solicitudes.ts`
- **error** · desarrollador_portal · PORTAL_SEGUIMIENTO_INOPERANTE: Las pantallas de solicitudes y detalle sustituyen el seguimiento por mensajes informativos y no realizan consultas, por lo que el empleado no puede consultar su estado ni historial según HU-001-CA-04. Permitir seleccionar o indicar una solicitud y consultar con autenticación del empleado GET /api/portal/solicitudes/{solicitud_id} y GET /api/portal/solicitudes/{solicitud_id}/historial; mostrar sus resultados y gestionar respuestas 401 y 404. `portal/src/app/notificaciones.ts`
- **error** · desarrollador_portal · PORTAL_AVISOS_NO_CONSULTABLES: La sección de notificación de cambio de estado muestra únicamente un texto fijo y no carga avisos del empleado, dejando inoperante la función de PA-002 vinculada a HU-002-CA-01. Integrar una consulta autenticada de notificaciones propias y mostrar los avisos reales, diferenciando la ausencia de avisos de los errores de autenticación o carga y sin acceder a la bandeja administrativa. `portal/src/app/notificaciones.ts`
- **advertencia** · agente_pruebas · PR-AISLAMIENTO-CREDENCIALES: Escenario.__init__ sustituye EMPLOYEE_API_TOKEN por ADMIN_API_TOKEN y request utiliza la misma credencial para portal y panel. Esto impide detectar que una credencial exclusiva de empleado obtenga acceso administrativo. Usar credenciales distintas tomadas del entorno, separar los encabezados del portal y del panel y añadir pruebas que rechacen la credencial de empleado en las operaciones administrativas. `backend/tests/test_ausencias_aceptacion.py`
- **advertencia** · agente_pruebas · PR-REGISTRO-SIN-REVISION-ASIGNADA: test_hu_001_ca_01_registro_para_revision_y_validacion comprueba la solicitud y su estado, pero no que el registro cree una revisión asignada al aprobador del flujo. Las pruebas de bandeja y decisiones insertan las revisiones directamente mediante Escenario.solicitud, por lo que no detectan solicitudes creadas por el portal que queden sin revisión. Añadir casos de creación por API para los tres flujos y comprobar la revisión inicial, su rol y aprobador, y su aparición en la bandeja correspondiente. `backend/tests/test_ausencias_aceptacion.py`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Registro autenticado para revisión, persistencia del solicitante y flujo; rechazo de datos obligatorios ausentes y acceso sin credencial. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Persistencia del motivo y rechazo centralizado de motivo ausente, vacío o compuesto por espacios. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Fechas y horas válidas; rechazo de períodos invertidos, horas incompletas o iguales, fechas inválidas y tipos inactivos o incompatibles. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Consultas actualizadas a /api/portal/solicitudes/{id} y su historial: seguimiento propio, auditoría, autenticación, límites de identificadores y aislamiento por identidad del servidor. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Notificación persistida al empleado tras aprobación o rechazo; una decisión repetida genera conflicto sin duplicar avisos. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Aviso al siguiente aprobador válido, rechazo de asignaciones incompatibles y aislamiento de notificaciones; validación de paginación. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Bandeja del jefe con datos de revisión y únicamente asignaciones propias; límites y errores de paginación. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Aprobación y rechazo persistidos con actor y versiones; estados inválidos, versiones obsoletas, decisiones duplicadas y conflicto concurrente sin doble decisión. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Observaciones asociadas a aprobación o rechazo; rechazo de observaciones vacías, excesivas y rechazo sin motivo. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Detalle e historial administrativos autenticados, auditoría de consultas y modificaciones, y denegación para revisores no asignados. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Validación y aprobación por Talento Humano; rechazo de decisiones incompatibles y de revisión antes de completar la etapa previa. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Observaciones de validación y rechazo vinculadas al actor de Talento Humano; errores de longitud y motivo obligatorio. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Auditoría persistida de acceso y decisiones de Talento Humano; aislamiento administrativo por asignación. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | CRUD autenticado del catálogo, auditoría, nombres duplicados permitidos, límite de 200 caracteres, estados inválidos, versiones estrictas y protección de tipos referenciados. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Asociación de los tres flujos conservando la configuración; conflictos de versión y rechazo de flujos inválidos o inactivos. |
| PR-016 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Regresión de ambos bloqueos: las antiguas rutas /api/solicitudes/{id} y /historial no exponen recursos existentes anónimamente; las consultas autorizadas del portal y del panel siguen funcionando. |
| PR-017 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Proyecciones del portal distintas de las administrativas: sin revisiones ni observaciones administrativas en el detalle y sin identidades de revisores en el historial. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_backend | 2 | 50441 | 7795 | 132.3 s |
| desarrollador_portal | 2 | 31116 | 3185 | 71.2 s |
| desarrollador_panel | 2 | 49176 | 1127 | 27.5 s |
| agente_pruebas | 2 | 75708 | 23746 | 386.8 s |
| validador_artefactos | 5 | 74161 | 1459 | 67.8 s |
