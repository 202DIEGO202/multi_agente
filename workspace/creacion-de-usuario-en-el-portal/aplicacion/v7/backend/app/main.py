import os
import hmac
from fastapi import FastAPI, APIRouter, Header, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional, List

app = FastAPI()

# --- Utilidades para conexión a BD ---

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
    'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]
NIVELES_ESTUDIOS_TODOS = [
    'Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]

class SolicitudCrear(BaseModel):
    cedula: str = Field(..., min_length=1)
    nombres_completos: str = Field(..., min_length=1)
    telefono: str = Field(..., min_length=1)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_ESTUDIOS_TODOS:
            raise ValueError(f'Nivel de estudios inválido')
        if v not in NIVELES_ESTUDIOS_VALIDOS:
            raise ValueError('Nivel de estudios mínimo: bachillerato')
        return v

    @validator('fecha_nacimiento')
    def validar_edad(cls, v):
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if edad <= 23:
            raise ValueError('La edad debe ser mayor a 23 años')
        return v

class SolicitudRespuesta(BaseModel):
    id: int
    estado: str

class DatosSolicitante(BaseModel):
    nombres_completos: str
    cedula: str
    area: str
    cargo: str
    fecha_nacimiento: date
    edad: int
    nivel_estudios: str

class DatosLider(BaseModel):
    nombres_completos: str
    cargo: str
    area: str
    correo_electronico: EmailStr
    fecha_hora_decision: Optional[datetime]

class SolicitudDetalle(BaseModel):
    id: int
    datos_solicitante: DatosSolicitante
    datos_lider: DatosLider
    estado: str
    motivo_rechazo: Optional[str]

class DecidirSolicitud(BaseModel):
    aprobar: bool
    motivo_rechazo: Optional[str] = None

# --- Routers ---

router_publico = APIRouter(prefix='/api')
router_admin = APIRouter(prefix='/api/admin', dependencies=[Depends(require_admin)])

# --- Endpoint 1: Health check ---

@router_publico.get('/health', tags=['Salud'])
async def health():
    return {'estado': 'ok'}

# --- Endpoint 2: Empleado crea solicitud ---

@router_publico.post('/solicitudes', response_model=SolicitudRespuesta, tags=['Solicitudes'])
async def crear_solicitud(solicitud: SolicitudCrear):
    # Validaciones ya hechas por Pydantic
    # Buscar usuario por cedula para obtener usuario_id y lider_area_id
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute('SELECT id, area_id FROM usuarios WHERE cedula = %s', (solicitud.cedula,))
            usuario = cur.fetchone()
            if usuario is None:
                raise HTTPException(status_code=422, detail='Empleado no encontrado por cédula')
            usuario_id, area_id = usuario
            # Obtener líder de área
            cur.execute('SELECT id, nombres_completos, cargo, correo_electronico FROM usuarios WHERE area_id = %s AND es_lider = TRUE', (area_id,))
            lider = cur.fetchone()
            if lider is None:
                raise HTTPException(status_code=422, detail='No se encontró líder de área para el empleado')
            lider_area_id = lider[0]
            # Insertar solicitud
            cur.execute(
                '''INSERT INTO solicitudes (usuario_id, nivel_estudios, estado, lider_area_id)
                   VALUES (%s, %s, 'Pendiente', %s) RETURNING id''',
                (usuario_id, solicitud.nivel_estudios, lider_area_id)
            )
            solicitud_id = cur.fetchone()[0]
            # Retornar solo id y estado
            return {'id': solicitud_id, 'estado': 'Pendiente'}

# --- Endpoint 3: Admin lista solicitudes ---

@router_admin.get('/solicitudes', tags=['Solicitudes'])
async def listar_solicitudes():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT s.id, u.nombres_completos, u.cedula, a.nombre, c.nombre, u.fecha_nacimiento, s.nivel_estudios, s.estado, s.fecha_decision, l.nombres_completos, l.cargo, l.area_id, l.correo_electronico, s.motivo_rechazo
                   FROM solicitudes s
                   JOIN usuarios u ON s.usuario_id = u.id
                   JOIN areas a ON u.area_id = a.id
                   JOIN cargos c ON u.cargo_id = c.id
                   JOIN usuarios l ON s.lider_area_id = l.id
                   ORDER BY s.fecha_envio DESC''')
            filas = cur.fetchall()
            resultados = []
            for f in filas:
                fecha_nac = f[5]
                hoy = date.today()
                edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
                datos_solicitante = {
                    'nombres_completos': f[1],
                    'cedula': f[2],
                    'area': f[3],
                    'cargo': f[4],
                    'fecha_nacimiento': f[5],
                    'edad': edad,
                    'nivel_estudios': f[6]
                }
                datos_lider = {
                    'nombres_completos': f[9],
                    'cargo': f[10],
                    'area': '',  # área del líder no se recupera directamente
                    'correo_electronico': f[12],
                    'fecha_hora_decision': f[8]
                }
                resultados.append({
                    'id': f[0],
                    'datos_solicitante': datos_solicitante,
                    'datos_lider': datos_lider,
                    'estado': f[7],
                    'motivo_rechazo': f[13]
                })
            return resultados

# --- Endpoint 4: Admin obtiene detalle solicitud ---

@router_admin.get('/solicitudes/{solicitud_id}', response_model=SolicitudDetalle, tags=['Solicitudes'])
async def obtener_solicitud(solicitud_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                '''SELECT s.id, u.nombres_completos, u.cedula, a.nombre, c.nombre, u.fecha_nacimiento, s.nivel_estudios, s.estado, s.fecha_decision, l.nombres_completos, l.cargo, l.area_id, l.correo_electronico, s.motivo_rechazo
                   FROM solicitudes s
                   JOIN usuarios u ON s.usuario_id = u.id
                   JOIN areas a ON u.area_id = a.id
                   JOIN cargos c ON u.cargo_id = c.id
                   JOIN usuarios l ON s.lider_area_id = l.id
                   WHERE s.id = %s''', (solicitud_id,))
            f = cur.fetchone()
            if f is None:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            fecha_nac = f[5]
            hoy = date.today()
            edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
            datos_solicitante = DatosSolicitante(
                nombres_completos=f[1],
                cedula=f[2],
                area=f[3],
                cargo=f[4],
                fecha_nacimiento=f[5],
                edad=edad,
                nivel_estudios=f[6]
            )
            datos_lider = DatosLider(
                nombres_completos=f[9],
                cargo=f[10],
                area='',
                correo_electronico=f[12],
                fecha_hora_decision=f[8]
            )
            return SolicitudDetalle(
                id=f[0],
                datos_solicitante=datos_solicitante,
                datos_lider=datos_lider,
                estado=f[7],
                motivo_rechazo=f[13]
            )

# --- Endpoint 5: Admin decide solicitud ---

@router_admin.post('/solicitudes/{solicitud_id}/decidir', tags=['Solicitudes'])
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud, authorization: str = Header(...)):
    # Validar motivo si rechaza
    if not decision.aprobar and (decision.motivo_rechazo is None or decision.motivo_rechazo.strip() == ''):
        raise HTTPException(status_code=422, detail='Motivo de rechazo obligatorio')

    admin_token = os.environ.get('ADMIN_API_TOKEN', '')
    token = authorization[7:] if authorization.startswith('Bearer ') else ''
    if not hmac.compare_digest(token, admin_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')

    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Obtener solicitud y estado actual
            cur.execute('SELECT estado, lider_area_id, usuario_id FROM solicitudes WHERE id = %s', (solicitud_id,))
            fila = cur.fetchone()
            if fila is None:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            estado_actual, lider_area_id, usuario_id = fila
            if estado_actual != 'Pendiente':
                raise HTTPException(status_code=422, detail='Solo solicitudes pendientes pueden ser decididas')

            # Registrar decisión
            nuevo_estado = 'Aprobada' if decision.aprobar else 'Rechazada'
            fecha_decision = datetime.utcnow()
            motivo = decision.motivo_rechazo if not decision.aprobar else None

            # Actualizar solicitud
            cur.execute(
                '''UPDATE solicitudes SET estado = %s, fecha_decision = %s, motivo_rechazo = %s WHERE id = %s''',
                (nuevo_estado, fecha_decision, motivo, solicitud_id)
            )

            # Registrar trazabilidad
            # Obtener id usuario admin desde token no disponible, se registra con lider_area_id para trazabilidad
            cur.execute(
                '''INSERT INTO trazabilidad (solicitud_id, usuario_id, accion, fecha, motivo)
                   VALUES (%s, %s, %s, %s, %s)''',
                (solicitud_id, lider_area_id, 'Aprobado' if decision.aprobar else 'Rechazado', fecha_decision, motivo)
            )

            # Notificaciones (simuladas, no implementadas)
            # Si aprobado, notificar admin AD
            # Si rechazado, notificar empleado con motivo

            return {'id': solicitud_id, 'estado': nuevo_estado}

app.include_router(router_publico)
app.include_router(router_admin)