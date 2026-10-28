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
    area_id INT NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    cargo_id INT NOT NULL REFERENCES cargos(id) ON DELETE RESTRICT
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

-- Tabla de trazabilidad de acciones sobre solicitudes
CREATE TABLE trazabilidad_solicitudes (
    id SERIAL PRIMARY KEY,
    solicitud_id INT NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobar', 'Rechazar')),
    fecha_accion TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    motivo TEXT
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitudes_usuario_id ON solicitudes(usuario_id);
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado);
CREATE INDEX idx_solicitudes_lider_area_id ON solicitudes(lider_area_id);

-- Función para validar edad mínima 23 años
CREATE OR REPLACE FUNCTION validar_edad_minima(fecha_nacimiento DATE) RETURNS BOOLEAN AS $$
DECLARE
    edad INT;
BEGIN
    edad := DATE_PART('year', AGE(CURRENT_DATE, fecha_nacimiento));
    RETURN edad > 23;
END;
$$ LANGUAGE plpgsql;

-- Restricción para validar edad mínima en tabla usuarios
ALTER TABLE usuarios ADD CONSTRAINT chk_edad_minima CHECK (validar_edad_minima(fecha_nacimiento));

-- Restricción para validar nivel de estudios mínimo bachillerato en tabla usuarios
ALTER TABLE usuarios ADD CONSTRAINT chk_nivel_estudios_minimo CHECK (
    nivel_estudios IN ('Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado')
);

-- Nota: La validación de edad y nivel de estudios también debe realizarse en la capa de aplicación para mensajes de error claros.