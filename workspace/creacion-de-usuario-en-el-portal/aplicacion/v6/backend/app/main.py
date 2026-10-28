import os
import hmac
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional, List

app = FastAPI()

# --- Constantes y utilidades ---
ADMIN_API_TOKEN = os.environ.get('ADMIN_API_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# --- Conexión a base de datos por petición ---
def get_db_connection():
    conn = psycopg.connect(DATABASE_URL, autocommit=True)
    try:
        yield conn
    finally:
        conn.close()

# --- Seguridad ---

def require_admin(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')
    token = authorization[7:]
    if not hmac.compare_digest(token, ADMIN_API_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')

# --- Modelos Pydantic ---

NIVELES_VALIDOS = [
    'Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]

ESTADO_PENDIENTE = 'Pendiente'
ESTADO_APROBADA = 'Aprobada'
ESTADO_RECHAZADA = 'Rechazada'

class SolicitudCrear(BaseModel):
    cedula: str = Field(..., min_length=1)
    nombres: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_VALIDOS:
            raise ValueError(f"Nivel de estudios inválido")
        # Validar mínimo bachillerato
        niveles_orden = {nivel: i for i, nivel in enumerate(NIVELES_VALIDOS)}
        if niveles_orden[v] < niveles_orden['Bachillerato']:
            raise ValueError("Nivel de estudios mínimo: bachillerato")
        return v

    @validator('fecha_nacimiento')
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
    nombres: str
    telefono: str
    correo_electronico: EmailStr
    fecha_nacimiento: date
    edad: int
    nivel_estudios: str
    area: str
    cargo: str
    estado: str
    fecha_envio: datetime
    fecha_decision: Optional[datetime]
    lider_area: dict
    motivo_rechazo: Optional[str]
    aprobador: Optional[dict]

class DecidirSolicitud(BaseModel):
    aprobar: bool
    motivo_rechazo: Optional[str] = None

# --- Rutas públicas (portal empleado) ---
portal_router = APIRouter(prefix='/api')

@portal_router.get('/health', tags=['salud'], response_model=dict)
def health():
    return {'estado': 'ok'}

@portal_router.post('/solicitudes', tags=['solicitudes'], response_model=SolicitudRespuesta, status_code=201)
async def crear_solicitud(solicitud: SolicitudCrear, conn=Depends(get_db_connection)):
    # Validaciones ya hechas por Pydantic
    # Buscar área y líder de área según cedula o lógica (simplificado: buscar usuario y su líder)
    with conn.cursor() as cur:
        # Buscar usuario por cedula
        cur.execute("SELECT id, area_id FROM usuarios WHERE cedula = %s", (solicitud.cedula,))
        usuario = cur.fetchone()
        if usuario:
            usuario_id, area_id = usuario
        else:
            # Insertar usuario temporal sin lider (no es líder)
            cur.execute(
                "INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo, es_lider)"
                " VALUES (%s,%s,%s,%s,%s,%s,(SELECT id FROM areas ORDER BY id LIMIT 1), 'Empleado', false) RETURNING id, area_id",
                (solicitud.cedula, solicitud.nombres, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios)
            )
            usuario_id, area_id = cur.fetchone()
        # Buscar líder de área
        cur.execute("SELECT id, nombres, cargo, area_id, correo_electronico FROM usuarios WHERE area_id = %s AND es_lider = true LIMIT 1", (area_id,))
        lider = cur.fetchone()
        if not lider:
            raise HTTPException(status_code=422, detail='No hay líder de área asignado para el área del usuario')
        lider_id, lider_nombres, lider_cargo, lider_area_id, lider_correo = lider
        # Insertar solicitud
        cur.execute(
            "INSERT INTO solicitudes (usuario_id, lider_area_id, estado) VALUES (%s, %s, %s) RETURNING id",
            (usuario_id, lider_id, ESTADO_PENDIENTE)
        )
        solicitud_id = cur.fetchone()[0]
    return {'id': solicitud_id, 'estado': ESTADO_PENDIENTE}

# --- Rutas administrativas (panel aprobadores) ---
admin_router = APIRouter(prefix='/api/admin', dependencies=[Depends(require_admin)])

@admin_router.get('/solicitudes', tags=['admin_solicitudes'])
async def listar_solicitudes(estado: Optional[str] = None, conn=Depends(get_db_connection)):
    with conn.cursor() as cur:
        if estado and estado not in [ESTADO_PENDIENTE, ESTADO_APROBADA, ESTADO_RECHAZADA]:
            raise HTTPException(status_code=422, detail='Estado inválido')
        if estado:
            cur.execute(
                "SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, a.nombre, u.cargo, s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo, "
                "l.id, l.nombres, l.cargo, l.correo_electronico "
                "FROM solicitudes s "
                "JOIN usuarios u ON s.usuario_id = u.id "
                "JOIN areas a ON u.area_id = a.id "
                "JOIN usuarios l ON s.lider_area_id = l.id "
                "WHERE s.estado = %s ORDER BY s.fecha_envio DESC",
                (estado,)
            )
        else:
            cur.execute(
                "SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, a.nombre, u.cargo, s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo, "
                "l.id, l.nombres, l.cargo, l.correo_electronico "
                "FROM solicitudes s "
                "JOIN usuarios u ON s.usuario_id = u.id "
                "JOIN areas a ON u.area_id = a.id "
                "JOIN usuarios l ON s.lider_area_id = l.id "
                "ORDER BY s.fecha_envio DESC"
            )
        filas = cur.fetchall()
        resultados = []
        for f in filas:
            edad = (date.today().year - f[5].year - ((date.today().month, date.today().day) < (f[5].month, f[5].day)))
            resultados.append({
                'id': f[0],
                'cedula': f[1],
                'nombres': f[2],
                'telefono': f[3],
                'correo_electronico': f[4],
                'fecha_nacimiento': f[5].isoformat(),
                'edad': edad,
                'nivel_estudios': f[6],
                'area': f[7],
                'cargo': f[8],
                'estado': f[9],
                'fecha_envio': f[10].isoformat(),
                'fecha_decision': f[11].isoformat() if f[11] else None,
                'motivo_rechazo': f[12],
                'lider_area': {
                    'id': f[13],
                    'nombres': f[14],
                    'cargo': f[15],
                    'correo_electronico': f[16]
                }
            })
    return resultados

@admin_router.get('/solicitudes/{solicitud_id}', tags=['admin_solicitudes'])
async def obtener_solicitud(solicitud_id: int, conn=Depends(get_db_connection)):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, a.nombre, u.cargo, s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo, "
            "l.id, l.nombres, l.cargo, l.correo_electronico "
            "FROM solicitudes s "
            "JOIN usuarios u ON s.usuario_id = u.id "
            "JOIN areas a ON u.area_id = a.id "
            "JOIN usuarios l ON s.lider_area_id = l.id "
            "WHERE s.id = %s",
            (solicitud_id,)
        )
        f = cur.fetchone()
        if not f:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        edad = (date.today().year - f[5].year - ((date.today().month, date.today().day) < (f[5].month, f[5].day)))
        return {
            'id': f[0],
            'cedula': f[1],
            'nombres': f[2],
            'telefono': f[3],
            'correo_electronico': f[4],
            'fecha_nacimiento': f[5].isoformat(),
            'edad': edad,
            'nivel_estudios': f[6],
            'area': f[7],
            'cargo': f[8],
            'estado': f[9],
            'fecha_envio': f[10].isoformat(),
            'fecha_decision': f[11].isoformat() if f[11] else None,
            'motivo_rechazo': f[12],
            'lider_area': {
                'id': f[13],
                'nombres': f[14],
                'cargo': f[15],
                'correo_electronico': f[16]
            }
        }

@admin_router.post('/solicitudes/{solicitud_id}/decidir', tags=['admin_solicitudes'])
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud, authorization: str = Header(...), conn=Depends(get_db_connection)):
    # Validar motivo si rechaza
    if not decision.aprobar and (not decision.motivo_rechazo or decision.motivo_rechazo.strip() == ''):
        raise HTTPException(status_code=422, detail='Motivo de rechazo obligatorio')

    # Obtener usuario admin del token para registro trazabilidad (simplificado: no extraemos usuario, solo validamos token)
    # En un sistema real, se extraería usuario del token

    with conn.cursor() as cur:
        # Obtener solicitud
        cur.execute("SELECT estado, usuario_id, lider_area_id FROM solicitudes WHERE id = %s", (solicitud_id,))
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        estado_actual, usuario_id, lider_area_id = fila
        if estado_actual != ESTADO_PENDIENTE:
            raise HTTPException(status_code=422, detail='Solo solicitudes pendientes pueden ser decididas')

        fecha_decision = datetime.utcnow()

        if decision.aprobar:
            # Aprobar
            cur.execute(
                "UPDATE solicitudes SET estado = %s, fecha_decision = %s, motivo_rechazo = NULL WHERE id = %s",
                (ESTADO_APROBADA, fecha_decision, solicitud_id)
            )
            accion = 'Aprobar'
            motivo = None
            # Notificar administrador AD (fuera de alcance, solo registro)
        else:
            # Rechazar
            cur.execute(
                "UPDATE solicitudes SET estado = %s, fecha_decision = %s, motivo_rechazo = %s WHERE id = %s",
                (ESTADO_RECHAZADA, fecha_decision, decision.motivo_rechazo.strip(), solicitud_id)
            )
            accion = 'Rechazar'
            motivo = decision.motivo_rechazo.strip()

        # Registrar trazabilidad
        # Obtener id usuario admin (simplificado: no hay usuario, se usa lider_area_id para registro)
        # En un sistema real, se usaría usuario autenticado
        cur.execute(
            "INSERT INTO trazabilidad_solicitudes (solicitud_id, usuario_id, accion, fecha_accion, motivo) VALUES (%s, %s, %s, %s, %s)",
            (solicitud_id, lider_area_id, accion, fecha_decision, motivo)
        )

    return {'mensaje': f'Solicitud {accion.lower()} con éxito'}

app.include_router(portal_router)
app.include_router(admin_router)