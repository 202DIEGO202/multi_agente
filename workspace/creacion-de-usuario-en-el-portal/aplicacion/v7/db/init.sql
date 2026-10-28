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
    area_id INT NOT NULL REFERENCES areas(id) ON DELETE RESTRICT,
    cargo_id INT NOT NULL REFERENCES cargos(id) ON DELETE RESTRICT,
    es_lider BOOLEAN NOT NULL DEFAULT FALSE
);

-- Tabla de solicitudes de creación de usuario
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    nivel_estudios nivel_estudios_enum NOT NULL,
    estado estado_solicitud_enum NOT NULL DEFAULT 'Pendiente',
    fecha_decision TIMESTAMP WITH TIME ZONE,
    lider_area_id INT NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    motivo_rechazo TEXT,
    CHECK (nivel_estudios IN ('Bachillerato', 'Técnico', 'Tecnológico', 'Universitario', 'Posgrado')),
    CHECK (motivo_rechazo IS NOT NULL OR estado != 'Rechazada'),
    CHECK (fecha_nacimiento_valida(usuario_id))
);

-- Función para validar edad mayor a 23 años
CREATE OR REPLACE FUNCTION edad_mayor_23(fecha_nac DATE) RETURNS BOOLEAN AS $$
DECLARE
    edad INT;
BEGIN
    edad := DATE_PART('year', AGE(CURRENT_DATE, fecha_nac));
    RETURN edad > 23;
END;
$$ LANGUAGE plpgsql;

-- Función para validar fecha de nacimiento del usuario en solicitudes
CREATE OR REPLACE FUNCTION fecha_nacimiento_valida(uid INT) RETURNS BOOLEAN AS $$
DECLARE
    fn DATE;
BEGIN
    SELECT fecha_nacimiento INTO fn FROM usuarios WHERE id = uid;
    IF fn IS NULL THEN
        RETURN FALSE;
    END IF;
    RETURN edad_mayor_23(fn);
END;
$$ LANGUAGE plpgsql;

-- Tabla de trazabilidad de acciones de aprobación/rechazo
CREATE TABLE trazabilidad (
    id SERIAL PRIMARY KEY,
    solicitud_id INT NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    usuario_id INT NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    accion VARCHAR(20) NOT NULL CHECK (accion IN ('Aprobado', 'Rechazado')),
    fecha TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
    motivo TEXT
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitudes_estado ON solicitudes(estado);
CREATE INDEX idx_solicitudes_lider ON solicitudes(lider_area_id);
CREATE INDEX idx_trazabilidad_solicitud ON trazabilidad(solicitud_id);
CREATE INDEX idx_usuarios_area ON usuarios(area_id);

-- Restricción para que no se cree ni active cuenta sin aprobación
-- Esto se controla a nivel aplicación, pero se puede reforzar con trigger si se desea

-- Nota: Validaciones de edad y nivel de estudios se aplican en la aplicación y en la base con CHECK y funciones

-- Fin del esquema