# Creación de Usuario en el Portal · aplicación generada (v1)

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
| GET | `/api/health` | Verificar estado del servicio, devuelve {'estado':'ok'} |
| POST | `/api/solicitudes` | Crear una nueva solicitud de creación de usuario con validación de datos y edad mínima |
| GET | `/api/solicitudes/{solicitud_id}` | Obtener datos detallados de una solicitud incluyendo datos del solicitante y aprobador |
| GET | `/api/solicitudes` | Listar todas las solicitudes con sus estados y datos básicos |
| PATCH | `/api/solicitudes/{solicitud_id}/estado` | Actualizar el estado de una solicitud para aprobar o rechazar con motivo obligatorio en rechazo |
