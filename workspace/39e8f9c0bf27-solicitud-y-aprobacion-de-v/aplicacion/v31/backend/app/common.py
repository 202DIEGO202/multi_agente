import os
import hmac
import hashlib
import base64
import json
import time
import uuid
from fastapi import Depends, Header, HTTPException, Request
import psycopg
from psycopg.rows import dict_row


def get_db():
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True, row_factory=dict_row) as conn:
        yield conn


def bearer(value):
    if not value:
        raise HTTPException(401, 'Se requiere un token Bearer', headers={'WWW-Authenticate': 'Bearer'})
    parts = value.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise HTTPException(401, 'Token inválido', headers={'WWW-Authenticate': 'Bearer'})
    return parts[1]


def secret():
    key = os.environ['PORTAL_TOKEN_SECRET'].encode()
    if len(key) < 32:
        raise HTTPException(503, 'La clave del portal debe tener al menos 32 bytes')
    return key


def encode(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


def issue_token(user_id):
    ttl = int(os.environ.get('PORTAL_TOKEN_TTL_SECONDS', '3600'))
    if not 60 <= ttl <= 86400:
        raise HTTPException(503, 'Duración de sesión mal configurada')
    expiry = int(time.time()) + ttl
    payload = encode(json.dumps({'usuario_id': user_id, 'exp': expiry, 'aud': 'portal'}, separators=(',', ':')).encode())
    signature = encode(hmac.new(secret(), payload.encode('ascii'), hashlib.sha256).digest())
    return {'token': payload + '.' + signature, 'tipo': 'Bearer', 'expira_en': expiry}


def verify_token(token):
    key = secret()
    try:
        if len(token) > 2048:
            raise ValueError()
        payload, signature = token.split('.')
        expected = encode(hmac.new(key, payload.encode('ascii'), hashlib.sha256).digest())
        if not hmac.compare_digest(signature.encode('ascii'), expected.encode('ascii')):
            raise ValueError()
        data = json.loads(base64.b64decode(payload + '=' * (-len(payload) % 4), altchars=b'-_', validate=True))
        if data.get('aud') != 'portal' or type(data.get('usuario_id')) is not int or data['usuario_id'] <= 0:
            raise ValueError()
        if type(data.get('exp')) is not int or data['exp'] <= int(time.time()):
            raise ValueError()
        return data['usuario_id']
    except (ValueError, TypeError, KeyError, UnicodeError):
        raise HTTPException(401, 'Token inválido o expirado', headers={'WWW-Authenticate': 'Bearer'})


def context(conn, actor, request):
    conn.execute("SELECT set_config('app.actor_id', %s, false), set_config('app.correlacion_id', %s, false)", (str(actor), str(uuid.uuid4())))


def audit(conn, operation, solicitud_id=None, allowed=True):
    conn.execute('SELECT registrar_acceso(%s, %s, %s)', (operation, solicitud_id, allowed))


def require_user(request: Request, authorization: str | None = Header(default=None), conn=Depends(get_db)):
    user_id = verify_token(bearer(authorization))
    user = conn.execute('SELECT * FROM empleados WHERE id = %s AND activo', (user_id,)).fetchone()
    if not user:
        raise HTTPException(401, 'Usuario inactivo o inexistente')
    context(conn, user['id'], request)
    audit(conn, 'ACCESO_PORTAL')
    return user


def require_admin(request: Request, authorization: str | None = Header(default=None), conn=Depends(get_db)):
    token = bearer(authorization)
    expected = os.environ['ADMIN_API_TOKEN']
    if not expected or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(401, 'Credencial administrativa inválida', headers={'WWW-Authenticate': 'Bearer'})
    # El actor está vinculado a la credencial en la configuración del servidor.
    actor_id = int(os.environ['ADMIN_ACTOR_ID'])
    user = conn.execute('SELECT * FROM empleados WHERE id = %s AND activo', (actor_id,)).fetchone()
    if not user:
        raise HTTPException(401, 'Operador administrativo inactivo')
    roles = conn.execute('SELECT rol_codigo FROM empleado_roles WHERE empleado_id = %s', (actor_id,)).fetchall()
    user['roles'] = {row['rol_codigo'] for row in roles}
    context(conn, actor_id, request)
    if not user['roles'].intersection({'JEFE_INMEDIATO', 'TALENTO_HUMANO'}):
        audit(conn, 'ACCESO_DENEGADO', allowed=False)
        raise HTTPException(403, 'El operador no tiene un rol administrativo')
    audit(conn, 'ACCESO_PANEL')
    return user


def require_hr(conn, user):
    if 'TALENTO_HUMANO' not in user['roles']:
        audit(conn, 'ACCESO_DENEGADO', allowed=False)
        raise HTTPException(403, 'Se requiere Talento Humano')


def own_request(conn, user, request_id, lock=False):
    # Consultas completas y constantes; solo los valores se parametrizan.
    if lock:
        row = conn.execute('SELECT * FROM solicitudes WHERE id = %s FOR UPDATE', (request_id,)).fetchone()
    else:
        row = conn.execute('SELECT * FROM solicitudes WHERE id = %s', (request_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Solicitud inexistente')
    if row['solicitante_id'] != user['id']:
        audit(conn, 'ACCESO_DENEGADO', request_id, False)
        raise HTTPException(404, 'Solicitud inexistente')
    return row


def admin_request(conn, user, request_id, lock=False):
    if lock:
        row = conn.execute('SELECT * FROM solicitudes WHERE id = %s FOR UPDATE', (request_id,)).fetchone()
    else:
        row = conn.execute('SELECT * FROM solicitudes WHERE id = %s', (request_id,)).fetchone()
    if not row:
        raise HTTPException(404, 'Solicitud inexistente')
    permitted = conn.execute('''SELECT 1 FROM revisiones r
        JOIN empleado_roles er ON er.rol_codigo = r.rol_codigo AND er.empleado_id = %s
        WHERE r.solicitud_id = %s AND (r.aprobador_id IS NULL OR r.aprobador_id = %s)
        AND %s <> %s LIMIT 1''', (user['id'], request_id, user['id'], user['id'], row['solicitante_id'])).fetchone()
    if not permitted:
        audit(conn, 'ACCESO_DENEGADO', request_id, False)
        raise HTTPException(404, 'Solicitud inexistente')
    return row


def validate_policy(data, policy, origen):
    if policy['requiere_motivo'] and not data.motivo:
        raise HTTPException(422, 'El tipo de ausencia requiere motivo u observación')
    if not policy['permite_horas'] and data.hora_inicio is not None:
        raise HTTPException(422, 'Este tipo de ausencia no permite horas')
    if origen == 'PORTAL' and data.referencia_formato is not None:
        raise HTTPException(422, 'El portal no admite referencia de formato')
    if origen == 'FORMATO_OFICIAL' and not data.referencia_formato:
        raise HTTPException(422, 'Se requiere referencia del formato oficial')


def assert_editable(conn, row, version):
    if row['version'] != version:
        raise HTTPException(409, 'La versión cambió; consulte nuevamente')
    if row['estado_codigo'] not in ('ENVIADA', 'EN_REVISION'):
        raise HTTPException(409, 'La solicitud está finalizada')
    if conn.execute('SELECT 1 FROM aprobaciones WHERE solicitud_id = %s LIMIT 1', (row['id'],)).fetchone():
        raise HTTPException(409, 'La solicitud ya tiene acciones de revisión')


def history(conn, request_id):
    return {
        'historial': conn.execute('SELECT * FROM historial_solicitud WHERE solicitud_id = %s ORDER BY version', (request_id,)).fetchall(),
        'observaciones': conn.execute('SELECT * FROM observaciones WHERE solicitud_id = %s ORDER BY creado_en, id', (request_id,)).fetchall(),
        'decisiones': conn.execute('SELECT * FROM aprobaciones WHERE solicitud_id = %s ORDER BY creado_en, id', (request_id,)).fetchall()
    }

CATALOG_SQL = '''SELECT t.*, f.codigo AS flujo_codigo, f.nombre AS flujo_nombre
    FROM tipos_ausencia t JOIN flujo_aprobacion f ON f.id = t.flujo_id'''