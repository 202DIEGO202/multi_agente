import hmac
import os
from typing import Annotated
from urllib.parse import urlsplit

import httpx
import psycopg
from fastapi import Depends, Header, HTTPException, Request
from psycopg.rows import dict_row


def require_admin(authorization: Annotated[str | None, Header()] = None):
    expected = os.environ.get('ADMIN_API_TOKEN')
    if not expected:
        raise HTTPException(503, 'Autenticación administrativa no configurada')
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Se requiere un token administrativo', headers={'WWW-Authenticate': 'Bearer'})
    supplied = authorization[7:]
    if not supplied or not hmac.compare_digest(supplied.encode('utf-8'), os.environ['ADMIN_API_TOKEN'].encode('utf-8')):
        raise HTTPException(401, 'Token administrativo inválido', headers={'WWW-Authenticate': 'Bearer'})


def get_db():
    try:
        with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as connection:
            yield connection
    except (psycopg.errors.SerializationFailure, psycopg.errors.DeadlockDetected, psycopg.errors.UniqueViolation, psycopg.errors.ForeignKeyViolation):
        raise HTTPException(409, 'Conflicto de versión, referencia o unicidad') from None
    except (psycopg.errors.CheckViolation, psycopg.errors.InvalidTextRepresentation, psycopg.errors.NotNullViolation):
        raise HTTPException(422, 'Los datos incumplen las restricciones del esquema') from None
    except psycopg.errors.InsufficientPrivilege:
        raise HTTPException(403, 'Operación no autorizada') from None
    except psycopg.errors.NoDataFound:
        raise HTTPException(409, 'La configuración referenciada ya no está disponible') from None
    except psycopg.errors.RaiseException:
        raise HTTPException(409, 'La operación no corresponde al estado o flujo actual') from None
    except psycopg.OperationalError:
        raise HTTPException(503, 'Base de datos no disponible') from None


def get_actor(request: Request, _: Annotated[None, Depends(require_admin)], db=Depends(get_db)):
    identity = os.environ.get('ADMIN_ACTOR_EXTERNAL_ID')
    if not identity:
        raise HTTPException(503, 'Identidad administrativa no configurada')
    actor = db.execute('SELECT id, identidad_externa, nombre FROM usuarios WHERE identidad_externa = %s AND activo', (identity,)).fetchone()
    if not actor:
        raise HTTPException(403, 'La identidad administrativa no está activa')
    actor['roles'] = [row['rol_codigo'] for row in db.execute('SELECT rol_codigo FROM usuarios_roles WHERE usuario_id = %s', (actor['id'],)).fetchall()]
    audit_access(db, actor, request, 'ACCESO', True)
    return actor


def get_employee_identity(authorization: Annotated[str | None, Header()] = None):
    unauthorized = HTTPException(401, 'Sesión de empleado inválida o vencida', headers={'WWW-Authenticate': 'Bearer'})
    if not authorization or not authorization.startswith('Bearer '):
        raise unauthorized
    token = authorization[7:]
    if not token or len(token) > 16384 or any(character.isspace() for character in token):
        raise unauthorized
    admin_token = os.environ.get('ADMIN_API_TOKEN')
    if admin_token and hmac.compare_digest(token.encode('utf-8'), admin_token.encode('utf-8')):
        raise unauthorized

    # La identidad procede del proveedor, nunca del cuerpo o de un encabezado de usuario.
    url = os.environ.get('EMPLOYEE_INTROSPECTION_URL', '')
    client_id = os.environ.get('EMPLOYEE_INTROSPECTION_CLIENT_ID')
    client_secret = os.environ.get('EMPLOYEE_INTROSPECTION_CLIENT_SECRET')
    audience = os.environ.get('EMPLOYEE_API_AUDIENCE')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or not client_id or not client_secret or not audience:
        raise HTTPException(503, 'Verificación de sesiones de empleado no configurada')
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            response = client.post(url, data={'token': token, 'token_type_hint': 'access_token'}, auth=(client_id, client_secret), headers={'Accept': 'application/json'})
        if response.status_code != 200:
            raise HTTPException(503, 'Proveedor de identidad no disponible')
        claims = response.json()
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, 'No fue posible verificar la sesión de empleado') from None
    if not isinstance(claims, dict) or claims.get('active') is not True:
        raise unauthorized
    subject = claims.get('sub')
    audiences = claims.get('aud')
    if isinstance(audiences, str):
        audiences = [audiences]
    if not isinstance(subject, str) or not subject.strip() or not isinstance(audiences, list) or audience not in audiences:
        raise unauthorized
    return subject


def get_employee_actor(request: Request, identity: Annotated[str, Depends(get_employee_identity)], db=Depends(get_db)):
    actor = db.execute('SELECT id, identidad_externa, nombre FROM usuarios WHERE identidad_externa = %s AND activo', (identity,)).fetchone()
    if not actor:
        raise HTTPException(403, 'El empleado no está registrado o está inactivo')
    actor['roles'] = [row['rol_codigo'] for row in db.execute('SELECT rol_codigo FROM usuarios_roles WHERE usuario_id = %s', (actor['id'],)).fetchall()]
    allowed = 'EMPLEADO' in actor['roles']
    audit_access(db, actor, request, 'ACCESO', allowed)
    if not allowed:
        raise HTTPException(403, 'Se requiere el rol de empleado')
    return actor


def audit_access(db, actor, request, operation, allowed, solicitud_id=None):
    db.execute('INSERT INTO auditoria_acceso(actor_id, solicitud_id, operacion, autorizado, recurso) VALUES (%s, %s, %s, %s, %s)', (actor['id'], solicitud_id, operation, allowed, request.url.path))


def set_actor(db, actor):
    db.execute("SELECT set_config('app.usuario_id', %s, true)", (str(actor['id']),))


def require_role(db, actor, request, role, operation='ACCION_SENSIBLE'):
    allowed = role in actor['roles']
    audit_access(db, actor, request, operation, allowed)
    if not allowed:
        raise HTTPException(403, 'El actor no tiene el rol requerido')


def authorized_request(db, actor, request, solicitud_id, operation):
    row = db.execute('SELECT * FROM solicitudes WHERE id = %s AND eliminado_en IS NULL', (solicitud_id,)).fetchone()
    if not row:
        audit_access(db, actor, request, operation, False)
        raise HTTPException(404, 'Solicitud no disponible')
    allowed = row['solicitante_id'] == actor['id'] or bool(db.execute('SELECT 1 FROM aprobaciones WHERE solicitud_id = %s AND aprobador_id = %s', (solicitud_id, actor['id'])).fetchone())
    audit_access(db, actor, request, operation, allowed, solicitud_id)
    if not allowed:
        raise HTTPException(404, 'Solicitud no disponible')
    return row