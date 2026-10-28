import os
import hmac
from fastapi import FastAPI, APIRouter, Header, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional

app = FastAPI()

# --- Conexión a la base de datos ---

def get_db_connection():
    conn = psycopg.connect(os.environ['DATABASE_URL'], autocommit=True)
    return conn

# --- Seguridad ---

def require_admin(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')
    token = authorization[7:]
    admin_token = os.environ.get('ADMIN_API_TOKEN', '')
    if not hmac.compare_digest(token, admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')

# --- Modelos Pydantic ---

NIVELES_ESTUDIOS_VALIDOS = [
    'Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]
NIVELES_ESTUDIOS_MINIMO = ['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado']

class SolicitudCrear(BaseModel):
    cedula: str = Field(..., min_length=1)
    nombres: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_ESTUDIOS_VALIDOS:
            raise ValueError(f"Nivel de estudios inválido")
        if v not in NIVELES_ESTUDIOS_MINIMO:
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

class SolicitudDetalleEmpleado(BaseModel):
    id: int
    estado: str

class SolicitudDetalleAdmin(BaseModel):
    id: int
    cedula: str
    nombres: str
    telefono: str
    correo_electronico: str
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

class DecidirSolicitud(BaseModel):
    accion: str = Field(..., regex='^(Aprobar|Rechazar)$')
    motivo_rechazo: Optional[str] = None

    @validator('motivo_rechazo', always=True)
    def motivo_obligatorio_si_rechaza(cls, v, values):
        if values.get('accion') == 'Rechazar' and (v is None or v.strip() == ''):
            raise ValueError('Motivo de rechazo es obligatorio si se rechaza la solicitud')
        return v

# --- Routers ---

router_publico = APIRouter(prefix='/api')
router_admin = APIRouter(prefix='/api/admin', dependencies=[Depends(require_admin)])

# --- Ruta health ---

@router_publico.get('/health', tags=['Salud'])
async def health():
    return {'estado': 'ok'}

# --- Rutas portal empleado ---

@router_publico.post('/solicitudes', response_model=SolicitudRespuesta, tags=['Solicitudes'])
async def crear_solicitud(solicitud: SolicitudCrear):
    # Validaciones ya hechas por Pydantic
    # Buscar usuario por cedula o correo para obtener area, cargo y lider
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Buscar usuario solicitante
            cur.execute("""
                SELECT id, area_id, cargo_id, es_lider FROM usuario WHERE cedula = %s
            """, (solicitud.cedula,))
            usuario = cur.fetchone()
            if usuario is None:
                raise HTTPException(status_code=422, detail='Usuario no encontrado en sistema')
            usuario_id, area_id, cargo_id, es_lider = usuario
            # Obtener lider de área
            cur.execute("""
                SELECT id, nombres, correo_electronico, cargo_id FROM usuario
                WHERE area_id = %s AND es_lider = TRUE LIMIT 1
            """, (area_id,))
            lider = cur.fetchone()
            if lider is None:
                raise HTTPException(status_code=422, detail='No hay líder asignado para el área')
            lider_id, lider_nombres, lider_correo, lider_cargo_id = lider
            # Insertar solicitud
            cur.execute("""
                INSERT INTO solicitud (usuario_id, lider_area_id, estado)
                VALUES (%s, %s, 'Pendiente') RETURNING id
            """, (usuario_id, lider_id))
            solicitud_id = cur.fetchone()[0]
            # Actualizar datos usuario con datos enviados (telefono, correo, fecha_nacimiento, nivel_estudios)
            cur.execute("""
                UPDATE usuario SET nombres=%s, telefono=%s, correo_electronico=%s, fecha_nacimiento=%s, nivel_estudios=%s
                WHERE id=%s
            """, (solicitud.nombres, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios, usuario_id))
            return {'id': solicitud_id, 'estado': 'Pendiente'}

# No hay GET público para solicitudes ni por id ni listado

# --- Rutas panel administrador ---

@router_admin.get('/solicitudes', tags=['Solicitudes'])
async def listar_solicitudes():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento,
                       date_part('year', age(u.fecha_nacimiento)) AS edad, u.nivel_estudios,
                       a.nombre AS area, c.nombre AS cargo, s.estado, s.fecha_envio, s.fecha_decision,
                       l.nombres AS lider_nombres, l.correo_electronico AS lider_correo, s.motivo_rechazo
                FROM solicitud s
                JOIN usuario u ON s.usuario_id = u.id
                JOIN area a ON u.area_id = a.id
                JOIN cargo c ON u.cargo_id = c.id
                JOIN usuario l ON s.lider_area_id = l.id
                ORDER BY s.fecha_envio DESC
            """)
            filas = cur.fetchall()
            resultados = []
            for f in filas:
                resultados.append({
                    'id': f[0],
                    'cedula': f[1],
                    'nombres': f[2],
                    'telefono': f[3],
                    'correo_electronico': f[4],
                    'fecha_nacimiento': f[5].isoformat(),
                    'edad': int(f[6]),
                    'nivel_estudios': f[7],
                    'area': f[8],
                    'cargo': f[9],
                    'estado': f[10],
                    'fecha_envio': f[11].isoformat(),
                    'fecha_decision': f[12].isoformat() if f[12] else None,
                    'lider_area': {
                        'nombres': f[13],
                        'correo_electronico': f[14]
                    },
                    'motivo_rechazo': f[15]
                })
            return resultados

@router_admin.get('/solicitudes/{solicitud_id}', tags=['Solicitudes'])
async def obtener_solicitud(solicitud_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT s.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento,
                       date_part('year', age(u.fecha_nacimiento)) AS edad, u.nivel_estudios,
                       a.nombre AS area, c.nombre AS cargo, s.estado, s.fecha_envio, s.fecha_decision,
                       l.nombres AS lider_nombres, l.correo_electronico AS lider_correo, s.motivo_rechazo
                FROM solicitud s
                JOIN usuario u ON s.usuario_id = u.id
                JOIN area a ON u.area_id = a.id
                JOIN cargo c ON u.cargo_id = c.id
                JOIN usuario l ON s.lider_area_id = l.id
                WHERE s.id = %s
            """, (solicitud_id,))
            f = cur.fetchone()
            if f is None:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            return {
                'id': f[0],
                'cedula': f[1],
                'nombres': f[2],
                'telefono': f[3],
                'correo_electronico': f[4],
                'fecha_nacimiento': f[5].isoformat(),
                'edad': int(f[6]),
                'nivel_estudios': f[7],
                'area': f[8],
                'cargo': f[9],
                'estado': f[10],
                'fecha_envio': f[11].isoformat(),
                'fecha_decision': f[12].isoformat() if f[12] else None,
                'lider_area': {
                    'nombres': f[13],
                    'correo_electronico': f[14]
                },
                'motivo_rechazo': f[15]
            }

@router_admin.post('/solicitudes/{solicitud_id}/decidir', tags=['Solicitudes'])
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Verificar existencia y estado actual
            cur.execute("SELECT estado, lider_area_id FROM solicitud WHERE id = %s", (solicitud_id,))
            fila = cur.fetchone()
            if fila is None:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            estado_actual, lider_area_id = fila
            if estado_actual != 'Pendiente':
                raise HTTPException(status_code=422, detail='La solicitud ya fue decidida')
            # Registrar acción y actualizar estado
            ahora = datetime.utcnow()
            if decision.accion == 'Aprobar':
                nuevo_estado = 'Aprobada'
                motivo = None
            else:
                nuevo_estado = 'Rechazada'
                motivo = decision.motivo_rechazo
            # Actualizar solicitud
            cur.execute("""
                UPDATE solicitud SET estado = %s, fecha_decision = %s, motivo_rechazo = %s
                WHERE id = %s
            """, (nuevo_estado, ahora, motivo, solicitud_id))
            # Insertar acción aprobacion
            # Para simplificar, se asume que el admin es el usuario que decide (no se tiene usuario admin en DB)
            # Se registra con lider_area_id para trazabilidad
            cur.execute("""
                INSERT INTO accion_aprobacion (solicitud_id, usuario_id, fecha_accion, accion, motivo)
                VALUES (%s, %s, %s, %s, %s)
            """, (solicitud_id, lider_area_id, ahora, 'Aprobado' if nuevo_estado == 'Aprobada' else 'Rechazado', motivo))
            # Notificar (simulado)
            # Si aprobado, notificar admin AD
            # Si rechazado, notificar empleado con motivo
            # Aquí solo se registra, no se implementa envío real
            return {'id': solicitud_id, 'estado': nuevo_estado}

app.include_router(router_publico)
app.include_router(router_admin)