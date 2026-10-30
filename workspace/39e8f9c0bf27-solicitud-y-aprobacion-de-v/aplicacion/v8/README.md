# Solicitud y aprobación de vacaciones y permisos. · aplicación v8

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
| GET | `/api/admin/tipos-ausencia` | administrador |
| GET | `/api/admin/tipos-ausencia/{tipo_id}` | administrador |
| POST | `/api/admin/tipos-ausencia` | administrador |
| PUT | `/api/admin/tipos-ausencia/{tipo_id}` | administrador |
| PUT | `/api/admin/tipos-ausencia/{tipo_id}/flujo` | administrador |
| DELETE | `/api/admin/tipos-ausencia/{tipo_id}` | administrador |
| GET | `/api/admin/flujos-aprobacion` | administrador |
| GET | `/api/admin/revisiones/pendientes` | administrador |
| GET | `/api/admin/solicitudes/{solicitud_id}` | administrador |
| GET | `/api/admin/solicitudes/{solicitud_id}/historial` | administrador |
| POST | `/api/admin/revisiones/{revision_id}/decision` | administrador |
| GET | `/api/admin/notificaciones` | administrador |
