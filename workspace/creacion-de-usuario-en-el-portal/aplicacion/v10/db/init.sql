-- Esquema para gestión de solicitudes de creación de usuario corporativo

-- Catálogo de niveles de estudios permitidos
CREATE TYPE nivel_estudios_enum AS ENUM (
    'Primaria',
    'Secundaria',
    'Bachillerato',
    'Técnico',
    'Tecnológico',
    'Universitario',
    'Posgrado'
);

-- Catálogo de estados de solicitud
CREATE TYPE estado_solicitud_enum AS ENUM (
    'Pendiente',
    'Aprobada',
    'Rechazada'
);

-- Tabla de áreas
CREATE TABLE areas (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla de cargos
CREATE TABLE cargos (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla de usuarios (empleados y líderes)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    cedula VARCHAR(20) NOT NULL UNIQUE,
    nombres_completos VARCHAR(200) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    correo_electronico VARCHAR(200) NOT NULL UNIQUE,
    fecha_nacimiento DATE NOT NULL,
    nivel_estudios nivel_estudios_enum NOT NULL CHECK (nivel_estudios IN ('Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado')),
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    cargo_id INTEGER NOT NULL REFERENCES cargos(id) ON DELETE RESTRICT
);

-- Tabla de solicitudes de creación de usuario
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    estado estado_solicitud_enum NOT NULL DEFAULT 'Pendiente',
    motivo_rechazo TEXT,
    fecha_decision TIMESTAMP WITH TIME ZONE,
    lider_area_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    CONSTRAINT chk_motivo_rechazo CHECK (
        (estado = 'Rechazada' AND motivo_rechazo IS NOT NULL AND length(trim(motivo_rechazo)) > 0) OR
        (estado IN ('Pendiente', 'Aprobada') AND motivo_rechazo IS NULL)
    )
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitudes_usuario_id ON solicitudes(usuario_id);
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado);
CREATE INDEX idx_solicitudes_lider_area_id ON solicitudes(lider_area_id);

-- Tabla de trazabilidad de acciones sobre solicitudes
CREATE TABLE trazabilidad_solicitudes (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    fecha_accion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobado', 'Rechazado')),
    motivo TEXT
);

-- Restricción para validar edad mínima (mayor a 23 años) al insertar o actualizar solicitudes
CREATE FUNCTION validar_edad_minima() RETURNS TRIGGER AS $$
DECLARE
    edad INTEGER;
BEGIN
    SELECT date_part('year', age(current_date, u.fecha_nacimiento)) INTO edad
    FROM usuarios u WHERE u.id = NEW.usuario_id;
    IF edad <= 23 THEN
        RAISE EXCEPTION 'La edad debe ser mayor a 23 años';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_edad_minima
BEFORE INSERT OR UPDATE ON solicitudes
FOR EACH ROW EXECUTE FUNCTION validar_edad_minima();

-- Restricción para validar nivel de estudios mínimo en usuarios
-- Ya está controlado por CHECK en la tabla usuarios

-- Nota: La creación y activación de cuentas en Active Directory es manual y no se automatiza en esta base.

-- Usuarios líderes de área deben estar en la tabla usuarios con su área y cargo correspondiente.

-- Se asume que el líder de área es asignado según el área del usuario solicitante.

-- Fin del esquema