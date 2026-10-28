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
    CHECK (estado <> 'Rechazada' OR (motivo_rechazo IS NOT NULL AND length(motivo_rechazo) > 0)),
    CHECK (estado = 'Rechazada' OR motivo_rechazo IS NULL)
);

-- Restricción para validar edad mínima > 23 años
CREATE FUNCTION validar_edad_minima() RETURNS trigger AS $$
BEGIN
    IF (DATE_PART('year', AGE(NEW.fecha_nacimiento)) <= 23) THEN
        RAISE EXCEPTION 'La edad debe ser mayor a 23 años';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_edad_minima
BEFORE INSERT OR UPDATE ON usuario
FOR EACH ROW EXECUTE FUNCTION validar_edad_minima();

-- Restricción para validar nivel de estudios mínimo Bachillerato
CREATE FUNCTION validar_nivel_estudios_minimo() RETURNS trigger AS $$
DECLARE
    niveles_validos nivel_estudios_enum[] := ARRAY['Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado'];
BEGIN
    IF NOT (NEW.nivel_estudios = ANY(niveles_validos)) THEN
        RAISE EXCEPTION 'Nivel de estudios mínimo: bachillerato';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_nivel_estudios_minimo
BEFORE INSERT OR UPDATE ON usuario
FOR EACH ROW EXECUTE FUNCTION validar_nivel_estudios_minimo();

-- Tabla de trazabilidad de acciones de aprobación/rechazo
CREATE TABLE trazabilidad (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobado', 'Rechazado')),
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    motivo TEXT
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitud_estado ON solicitud(estado);
CREATE INDEX idx_solicitud_usuario ON solicitud(usuario_id);
CREATE INDEX idx_trazabilidad_solicitud ON trazabilidad(solicitud_id);

-- Vista para obtener edad calculada y datos completos del solicitante
CREATE VIEW vista_solicitud_detalle AS
SELECT
    s.id AS solicitud_id,
    u.cedula,
    u.nombres,
    u.telefono,
    u.correo_electronico,
    u.fecha_nacimiento,
    DATE_PART('year', AGE(u.fecha_nacimiento))::INT AS edad,
    u.nivel_estudios,
    a.nombre AS area,
    c.nombre AS cargo,
    s.estado,
    s.fecha_envio,
    s.fecha_decision,
    s.motivo_rechazo,
    l.id AS lider_id,
    l.nombres AS lider_nombres,
    l.correo_electronico AS lider_correo,
    lc.nombre AS lider_cargo,
    la.nombre AS lider_area
FROM solicitud s
JOIN usuario u ON s.usuario_id = u.id
JOIN area a ON u.area_id = a.id
JOIN cargo c ON u.cargo_id = c.id
JOIN usuario l ON s.lider_area_id = l.id
JOIN cargo lc ON l.cargo_id = lc.id
JOIN area la ON l.area_id = la.id;

-- Nota: La creación y activación manual de cuentas en Active Directory se gestiona fuera de la base de datos.