# Reporte de construcción v18

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_portal · PANTALLA_ADMIN_EN_EMPLEADO: PA-005 · Administración de tipos de ausencia es una pantalla de aprobadores y aparece en la aplicación del empleado `portal/src/app/solicitudes.ts`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Registro autenticado 201, persistencia, revisión inicial, historial, auditoría y rechazo de datos incompletos. Aprovisionamiento inicial restringido, rechazo de repetición y conservación de auditoría ordinaria. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Persistencia del motivo y rechazo backend de motivo obligatorio nulo, vacío o compuesto por espacios. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Catálogo autenticado con identificadores reales, registro de fechas y horas, límites temporales y rechazo de etiquetas como identificadores, tipos inactivos y horas no permitidas. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Listado propio con estado y último cambio, detalle e historial autenticados, auditoría, aislamiento, proyecciones sin datos administrativos y validación de identificadores y paginación. |
| PR-005 | HU-002-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Avisos persistidos y consultables tras aprobación o rechazo, estado anterior y nuevo, ausencia de duplicados, lista vacía, aislamiento y rechazo de credenciales administrativas o inválidas. |
| PR-006 | HU-002-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Notificación al aprobador inicial y al siguiente aprobador, aislamiento de bandejas y rechazo de asignaciones inválidas. |
| PR-007 | HU-003-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Bandeja de revisiones asignadas con datos necesarios y validación de límites de paginación. |
| PR-008 | HU-003-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Aprobación y rechazo 200, versiones y actor persistidos, estados inválidos, conflictos concurrentes y rechazo de decisiones o versiones inválidas. |
| PR-009 | HU-003-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Observaciones asociadas a aprobación y rechazo; rechazo de observaciones vacías, excesivas o ausentes cuando son obligatorias. |
| PR-010 | HU-003-CA-04 | `backend/tests/test_ausencias_aceptacion.py` | Auditoría de detalle, historial y decisión; rechazo de accesos y acciones de un jefe no asignado. |
| PR-011 | HU-004-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | Validación y aprobación por Talento Humano, orden de etapas y rechazo de decisiones incompatibles con el rol o la validación requerida. |
| PR-012 | HU-004-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Observaciones de validación y rechazo de Talento Humano persistidas; validación de longitud y obligatoriedad. |
| PR-013 | HU-004-CA-03 | `backend/tests/test_ausencias_aceptacion.py` | Auditoría de consultas y decisiones de Talento Humano con aislamiento de actores no asignados. |
| PR-014 | HU-005-CA-01 | `backend/tests/test_ausencias_aceptacion.py` | CRUD autenticado del catálogo, auditoría, nombres repetidos permitidos, límite de nombre, estados inválidos, control de versiones y protección de referencias. |
| PR-015 | HU-005-CA-02 | `backend/tests/test_ausencias_aceptacion.py` | Consulta y asociación de los tres flujos conservando configuración; rechazo de flujos inválidos o inactivos y versiones obsoletas. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_portal | 2 | 44037 | 11050 | 180.8 s |
