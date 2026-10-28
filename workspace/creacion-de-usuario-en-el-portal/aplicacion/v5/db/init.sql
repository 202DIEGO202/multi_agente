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
CREATE TABLE area (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla de cargos
CREATE TABLE cargo (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) NOT NULL UNIQUE
);

-- Tabla de usuarios (empleados y líderes)
CREATE TABLE usuario (
    id SERIAL PRIMARY KEY,
    cedula VARCHAR(20) NOT NULL UNIQUE,
    nombres VARCHAR(200) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    correo_electronico VARCHAR(200) NOT NULL UNIQUE,
    fecha_nacimiento DATE NOT NULL,
    nivel_estudios nivel_estudios_enum NOT NULL,
    area_id INTEGER NOT NULL REFERENCES area(id) ON DELETE RESTRICT,
    cargo_id INTEGER NOT NULL REFERENCES cargo(id) ON DELETE RESTRICT,
    es_lider BOOLEAN NOT NULL DEFAULT FALSE
);

-- Tabla de solicitudes de creación de usuario
CREATE TABLE solicitud (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    estado estado_solicitud_enum NOT NULL DEFAULT 'Pendiente',
    fecha_decision TIMESTAMP WITH TIME ZONE,
    lider_area_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    motivo_rechazo TEXT,
    CHECK (estado <> 'Rechazada' OR (motivo_rechazo IS NOT NULL AND length(motivo_rechazo) > 0))
);

-- Restricción para validar edad mínima > 23 años al momento de envío
CREATE FUNCTION validar_edad_minima() RETURNS trigger AS $$
DECLARE
    edad INTEGER;
BEGIN
    edad := date_part('year', age(NEW.fecha_nacimiento));
    IF edad <= 23 THEN
        RAISE EXCEPTION 'La edad debe ser mayor a 23 años';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_edad_minima
BEFORE INSERT OR UPDATE ON usuario
FOR EACH ROW EXECUTE FUNCTION validar_edad_minima();

-- Restricción para validar nivel de estudios mínimo Bachillerato
CREATE FUNCTION validar_nivel_estudios() RETURNS trigger AS $$
DECLARE
    niveles_validos nivel_estudios_enum[] := ARRAY['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];
BEGIN
    IF NOT (NEW.nivel_estudios = ANY(niveles_validos)) THEN
        RAISE EXCEPTION 'Nivel de estudios mínimo: bachillerato';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_nivel_estudios
BEFORE INSERT OR UPDATE ON usuario
FOR EACH ROW EXECUTE FUNCTION validar_nivel_estudios();

-- Tabla para registrar acciones de aprobación o rechazo (trazabilidad)
CREATE TABLE accion_aprobacion (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    fecha_accion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobado', 'Rechazado')),
    motivo TEXT
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitud_estado ON solicitud(estado);
CREATE INDEX idx_solicitud_lider_area ON solicitud(lider_area_id);
CREATE INDEX idx_usuario_cedula ON usuario(cedula);
CREATE INDEX idx_usuario_correo ON usuario(correo_electronico);

-- Vista para obtener edad calculada y datos relevantes para aprobación
CREATE VIEW vista_solicitud_detalle AS
SELECT
    s.id AS solicitud_id,
    u.nombres AS solicitante_nombres,
    u.cedula AS solicitante_cedula,
    a.nombre AS area_nombre,
    c.nombre AS cargo_nombre,
    u.fecha_nacimiento,
    date_part('year', age(u.fecha_nacimiento)) AS edad,
    u.nivel_estudios,
    l.nombres AS lider_nombres,
    l.cargo_id AS lider_cargo_id,
    l.correo_electronico AS lider_correo,
    s.estado,
    s.fecha_envio,
    s.fecha_decision,
    s.motivo_rechazo
FROM solicitud s
JOIN usuario u ON s.usuario_id = u.id
JOIN area a ON u.area_id = a.id
JOIN cargo c ON u.cargo_id = c.id
JOIN usuario l ON s.lider_area_id = l.id;

-- Comentarios:
-- 1. La tabla usuario incluye empleados y líderes, diferenciados por es_lider.
-- 2. La solicitud referencia al usuario solicitante y al líder de área asignado.
-- 3. Se validan edad mínima y nivel de estudios mediante triggers.
-- 4. La tabla accion_aprobacion registra aprobaciones y rechazos con trazabilidad.
-- 5. Los índices facilitan búsquedas por estado, líder y datos de usuario.
-- 6. La vista vista_solicitud_detalle facilita la consulta para la pantalla de aprobación.