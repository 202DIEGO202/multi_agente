-- Creación de tablas para gestión de solicitudes de creación de usuario

-- Tabla de usuarios (empleados y líderes)
CREATE TABLE usuarios (
    id SERIAL PRIMARY KEY,
    cedula VARCHAR(20) UNIQUE NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    telefono VARCHAR(20),
    correo_electronico VARCHAR(100) UNIQUE NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    nivel_estudios VARCHAR(50) NOT NULL,
    area VARCHAR(100),
    cargo VARCHAR(100),
    es_lider BOOLEAN NOT NULL DEFAULT FALSE
);

-- Tabla de estados posibles para solicitudes
CREATE TABLE estados_solicitud (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(50) UNIQUE NOT NULL
);

-- Insertar estados iniciales
INSERT INTO estados_solicitud (nombre) VALUES
('Pendiente'),
('Aprobada'),
('Rechazada');

-- Tabla de solicitudes
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    estado_id INTEGER NOT NULL REFERENCES estados_solicitud(id),
    motivo_rechazo TEXT,
    CONSTRAINT chk_motivo_rechazo CHECK (
        (estado_id = (SELECT id FROM estados_solicitud WHERE nombre = 'Rechazada') AND motivo_rechazo IS NOT NULL AND length(trim(motivo_rechazo)) > 0)
        OR
        (estado_id != (SELECT id FROM estados_solicitud WHERE nombre = 'Rechazada') AND motivo_rechazo IS NULL)
    )
);

-- Tabla de aprobaciones
CREATE TABLE aprobaciones (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    lider_id INTEGER NOT NULL REFERENCES usuarios(id),
    fecha_aprobacion TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    aprobado BOOLEAN NOT NULL,
    motivo_rechazo TEXT,
    CONSTRAINT chk_motivo_rechazo_aprobacion CHECK (
        (aprobado = false AND motivo_rechazo IS NOT NULL AND length(trim(motivo_rechazo)) > 0)
        OR
        (aprobado = true AND motivo_rechazo IS NULL)
    )
);

-- Índices para optimizar consultas frecuentes
CREATE INDEX idx_solicitudes_usuario ON solicitudes(usuario_id);
CREATE INDEX idx_aprobaciones_solicitud ON aprobaciones(solicitud_id);

-- Restricción para validar edad mínima y nivel de estudios en solicitudes
-- Se implementa mediante trigger y función

CREATE OR REPLACE FUNCTION validar_edad_nivel_estudios() RETURNS TRIGGER AS $$
DECLARE
    edad INTEGER;
    nivel_minimo CONSTANT TEXT := 'bachillerato';
    nivel_usuario TEXT;
BEGIN
    -- Calcular edad
    SELECT date_part('year', age(NEW.fecha_nacimiento)) INTO edad FROM usuarios WHERE id = NEW.usuario_id;
    -- Obtener nivel de estudios
    SELECT nivel_estudios INTO nivel_usuario FROM usuarios WHERE id = NEW.usuario_id;

    IF edad <= 23 THEN
        RAISE EXCEPTION 'La edad debe ser mayor a 23 años';
    END IF;

    -- Validar nivel de estudios mínimo (asumiendo orden alfabético para ejemplo, se puede mejorar)
    IF lower(nivel_usuario) NOT IN ('bachillerato', 'tecnico', 'tecnologo', 'profesional', 'especializacion', 'maestria', 'doctorado') THEN
        RAISE EXCEPTION 'Nivel de estudios mínimo: bachillerato';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_validar_edad_nivel_estudios
BEFORE INSERT ON solicitudes
FOR EACH ROW EXECUTE FUNCTION validar_edad_nivel_estudios();

-- Datos semilla de usuarios ficticios
INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area, cargo, es_lider) VALUES
('1234567890', 'Juan Pérez', '3001234567', 'juan.perez@empresa.com', '1985-05-20', 'profesional', 'Tecnología', 'Analista', false),
('0987654321', 'Ana Gómez', '3007654321', 'ana.gomez@empresa.com', '1980-03-15', 'maestria', 'Tecnología', 'Líder de Área', true);

-- Insertar una solicitud de ejemplo
INSERT INTO solicitudes (usuario_id, estado_id) VALUES
(1, (SELECT id FROM estados_solicitud WHERE nombre = 'Pendiente'));

-- Insertar una aprobación de ejemplo (pendiente, sin aprobación aún)
-- No se inserta hasta que líder apruebe o rechace