# Arquitectura · Creación de Usuario en el Portal (v3)

Origen: backlog v13 · línea base v11.

## 1. Visión general
La aplicación para la creación de usuarios en el portal corporativo se implementa como un monolito modular con frontend Angular, backend API en Python con FastAPI y base de datos PostgreSQL. Se integra con el servicio externo Active Directory para la gestión manual de cuentas. Se validan datos de usuario, se gestiona la aprobación por líder de área y se notifica al administrador de AD para la creación de la cuenta. Se garantiza trazabilidad y notificaciones en todo el proceso.

Estilo: **monolito modular**.

## 2. Atributos de calidad
| ID | Atributo | Escenario | Medida | Prioridad | Requisitos |
|---|---|---|---|---|---|
| AC-001 | usabilidad | Cuando el empleado completa la solicitud, el sistema valida los datos y muestra mensajes claros de error para correcciones. | Mensajes de error específicos y bloqueos de envío hasta corrección. | alta | RES-001, RES-002, RF-003 |
| AC-002 | trazabilidad | Cuando el líder de área aprueba o rechaza una solicitud, el sistema registra quién, cuándo y motivo (en caso de rechazo). | Registro completo de acciones con usuario, fecha y motivo. | alta | RF-007, RF-006 |
| AC-003 | seguridad | Cuando se aprueba una solicitud, solo el administrador de Active Directory puede crear y activar la cuenta manualmente. | Control de acceso y notificación segura al administrador de AD. | alta | RF-004, RF-005, RN-001 |
| AC-004 | confiabilidad | El sistema debe garantizar que no se cree ni active ninguna cuenta sin aprobación previa del líder de área. | Bloqueo de creación automática y control de estados de solicitud. | alta | RN-001, RF-001 |

## 3. Decisiones y tradeoffs (ADR)
### ADR-001 · Elección del estilo arquitectónico monolito modular
- **Contexto:** Se requiere una aplicación con frontend web, backend API y base de datos, con integración a sistemas externos, para un proceso de creación de usuarios.
- **Decisión:** Se adopta un monolito modular para facilitar el desarrollo inicial, despliegue y mantenimiento, separando responsabilidades en módulos internos.
- **Alternativas:** Monolito en capas; Microservicios; Aplicación serverless
- **A favor:** Despliegue sencillo con un solo artefacto; Facilidad para compartir código y datos internos; Menor complejidad inicial
- **En contra (tradeoff):** Menor escalabilidad independiente de módulos; Riesgo de acoplamiento entre módulos; Despliegue completo ante cualquier cambio
- **Atributos:** AC-001, AC-002, AC-003, AC-004

### ADR-002 · Decisión sobre persistencia y base de datos relacional
- **Contexto:** La aplicación requiere almacenar solicitudes, usuarios, aprobaciones y trazabilidad con integridad y consultas estructuradas.
- **Decisión:** Se utiliza PostgreSQL como base de datos relacional para garantizar integridad, consultas complejas y soporte transaccional.
- **Alternativas:** Base de datos relacional PostgreSQL; Base de datos NoSQL; Almacenamiento en archivos
- **A favor:** Integridad referencial y transacciones; Amplio soporte y comunidad; Facilidad para consultas SQL complejas
- **En contra (tradeoff):** Menor flexibilidad para datos no estructurados; Requiere diseño de esquema previo
- **Atributos:** AC-002, AC-004

## 4. Contenedores y componentes (C4)
| ID | Nombre | Tipo | Tecnología | Responsabilidad |
|---|---|---|---|---|
| CT-001 | Portal Web | aplicacion_web | Angular | Interfaz de usuario para empleados y líderes de área para gestionar solicitudes de creación de usuario. |
| CT-002 | API Backend | api | Python con FastAPI | Lógica de negocio, validaciones, gestión de solicitudes, aprobaciones y notificaciones. |
| CT-003 | Base de Datos | base_datos | PostgreSQL | Almacenamiento de datos de solicitudes, usuarios, aprobaciones y trazabilidad. |
| CT-004 | Active Directory | servicio_externo | Microsoft Active Directory | Gestión manual de cuentas corporativas, creación y activación por administrador. |
| CT-005 | Servicio de Correo | servicio_externo | SMTP | Envío de notificaciones por correo electrónico a empleados, líderes y administradores. |

| ID | Componente | Contenedor | Historias | Operaciones |
|---|---|---|---|---|
| CM-001 | Módulo UI Solicitud Usuario | CT-001 | HU-007 |  |
| CM-002 | Módulo UI Aprobación Líder | CT-001 | HU-009, HU-010, HU-011 |  |
| CM-003 | Controlador Solicitudes | CT-002 | HU-007, HU-009, HU-010, HU-011 | crearSolicitud; obtenerSolicitud; actualizarEstadoSolicitud; listarSolicitudes |
| CM-004 | Servicio Validación de Datos | CT-002 | HU-007 | validarDatosSolicitud |
| CM-005 | Servicio Gestión de Aprobaciones | CT-002 | HU-010, HU-011 | aprobarSolicitud; rechazarSolicitud; notificar |
| CM-006 | Repositorio Solicitudes | CT-002 | HU-007, HU-009, HU-010, HU-011 | guardarSolicitud; actualizarSolicitud; obtenerSolicitudPorId |
| CM-007 | Integración Active Directory | CT-002 | HU-010 | notificarAdministradorAD |
| CM-008 | Integración Servicio Correo | CT-002 | HU-010, HU-011 | enviarCorreo |
| CM-009 | Esquema Datos Solicitudes | CT-003 | HU-007, HU-009, HU-010, HU-011 |  |

## 5. Ejecutar en local
1. Instale Docker Desktop.
2. Copie `.env.example` a `.env` y defina las contraseñas.
3. Ejecute `docker compose up --build`.
   - Portal Web Local: http://localhost:4200
   - API Backend Local: http://localhost:8000

## 6. Desplegar en la nube (AWS EKS)
En entorno local, se utiliza Docker Compose para levantar tres contenedores: portal web, API backend y base de datos PostgreSQL, cada uno en un contenedor independiente. En entorno nube, se despliegan los contenedores en AWS EKS usando Deployments con réplicas configurables para asegurar disponibilidad. El acceso externo se gestiona mediante un AWS ALB configurado como Ingress. La base de datos se aloja en AWS RDS PostgreSQL para gestión y escalabilidad. Los secretos sensibles se almacenan en AWS Secrets Manager y las imágenes de contenedores se alojan en AWS ECR. Se implementa monitoreo con AWS CloudWatch para logs y métricas.

1. Construya y publique las imágenes en ECR: `docker build` + `docker push ${ECR_REGISTRY}/<servicio>:${TAG}`.
2. Cree el secreto de la aplicación (valores desde AWS Secrets Manager):
   `kubectl -n <namespace> create secret generic app-secrets --from-env-file=.env.produccion`
3. Aplique los manifiestos: `kubectl apply -f k8s.yaml`.

**Seguridad:** Se controla el acceso a la API y portal mediante mecanismos propios de la aplicación. Los secretos como credenciales de base de datos y SMTP se gestionan con AWS Secrets Manager en nube y variables de entorno en local. La comunicación entre portal y API se realiza sobre HTTPS. La base de datos está protegida con credenciales seguras y acceso restringido. En nube, el ALB gestiona TLS para asegurar la comunicación externa. No se permite creación automática de cuentas en Active Directory, que es gestionado manualmente por administradores. Se registran todas las acciones para trazabilidad y auditoría.

**Observabilidad:** Se utiliza AWS CloudWatch para recolectar logs y métricas de los contenedores en nube, permitiendo monitoreo de salud y rendimiento. En local, se pueden consultar logs de Docker Compose. Se registran eventos importantes para trazabilidad, incluyendo acciones de usuarios y estados de solicitudes. Se configuran alertas básicas para detectar fallos o problemas de disponibilidad. La aplicación genera mensajes de error específicos para mejorar la usabilidad y facilitar la detección de problemas.

| Nodo | Entorno | Tecnología | Aloja | Explicación |
|---|---|---|---|---|
| Portal Web Local | local | Angular | CT-001 | Contenedor local que ejecuta el portal web Angular para que empleados y líderes gestionen solicitudes de creación de usuario. |
| API Backend Local | local | Python con FastAPI | CT-002 | Contenedor local que ejecuta la API backend con la lógica de negocio, validaciones y gestión de solicitudes. |
| Base de Datos PostgreSQL Local | local | PostgreSQL | CT-003 | Base de datos local PostgreSQL que almacena datos de solicitudes, usuarios, aprobaciones y trazabilidad. |
| AWS ECR | nube | AWS ECR |  | Registro de imágenes de contenedores en AWS para almacenar y distribuir las imágenes de la aplicación. |
| AWS ALB Ingress | nube | AWS ALB |  | Balanceador de carga AWS ALB que gestiona el tráfico HTTPS hacia los servicios desplegados en EKS. |
| Portal Web EKS | nube | Angular | CT-001 | Deployment en EKS con réplicas del portal web Angular para alta disponibilidad y escalabilidad. |
| API Backend EKS | nube | Python con FastAPI | CT-002 | Deployment en EKS con réplicas de la API backend para gestionar la lógica de negocio y solicitudes. |
| AWS RDS PostgreSQL | nube | AWS RDS PostgreSQL | CT-003 | Base de datos gestionada en AWS RDS PostgreSQL para almacenamiento seguro y escalable de datos. |
| AWS Secrets Manager | nube | AWS Secrets Manager |  | Servicio AWS para almacenar y gestionar de forma segura las credenciales y secretos usados por la aplicación. |
| AWS CloudWatch | nube | AWS CloudWatch |  | Servicio AWS para monitoreo, recolección de logs y métricas de la aplicación desplegada en la nube. |
| Active Directory Local | local | Microsoft Active Directory |  | Servicio externo local de Active Directory para gestión manual de cuentas corporativas. |
| Servicio SMTP Local | local | SMTP |  | Servicio externo local SMTP para envío de notificaciones por correo electrónico. |
| Active Directory Corporativo | nube | Microsoft Active Directory |  | Servicio externo corporativo de Active Directory para gestión manual de cuentas. |
| Servicio SMTP Corporativo | nube | SMTP |  | Servicio externo SMTP en nube para envío de correos electrónicos de notificación. |

## 7. Plan de implementación
Plan de implementación para el sistema de gestión de solicitudes de creación de usuario, siguiendo un estilo monolito modular con contenedores para Portal Web (Angular), API Backend (Python con FastAPI), Base de Datos (PostgreSQL) e integraciones con Active Directory y Servicio de Correo. Se prioriza la configuración del entorno local y esquema de datos, seguido del desarrollo backend, frontend, integraciones, despliegue en la nube y pruebas. Cada tarea técnica está asignada a un rol específico, con dependencias claras y criterios de terminado verificables.

| Orden | ID | Tarea | Rol | Depende de | Esfuerzo |
|---|---|---|---|---|---|
| 1 | TT-001 | Configurar entorno local para desarrollo frontend, backend y base de datos | devops | — | M |
| 2 | TT-002 | Diseñar y crear esquema de base de datos para solicitudes y aprobaciones | datos | TT-001 | M |
| 3 | TT-003 | Implementar repositorio de solicitudes para persistencia en base de datos | backend | TT-002 | M |
| 4 | TT-004 | Desarrollar servicio de validación de datos de solicitud | backend | TT-003 | S |
| 5 | TT-005 | Implementar controlador de solicitudes con endpoints CRUD | backend | TT-003, TT-004 | L |
| 6 | TT-006 | Desarrollar servicio de gestión de aprobaciones y notificaciones | backend | TT-005 | M |
| 7 | TT-007 | Implementar integración con Active Directory para notificación a administrador | backend | TT-006 | M |
| 8 | TT-008 | Implementar integración con servicio de correo para notificaciones | backend | TT-006 | M |
| 9 | TT-009 | Desarrollar módulo UI para formulario de solicitud de usuario | frontend | TT-005 | M |
| 10 | TT-010 | Desarrollar módulo UI para aprobación y visualización de solicitudes por líder | frontend | TT-005 | M |
| 11 | TT-011 | Configurar despliegue en nube para backend, frontend y base de datos | devops | TT-001, TT-002 | L |
| 12 | TT-012 | Configurar integración de servicios externos en nube | devops | TT-011 | M |
| 13 | TT-013 | Implementar pruebas funcionales y de integración para todo el sistema | qa | TT-009, TT-010, TT-011, TT-012 | L |
