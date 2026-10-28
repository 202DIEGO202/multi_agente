import os
import hmac
from fastapi import FastAPI, APIRouter, Header, HTTPException, Depends, status
from pydantic import BaseModel, Field, EmailStr, validator
from datetime import date, datetime
import psycopg
from typing import Optional

app = FastAPI()

# --- Conexión a base de datos ---

def get_db_connection():
    conn = psycopg.connect(os.environ['DATABASE_URL'], autocommit=True)
    return conn

# --- Seguridad ---

def require_admin(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith('Bearer '):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No autorizado')
    token = authorization[7:]
    expected_token = os.environ.get('ADMIN_API_TOKEN', '')
    if not hmac.compare_digest(token, expected_token):
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
        if v not in NIVELES_ESTUDIOS:
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

class SolicitudDetalleAprobador(BaseModel):
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

class LiderAreaInfo(BaseModel):
    id: int
    nombre: str
    cargo: str
    area: str
    correo_electronico: EmailStr
    fecha_hora_decision: Optional[datetime]

class SolicitudAprobacionDetalle(BaseModel):
    solicitud: SolicitudDetalleAprobador
    lider_area: LiderAreaInfo
    estado: str
    motivo_rechazo: Optional[str]

class DecidirSolicitud(BaseModel):
    aprobar: bool
    motivo_rechazo: Optional[str] = None

# --- Routers ---

router_publico = APIRouter(prefix="/api")
router_admin = APIRouter(prefix="/api/admin", dependencies=[Depends(require_admin)])

# --- Rutas públicas ---

@router_publico.get("/health", tags=["salud"])
async def health():
    return {"estado": "ok"}

@router_publico.post("/solicitudes", response_model=SolicitudRespuesta, tags=["solicitudes"])
async def crear_solicitud(solicitud: SolicitudCrear):
    # Validaciones ya hechas por Pydantic
    # Insertar o actualizar usuario y crear solicitud
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Buscar usuario por cedula
            cur.execute("SELECT id, nivel_estudios FROM usuario WHERE cedula = %s", (solicitud.cedula,))
            usuario = cur.fetchone()
            if usuario:
                usuario_id = usuario[0]
                nivel_actual = usuario[1]
                # Validar nivel estudios mínimo
                if solicitud.nivel_estudios not in NIVELES_ESTUDIOS_MINIMO:
                    raise HTTPException(status_code=422, detail="Nivel de estudios mínimo: bachillerato")
                # Actualizar datos usuario
                cur.execute(
                    "UPDATE usuario SET nombres_completos=%s, telefono=%s, correo_electronico=%s, fecha_nacimiento=%s, nivel_estudios=%s WHERE id=%s",
                    (solicitud.nombres_completos, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios, usuario_id)
                )
            else:
                # Insertar usuario
                # Para area y cargo asignamos valores dummy 1 (se asume que se asignan en otro proceso o se requiere lógica adicional)
                # Aquí se asume que el área y cargo se asignan según reglas de negocio no expuestas, se usa 1 para evitar error FK
                cur.execute(
                    "INSERT INTO usuario (cedula, nombres_completos, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area_id, cargo_id) VALUES (%s,%s,%s,%s,%s,%s,1,1) RETURNING id",
                    (solicitud.cedula, solicitud.nombres_completos, solicitud.telefono, solicitud.correo_electronico, solicitud.fecha_nacimiento, solicitud.nivel_estudios)
                )
                usuario_id = cur.fetchone()[0]

            # Obtener líder de área según área del usuario
            cur.execute("SELECT area_id FROM usuario WHERE id = %s", (usuario_id,))
            area_id = cur.fetchone()[0]
            cur.execute("SELECT id FROM usuario WHERE area_id = %s AND cargo_id = (SELECT id FROM cargo WHERE nombre = 'Líder de área' LIMIT 1) LIMIT 1", (area_id,))
            lider = cur.fetchone()
            if not lider:
                raise HTTPException(status_code=422, detail="No se encontró líder de área para el área del usuario")
            lider_area_id = lider[0]

            # Validar edad > 23 años (repetido para seguridad)
            hoy = date.today()
            edad = hoy.year - solicitud.fecha_nacimiento.year - ((hoy.month, hoy.day) < (solicitud.fecha_nacimiento.month, solicitud.fecha_nacimiento.day))
            if edad <= 23:
                raise HTTPException(status_code=422, detail="La edad debe ser mayor a 23 años")

            # Validar nivel estudios mínimo
            if solicitud.nivel_estudios not in NIVELES_ESTUDIOS_MINIMO:
                raise HTTPException(status_code=422, detail="Nivel de estudios mínimo: bachillerato")

            # Crear solicitud
            cur.execute(
                "INSERT INTO solicitud (usuario_id, lider_area_id) VALUES (%s, %s) RETURNING id, estado",
                (usuario_id, lider_area_id)
            )
            fila = cur.fetchone()
            return {"id": fila[0], "estado": fila[1]}

# --- Rutas administrativas ---

@router_admin.get("/solicitudes", tags=["admin_solicitudes"])
async def listar_solicitudes():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.id, u.cedula, u.nombres_completos, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, a.nombre, c.nombre, s.estado, s.motivo_rechazo, s.fecha_envio, s.fecha_decision, la.nombres_completos, la.cargo_id, la.area_id, la.correo_electronico, s.lider_area_id "
                "FROM solicitud s "
                "JOIN usuario u ON s.usuario_id = u.id "
                "JOIN area a ON u.area_id = a.id "
                "JOIN cargo c ON u.cargo_id = c.id "
                "JOIN usuario la ON s.lider_area_id = la.id "
                "ORDER BY s.fecha_envio DESC"
            )
            filas = cur.fetchall()
            resultados = []
            for f in filas:
                edad = (date.today().year - f[5].year - ((date.today().month, date.today().day) < (f[5].month, f[5].day)))
                resultados.append({
                    "id": f[0],
                    "cedula": f[1],
                    "nombres_completos": f[2],
                    "telefono": f[3],
                    "correo_electronico": f[4],
                    "fecha_nacimiento": f[5].isoformat(),
                    "edad": edad,
                    "nivel_estudios": f[6],
                    "area": f[7],
                    "cargo": f[8],
                    "estado": f[9],
                    "motivo_rechazo": f[10],
                    "fecha_envio": f[11].isoformat() if f[11] else None,
                    "fecha_decision": f[12].isoformat() if f[12] else None,
                    "lider_area_nombre": f[13],
                    "lider_area_correo": f[16],
                })
            return resultados

@router_admin.get("/solicitudes/{solicitud_id}", response_model=SolicitudAprobacionDetalle, tags=["admin_solicitudes"])
async def obtener_solicitud(solicitud_id: int):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT s.id, u.cedula, u.nombres_completos, u.telefono, u.correo_electronico, u.fecha_nacimiento, u.nivel_estudios, a.nombre, c.nombre, s.estado, s.motivo_rechazo, s.fecha_envio, s.fecha_decision, la.id, la.nombres_completos, la.cargo_id, la.area_id, la.correo_electronico "
                "FROM solicitud s "
                "JOIN usuario u ON s.usuario_id = u.id "
                "JOIN area a ON u.area_id = a.id "
                "JOIN cargo c ON u.cargo_id = c.id "
                "JOIN usuario la ON s.lider_area_id = la.id "
                "WHERE s.id = %s",
                (solicitud_id,)
            )
            fila = cur.fetchone()
            if not fila:
                raise HTTPException(status_code=404, detail="Solicitud no encontrada")
            edad = (date.today().year - fila[5].year - ((date.today().month, date.today().day) < (fila[5].month, fila[5].day)))
            lider_cargo = None
            lider_area = None
            # Obtener nombre cargo líder
            cur.execute("SELECT nombre FROM cargo WHERE id = %s", (fila[15],))
            res_cargo = cur.fetchone()
            if res_cargo:
                lider_cargo = res_cargo[0]
            # Obtener nombre área líder
            cur.execute("SELECT nombre FROM area WHERE id = %s", (fila[16],))
            res_area = cur.fetchone()
            if res_area:
                lider_area = res_area[0]
            lider_info = LiderAreaInfo(
                id=fila[13],
                nombre=fila[14],
                cargo=lider_cargo or "",
                area=lider_area or "",
                correo_electronico=fila[17],
                fecha_hora_decision=fila[12]
            )
            solicitud_info = SolicitudDetalleAprobador(
                id=fila[0],
                cedula=fila[1],
                nombres_completos=fila[2],
                telefono=fila[3],
                correo_electronico=fila[4],
                fecha_nacimiento=fila[5],
                edad=edad,
                nivel_estudios=fila[6],
                area=fila[7],
                cargo=fila[8]
            )
            return SolicitudAprobacionDetalle(
                solicitud=solicitud_info,
                lider_area=lider_info,
                estado=fila[9],
                motivo_rechazo=fila[10]
            )

@router_admin.post("/solicitudes/{solicitud_id}/decidir", tags=["admin_solicitudes"])
async def decidir_solicitud(solicitud_id: int, decision: DecidirSolicitud, authorization: str = Header(...)):
    # Obtener id usuario admin desde token o contexto (no definido, se usa dummy 0)
    usuario_admin_id = 0
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            # Obtener solicitud
            cur.execute("SELECT estado FROM solicitud WHERE id = %s", (solicitud_id,))
            fila = cur.fetchone()
            if not fila:
                raise HTTPException(status_code=404, detail="Solicitud no encontrada")
            estado_actual = fila[0]
            if estado_actual != 'Pendiente':
                raise HTTPException(status_code=422, detail="Solo se pueden decidir solicitudes en estado Pendiente")

            if decision.aprobar:
                # Aprobar
                cur.execute(
                    "UPDATE solicitud SET estado='Aprobada', fecha_decision=now(), motivo_rechazo=NULL WHERE id=%s",
                    (solicitud_id,)
                )
                # Insertar trazabilidad
                cur.execute(
                    "INSERT INTO trazabilidad (solicitud_id, usuario_id, accion) VALUES (%s, %s, 'Aprobado')",
                    (solicitud_id, usuario_admin_id)
                )
                # Notificar administrador AD (simulado)
                # Aquí se podría llamar a integración externa
                return {"mensaje": "Solicitud aprobada y administrador de AD notificado"}
            else:
                # Rechazar
                if not decision.motivo_rechazo or decision.motivo_rechazo.strip() == '':
                    raise HTTPException(status_code=422, detail="Motivo de rechazo obligatorio")
                cur.execute(
                    "UPDATE solicitud SET estado='Rechazada', fecha_decision=now(), motivo_rechazo=%s WHERE id=%s",
                    (decision.motivo_rechazo.strip(), solicitud_id)
                )
                cur.execute(
                    "INSERT INTO trazabilidad (solicitud_id, usuario_id, accion, motivo) VALUES (%s, %s, 'Rechazado', %s)",
                    (solicitud_id, usuario_admin_id, decision.motivo_rechazo.strip())
                )
                # Notificar empleado (simulado)
                return {"mensaje": "Solicitud rechazada y empleado notificado"}

app.include_router(router_publico)
app.include_router(router_admin)