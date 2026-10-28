import os
from datetime import date, datetime
from typing import Optional, List
from fastapi import FastAPI, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr, Field, validator
import psycopg
from psycopg.rows import dict_row

app = FastAPI()

# Dependencia para obtener conexión a la base de datos por petición
def get_db():
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise RuntimeError('DATABASE_URL no está configurada')
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as conn:
        yield conn

# Constantes para validaciones
NIVELES_ESTUDIOS_VALIDOS = [
    'Bachillerato', 'Tecnico', 'Tecnologo', 'Profesional',
    'Especializacion', 'Maestria', 'Doctorado'
]
EDAD_MINIMA = 24  # mayor a 23 años

# Modelos Pydantic
class SolicitudBase(BaseModel):
    cedula: str = Field(..., max_length=20)
    nombres: str = Field(..., max_length=100)
    telefono: Optional[str] = Field(None, max_length=20)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_ESTUDIOS_VALIDOS:
            raise ValueError(f'Nivel de estudios mínimo: bachillerato')
        # Validar que nivel sea al menos bachillerato
        niveles_orden = {nivel: i for i, nivel in enumerate(NIVELES_ESTUDIOS_VALIDOS)}
        if niveles_orden[v] < niveles_orden['Bachillerato']:
            raise ValueError('Nivel de estudios mínimo: bachillerato')
        return v

    @validator('fecha_nacimiento')
    def validar_edad(cls, v):
        hoy = date.today()
        edad = hoy.year - v.year - ((hoy.month, hoy.day) < (v.month, v.day))
        if edad < EDAD_MINIMA:
            raise ValueError('La edad debe ser mayor a 23 años')
        return v

class SolicitudCreate(SolicitudBase):
    pass

class Usuario(BaseModel):
    id: int
    cedula: str
    nombres: str
    telefono: Optional[str]
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str
    area: Optional[str]
    cargo: Optional[str]
    es_lider: bool

class Estado(BaseModel):
    id: int
    nombre: str

class Solicitud(SolicitudBase):
    id: int
    usuario_id: int
    fecha_envio: datetime
    estado: Estado

class AprobacionBase(BaseModel):
    aprobado: bool
    motivo_rechazo: Optional[str] = None

    @validator('motivo_rechazo')
    def motivo_rechazo_obligatorio_si_rechazado(cls, v, values):
        if 'aprobado' in values and values['aprobado'] is False:
            if not v or not v.strip():
                raise ValueError('Motivo de rechazo es obligatorio si la solicitud es rechazada')
        return v

class AprobacionCreate(AprobacionBase):
    pass

class DatosAprobador(BaseModel):
    id: int
    nombres: str
    cargo: Optional[str]

class DatosSolicitante(BaseModel):
    cedula: str
    nombres: str
    area: Optional[str]
    cargo: Optional[str]
    fecha_nacimiento: date
    edad: int
    nivel_estudios: str

# Endpoints
@app.get('/api/health')
async def health():
    return {'estado': 'ok'}

@app.post('/api/solicitudes', status_code=status.HTTP_201_CREATED, response_model=Solicitud)
async def crear_solicitud(solicitud: SolicitudCreate, db=Depends(get_db)):
    # Validar datos (edad y nivel estudios) ya en Pydantic
    # Buscar usuario por cedula
    with db.cursor() as cur:
        cur.execute('SELECT * FROM usuarios WHERE cedula = %s', (solicitud.cedula,))
        usuario = cur.fetchone()
        if not usuario:
            raise HTTPException(status_code=422, detail='Usuario no encontrado para la cédula proporcionada')
        # Insertar solicitud con estado Pendiente
        cur.execute('SELECT id FROM estados WHERE nombre = %s', ('Pendiente',))
        estado = cur.fetchone()
        if not estado:
            raise HTTPException(status_code=500, detail='Estado Pendiente no configurado')
        estado_id = estado['id']
        cur.execute(
            '''INSERT INTO solicitudes (usuario_id, estado_id, nivel_estudios, fecha_nacimiento, cedula, nombres, telefono, correo_electronico)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id, fecha_envio''',
            (usuario['id'], estado_id, solicitud.nivel_estudios, solicitud.fecha_nacimiento, solicitud.cedula,
             solicitud.nombres, solicitud.telefono, solicitud.correo_electronico)
        )
        fila = cur.fetchone()
        solicitud_id = fila['id']
        fecha_envio = fila['fecha_envio']
        # Construir respuesta
        return {
            'id': solicitud_id,
            'usuario_id': usuario['id'],
            'fecha_envio': fecha_envio,
            'estado': {'id': estado_id, 'nombre': 'Pendiente'},
            **solicitud.dict()
        }

@app.get('/api/solicitudes/{solicitud_id}', response_model=dict)
async def obtener_solicitud(solicitud_id: int, db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(
            '''SELECT s.id, s.usuario_id, s.fecha_envio, e.id as estado_id, e.nombre as estado_nombre,
                      s.nivel_estudios, s.fecha_nacimiento, s.cedula, s.nombres, s.telefono, s.correo_electronico
               FROM solicitudes s
               JOIN estados e ON s.estado_id = e.id
               WHERE s.id = %s''', (solicitud_id,))
        solicitud = cur.fetchone()
        if not solicitud:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        # Obtener datos usuario solicitante
        cur.execute('SELECT area, cargo FROM usuarios WHERE id = %s', (solicitud['usuario_id'],))
        usuario = cur.fetchone()
        # Obtener datos aprobador (líder) si existe aprobación
        cur.execute(
            '''SELECT a.aprobador_id, u.nombres, u.cargo
               FROM aprobaciones a
               JOIN usuarios u ON a.aprobador_id = u.id
               WHERE a.solicitud_id = %s
               ORDER BY a.fecha DESC LIMIT 1''', (solicitud_id,))
        aprobacion = cur.fetchone()
        respuesta = {
            'solicitud': {
                'id': solicitud['id'],
                'usuario_id': solicitud['usuario_id'],
                'fecha_envio': solicitud['fecha_envio'],
                'estado': {'id': solicitud['estado_id'], 'nombre': solicitud['estado_nombre']},
                'nivel_estudios': solicitud['nivel_estudios'],
                'fecha_nacimiento': solicitud['fecha_nacimiento'],
                'cedula': solicitud['cedula'],
                'nombres': solicitud['nombres'],
                'telefono': solicitud['telefono'],
                'correo_electronico': solicitud['correo_electronico']
            },
            'solicitante': {
                'cedula': solicitud['cedula'],
                'nombres': solicitud['nombres'],
                'area': usuario['area'] if usuario else None,
                'cargo': usuario['cargo'] if usuario else None,
                'fecha_nacimiento': solicitud['fecha_nacimiento'],
                'edad': (date.today().year - solicitud['fecha_nacimiento'].year -
                         ((date.today().month, date.today().day) < (solicitud['fecha_nacimiento'].month, solicitud['fecha_nacimiento'].day))),
                'nivel_estudios': solicitud['nivel_estudios']
            },
            'aprobador': {
                'id': aprobacion['aprobador_id'],
                'nombres': aprobacion['nombres'],
                'cargo': aprobacion['cargo']
            } if aprobacion else None
        }
        return respuesta

@app.get('/api/solicitudes', response_model=List[Solicitud])
async def listar_solicitudes(db=Depends(get_db)):
    with db.cursor() as cur:
        cur.execute(
            '''SELECT s.id, s.usuario_id, s.fecha_envio, e.id as estado_id, e.nombre as estado_nombre,
                      s.nivel_estudios, s.fecha_nacimiento, s.cedula, s.nombres, s.telefono, s.correo_electronico
               FROM solicitudes s
               JOIN estados e ON s.estado_id = e.id
               ORDER BY s.fecha_envio DESC''')
        filas = cur.fetchall()
        resultados = []
        for s in filas:
            resultados.append({
                'id': s['id'],
                'usuario_id': s['usuario_id'],
                'fecha_envio': s['fecha_envio'],
                'estado': {'id': s['estado_id'], 'nombre': s['estado_nombre']},
                'nivel_estudios': s['nivel_estudios'],
                'fecha_nacimiento': s['fecha_nacimiento'],
                'cedula': s['cedula'],
                'nombres': s['nombres'],
                'telefono': s['telefono'],
                'correo_electronico': s['correo_electronico']
            })
        return resultados

@app.patch('/api/solicitudes/{solicitud_id}/estado', status_code=status.HTTP_200_OK)
async def actualizar_estado_solicitud(solicitud_id: int, aprobacion: AprobacionCreate, db=Depends(get_db)):
    # Validar motivo rechazo si es rechazado ya en Pydantic
    with db.cursor() as cur:
        # Verificar existencia solicitud y estado actual
        cur.execute('SELECT estado_id FROM solicitudes WHERE id = %s', (solicitud_id,))
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        estado_actual_id = fila['estado_id']
        # Obtener id estados
        cur.execute('SELECT id FROM estados WHERE nombre = %s', ('Aprobada',))
        estado_aprobada = cur.fetchone()
        cur.execute('SELECT id FROM estados WHERE nombre = %s', ('Rechazada',))
        estado_rechazada = cur.fetchone()
        if not estado_aprobada or not estado_rechazada:
            raise HTTPException(status_code=500, detail='Estados no configurados')
        # Actualizar estado y registrar aprobación
        nuevo_estado_id = estado_aprobada['id'] if aprobacion.aprobado else estado_rechazada['id']
        # Obtener usuario aprobador (simulado: se asume usuario con es_lider=True)
        # En producción, se debe obtener usuario autenticado
        cur.execute('SELECT id FROM usuarios WHERE es_lider = TRUE LIMIT 1')
        aprobador = cur.fetchone()
        if not aprobador:
            raise HTTPException(status_code=500, detail='No hay usuario líder configurado')
        aprobador_id = aprobador['id']
        # Actualizar estado solicitud
        cur.execute('UPDATE solicitudes SET estado_id = %s WHERE id = %s', (nuevo_estado_id, solicitud_id))
        # Insertar registro aprobación
        cur.execute(
            '''INSERT INTO aprobaciones (solicitud_id, aprobador_id, aprobado, motivo_rechazo)
               VALUES (%s, %s, %s, %s)''',
            (solicitud_id, aprobador_id, aprobacion.aprobado, aprobacion.motivo_rechazo)
        )
        # Notificaciones simuladas (correo o integración)
        # Si aprobado, notificar administrador AD
        if aprobacion.aprobado:
            # Aquí se llamaría integración con Active Directory y correo
            pass
        else:
            # Notificar empleado con motivo rechazo
            pass
        return {'mensaje': 'Estado actualizado correctamente'}