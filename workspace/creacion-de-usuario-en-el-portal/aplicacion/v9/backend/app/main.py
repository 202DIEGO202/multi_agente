import os
import hmac
from fastapi import FastAPI, Depends, Header, HTTPException, status
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional

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

    @validator('nivel_estudios')
    def validar_nivel_estudios(cls, v):
        if v not in NIVELES_ESTUDIOS_VALIDOS:
            raise ValueError(f"Nivel de estudios inválido")
        if v not in NIVELES_ESTUDIOS_MINIMO:
            raise ValueError("Nivel de estudios mínimo: bachillerato")
        return v

    @validator('fecha_nacimiento')
    def validar_edad_minima(cls, v):
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
    fecha_decision_str: Optional[str]

class DecidirSolicitud(BaseModel):
    aprobar: bool
    motivo_rechazo: Optional[str] = None

# --- Rutas públicas (portal empleado) ---
portal_router = APIRouter(prefix='/api', tags=['portal'])

@portal_router.get('/health', tags=['salud'], response_model=dict)
def health():
    return {'estado': 'ok'}

@portal_router.post('/solicitudes', response_model=SolicitudRespuesta, status_code=201)
async def crear_solicitud(solicitud: SolicitudCrear, conn=Depends(get_db_connection)):
    # Validaciones ya hechas por Pydantic
    # Buscar si usuario ya existe por cedula o correo
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM usuarios WHERE cedula = %s OR correo_electronico = %s", (solicitud.cedula, solicitud.correo_electronico))
        usuario = cur.fetchone()
        if usuario is None:
            # Insertar usuario temporal para solicitud
            # Buscar area y cargo del usuario para asignar lider_area
            # Para simplificar, asumimos que el usuario ya tiene area y cargo asignados en usuarios
            # Pero si no existe, error 422
            raise HTTPException(status_code=422, detail="Usuario no registrado en sistema con área y cargo asignados")
        usuario_id = usuario[0]

        # Obtener lider_area_id según area del usuario
        cur.execute("SELECT area_id FROM usuarios WHERE id = %s", (usuario_id,))
        area = cur.fetchone()
        if area is None:
            raise HTTPException(status_code=422, detail="Área del usuario no encontrada")
        area_id = area[0]

        # Obtener lider_area_id (usuario con cargo líder en esa área)
        cur.execute("SELECT id FROM usuarios WHERE area_id = %s AND cargo_id IN (SELECT id FROM cargos WHERE nombre ILIKE 'líder%') LIMIT 1", (area_id,))
        lider = cur.fetchone()
        if lider is None:
            raise HTTPException(status_code=422, detail="Líder de área no asignado")
        lider_area_id = lider[0]

        # Insertar solicitud
        cur.execute(
            "INSERT INTO solicitudes (usuario_id, lider_area_id, estado) VALUES (%s, %s, 'Pendiente') RETURNING id",
            (usuario_id, lider_area_id)
        )
        solicitud_id = cur.fetchone()[0]

    return SolicitudRespuesta(id=solicitud_id, estado='Pendiente')

# --- Rutas administrativas (panel aprobadores) ---
admin_router = APIRouter(prefix='/api/admin', tags=['admin'], dependencies=[Depends(require_admin)])

@admin_router.get('/solicitudes', response_model=list[SolicitudDetalle])
async def listar_solicitudes(conn=Depends(get_db_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, u.cedula, u.nombres_completos, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios,
                   a.nombre as area, c.nombre as cargo, s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo,
                   la.id as lider_id, la.nombres_completos as lider_nombre, la.correo_electronico as lider_correo,
                   la_cargo.nombre as lider_cargo, la_area.nombre as lider_area
            FROM solicitudes s
            JOIN usuarios u ON s.usuario_id = u.id
            JOIN areas a ON u.area_id = a.id
            JOIN cargos c ON u.cargo_id = c.id
            JOIN usuarios la ON s.lider_area_id = la.id
            JOIN cargos la_cargo ON la.cargo_id = la_cargo.id
            JOIN areas la_area ON la.area_id = la_area.id
            ORDER BY s.fecha_envio DESC
            """
        )
        filas = cur.fetchall()

    resultados = []
    for f in filas:
        fecha_nac = f[5]
        hoy = date.today()
        edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
        fecha_decision_str = f[10].strftime('%Y-%m-%d %H:%M:%S') if f[10] else None
        resultados.append(SolicitudDetalle(
            id=f[0], cedula=f[1], nombres_completos=f[2], telefono=f[3], correo_electronico=f[4],
            fecha_nacimiento=fecha_nac, edad=edad, nivel_estudios=f[6], area=f[7], cargo=f[8], estado=f[9],
            fecha_envio=f[10] if f[10] else f[9], fecha_decision=f[10], lider_area={
                'id': f[11], 'nombre': f[12], 'correo_electronico': f[13], 'cargo': f[14], 'area': f[15]
            }, motivo_rechazo=f[11], fecha_decision_str=fecha_decision_str
        ))
    return resultados

@admin_router.get('/solicitudes/{solicitud_id}', response_model=SolicitudDetalle)
async def obtener_solicitud(solicitud_id: int, conn=Depends(get_db_connection)):
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT s.id, u.cedula, u.nombres_completos, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios,
                   a.nombre as area, c.nombre as cargo, s.estado, s.fecha_envio, s.fecha_decision, s.motivo_rechazo,
                   la.id as lider_id, la.nombres_completos as lider_nombre, la.correo_electronico as lider_correo,
                   la_cargo.nombre as lider_cargo, la_area.nombre as lider_area
            FROM solicitudes s
            JOIN usuarios u ON s.usuario_id = u.id
            JOIN areas a ON u.area_id = a.id
            JOIN cargos c ON u.cargo_id = c.id
            JOIN usuarios la ON s.lider_area_id = la.id
            JOIN cargos la_cargo ON la.cargo_id = la_cargo.id
            JOIN areas la_area ON la.area_id = la_area.id
            WHERE s.id = %s
            """,
            (solicitud_id,)
        )
        f = cur.fetchone()
        if f is None:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')

    fecha_nac = f[5]
    hoy = date.today()
    edad = hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))
    fecha_decision_str = f[10].strftime('%Y-%m-%d %H:%M:%S') if f[10] else None
    return SolicitudDetalle(
        id=f[0], cedula=f[1], nombres_completos=f[2], telefono=f[3], correo_electronico=f[4],
        fecha_nacimiento=fecha_nac, edad=edad, nivel_estudios=f[6], area=f[7], cargo=f[8], estado=f[9],
        fecha_envio=f[10] if f[10] else f[9], fecha_decision=f[10], lider_area={
            'id': f[11], 'nombre': f[12], 'correo_electronico': f[13], 'cargo': f[14], 'area': f[15]
        }, motivo_rechazo=f[11], fecha_decision_str=fecha_decision_str
    )

@admin_router.patch('/solicitudes/{solicitud_id}/decidir', status_code=204)
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud, conn=Depends(get_db_connection), authorization: str = Header(...)):
    # Validar motivo si rechaza
    if not decision.aprobar and (decision.motivo_rechazo is None or decision.motivo_rechazo.strip() == ''):
        raise HTTPException(status_code=422, detail='Motivo de rechazo obligatorio')

    # Obtener usuario admin del token (no implementado, se usa token solo para validar)
    # Para trazabilidad se puede usar un usuario ficticio admin_id=0
    admin_id = 0

    with conn.cursor() as cur:
        cur.execute("SELECT estado FROM solicitudes WHERE id = %s", (solicitud_id,))
        fila = cur.fetchone()
        if fila is None:
            raise HTTPException(status_code=404, detail='Solicitud no encontrada')
        estado_actual = fila[0]
        if estado_actual != 'Pendiente':
            raise HTTPException(status_code=422, detail='Solo solicitudes pendientes pueden ser decididas')

        fecha_decision = datetime.utcnow()

        if decision.aprobar:
            # Aprobar
            cur.execute(
                "UPDATE solicitudes SET estado = 'Aprobada', fecha_decision = %s, motivo_rechazo = NULL WHERE id = %s",
                (fecha_decision, solicitud_id)
            )
            accion = 'Aprobar'
            motivo = None
            # Notificar administrador AD (no implementado)
        else:
            # Rechazar
            cur.execute(
                "UPDATE solicitudes SET estado = 'Rechazada', fecha_decision = %s, motivo_rechazo = %s WHERE id = %s",
                (fecha_decision, decision.motivo_rechazo.strip(), solicitud_id)
            )
            accion = 'Rechazar'
            motivo = decision.motivo_rechazo.strip()

        # Registrar trazabilidad
        cur.execute(
            "INSERT INTO trazabilidad_solicitudes (solicitud_id, usuario_id, accion, fecha_accion, motivo) VALUES (%s, %s, %s, %s, %s)",
            (solicitud_id, admin_id, accion, fecha_decision, motivo)
        )

    return

app.include_router(portal_router)
app.include_router(admin_router)