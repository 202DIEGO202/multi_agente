import base64
import binascii
import hmac
import json
import math
import os
import time

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from fastapi import Depends, HTTPException, Request

from .db import audit, get_db


def unauthorized():
    return HTTPException(401, 'Credenciales ausentes o inválidas', headers={'WWW-Authenticate': 'Bearer'})


def bearer(value):
    if not value:
        raise unauthorized()
    parts = value.split()
    if len(parts) != 2 or parts[0].lower() != 'bearer':
        raise unauthorized()
    return parts[1]


def decode_segment(value):
    if not value or any(c not in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_' for c in value):
        raise ValueError('Segmento inválido')
    return base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Propiedad duplicada')
        result[key] = value
    return result


def numeric_date(claims, name, required=True):
    value = claims.get(name)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Fecha JWT inválida')
    if not math.isfinite(value):
        raise ValueError('Fecha JWT inválida')
    return value


def verified_claims(token):
    try:
        pem = os.environ['IDENTITY_JWT_PUBLIC_KEY'].replace('\\n', '\n').encode('utf-8')
        issuer = os.environ['IDENTITY_JWT_ISSUER']
        audience = os.environ['IDENTITY_JWT_AUDIENCE']
        key = serialization.load_pem_public_key(pem)
        if not isinstance(key, rsa.RSAPublicKey) or key.key_size < 2048 or not issuer or not audience:
            raise ValueError('Configuración de identidad inválida')
    except (KeyError, ValueError, TypeError, AttributeError, UnsupportedAlgorithm) as exc:
        raise HTTPException(503, 'Proveedor de identidad no configurado correctamente') from exc
    try:
        if len(token) > 32768:
            raise ValueError('Token demasiado grande')
        header_segment, claims_segment, signature_segment = token.split('.')
        header = json.loads(decode_segment(header_segment), object_pairs_hook=unique_object)
        claims = json.loads(decode_segment(claims_segment), object_pairs_hook=unique_object)
        if not isinstance(header, dict) or not isinstance(claims, dict):
            raise ValueError('JWT inválido')
        if header.get('alg') != 'RS256' or 'crit' in header or 'b64' in header:
            raise ValueError('Cabecera JWT no admitida')
        key.verify(
            decode_segment(signature_segment),
            (header_segment + '.' + claims_segment).encode('ascii'),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        now = time.time()
        expiration = numeric_date(claims, 'exp')
        issued = numeric_date(claims, 'iat')
        not_before = numeric_date(claims, 'nbf', required=False)
        if expiration <= now or issued > now or (not_before is not None and not_before > now):
            raise ValueError('Token fuera de vigencia')
        if claims.get('iss') != issuer:
            raise ValueError('Emisor inválido')
        audiences = claims.get('aud')
        if isinstance(audiences, str):
            audiences = [audiences]
        if not isinstance(audiences, list) or not all(isinstance(item, str) for item in audiences) or audience not in audiences:
            raise ValueError('Audiencia inválida')
        if not isinstance(claims.get('sub'), str) or not claims['sub'].strip():
            raise ValueError('Identidad inválida')
        return claims
    except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error, InvalidSignature) as exc:
        raise unauthorized() from exc


def authenticated_identity(token, connection, request):
    claims = verified_claims(token)
    actor = connection.execute('SELECT id, identidad_externa FROM usuarios WHERE identidad_externa=%s AND activo', (claims['sub'],)).fetchone()
    if not actor:
        raise unauthorized()
    actor['roles'] = [r['rol_codigo'] for r in connection.execute('SELECT rol_codigo FROM usuario_roles WHERE usuario_id=%s', (actor['id'],)).fetchall()]
    audit(connection, actor, request, 'ACCESO', detail={'ruta': request.url.path, 'metodo': request.method})
    return actor


def require_employee(request: Request, connection=Depends(get_db)):
    actor = authenticated_identity(bearer(request.headers.get('Authorization')), connection, request)
    if 'EMPLEADO' not in actor['roles']:
        audit(connection, actor, request, 'ACCESO', authorized=False, detail={'rol_requerido': 'EMPLEADO'})
        raise HTTPException(403, 'Se requiere el rol de empleado')
    return actor


def require_admin(request: Request, connection=Depends(get_db)):
    token = bearer(request.headers.get('Authorization'))
    try:
        expected = os.environ['ADMIN_API_TOKEN']
    except KeyError as exc:
        raise HTTPException(503, 'Acceso administrativo no configurado') from exc
    if not expected or not hmac.compare_digest(token.encode('utf-8'), expected.encode('utf-8')):
        raise unauthorized()
    identity = bearer(request.headers.get('X-Identity-Token'))
    actor = authenticated_identity(identity, connection, request)
    if not {'JEFE_INMEDIATO', 'TALENTO_HUMANO'}.intersection(actor['roles']):
        audit(connection, actor, request, 'ACCESO', authorized=False, detail={'administrador': True})
        raise HTTPException(403, 'Se requiere un rol aprobador')
    return actor


def require_hr(actor, connection, request):
    if 'TALENTO_HUMANO' not in actor['roles']:
        audit(connection, actor, request, 'CONSULTAR_CATALOGO', authorized=False)
        raise HTTPException(403, 'La administración del catálogo corresponde a Talento Humano')