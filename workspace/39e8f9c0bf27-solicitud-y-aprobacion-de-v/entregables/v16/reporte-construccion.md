# Reporte de construcción v16

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_datos · DATOS-001: El disparador auditoria_cambios de usuarios exige que actor_actual() encuentre un usuario activo existente. Como la inicialización no crea usuarios, la inserción del primero falla y se revierte incluso si app.usuario_id contiene su identificador: auditar_modificacion() inserta en auditoria_modificacion y evalúa actor_actual() para esa misma inserción. Se debe proporcionar un mecanismo de aprovisionamiento inicial restringido que cree el primer usuario antes de habilitar este disparador, sin permitir omitir la auditoría en las operaciones ordinarias. `db/init.sql`
- **error** · desarrollador_portal · PORTAL_REGISTRO_NO_IMPLEMENTADO: Enviar solicitud solo realiza validaciones locales y muestra un aviso; nunca persiste los datos, por lo que el empleado no puede registrar solicitudes para revisión (HU-001-CA-01, HU-001-CA-02 y HU-001-CA-03). Implementar el envío autenticado a POST /api/solicitudes usando tipo_ausencia_id, fecha_inicio, fecha_fin, hora_inicio, hora_fin y motivo. Resolver la selección del tipo a su identificador real, en lugar de enviar las etiquetas fijas del selector, y mostrar el resultado o los errores del servidor. `portal/src/app/solicitudes.ts`
- **error** · desarrollador_portal · PORTAL_AUTENTICACION_OMITIDA: cargarDetalle() y cargarHistorial() realizan las consultas sin el encabezado Authorization: Bearer exigido por el contrato. credentials: 'same-origin' no proporciona esa credencial, por lo que las consultas reciben 401 e impiden el seguimiento de HU-001-CA-04. Incorporar la credencial de la sesión del empleado mediante un servicio de autenticación del portal y enviarla en ambas peticiones, sin reutilizar credenciales administrativas. `portal/src/app/notificaciones.ts`
- **error** · desarrollador_portal · PORTAL_AVISOS_NO_IMPLEMENTADOS: La sección «Notificación de cambio de estado» muestra únicamente un aviso fijo de imposibilidad de carga; no consulta ni presenta notificaciones del empleado. Esto deja sin funcionalidad el control de PA-002 asociado a HU-002-CA-01. Integrar la fuente autenticada de notificaciones propias y mostrar los cambios de estado recibidos, distinguiendo carga, ausencia de avisos y errores reales, sin exponer información administrativa. `portal/src/app/notificaciones.ts`
- **advertencia** · agente_pruebas · PR-AISLAMIENTO-CREDENCIALES: Escenario.__init__ asigna ADMIN_API_TOKEN a EMPLOYEE_API_TOKEN y todas las peticiones autenticadas usan qa.headers con la credencial administrativa. Esto impide detectar que el portal acepte exclusivamente credenciales administrativas o que una credencial exclusiva de empleado conceda acceso al panel. Configurar dos credenciales distintas mediante variables de entorno, usar cabeceras específicas para cada aplicación y añadir una regresión que compruebe la denegación de operaciones administrativas con la credencial del empleado. `backend/tests/test_ausencias_aceptacion.py`

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
| desarrollador_portal | 2 | 34682 | 6746 | 119.0 s |
| validador_artefactos | 12 | 163578 | 3345 | 149.2 s |
