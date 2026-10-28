# Reporte de construcción v2

## Validación de artefactos
- **advertencia** · desarrollador_frontend · El frontend realiza llamadas a endpoints '/api/solicitudes', '/api/solicitudes/{id}' y '/api/solicitudes/{id}/estado' que existen y están definidos en el backend, asegurando coherencia en rutas y métodos HTTP. `frontend/src/app/solicitud-form.component.ts`
- **advertencia** · desarrollador_datos · El backend utiliza las tablas 'usuarios', 'solicitudes', 'estados_solicitud' y 'aprobaciones' definidas en el script SQL, incluyendo restricciones y validaciones de negocio implementadas en la base de datos y en el backend. `backend/app/main.py`
- **advertencia** · desarrollador_backend · Las reglas de negocio críticas como validación de edad mínima, nivel de estudios, motivo de rechazo obligatorio y actualización de estados se validan en el backend y en la base de datos mediante constraints y validadores Pydantic. `backend/app/main.py`
- **advertencia** · agente_pruebas · Las pruebas en 'backend/tests/test_solicitudes.py' cubren creación de solicitudes válidas e inválidas, validaciones de edad y nivel de estudios, visualización de solicitudes, aprobación y rechazo con motivo obligatorio, verificando los criterios de aceptación de las historias de usuario. `backend/tests/test_solicitudes.py`
- **advertencia** · agente_iac · La infraestructura como código en Terraform configura un cluster EKS, base de datos RDS PostgreSQL, repositorios ECR para backend y frontend, y Secrets Manager para la contraseña de RDS, cumpliendo con los requisitos de IaC para EKS + RDS + ECR. `infra/terraform/main.tf`

## Casos de prueba
| ID | Criterio | Archivo | Descripción |
|---|---|---|---|
| PR-001 | HU-007-CA-01 | `backend/tests/test_solicitudes.py` | Crear solicitud con datos válidos y verificar que se crea con estado Pendiente. |
| PR-002 | HU-007-CA-02 | `backend/tests/test_solicitudes.py` | Intentar crear solicitud con datos incompletos y recibir error de validación. |
| PR-003 | HU-007-CA-02 | `backend/tests/test_solicitudes.py` | Intentar crear solicitud con edad menor o igual a 23 años y recibir mensaje de error específico. |
| PR-004 | HU-007-CA-03 | `backend/tests/test_solicitudes.py` | Intentar crear solicitud con nivel de estudios menor a bachillerato y recibir mensaje de error específico. |
| PR-005 | HU-009-CA-01 | `backend/tests/test_solicitudes.py` | Visualizar datos de una solicitud creada y verificar que se muestran correctamente. |
| PR-006 | HU-010-CA-01 | `backend/tests/test_solicitudes.py` | Aprobar una solicitud y verificar que la respuesta indica éxito. |
| PR-007 | HU-011-CA-01 | `backend/tests/test_solicitudes.py` | Intentar rechazar una solicitud sin motivo y recibir error; luego rechazar con motivo y verificar éxito. |
| PR-008 | HU-011-CA-01 | `backend/tests/test_solicitudes.py` | Verificar que al rechazar una solicitud se actualiza el estado a 'Rechazada' y se guarda el motivo. |

## Consumo por agente
| Agente | Llamadas | Tokens entrada | Tokens salida | Tiempo |
|---|---|---|---|---|
| desarrollador_datos | 1 | 1578 | 1293 | 10.5 s |
| desarrollador_backend | 1 | 3740 | 3351 | 28.2 s |
| desarrollador_frontend | 1 | 2133 | 4188 | 27.0 s |
| agente_pruebas | 1 | 4153 | 2081 | 15.1 s |
| agente_iac | 1 | 868 | 1187 | 10.3 s |
| validador_artefactos | 1 | 4776 | 454 | 4.4 s |
