import os
from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator
from datetime import date, datetime
import psycopg
from typing import Optional, List

app = FastAPI()

# Dependencia para obtener conexión a la base de datos por petición
async def get_db():
    dsn = os.environ.get('DATABASE_URL')
    if not dsn:
        raise RuntimeError('DATABASE_URL no está configurada')
    with psycopg.connect(dsn, autocommit=True) as conn:
        yield conn

# Modelos Pydantic
class SolicitudCrear(BaseModel):
    cedula: str = Field(..., min_length=5, max_length=20)
    nombres: str = Field(..., min_length=3, max_length=100)
    telefono: Optional[str] = Field(None, max_length=20)
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str = Field(..., max_length=50)

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        niveles_validos = ['bachillerato', 'tecnico', 'tecnologo', 'profesional', 'especializacion', 'maestria', 'doctorado']
        if v.lower() not in niveles_validos:
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
    cedula: str
    nombres: str
    telefono: Optional[str]
    correo_electronico: EmailStr
    fecha_nacimiento: date
    nivel_estudios: str
    area: Optional[str]
    cargo: Optional[str]
    estado: str
    motivo_rechazo: Optional[str]

class ActualizarEstadoSolicitud(BaseModel):
    aprobado: bool
    motivo_rechazo: Optional[str] = None

    @validator('motivo_rechazo')
    def motivo_rechazo_obligatorio_si_rechazado(cls, v, values):
        if 'aprobado' in values and not values['aprobado']:
            if not v or not v.strip():
                raise ValueError('Motivo de rechazo es obligatorio cuando se rechaza la solicitud')
        return v

# Utilidades
def calcular_edad(fecha_nacimiento: date) -> int:
    hoy = date.today()
    return hoy.year - fecha_nacimiento.year - ((hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day))

# Endpoints
@app.get('/api/health')
async def health():
    return {'estado': 'ok'}

@app.post('/api/solicitudes', response_model=SolicitudRespuesta)
async def crear_solicitud(solicitud: SolicitudCrear, conn=Depends(get_db)):
    # Validaciones ya hechas por Pydantic
    # Verificar si usuario ya existe por cédula o correo
    with conn.cursor() as cur:
        cur.execute('SELECT id FROM usuarios WHERE cedula = %s OR correo_electronico = %s', (solicitud.cedula, solicitud.correo_electronico))
        usuario = cur.fetchone()
        if usuario:
            raise HTTPException(status_code=422, detail='Usuario con cédula o correo ya existe')

        # Insertar usuario
        cur.execute(
            '''INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, es_lider)
               VALUES (%s, %s, %s, %s, %s, %s, false) RETURNING id''',
            (solicitud.cedula, solicitud.nombres, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios.lower())
        )
        usuario_id = cur.fetchone()[0]

        # Obtener estado 'Pendiente'
        cur.execute("SELECT id FROM estados_solicitud WHERE nombre = 'Pendiente'")
        estado_pendiente = cur.fetchone()[0]

        # Insertar solicitud
        cur.execute(
            'INSERT INTO solicitudes (usuario_id, estado_id) VALUES (%s, %s) RETURNING id',
            (usuario_id, estado_pendiente)
        )
        solicitud_id = cur.fetchone()[0]

        # Devolver datos
        cur.execute(
            '''SELECT u.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, u.area, u.cargo, es.nombre, s.motivo_rechazo
               FROM usuarios u
               JOIN solicitudes s ON s.usuario_id = u.id
               JOIN estados_solicitud es ON s.estado_id = es.id
               WHERE s.id = %s''',
            (solicitud_id,)
        )
        fila = cur.fetchone()

    return {
        'id': fila[0],
        'cedula': fila[1],
        'nombres': fila[2],
        'telefono': fila[3],
        'correo_electronico': fila[4],
        'fecha_nacimiento': fila[5],
        'nivel_estudios': fila[6],
        'area': fila[7],
        'cargo': fila[8],
        'estado': fila[9],
        'motivo_rechazo': fila[10]
    }

@app.get('/api/solicitudes/{solicitud_id}', response_model=SolicitudRespuesta)
async def obtener_solicitud(solicitud_id: int, conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            '''SELECT u.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, u.area, u.cargo, es.nombre, s.motivo_rechazo
               FROM solicitudes s
               JOIN usuarios u ON s.usuario_id = u.id
               JOIN estados_solicitud es ON s.estado_id = es.id
               WHERE s.id = %s''',
            (solicitud_id,)
        )
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')

    return {
        'id': fila[0],
        'cedula': fila[1],
        'nombres': fila[2],
        'telefono': fila[3],
        'correo_electronico': fila[4],
        'fecha_nacimiento': fila[5],
        'nivel_estudios': fila[6],
        'area': fila[7],
        'cargo': fila[8],
        'estado': fila[9],
        'motivo_rechazo': fila[10]
    }

@app.get('/api/solicitudes', response_model=List[SolicitudRespuesta])
async def listar_solicitudes(conn=Depends(get_db)):
    with conn.cursor() as cur:
        cur.execute(
            '''SELECT u.id, u.cedula, u.nombres, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, u.area, u.cargo, es.nombre, s.motivo_rechazo
               FROM solicitudes s
               JOIN usuarios u ON s.usuario_id = u.id
               JOIN estados_solicitud es ON s.estado_id = es.id
               ORDER BY s.fecha_envio DESC'''
        )
        filas = cur.fetchall()

    resultados = []
    for fila in filas:
        resultados.append({
            'id': fila[0],
            'cedula': fila[1],
            'nombres': fila[2],
            'telefono': fila[3],
            'correo_electronico': fila[4],
            'fecha_nacimiento': fila[5],
            'nivel_estudios': fila[6],
            'area': fila[7],
            'cargo': fila[8],
            'estado': fila[9],
            'motivo_rechazo': fila[10]
        })
    return resultados

@app.patch('/api/solicitudes/{solicitud_id}/estado')
async def actualizar_estado_solicitud(solicitud_id: int, datos: ActualizarEstadoSolicitud, request: Request, conn=Depends(get_db)):
    # Simular autenticación: se espera que el líder esté autenticado y su id esté en headers (ejemplo)
    lider_id = request.headers.get('X-Lider-Id')
    if not lider_id:
        raise HTTPException(status_code=401, detail='No autorizado: falta id de líder')

    with conn.cursor() as cur:
        # Verificar existencia de solicitud y estado actual
        cur.execute('SELECT estado_id FROM solicitudes WHERE id = %s', (solicitud_id,))
        fila = cur.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        estado_actual_id = fila[0]

        # Obtener ids de estados
        cur.execute("SELECT id FROM estados_solicitud WHERE nombre = 'Aprobada'")
        estado_aprobada_id = cur.fetchone()[0]
        cur.execute("SELECT id FROM estados_solicitud WHERE nombre = 'Rechazada'")
        estado_rechazada_id = cur.fetchone()[0]

        nuevo_estado_id = estado_aprobada_id if datos.aprobado else estado_rechazada_id

        # Actualizar solicitud
        cur.execute(
            'UPDATE solicitudes SET estado_id = %s, motivo_rechazo = %s WHERE id = %s',
            (nuevo_estado_id, datos.motivo_rechazo if not datos.aprobado else None, solicitud_id)
        )

        # Insertar registro en aprobaciones
        cur.execute(
            'INSERT INTO aprobaciones (solicitud_id, lider_id, aprobado, motivo_rechazo) VALUES (%s, %s, %s, %s)',
            (solicitud_id, int(lider_id), datos.aprobado, datos.motivo_rechazo)
        )

        # Notificaciones simuladas
        # Si aprobado, notificar administrador AD (simulado)
        if datos.aprobado:
            # Aquí se llamaría integración con Active Directory y correo
            pass
        else:
            # Notificar empleado con motivo rechazo (simulado)
            pass

    return {'mensaje': 'Estado de solicitud actualizado correctamente'}