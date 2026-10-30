# Reporte de construcción v1

Aplicaciones: portal, panel. Arquitectura v4, backlog v1.

## Validación (reglas, ejecución real en Docker y revisión)
- **error** · desarrollador_backend · LISTADO_PUBLICO_DUPLICADO: /api/tipos-ausencia es público y expone los mismos datos que el administrativo /api/admin/tipos-ausencia `backend/app/main.py`
- **error** · desarrollador_portal · PANTALLA_INCOMPLETA: PA-004 · Validación de Talento Humano: faltan campos o textos del mockup (cobertura 20%) 
- **advertencia** · agente_pruebas · CRITERIOS_SIN_PRUEBA: Criterios sin caso de prueba: HU-002-CA-01, HU-002-CA-02, HU-004-CA-03, HU-005-CA-02 

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-001-CA-01 | `backend/tests/test_historias_vacaciones.py` | Crear solicitud de vacaciones/permisos con datos válidos y validar 201. Incluye validación de fechas inválidas con 422. |
| PR-002 | HU-001-CA-02 | `backend/tests/test_historias_vacaciones.py` | Crear solicitud de permiso que requiere motivo y verificar aceptación con motivo y rechazo por falta de motivo. |
| PR-003 | HU-001-CA-03 | `backend/tests/test_historias_vacaciones.py` | Crear solicitud con horas obligatorias, verificar guardado correcto y rechazo cuando faltan horas. |
| PR-004 | HU-001-CA-04 | `backend/tests/test_historias_vacaciones.py` | Consultar detalle y trazabilidad administrativa; verificar acceso sin token a /api/admin/ con 401/403 y acceso autorizado con 200. |
| PR-005 | HU-003-CA-01 | `backend/tests/test_historias_vacaciones.py` | Consultar bandeja administrativa de solicitudes pendientes con token correcto y obtener listado. |
| PR-006 | HU-003-CA-02 | `backend/tests/test_historias_vacaciones.py` | Aprobar una solicitud con token administrativo y verificar estado APROBADA. Incluye control de decisión única en solicitud ya decidida. |
| PR-007 | HU-003-CA-03 | `backend/tests/test_historias_vacaciones.py` | Validar que la observación es obligatoria al rechazar o decidir una solicitud. |
| PR-008 | HU-003-CA-04 | `backend/tests/test_historias_vacaciones.py` | Verificar trazabilidad y conflicto de estado ante una segunda decisión sobre la misma solicitud. |
| PR-009 | HU-004-CA-01 | `backend/tests/test_historias_vacaciones.py` | Talento Humano aprueba/revisa una solicitud con token administrativo y recibe estado exitoso. |
| PR-010 | HU-004-CA-02 | `backend/tests/test_historias_vacaciones.py` | Guardar observaciones asociadas a la revisión al rechazar una solicitud. |
| PR-011 | HU-005-CA-01 | `backend/tests/test_historias_vacaciones.py` | Listar catálogo público reducido y catálogo administrativo completo; verificar que /api/admin/ sin token responde 401/403. |
| PR-012 | HU-005-CA-02 | `backend/tests/test_historias_vacaciones.py` | Crear tipo de ausencia administrativo con flujo configurable y validar respuesta 201 o 200 con id. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 6917 | 2989 | 14.7 s |
| desarrollador_backend | 3 | 38449 | 12632 | 50.3 s |
| desarrollador_portal | 3 | 32634 | 7065 | 215.8 s |
| agente_pruebas | 3 | 46905 | 9567 | 251.1 s |
| agente_iac | 1 | 1285 | 2228 | 23.1 s |
| desarrollador_panel | 3 | 24827 | 4572 | 21.7 s |
