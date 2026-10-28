# Reporte de construcción v1

## Validación de artefactos
- **advertencia** · desarrollador_frontend · No se encontró código fuente de llamadas HTTP en el frontend para verificar que los endpoints definidos en backend se consumen correctamente. Se recomienda revisar que las rutas '/api/solicitudes', '/api/solicitudes/{id}', '/api/solicitudes/{id}/estado' y '/api/health' sean invocadas adecuadamente. `frontend/src/app/app.ts`
- **advertencia** · desarrollador_backend · El backend usa tablas 'usuarios', 'solicitudes', 'estados', 'aprobaciones' que coinciden con las definidas en db/init.sql. Sin embargo, no se dispone del código completo para confirmar que todas las reglas de negocio y constraints SQL se respetan en las operaciones. `backend/app/main.py`
- **advertencia** · desarrollador_backend · Las validaciones de edad mínima y nivel de estudios se implementan en el backend con Pydantic y constraints SQL. No se puede confirmar si todas las reglas de negocio, como motivo obligatorio en rechazo, se validan en backend sin el código completo. `backend/app/main.py`
- **advertencia** · agente_pruebas · Los casos de prueba en backend/tests/test_solicitudes.py cubren creación, validación de edad y nivel de estudios, obtención de detalles y actualización de estado con aprobación y rechazo. Se recomienda verificar que las pruebas ejecutan realmente las rutas y validan respuestas y errores esperados. `backend/tests/test_solicitudes.py`
- **advertencia** · agente_iac · La infraestructura definida en infra/terraform/main.tf incluye módulo VPC, módulo EKS para cluster Kubernetes, recursos ECR para repositorios de backend y frontend, y RDS PostgreSQL con subnet group y secreto para contraseña. Esto corresponde a la arquitectura solicitada. `infra/terraform/main.tf`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_solicitudes.py` | Crear solicitud con datos válidos y edad mayor a 23 años y nivel de estudios mínimo bachillerato. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_solicitudes.py` | Intentar crear solicitud con edad menor a 24 años y recibir error de validación. |
| PR-003 | HU-007-CA-03 | `backend/tests/test_solicitudes.py` | Intentar crear solicitud con nivel de estudios menor a bachillerato y recibir error específico. |
| PR-004 | HU-009-CA-01 | `backend/tests/test_solicitudes.py` | Obtener datos detallados de una solicitud incluyendo datos del solicitante y aprobador. |
| PR-005 | HU-010-CA-01 | `backend/tests/test_solicitudes.py` | Aprobar una solicitud y verificar que la respuesta indica éxito. |
| PR-006 | HU-011-CA-01 | `backend/tests/test_solicitudes.py` | Rechazar una solicitud con motivo obligatorio y verificar respuesta exitosa. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_solicitudes.py` | Intentar rechazar una solicitud sin motivo y recibir error de validación. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 1578 | 1058 | 8.9 s |
| desarrollador_backend | 1 | 3510 | 3910 | 28.9 s |
| desarrollador_frontend | 1 | 2215 | 5621 | 38.6 s |
| agente_pruebas | 1 | 4253 | 2430 | 17.4 s |
| agente_iac | 1 | 868 | 1728 | 14.2 s |
| validador_artefactos | 1 | 4854 | 492 | 3.8 s |
