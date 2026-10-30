# Reporte de construcción v27

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PANTALLA_ADMIN_EN_EMPLEADO: PA-005 · Administración de tipos de ausencia es una pantalla de aprobadores y aparece en la aplicación del empleado `portal/src/app/solicitudes.component.ts`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Creación por portal y formato oficial, envío a revisión, persistencia transaccional, referencia obligatoria y prevención de suplantación del solicitante. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Persistencia del motivo, obligatoriedad configurada en backend, motivo opcional y rechazo de contenido vacío. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Tipo, fechas y horas persistidos; modalidades NO_APLICA, OPCIONAL y OBLIGATORIA; fechas invertidas, horas incompletas e intervalos inválidos. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_aceptacion_ausencias.py` | Consulta de estado e historial ordenado, auditoría persistida, filtros inválidos, paginación y aislamiento entre solicitantes. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Avisos persistidos al solicitante por cambios de estado, ausencia de duplicados, aislamiento y protección de datos internos de correo. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Avisos al aprobador del paso activo, activación secuencial JEFE_TH, procesamiento autorizado de cola y límites de consulta; sin conexiones SMTP. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Bandeja del jefe asignado con versiones, rechazo de acceso del empleado, paginación y bloqueo de decisiones fuera del orden del flujo. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Aprobación y rechazo persistidos con actor y fecha; validación del motivo de rechazo, estados cerrados, autoaprobación y conflicto concurrente con una única decisión válida. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Observaciones de revisión y decisión asociadas a la aprobación; rechazo de texto vacío, versión obsoleta y revisión cerrada. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_aceptacion_ausencias.py` | Auditoría de detalle, historial, decisión y modificaciones del jefe, con actor, fecha y operación; protección de todas las rutas administrativas sin token. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Validación previa seguida de aprobación y validación-aprobación conjunta por Talento Humano; rechazo de aprobación sin validar y validación repetida. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Observaciones persistidas de revisión, validación, aprobación y rechazo de Talento Humano, asociadas al actor y revisión; validación de contenido y motivo. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_aceptacion_ausencias.py` | Auditoría persistida de accesos y modificaciones de Talento Humano; aislamiento del historial, límites y operaciones sobre solicitudes cerradas. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_aceptacion_ausencias.py` | Alta, consulta, modificación, desactivación y eliminación del catálogo; duplicados, estados inválidos, permisos, versiones, paginación y conservación de reglas en solicitudes existentes. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_aceptacion_ausencias.py` | Consulta y asociación de los tres flujos cerrados, incremento de versión, conflictos optimistas y rechazo de flujos o versiones inválidos. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_portal | 3 | 44901 | 8516 | 131.0 s |
