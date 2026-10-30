# Arquitectura · Solicitud y aprobación de vacaciones y permisos. (v4)

Origen: backlog v1 · línea base v9.

## 1. Visión general
Aplicación interna para gestionar solicitudes de vacaciones y permisos con portal web Angular, una API backend en FastAPI y PostgreSQL como base de datos relacional. El sistema incluye flujo de aprobación por jefe inmediato y Talento Humano, catálogo administrable de tipos de ausencia, notificaciones por correo SMTP, auditoría completa y control de concurrencia con bloqueo optimista para evitar aprobaciones duplicadas o concurrentes.

Estilo: **monolito modular**.

## 2. Atributos de calidad
| ID | Atributo | Escenario | Medida | Prioridad | Requisitos |
|---|---|---|---|---|---|
| AC-001 | seguridad | Cuando un usuario consulta el historial de una solicitud o ejecuta una aprobación, el sistema verifica permisos y registra la identidad del actor, de modo que solo usuarios autorizados accedan a información sensible. | 0 accesos no autorizados en pruebas de autorización; 100% de consultas a historial y acciones sensibles auditadas con usuario, fecha y operación. | alta | RF-008, RF-013, RF-009, RF-010, RF-011 |
| AC-002 | confiabilidad | Cuando dos aprobadores intentan decidir simultáneamente sobre la misma solicitud, el sistema rechaza la segunda operación si la versión ya cambió y evita doble aprobación. | 100% de conflictos concurrentes detectados mediante control optimista; ninguna solicitud termina con dos decisiones válidas para la misma revisión. | alta | RF-010, RF-011 |
| AC-003 | trazabilidad | Cuando se crea, aprueba, rechaza o modifica una solicitud o el catálogo, el sistema registra quién hizo el cambio, qué cambió y cuándo, incluyendo la consulta del historial por parte del solicitante. | 100% de operaciones de creación, actualización, aprobación, rechazo, consulta de historial y administración del catálogo con evento de auditoría persistido. | alta | RF-013, RF-007, RF-008, RF-010, RF-011, RF-012 |
| AC-004 | mantenibilidad | Cuando se cambie la regla de obligatoriedad del motivo/observación por tipo de ausencia, la validación debe mantenerse en el backend para asegurar el rechazo de solicitudes inválidas aunque no pasen por la UI. | La validación se encuentra centralizada en el servicio backend y cubre 100% de los tipos configurados; el rechazo ocurre en API con respuesta explícita de validación. | alta | RF-002 |
| AC-005 | disponibilidad | Cuando un empleado o aprobador usa el portal durante la jornada laboral, el sistema debe seguir operativo para registrar solicitudes, revisar bandejas y enviar notificaciones. | Servicio disponible para operación interna con reinicio sin pérdida de datos; persistencia transaccional en PostgreSQL y despliegue containerizado. | media | RF-001, RF-003, RF-005, RF-006, RF-009 |
| AC-006 | usabilidad | Cuando el empleado registra una solicitud, el sistema presenta un formulario guiado para tipo de ausencia, fechas, horas y motivo/observación si aplica, reduciendo errores de captura. | Campos obligatorios visibles y validación inmediata en UI; reducción de intentos inválidos capturados en frontend, con rechazo equivalente en backend. | media | RF-003, RF-004, RF-002 |

## 3. Decisiones y tradeoffs (ADR)
### ADR-001 · Adoptar monolito modular para el backend
- **Contexto:** El alcance actual cubre solicitudes, aprobaciones, catálogo, notificaciones y auditoría. Se requiere rapidez de entrega, simplicidad operativa y posibilidad de crecer por módulos sin dividir en microservicios.
- **Decisión:** Implementar una única API en FastAPI organizada como monolito modular, con módulos internos separados por responsabilidad: solicitudes, aprobaciones, catálogo, notificaciones y auditoría.
- **Alternativas:** Microservicios por dominio; Monolito en capas tradicional
- **A favor:** Menor complejidad operativa y de despliegue; Transacciones simples dentro de una sola base de datos; Separación interna por módulos facilita evolución futura
- **En contra (tradeoff):** Escalado fino por dominio no está disponible; Un fallo del proceso afecta a todos los módulos; Requiere disciplina arquitectónica para evitar acoplamiento interno
- **Atributos:** AC-005, AC-003, AC-004

### ADR-002 · Persistir en PostgreSQL relacional con transacciones y control optimista
- **Contexto:** Las solicitudes tienen estados, historial, auditoría y reglas de aprobación secuenciales. Se necesita consistencia fuerte y soporte de consultas relacionales.
- **Decisión:** Usar PostgreSQL como única base de datos relacional con transacciones ACID, tablas normalizadas y columna de versión para bloqueo optimista en decisiones de aprobación.
- **Alternativas:** Base de datos NoSQL documental; Persistencia en archivos o almacenamiento local
- **A favor:** Consistencia fuerte para aprobaciones y auditoría; Consultas relacionales naturales para historial, bandejas y catálogo; Soporte claro para control de concurrencia mediante versión
- **En contra (tradeoff):** Mayor modelado inicial de esquema; Menor flexibilidad que un documento para cambios no estructurados; Requiere cuidado en migraciones de esquema
- **Atributos:** AC-002, AC-003, AC-005

### ADR-003 · Enviar notificaciones por SMTP desde el backend
- **Contexto:** El sistema debe avisar cambios de estado y pendientes de revisión. El entorno permitido incluye SMTP y no se exigen canales adicionales.
- **Decisión:** Integrar un servicio de notificaciones SMTP dentro del backend para enviar correos a empleado y aprobadores cuando cambie el estado o exista una solicitud pendiente.
- **Alternativas:** Integración con plataforma de mensajería externa; Solo notificación dentro de la aplicación sin correo
- **A favor:** Cumple el aviso oportuno con tecnología permitida; Implementación simple y adecuada para un entorno interno; No introduce dependencias adicionales
- **En contra (tradeoff):** Menor riqueza de canales frente a una plataforma de mensajería; Entrega dependiente de la infraestructura de correo; Requiere configuración y monitoreo de SMTP
- **Atributos:** AC-005, AC-003

## 4. Contenedores y componentes (C4)
| ID | Nombre | Tipo | Tecnología | Responsabilidad |
|---|---|---|---|---|
| CT-001 | Portal interno de solicitudes | aplicacion_web | Angular + Nginx | Interfaz web para que empleados, jefes inmediatos y Talento Humano gestionen solicitudes, bandejas, notificaciones y catálogo. |
| CT-002 | API de gestión de ausencias | api | Python + FastAPI | Expone endpoints para solicitudes, aprobación, validación, catálogo, notificaciones, auditoría y control de concurrencia. |
| CT-003 | Base de datos de ausencias | base_datos | PostgreSQL | Persiste solicitudes, tipos de ausencia, estados, historial, observaciones, auditoría, notificaciones y versiones para concurrencia. |
| CT-004 | Servidor SMTP corporativo | servicio_externo | SMTP | Envía correos de notificación sobre cambios de estado y pendientes de revisión. |

| ID | Componente | Contenedor | Historias | Operaciones |
|---|---|---|---|---|
| CM-001 | Módulo UI de solicitudes | CT-001 | HU-001, HU-002 | Crear solicitud; Consultar estado; Consultar historial; Ver detalle de solicitud |
| CM-002 | Módulo UI de revisión | CT-001 | HU-003, HU-004 | Listar pendientes; Aprobar solicitud; Rechazar solicitud; Registrar observación |
| CM-003 | Módulo UI de catálogo | CT-001 | HU-005 | Listar tipos de ausencia; Crear tipo de ausencia; Editar tipo de ausencia; Asignar flujo de aprobación; Eliminar tipo de ausencia |
| CM-004 | Controlador de solicitudes | CT-002 | HU-001, HU-002 | POST /solicitudes; GET /solicitudes/{id}; GET /solicitudes?estado&solicitante; GET /solicitudes/{id}/historial; PUT /solicitudes/{id}; DELETE /solicitudes/{id} |
| CM-005 | Controlador de revisiones | CT-002 | HU-003, HU-004 | GET /revisiones/pendientes; POST /solicitudes/{id}/aprobar; POST /solicitudes/{id}/rechazar; POST /solicitudes/{id}/validar; GET /revisiones/mi-bandeja |
| CM-006 | Controlador de catálogo | CT-002 | HU-005 | GET /tipos-ausencia; POST /tipos-ausencia; PUT /tipos-ausencia/{id}; DELETE /tipos-ausencia/{id}; PUT /tipos-ausencia/{id}/flujo |
| CM-007 | Servicio de solicitudes | CT-002 | HU-001 | Validar campos obligatorios; Validar motivo/observación por tipo; Crear solicitud; Consultar detalle |
| CM-008 | Servicio de revisiones | CT-002 | HU-003, HU-004 | Verificar versión; Registrar decisión; Cambiar estado; Guardar observación; Generar notificación |
| CM-009 | Servicio de catálogo | CT-002 | HU-005 | Crear tipo de ausencia; Actualizar tipo de ausencia; Asignar flujo; Consultar catálogo |
| CM-010 | Servicio de notificaciones | CT-002 | HU-002 | Crear notificación; Enviar correo; Registrar resultado de envío |
| CM-011 | Servicio de auditoría | CT-002 | HU-001, HU-003, HU-004, HU-005 | Registrar acceso; Registrar consulta sensible; Registrar modificación; Registrar decisión |
| CM-012 | Repositorio de solicitudes | CT-002 | HU-001, HU-003, HU-004 | Insertar solicitud; Actualizar solicitud; Consultar solicitud; Listar pendientes; Guardar historial |
| CM-013 | Repositorio de catálogo | CT-002 | HU-005 | Insertar tipo de ausencia; Actualizar tipo de ausencia; Eliminar tipo de ausencia; Consultar tipos de ausencia; Guardar flujo |
| CM-014 | Repositorio de auditoría | CT-002 | HU-001, HU-003, HU-004, HU-005 | Insertar evento de auditoría; Consultar eventos de auditoría |
| CM-015 | Integración SMTP | CT-002 | HU-002 | Enviar correo de cambio de estado; Enviar correo de pendiente |
| CM-016 | Esquema de datos de solicitudes | CT-003 | HU-001, HU-002, HU-003, HU-004 | Persistir solicitudes; Persistir historial; Persistir decisiones; Persistir versión; Persistir notificaciones |
| CM-017 | Esquema de datos de catálogo y auditoría | CT-003 | HU-005, HU-001, HU-003, HU-004 | Persistir catálogo; Persistir flujo; Persistir auditoría |

## 5. Ejecutar en local
1. Instale Docker Desktop.
2. Copie `.env.example` a `.env` y defina las contraseñas.
3. Ejecute `docker compose up --build`.
   - Portal interno de solicitudes: http://localhost:4200
   - API de gestión de ausencias: http://localhost:8000

## 6. Desplegar en la nube (AWS EKS)
Entorno local: Docker Compose levanta CT-001, CT-002 y CT-003 en una sola red interna, con PostgreSQL como servicio persistente para el desarrollador. Entorno nube: la UI y la API se despliegan como Deployments en AWS EKS con réplicas para disponibilidad; el acceso externo entra por AWS ALB; la base de datos se externaliza a AWS RDS PostgreSQL; las credenciales y parámetros sensibles se obtienen desde AWS Secrets Manager; las imágenes se publican en AWS ECR; y la telemetría y logs se envían a AWS CloudWatch. Todo contenedor propio está presente en ambos entornos. Los sistemas externos se modelan como servicio_externo y no se ejecutan dentro del clúster.

1. Construya y publique las imágenes en ECR: `docker build` + `docker push ${ECR_REGISTRY}/<servicio>:${TAG}`.
2. Cree el secreto de la aplicación (valores desde AWS Secrets Manager):
   `kubectl -n <namespace> create secret generic app-secrets --from-env-file=.env.produccion`
3. Aplique los manifiestos: `kubectl apply -f k8s.yaml`.

**Seguridad:** En local y en nube, los contenedores no deben contener secretos embebidos; las variables sensibles se inyectan desde archivos de entorno locales o Secrets Manager en AWS. La API valida permisos, obligatoriedad de campos y reglas de negocio, incluyendo el motivo/observación según el tipo de ausencia. Las aprobaciones usan control optimista con versión o marca de concurrencia para impedir doble decisión. Toda consulta a historial y toda modificación de catálogo debe registrar auditoría con identidad del usuario, fecha, operación y entidad afectada. El SMTP corporativo se consume como servicio externo sin almacenar credenciales en texto claro.

**Observabilidad:** AWS CloudWatch centraliza logs y métricas del entorno nube. La API debe emitir logs estructurados de validación, auditoría, aprobaciones, rechazos por concurrencia y consultas sensibles. En local, los logs de Docker Compose se revisan por contenedor. Se recomienda exponer métricas básicas de salud de API y base de datos, además de trazas de errores de negocio y de persistencia.

| Nodo | Entorno | Tecnología | Aloja | Explicación |
|---|---|---|---|---|
| Portal interno de solicitudes | local | Angular + Nginx | CT-001 | Contenedor local de la interfaz web para que los usuarios consulten y gestionen solicitudes desde el navegador. |
| API de gestión de ausencias | local | Python + FastAPI | CT-002 | Contenedor local del backend que expone los endpoints de negocio, valida reglas, registra auditoría y coordina aprobaciones. |
| Base de datos de ausencias | local | PostgreSQL | CT-003 | Base de datos local para guardar solicitudes, catálogo, estados, historial, auditoría y control de concurrencia. |
| Servidor SMTP corporativo | local | SMTP |  | Servicio de correo externo usado por la API para enviar notificaciones de cambios de estado y pendientes. |
| Portal interno de solicitudes | nube | Angular + Nginx | CT-001 | Deployment en EKS para servir la interfaz web con al menos dos réplicas y facilitar disponibilidad. |
| API de gestión de ausencias | nube | Python + FastAPI | CT-002 | Deployment en EKS del backend; maneja validaciones, auditoría, concurrencia optimista y lógica de negocio. |
| Base de datos de ausencias | nube | AWS RDS PostgreSQL | CT-003 | Base de datos administrada en AWS para persistencia confiable y recuperación ante fallos. |
| AWS ALB | nube | AWS ALB | CT-001, CT-002 | Balanceador de entrada que publica la aplicación en Kubernetes y enruta tráfico hacia la UI o la API. |
| AWS Secrets Manager | nube | AWS Secrets Manager | CT-002, CT-003 | Almacén seguro de secretos y credenciales usado por los pods y la base de datos administrada. |
| AWS ECR | nube | AWS ECR | CT-001, CT-002 | Registro de imágenes donde se publican las versiones de la UI y la API para el despliegue en EKS. |
| AWS CloudWatch | nube | AWS CloudWatch | CT-001, CT-002, CT-003 | Servicio de observabilidad para logs, métricas y alertas del entorno nube. |
| Servidor SMTP corporativo | nube | SMTP |  | Servicio de correo externo consumido desde la API para notificaciones por email. |

## 7. Plan de implementación
Plan técnico en orden de ejecución: primero preparar entorno local y esquema de datos, luego backend, frontend, integraciones, despliegue en nube y pruebas. Se cubren todos los componentes CM-001 a CM-017 usando las tecnologías indicadas.

| Orden | ID | Tarea | Rol | Depende de | Esfuerzo |
|---|---|---|---|---|---|
| 1 | TT-001 | Preparar entorno local de desarrollo y ejecución | devops | — | M |
| 2 | TT-002 | Definir y crear el esquema de datos inicial | datos | TT-001 | L |
| 3 | TT-003 | Implementar la base del backend FastAPI | backend | TT-001, TT-002 | M |
| 4 | TT-004 | Implementar repositorios de persistencia | backend | TT-002, TT-003 | M |
| 5 | TT-005 | Implementar servicio y controlador de solicitudes | backend | TT-003, TT-004 | L |
| 6 | TT-006 | Implementar servicio y controlador de revisiones | backend | TT-003, TT-004 | L |
| 7 | TT-007 | Implementar servicio y controlador de catálogo | backend | TT-003, TT-004 | M |
| 8 | TT-008 | Implementar servicio de notificaciones e integración SMTP | backend | TT-003, TT-004, TT-006 | M |
| 9 | TT-009 | Implementar módulo UI de solicitudes | frontend | TT-003, TT-005 | L |
| 10 | TT-010 | Implementar módulo UI de revisión | frontend | TT-003, TT-006 | M |
| 11 | TT-011 | Implementar módulo UI de catálogo | frontend | TT-003, TT-007 | M |
| 12 | TT-012 | Integrar frontend con API y flujo de autenticación funcional de sesión | frontend | TT-009, TT-010, TT-011 | M |
| 13 | TT-013 | Preparar despliegue en nube para backend, frontend y base de datos | devops | TT-001, TT-002, TT-003 | L |
| 14 | TT-014 | Desplegar y validar la aplicación en nube | devops | TT-013, TT-012, TT-008 | M |
| 15 | TT-015 | Ejecutar pruebas funcionales, de integración y regresión | qa | TT-014 | M |
