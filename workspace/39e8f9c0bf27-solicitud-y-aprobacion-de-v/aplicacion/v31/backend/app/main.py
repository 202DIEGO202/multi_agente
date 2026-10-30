from fastapi import FastAPI, Request, Depends
from fastapi.responses import JSONResponse
import psycopg
from .portal import router as portal_router
from .admin import router as admin_router
from .common import require_admin

app = FastAPI()
app.include_router(portal_router)
app.include_router(admin_router)


@app.get('/api/health')
def health():
    return {'estado': 'ok'}


@app.get('/api/admin/')
def admin_inicio(user=Depends(require_admin)):
    # Entrada del panel; no devuelve información de otros empleados.
    recursos = {
        'solicitudes': '/api/admin/solicitudes',
        'notificaciones': '/api/admin/notificaciones'
    }
    if 'TALENTO_HUMANO' in user['roles']:
        recursos['tipos_ausencia'] = '/api/admin/tipos-ausencia'
        recursos['flujos'] = '/api/admin/flujos'
    return {'estado': 'ok', 'recursos': recursos}


@app.exception_handler(psycopg.Error)
async def database_error(request: Request, exc: psycopg.Error):
    codes = {'23505': (409, 'El registro o la acción ya existe'),
             '23503': (409, 'Existen referencias relacionadas o falta un registro relacionado'),
             '40001': (409, 'La versión cambió; actualice la información'),
             '40P01': (409, 'Conflicto concurrente; vuelva a intentar'),
             '23514': (422, 'La operación incumple una regla de negocio'),
             '23502': (422, 'Falta un dato obligatorio'),
             '42501': (403, 'Operación no autorizada'),
             'P0002': (422, 'No existe un registro requerido')}
    status, message = codes.get(exc.sqlstate, (503, 'Servicio de datos temporalmente no disponible'))
    return JSONResponse(status_code=status, content={'detail': message})