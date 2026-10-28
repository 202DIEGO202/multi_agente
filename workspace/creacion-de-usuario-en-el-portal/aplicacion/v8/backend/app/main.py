import os
import hmac
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional

app = FastAPI()

# --- Conexión a la base de datos ---

def get_db_connection():
    conn = psycopg.connect(os.environ['DATABASE_URL'], autocommit=True)
    try:
        yield conn
    finally:
        conn.close()

# --- Seguridad ---

def require_admin(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')
    token = authorization[7:]
    expected_token = os.environ.get('ADMIN_API_TOKEN', '')
    if not hmac.compare_digest(token, expected_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')

# --- Modelos Pydantic ---

NIVELES_ESTUDIOS = [
    'Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]

ESTADOS_SOLICITUD = ['Pendiente', 'Aprobada', 'Rechazada']

MIN_EDAD = 24  # mayor a 23 años
MIN_NIVEL_ESTUDIOS = 'Bachillerato'


class SolicitudCrear(BaseModel):
    cedula: str = Field(..., min_length=1)
    nombres: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_ESTUDIOS:
            raise ValueError(f"Nivel de estudios inválido")
        # Validar mínimo bachillerato
        niveles_validos = NIVELES_ESTUDIOS[NIVELES_ESTUDIOS.index(MIN_NIVEL_ESTUDIOS):]
        if v not in niveles_validos:
            raise ValueError(f"Nivel de estudios mínimo: {MIN_NIVEL_ESTUDIOS}")
        return v

    @validator('fecha_nacimiento')
    def validar_edad(cls, v):
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if edad < MIN_EDAD:
            raise ValueError(f"La edad debe ser mayor a 23 años")
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
    estado: str
    fecha_envio: datetime
    fecha_decision: Optional[datetime]
    lider_area: dict
    motivo_rechazo: Optional[str]
    aprobador: Optional[dict]


class DecidirSolicitud(BaseModel):
    accion: str = Field(..., regex='^(Aprobar|Rechazar)$')
    motivo_rechazo: Optional[str] = None

    @validator('motivo_rechazo')
    def motivo_obligatorio_si_rechaza(cls, v, values):
        if values.get('accion') == 'Rechazar' and (v is None or v.strip() == ''):
            raise ValueError('Motivo de rechazo es obligatorio si se rechaza la solicitud')
        return v


# --- Rutas públicas (portal empleado) ---

router_publico = APIRouter(prefix='/api')

@router_publico.get('/health', tags=['salud'], response_model=dict)
async def health():
    return {'estado': 'ok'}

@router_publico.post('/solicitudes', tags=['solicitudes'], response_model=SolicitudRespuesta)
async def crear_solicitud(solicitud: SolicitudCrear):
    # Validaciones ya hechas por Pydantic
    # Insertar usuario si no existe, obtener usuario_id y lider_area_id
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            # Buscar usuario por cedula
            cur.execute('SELECT id, area_id FROM usuarios WHERE cedula = %s', (solicitud.cedula,))
            usuario = cur.fetchone()
            if usuario:
                usuario_id = usuario[0]
                area_id = usuario[1]
                # Actualizar datos del usuario para mantener actualizados
                cur.execute('''
                    UPDATE usuarios SET nombres=%s, telefono=%s, correo_electronico=%s, fecha_nacimiento=%s, nivel_estudios=%s
                    WHERE id=%s
                ''', (solicitud.nombres, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios, usuario_id))
            else:
                # Para esta app, se requiere area y cargo para usuario, pero no se recibe en solicitud
                # Se asume que el empleado ya existe en usuarios para asignar area y lider
                # Si no existe, se rechaza la creación
                raise HTTPException(status_code=422, detail='Usuario no registrado en sistema o falta asignar área y cargo')

            # Obtener lider_area_id
            cur.execute('''
                SELECT id, nombres, cargo, area_id, correo_electronico FROM usuarios
                WHERE area_id = %s AND es_lider = TRUE
                LIMIT 1
            ''', (area_id,))
            lider = cur.fetchone()
            if not lider:
                raise HTTPException(status_code=422, detail='No hay líder de área asignado para el área del usuario')
            lider_area_id = lider[0]

            # Insertar solicitud
            cur.execute('''
                INSERT INTO solicitudes (usuario_id, lider_area_id, estado)
                VALUES (%s, %s, 'Pendiente') RETURNING id
            ''', (usuario_id, lider_area_id))
            solicitud_id = cur.fetchone()[0]

    return {'id': solicitud_id, 'estado': 'Pendiente'}

# --- Rutas administrativas (panel aprobadores) ---

router_admin = APIRouter(prefix='/api/admin', dependencies=[Depends(require_admin)])

@router_admin.get('/solicitudes', tags=['solicitudes'])
async def listar_solicitudes():
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios,
                       s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo,
                       la.id, la.nombres, la.cargo, la.area_id, la.correo_electronico
                FROM solicitudes s
                JOIN usuarios u ON s.usuario_id = u.id
                JOIN usuarios la ON s.lider_area_id = la.id
                ORDER BY s.fecha_envio DESC
            ''')
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
                    'fecha_nacimiento': f[5],
                    'edad': edad,
                    'nivel_estudios': f[6],
                    'estado': f[7],
                    'fecha_envio': f[8],
                    'fecha_decision': f[9],
                    'motivo_rechazo': f[10],
                    'lider_area': {
                        'id': f[11],
                        'nombres': f[12],
                        'cargo': f[13],
                        'area_id': f[14],
                        'correo_electronico': f[15]
                    }
                })
    return resultados

@router_admin.get('/solicitudes/{solicitud_id}', tags=['solicitudes'])
async def obtener_solicitud(solicitud_id: int):
    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios,
                       s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo,
                       la.id, la.nombres, la.cargo, la.area_id, la.correo_electronico
                FROM solicitudes s
                JOIN usuarios u ON s.usuario_id = u.id
                JOIN usuarios la ON s.lider_area_id = la.id
                WHERE s.id = %s
            ''', (solicitud_id,))
            f = cur.fetchone()
            if not f:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            edad = (date.today().year - f[5].year - ((date.today().month, date.today().day) < (f[5].month, f[5].day)))
            # Obtener datos aprobador (líder de área) y fecha decisión
            aprobador = None
            if f[9]:
                aprobador = {
                    'nombre': f[12],
                    'cargo': f[13],
                    'area_id': f[14],
                    'correo_electronico': f[15],
                    'fecha_decision': f[9].isoformat()
                }
            return {
                'id': f[0],
                'cedula': f[1],
                'nombres': f[2],
                'telefono': f[3],
                'correo_electronico': f[4],
                'fecha_nacimiento': f[5],
                'edad': edad,
                'nivel_estudios': f[6],
                'estado': f[7],
                'fecha_envio': f[8],
                'fecha_decision': f[9],
                'motivo_rechazo': f[10],
                'lider_area': {
                    'id': f[11],
                    'nombres': f[12],
                    'cargo': f[13],
                    'area_id': f[14],
                    'correo_electronico': f[15]
                },
                'aprobador': aprobador
            }

@router_admin.post('/solicitudes/{solicitud_id}/decidir', tags=['solicitudes'])
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud, authorization: str = Header(...)):
    # Validar token con require_admin
    require_admin(authorization)

    with psycopg.connect(os.environ['DATABASE_URL'], autocommit=True) as conn:
        with conn.cursor() as cur:
            # Obtener solicitud y estado actual
            cur.execute('SELECT estado, usuario_id, lider_area_id FROM solicitudes WHERE id = %s', (solicitud_id,))
            fila = cur.fetchone()
            if not fila:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            estado_actual, usuario_id, lider_area_id = fila
            if estado_actual != 'Pendiente':
                raise HTTPException(status_code=422, detail='Solo se pueden decidir solicitudes en estado Pendiente')

            # Obtener id del usuario admin que decide (simulado por token, aquí no se extrae usuario real)
            # Para trazabilidad se usa lider_area_id como usuario que decide
            usuario_decide_id = lider_area_id

            fecha_decision = datetime.utcnow()

            if decision.accion == 'Aprobar':
                # Actualizar estado a Aprobada
                cur.execute('''
                    UPDATE solicitudes SET estado = 'Aprobada', fecha_decision = %s, motivo_rechazo = NULL
                    WHERE id = %s
                ''', (fecha_decision, solicitud_id))
                # Insertar trazabilidad
                cur.execute('''
                    INSERT INTO trazabilidad_aprobaciones (solicitud_id, usuario_id, fecha_accion, accion, motivo)
                    VALUES (%s, %s, %s, 'Aprobado', NULL)
                ''', (solicitud_id, usuario_decide_id, fecha_decision))
                # Notificar administrador AD (simulado)
                # En producción se enviaría correo o tarea

            elif decision.accion == 'Rechazar':
                # Validar motivo ya hecho por Pydantic
                cur.execute('''
                    UPDATE solicitudes SET estado = 'Rechazada', fecha_decision = %s, motivo_rechazo = %s
                    WHERE id = %s
                ''', (fecha_decision, decision.motivo_rechazo, solicitud_id))
                cur.execute('''
                    INSERT INTO trazabilidad_aprobaciones (solicitud_id, usuario_id, fecha_accion, accion, motivo)
                    VALUES (%s, %s, %s, 'Rechazado', %s)
                ''', (solicitud_id, usuario_decide_id, fecha_decision, decision.motivo_rechazo))

            else:
                raise HTTPException(status_code=422, detail='Acción inválida')

    return {'mensaje': f'Solicitud {decision.accion.lower()} con éxito'}

app.include_router(router_publico)
app.include_router(router_admin)