import os
import hmac
from fastapi import FastAPI, Depends, Header, HTTPException, status, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional, List

app = FastAPI()

# --- Constantes y utilidades ---
ADMIN_API_TOKEN = os.environ.get('ADMIN_API_TOKEN', '')
DATABASE_URL = os.environ.get('DATABASE_URL', '')

# Validaciones de negocio
NIVELES_ESTUDIOS_VALIDOS = [
    'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'
]

# --- Modelos Pydantic ---
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
            raise ValueError('Nivel de estudios mínimo: bachillerato')
        return v

    @validator('fecha_nacimiento')
    def validar_edad(cls, v):
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if edad <= 23:
            raise ValueError('La edad debe ser mayor a 23 años')
        return v

class SolicitudRespuestaEmpleado(BaseModel):
    id: int
    estado: str

class DatosSolicitante(BaseModel):
    cedula: str
    nombres: str
    telefono: str
    correo_electronico: EmailStr
    fecha_nacimiento: date
    edad: int
    nivel_estudios: str
    area: str
    cargo: str

class DatosLider(BaseModel):
    id: int
    nombres: str
    cargo: str
    area: str
    correo_electronico: EmailStr

class SolicitudDetalle(BaseModel):
    id: int
    estado: str
    fecha_envio: datetime
    fecha_decision: Optional[datetime]
    motivo_rechazo: Optional[str]
    solicitante: DatosSolicitante
    lider_area: DatosLider
    fecha_hora_decision: Optional[datetime]

class DecidirSolicitud(BaseModel):
    aprobar: bool
    motivo_rechazo: Optional[str] = None

# --- Dependencias ---

def get_db_connection():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        yield conn

async def require_admin(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')
    token = authorization[7:]
    if not hmac.compare_digest(token, ADMIN_API_TOKEN):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')

# --- Rutas públicas para empleados ---

@app.get('/api/health', tags=['Salud'])
async def health():
    return {'estado': 'ok'}

@app.post('/api/solicitudes', response_model=SolicitudRespuestaEmpleado, tags=['Empleado'], status_code=201)
async def crear_solicitud(solicitud: SolicitudCrear, request: Request):
    # Validaciones ya hechas por Pydantic
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Buscar area y cargo por nombre para asignar usuario
            # Para simplificar, asignamos area y cargo fijos (en producción se obtendrían del usuario autenticado)
            cur.execute("SELECT id FROM area LIMIT 1")
            area_id = cur.fetchone()
            if not area_id:
                raise HTTPException(status_code=500, detail='Configuración de área no encontrada')
            area_id = area_id[0]
            cur.execute("SELECT id FROM cargo LIMIT 1")
            cargo_id = cur.fetchone()
            if not cargo_id:
                raise HTTPException(status_code=500, detail='Configuración de cargo no encontrada')
            cargo_id = cargo_id[0]

            # Insertar usuario
            try:
                cur.execute(
                    "INSERT INTO usuario (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo_id, es_lider)"
                    " VALUES (%s,%s,%s,%s,%s,%s,%s,%s,false) RETURNING id",
                    (solicitud.cedula, solicitud.nombres, solicitud.telefono, solicitud.correo_electronico,
                     solicitud.fecha_nacimiento, solicitud.nivel_estudios, area_id, cargo_id)
                )
                usuario_id = cur.fetchone()[0]
            except psycopg.errors.UniqueViolation:
                raise HTTPException(status_code=422, detail='Cédula o correo electrónico ya registrado')

            # Obtener líder de área
            cur.execute("SELECT id FROM usuario WHERE area_id = %s AND es_lider = true LIMIT 1", (area_id,))
            lider = cur.fetchone()
            if not lider:
                raise HTTPException(status_code=500, detail='Líder de área no asignado')
            lider_id = lider[0]

            # Insertar solicitud
            cur.execute(
                "INSERT INTO solicitud (usuario_id, lider_area_id) VALUES (%s, %s) RETURNING id, estado",
                (usuario_id, lider_id)
            )
            fila = cur.fetchone()
            return {'id': fila[0], 'estado': fila[1]}

@app.get('/api/solicitudes/{solicitud_id}', response_model=SolicitudRespuestaEmpleado, tags=['Empleado'])
async def obtener_solicitud(solicitud_id: int):
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT s.id, s.estado, s.usuario_id FROM solicitud s WHERE s.id = %s", (solicitud_id,))
            fila = cur.fetchone()
            if not fila:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            # Solo devolver id y estado para empleado
            return {'id': fila[0], 'estado': fila[1]}

# --- Rutas administrativas para líderes de área ---

@app.get('/api/admin/solicitudes', dependencies=[Depends(require_admin)], tags=['Administrador'])
async def listar_solicitudes():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, estado FROM solicitud ORDER BY fecha_envio DESC")
            filas = cur.fetchall()
            return [{'id': f[0], 'estado': f[1]} for f in filas]

@app.get('/api/admin/solicitudes/{solicitud_id}', response_model=SolicitudDetalle, dependencies=[Depends(require_admin)], tags=['Administrador'])
async def detalle_solicitud(solicitud_id: int):
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    s.id, s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo,
                    u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento,
                    DATE_PART('year', AGE(u.fecha_nacimiento))::INT AS edad, u.nivel_estudios,
                    a.nombre AS area, c.nombre AS cargo,
                    l.id AS lider_id, l.nombres AS lider_nombres, lc.nombre AS lider_cargo, la.nombre AS lider_area, l.correo_electronico AS lider_correo
                FROM solicitud s
                JOIN usuario u ON s.usuario_id = u.id
                JOIN area a ON u.area_id = a.id
                JOIN cargo c ON u.cargo_id = c.id
                JOIN usuario l ON s.lider_area_id = l.id
                JOIN cargo lc ON l.cargo_id = lc.id
                JOIN area la ON l.area_id = la.id
                WHERE s.id = %s
            """, (solicitud_id,))
            fila = cur.fetchone()
            if not fila:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')

            fecha_hora_decision = fila[3] if fila[3] else None

            solicitante = DatosSolicitante(
                cedula=fila[5], nombres=fila[6], telefono=fila[7], correo_electronico=fila[8],
                fecha_nacimiento=fila[9], edad=fila[10], nivel_estudios=fila[11], area=fila[12], cargo=fila[13]
            )
            lider_area = DatosLider(
                id=fila[14], nombres=fila[15], cargo=fila[16], area=fila[17], correo_electronico=fila[18]
            )

            return SolicitudDetalle(
                id=fila[0], estado=fila[1], fecha_envio=fila[2], fecha_decision=fila[3], motivo_rechazo=fila[4],
                solicitante=solicitante, lider_area=lider_area, fecha_hora_decision=fecha_hora_decision
            )

@app.post('/api/admin/solicitudes/{solicitud_id}/decidir', dependencies=[Depends(require_admin)], tags=['Administrador'])
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud):
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        with conn.cursor() as cur:
            # Obtener solicitud y estado actual
            cur.execute("SELECT estado, lider_area_id FROM solicitud WHERE id = %s", (solicitud_id,))
            fila = cur.fetchone()
            if not fila:
                raise HTTPException(status_code=404, detail='Solicitud no encontrada')
            estado_actual, lider_area_id = fila
            if estado_actual != 'Pendiente':
                raise HTTPException(status_code=422, detail='La solicitud ya fue decidida')

            if decision.aprobar:
                # Aprobar solicitud
                cur.execute(
                    "UPDATE solicitud SET estado = 'Aprobada', fecha_decision = now(), motivo_rechazo = NULL WHERE id = %s",
                    (solicitud_id,)
                )
                # Registrar trazabilidad
                cur.execute(
                    "INSERT INTO trazabilidad (solicitud_id, usuario_id, accion) VALUES (%s, %s, 'Aprobado')",
                    (solicitud_id, lider_area_id)
                )
                # Notificar administrador AD (simulado)
                # En producción se integraría con sistema de correo o tareas
                return {'mensaje': 'Solicitud aprobada y administrador notificado'}
            else:
                # Rechazo requiere motivo
                if not decision.motivo_rechazo or decision.motivo_rechazo.strip() == '':
                    raise HTTPException(status_code=422, detail='Motivo de rechazo obligatorio')
                cur.execute(
                    "UPDATE solicitud SET estado = 'Rechazada', fecha_decision = now(), motivo_rechazo = %s WHERE id = %s",
                    (decision.motivo_rechazo, solicitud_id)
                )
                # Registrar trazabilidad
                cur.execute(
                    "INSERT INTO trazabilidad (solicitud_id, usuario_id, accion, motivo) VALUES (%s, %s, 'Rechazado', %s)",
                    (solicitud_id, lider_area_id, decision.motivo_rechazo)
                )
                # Notificar empleado (simulado)
                return {'mensaje': 'Solicitud rechazada y empleado notificado'}