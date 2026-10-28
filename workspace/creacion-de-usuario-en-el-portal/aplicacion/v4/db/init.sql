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
    nombres_completos VARCHAR(200) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    correo_electronico VARCHAR(200) NOT NULL UNIQUE,
    fecha_nacimiento DATE NOT NULL,
    nivel_estudios nivel_estudios_enum NOT NULL CHECK (nivel_estudios IN ('Primaria', 'Secundaria', 'Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado')),
    area_id INTEGER NOT NULL REFERENCES area(id) ON DELETE RESTRICT,
    cargo_id INTEGER NOT NULL REFERENCES cargo(id) ON DELETE RESTRICT
);

-- Tabla de solicitudes de creación de usuario
CREATE TABLE solicitud (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    estado estado_solicitud_enum NOT NULL DEFAULT 'Pendiente',
    motivo_rechazo TEXT,
    fecha_decision TIMESTAMP WITH TIME ZONE,
    lider_area_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    CONSTRAINT chk_motivo_rechazo CHECK (
        (estado = 'Rechazada' AND motivo_rechazo IS NOT NULL AND length(trim(motivo_rechazo)) > 0) OR
        (estado <> 'Rechazada' AND motivo_rechazo IS NULL)
    )
);

-- Restricción para validar edad mínima > 23 años al enviar solicitud
CREATE FUNCTION validar_edad_minima() RETURNS trigger AS $$
DECLARE
    edad INTEGER;
BEGIN
    edad := date_part('year', age(NEW.fecha_envio, (SELECT fecha_nacimiento FROM usuario WHERE id = NEW.usuario_id)));
    IF edad <= 23 THEN
        RAISE EXCEPTION 'La edad debe ser mayor a 23 años';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_edad_minima
BEFORE INSERT ON solicitud
FOR EACH ROW EXECUTE FUNCTION validar_edad_minima();

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitud_usuario_id ON solicitud(usuario_id);
CREATE INDEX idx_solicitud_estado ON solicitud(estado);
CREATE INDEX idx_usuario_area ON usuario(area_id);

-- Tabla para registro de acciones de aprobación/rechazo (trazabilidad)
CREATE TABLE trazabilidad (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE RESTRICT,
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobado', 'Rechazado')),
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    motivo TEXT
);

-- Restricción para nivel de estudios mínimo bachillerato en usuario solicitante
CREATE FUNCTION validar_nivel_estudios_minimo() RETURNS trigger AS $$
BEGIN
    IF NEW.nivel_estudios NOT IN ('Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado') THEN
        RAISE EXCEPTION 'Nivel de estudios mínimo: bachillerato';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_nivel_estudios_minimo
BEFORE INSERT OR UPDATE ON usuario
FOR EACH ROW EXECUTE FUNCTION validar_nivel_estudios_minimo();

-- Nota: La validación de edad se realiza al crear la solicitud, la validación de nivel de estudios al crear o actualizar usuario.

-- Para garantizar que el líder de área asignado sea el correcto según el área del empleado, se debe gestionar en la lógica de aplicación.

-- Fin del esquema