# Creación de Usuario en el Portal · aplicación generada (v2)

Generada por Trama desde la arquitectura v3 y el backlog v13.

## Ejecutar en local
1. Instale Docker Desktop.
2. Copie `.env.example` a `.env` y cambie `POSTGRES_PASSWORD`.
3. `docker compose up -d --build`
4. Frontend: http://localhost:8100 · API: http://localhost:8101/api/health
5. Pruebas: `docker compose exec backend pytest -q`

## Estructura
- `db/init.sql`: esquema de base de datos (se aplica al crear el contenedor).
- `backend/app`: API FastAPI. `backend/tests`: pruebas trazadas a criterios de aceptación.
- `frontend/src/app`: aplicación Angular servida por Nginx (proxy `/api` hacia el backend).
- `infra/terraform`: infraestructura en AWS EKS (se revisa y aplica con `terraform plan/apply`).

## Endpoints
| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Verifica el estado del servicio, responde con {'estado':'ok'} |
| POST | `/api/solicitudes` | Empleado completa y envía solicitud para creación de usuario con validaciones de edad y nivel de estudios |
| GET | `/api/solicitudes/{solicitud_id}` | Líder de área visualiza datos del solicitante y del aprobador en solicitud de creación de usuario |
| GET | `/api/solicitudes` | Listar todas las solicitudes con datos del solicitante y estado |
| PATCH | `/api/solicitudes/{solicitud_id}/estado` | Líder de área aprueba o rechaza solicitud, registra trazabilidad y notifica a partes involucradas |
