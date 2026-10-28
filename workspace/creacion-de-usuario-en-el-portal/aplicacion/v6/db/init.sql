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
    nivel_estudios nivel_estudios_enum NOT NULL,
    area_id INTEGER NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    cargo VARCHAR(100) NOT NULL,
    es_lider BOOLEAN NOT NULL DEFAULT FALSE
);

-- Tabla de solicitudes de creación de usuario
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    estado estado_solicitud_enum NOT NULL DEFAULT 'Pendiente',
    fecha_decision TIMESTAMP WITH TIME ZONE,
    lider_area_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    motivo_rechazo TEXT,
    CONSTRAINT chk_motivo_rechazo CHECK (
        (estado = 'Rechazada' AND motivo_rechazo IS NOT NULL AND length(trim(motivo_rechazo)) > 0) OR
        (estado <> 'Rechazada' AND motivo_rechazo IS NULL)
    )
);

-- Tabla de trazabilidad de acciones sobre solicitudes
CREATE TABLE trazabilidad_solicitudes (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobar', 'Rechazar')),
    fecha_accion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    motivo TEXT
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado);
CREATE INDEX idx_solicitudes_lider_area ON solicitudes(lider_area_id);
CREATE INDEX idx_usuarios_area ON usuarios(area_id);

-- Restricciones de negocio
-- Validar edad mínima 24 años (mayor a 23) al enviar solicitud
-- Se implementará en la aplicación, pero se agrega función para validación en base si se desea

-- Función para calcular edad
CREATE OR REPLACE FUNCTION calcular_edad(fecha_nacimiento DATE) RETURNS INTEGER AS $$
BEGIN
    RETURN date_part('year', age(current_date, fecha_nacimiento));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Restricción para nivel de estudios mínimo Bachillerato
-- Se implementa en la aplicación, pero se puede validar con trigger si se desea

-- Nota: La creación y activación de cuentas en Active Directory es manual y fuera de esta base.

-- Fin del esquema