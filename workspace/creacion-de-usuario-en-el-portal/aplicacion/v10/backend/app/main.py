import os
import hmac
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field, EmailStr, field_validator
from datetime import date, datetime
import psycopg
from typing import Optional

app = FastAPI()

# --- Constantes y utilidades ---
ADMIN_API_TOKEN = os.environ.get('ADMIN_API_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# --- Dependencias ---

def get_db_connection():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        yield conn


def require_admin(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')
    token = authorization[7:]
    if not hmac.compare_digest(token, ADMIN_API_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')

# --- Modelos Pydantic ---

NIVELES_ESTUDIOS_VALIDOS = [
    'Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]
NIVELES_ESTUDIOS_MINIMO = ['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado']

class SolicitudCrear(BaseModel):
    cedula: str = Field(..., min_length=1)
    nombres_completos: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str

    @field_validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_ESTUDIOS_VALIDOS:
            raise ValueError(f"Nivel de estudios inválido")
        if v not in NIVELES_ESTUDIOS_MINIMO:
            raise ValueError("Nivel de estudios mínimo: bachillerato")
        return v

    @field_validator('fecha_nacimiento')
    def validar_edad(cls, v):
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if edad <= 23:
            raise ValueError("La edad debe ser mayor a 23 años")
        return v

class SolicitudRespuesta(BaseModel):
    id: int
    estado: str

class SolicitudDetalle(BaseModel):
    id: int
    cedula: str
    nombres_completos: str
    telefono: str
    correo_electronico: EmailStr
    fecha_nacimiento: date
    edad: int
    nivel_estudios: str
    area: str
    cargo: str
    estado: str
    motivo_rechazo: Optional[str]
    fecha_envio: datetime
    fecha_decision: Optional[datetime]
    lider_area: dict
    aprobador: Optional[dict]

class DecidirSolicitud(BaseModel):
    aprobar: bool
    motivo_rechazo: Optional[str] = None

# --- Rutas públicas (portal empleado) ---
portal_router = APIRouter(prefix='/api', tags=['portal'])

@portal_router.get('/health', tags=['salud'], response_model=dict)
def health():
    return {'estado': 'ok'}

@portal_router.post('/solicitudes', response_model=SolicitudRespuesta, status_code=201, tags=['solicitudes'])
def crear_solicitud(solicitud: SolicitudCrear, conn=Depends(get_db_connection)):
    # Validaciones ya hechas por Pydantic
    with conn.cursor() as cur:
        # Verificar que no exista usuario con misma cedula o correo
        cur.execute("SELECT id FROM usuarios WHERE cedula = %s OR correo_electronico = %s", (solicitud.cedula, solicitud.correo_electronico))
        if cur.fetchone():
            raise HTTPException(status_code=422, detail='Cédula o correo electrónico ya registrado')

        # Obtener area_id y lider_area_id según cedula si existe usuario para asignar lider_area
        cur.execute("SELECT area_id FROM usuarios WHERE cedula = %s", (solicitud.cedula,))
        res = cur.fetchone()
        if res:
            area_id = res[0]
        else:
            # No existe usuario previo, no se puede asignar área
            raise HTTPException(status_code=422, detail='No se pudo asignar área para la solicitud')

        # Obtener lider_area_id para esa area
        cur.execute("SELECT id FROM usuarios WHERE area_id = %s AND cargo_id IN (SELECT id FROM cargos WHERE nombre ILIKE '%lider%') LIMIT 1", (area_id,))
        res2 = cur.fetchone()
        if res2:
            lider_area_id = res2[0]
        else:
            raise HTTPException(status_code=422, detail='No se pudo asignar líder de área para la solicitud')

        # Insertar usuario temporal para solicitud con cargo 'Empleado'
        cur.execute(
            "INSERT INTO usuarios (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo_id)"
            " VALUES (%s,%s,%s,%s,%s,%s,%s,(SELECT id FROM cargos WHERE nombre ILIKE 'Empleado' LIMIT 1)) RETURNING id",
            (solicitud.cedula, solicitud.nombres_completos, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios, area_id)
        )
        usuario_id = cur.fetchone()[0]

        # Insertar solicitud
        cur.execute(
            "INSERT INTO solicitudes (usuario_id, lider_area_id) VALUES (%s, %s) RETURNING id, estado",
            (usuario_id, lider_area_id)
        )
        fila = cur.fetchone()
        solicitud_id, estado = fila

    return SolicitudRespuesta(id=solicitud_id, estado=estado)

# --- Rutas administrativas (panel aprobadores) ---
admin_router = APIRouter(prefix='/api/admin', tags=['admin'], dependencies=[Depends(require_admin)])

@admin_router.get('/solicitudes', tags=['solicitudes'])
def listar_solicitudes(conn=Depends(get_db_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, u.cedula, u.nombres_completos, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios,
                   a.nombre as area, c.nombre as cargo, s.estado, s.motivo_rechazo, s.fecha_envio, s.fecha_decision,
                   la.id as lider_area_id, la.nombres_completos as lider_nombre, la.correo_electronico as lider_correo
            FROM solicitudes s
            JOIN usuarios u ON s.usuario_id = u.id
            JOIN areas a ON u.area_id = a.id
            JOIN cargos c ON u.cargo_id = c.id
            JOIN usuarios la ON s.lider_area_id = la.id
            ORDER BY s.fecha_envio DESC
            """
        )
        filas = cur.fetchall()
        resultados = []
        for f in filas:
            fecha_nac = f[5]
            hoy = date.today()
            edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
            resultados.append({
                'id': f[0],
                'cedula': f[1],
                'nombres_completos': f[2],
                'telefono': f[3],
                'correo_electronico': f[4],
                'fecha_nacimiento': f[5].isoformat(),
                'edad': edad,
                'nivel_estudios': f[6],
                'area': f[7],
                'cargo': f[8],
                'estado': f[9],
                'motivo_rechazo': f[10],
                'fecha_envio': f[11].isoformat() if f[11] else None,
                'fecha_decision': f[12].isoformat() if f[12] else None,
                'lider_area': {
                    'id': f[13],
                    'nombre': f[14],
                    'correo_electronico': f[15]
                },
                'aprobador': None
            })
    return resultados

@admin_router.get('/solicitudes/{solicitud_id}', response_model=SolicitudDetalle, tags=['solicitudes'])
def obtener_solicitud(solicitud_id: int, conn=Depends(get_db_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, u.cedula, u.nombres_completos, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios,
                   a.nombre as area, c.nombre as cargo, s.estado, s.motivo_rechazo, s.fecha_envio, s.fecha_decision,
                   la.id as lider_area_id, la.nombres_completos as lider_nombre, la.cargo_id as lider_cargo_id, la.correo_electronico as lider_correo,
                   ts.usuario_id as aprobador_id, ts.fecha_accion, ts.accion, ts.motivo
            FROM solicitudes s
            JOIN usuarios u ON s.usuario_id = u.id
            JOIN areas a ON u.area_id = a.id
            JOIN cargos c ON u.cargo_id = c.id
            JOIN usuarios la ON s.lider_area_id = la.id
            LEFT JOIN trazabilidad_solicitudes ts ON ts.solicitud_id = s.id
            WHERE s.id = %s
            ORDER BY ts.fecha_accion DESC
            LIMIT 1
            """,
            (solicitud_id,)
        )
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')

        fecha_nac = fila[5]
        hoy = date.today()
        edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))

        aprobador = None
        if fila[16]:
            cur.execute("SELECT nombres_completos, correo_electronico, cargo_id, area_id FROM usuarios WHERE id = %s", (fila[16],))
            ap = cur.fetchone()
            if ap:
                aprobador = {
                    'id': fila[16],
                    'nombre': ap[0],
                    'correo_electronico': ap[1],
                    'cargo_id': ap[2],
                    'area_id': ap[3],
                    'fecha_decision': fila[17].isoformat() if fila[17] else None,
                    'accion': fila[18],
                    'motivo': fila[19]
                }

        lider_area = {
            'id': fila[13],
            'nombre': fila[14],
            'cargo_id': fila[15],
            'correo_electronico': fila[16]
        }

        return SolicitudDetalle(
            id=fila[0],
            cedula=fila[1],
            nombres_completos=fila[2],
            telefono=fila[3],
            correo_electronico=fila[4],
            fecha_nacimiento=fila[5],
            edad=edad,
            nivel_estudios=fila[6],
            area=fila[7],
            cargo=fila[8],
            estado=fila[9],
            motivo_rechazo=fila[10],
            fecha_envio=fila[11],
            fecha_decision=fila[12],
            lider_area=lider_area,
            aprobador=aprobador
        )

@admin_router.post('/solicitudes/{solicitud_id}/decidir', tags=['solicitudes'])
def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud, conn=Depends(get_db_connection), authorization: str = Header(...)):
    # Validar token admin ya hecho por dependencia require_admin
    with conn.cursor() as cur:
        cur.execute("SELECT estado, usuario_id, lider_area_id FROM solicitudes WHERE id = %s", (solicitud_id,))
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        estado_actual, usuario_id, lider_area_id = fila
        if estado_actual != 'Pendiente':
            raise HTTPException(status_code=422, detail='La solicitud ya fue decidida')

        if decision.aprobar:
            fecha_decision = datetime.utcnow()
            cur.execute(
                "UPDATE solicitudes SET estado = 'Aprobada', motivo_rechazo = NULL, fecha_decision = %s WHERE id = %s",
                (fecha_decision, solicitud_id)
            )
            cur.execute(
                "INSERT INTO trazabilidad_solicitudes (solicitud_id, usuario_id, fecha_accion, accion) VALUES (%s, (SELECT id FROM usuarios WHERE correo_electronico = %s LIMIT 1), %s, 'Aprobado')",
                (solicitud_id, get_email_from_token(authorization), fecha_decision)
            )
            # Notificar administrador AD (simulado)

        else:
            if not decision.motivo_rechazo or not decision.motivo_rechazo.strip():
                raise HTTPException(status_code=422, detail='Motivo de rechazo obligatorio')
            fecha_decision = datetime.utcnow()
            cur.execute(
                "UPDATE solicitudes SET estado = 'Rechazada', motivo_rechazo = %s, fecha_decision = %s WHERE id = %s",
                (decision.motivo_rechazo.strip(), fecha_decision, solicitud_id)
            )
            cur.execute(
                "INSERT INTO trazabilidad_solicitudes (solicitud_id, usuario_id, fecha_accion, accion, motivo) VALUES (%s, (SELECT id FROM usuarios WHERE correo_electronico = %s LIMIT 1), %s, 'Rechazado', %s)",
                (solicitud_id, get_email_from_token(authorization), fecha_decision, decision.motivo_rechazo.strip())
            )

    return {'mensaje': 'Decisión registrada'}

# --- Función auxiliar para obtener email del admin desde token (simulado) ---
def get_email_from_token(authorization: str) -> str:
    return 'admin@empresa.com'

# --- Registro de routers ---
app.include_router(portal_router)
app.include_router(admin_router)