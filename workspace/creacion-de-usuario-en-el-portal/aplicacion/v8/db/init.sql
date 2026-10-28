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

-- Tabla de usuarios (empleados y líderes)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    cedula VARCHAR(20) NOT NULL UNIQUE,
    nombres VARCHAR(150) NOT NULL,
    telefono VARCHAR(30) NOT NULL,
    correo_electronico VARCHAR(150) NOT NULL UNIQUE,
    fecha_nacimiento DATE NOT NULL,
    nivel_estudios nivel_estudios_enum NOT NULL CHECK (nivel_estudios IN ('Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado')),
    area_id INT NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    cargo VARCHAR(100) NOT NULL,
    es_lider BOOLEAN NOT NULL DEFAULT FALSE
);

-- Tabla de solicitudes de creación de usuario
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    estado estado_solicitud_enum NOT NULL DEFAULT 'Pendiente',
    fecha_decision TIMESTAMP WITH TIME ZONE,
    lider_area_id INT NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    motivo_rechazo TEXT,
    CHECK (
        (estado = 'Rechazada' AND motivo_rechazo IS NOT NULL) OR
        (estado <> 'Rechazada' AND motivo_rechazo IS NULL)
    )
);

-- Restricción para validar edad mayor a 23 años al enviar solicitud
CREATE FUNCTION validar_edad_mayor_23() RETURNS TRIGGER AS $$
BEGIN
    IF (DATE_PART('year', AGE(NEW.fecha_envio, (SELECT fecha_nacimiento FROM usuarios WHERE id = NEW.usuario_id))) <= 23) THEN
        RAISE EXCEPTION 'La edad debe ser mayor a 23 años';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_edad
BEFORE INSERT ON solicitudes
FOR EACH ROW EXECUTE FUNCTION validar_edad_mayor_23();

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado);
CREATE INDEX idx_solicitudes_lider_area ON solicitudes(lider_area_id);
CREATE INDEX idx_usuarios_area ON usuarios(area_id);

-- Tabla para registrar trazabilidad de aprobaciones y rechazos
CREATE TABLE trazabilidad_aprobaciones (
    id SERIAL PRIMARY KEY,
    solicitud_id INT NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    fecha_accion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobado', 'Rechazado')),
    motivo TEXT
);

-- Restricción para que motivo sea obligatorio si acción es 'Rechazado'
ALTER TABLE trazabilidad_aprobaciones ADD CONSTRAINT chk_motivo_rechazo CHECK (
    (accion = 'Rechazado' AND motivo IS NOT NULL AND length(motivo) > 0) OR
    (accion = 'Aprobado' AND motivo IS NULL)
);

-- Validación de nivel de estudios mínimo en usuarios (solo para solicitudes)
-- Se asume que el nivel de estudios en usuarios ya está restringido a mínimo Bachillerato

-- Nota: La validación de nivel de estudios y edad se debe reforzar en la lógica de aplicación,
-- pero se incluye trigger para edad para evitar inserciones inválidas.