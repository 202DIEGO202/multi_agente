# Reporte de construcción v15

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PANTALLA_ADMIN_EN_EMPLEADO: PA-005 · Administración de tipos de ausencia es una pantalla de aprobadores y aparece en la aplicación del empleado `portal/src/app/solicitudes.ts`

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
| validador_artefactos | 5 | 74161 | 1457 | 93.5 s |
| desarrollador_portal | 2 | 33552 | 7095 | 144.1 s |
