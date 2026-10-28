# Creación de Usuario en el Portal · aplicación v5

Generada por Trama a partir de la arquitectura aprobada, las historias y los mockups.

## Aplicaciones
- `portal/`: aplicación del empleado. No tiene acceso a funciones administrativas.
- `panel/`: panel para aprobadores y administración. Requiere `ADMIN_API_TOKEN`.
- `backend/`: API FastAPI. `db/`: esquema PostgreSQL. `infra/terraform/`: infraestructura AWS.

## Ejecutar en local
1. Copie `.env.example` a `.env` y defina `POSTGRES_PASSWORD` y `ADMIN_API_TOKEN`.
2. `docker compose up -d --build`
3. Portal: http://localhost:8100 · Panel: http://localhost:8101
4. Pruebas: `docker compose exec backend pytest -q`

## Endpoints
| Método | Ruta | Acceso |
|---|---|---|
| GET | `/api/health` | publico |
| POST | `/api/solicitudes` | publico |
| GET | `/api/admin/solicitudes` | administrador |
| GET | `/api/admin/solicitudes/{solicitud_id}` | administrador |
| POST | `/api/admin/solicitudes/{solicitud_id}/decidir` | administrador |
