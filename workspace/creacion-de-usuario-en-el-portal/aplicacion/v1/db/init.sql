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
CREATE TABLE estados (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(20) UNIQUE NOT NULL
);

-- Insertar estados iniciales
INSERT INTO estados (nombre) VALUES
('Pendiente'),
('Aprobada'),
('Rechazada');

-- Tabla de solicitudes
CREATE TABLE solicitudes (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha_envio TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    estado_id INTEGER NOT NULL REFERENCES estados(id),
    nivel_estudios VARCHAR(50) NOT NULL,
    fecha_nacimiento DATE NOT NULL,
    cedula VARCHAR(20) NOT NULL,
    nombres VARCHAR(100) NOT NULL,
    telefono VARCHAR(20),
    correo_electronico VARCHAR(100) NOT NULL,
    CONSTRAINT chk_edad CHECK (DATE_PART('year', AGE(fecha_nacimiento)) > 23),
    CONSTRAINT chk_nivel_estudios CHECK (nivel_estudios IN ('Bachillerato', 'Tecnico', 'Tecnologo', 'Profesional', 'Especializacion', 'Maestria', 'Doctorado'))
);

-- Tabla de aprobaciones y rechazos
CREATE TABLE aprobaciones (
    id SERIAL PRIMARY KEY,
    solicitud_id INTEGER NOT NULL REFERENCES solicitudes(id) ON DELETE CASCADE,
    aprobador_id INTEGER NOT NULL REFERENCES usuarios(id),
    fecha TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    aprobado BOOLEAN NOT NULL,
    motivo_rechazo TEXT
);

-- Índices para optimizar consultas frecuentes
CREATE INDEX idx_solicitudes_usuario_id ON solicitudes(usuario_id);
CREATE INDEX idx_aprobaciones_solicitud_id ON aprobaciones(solicitud_id);

-- Datos semilla de usuarios ficticios
INSERT INTO usuarios (cedula, nombres, telefono, correo_electronico, fecha_nacimiento, nivel_estudios, area, cargo, es_lider) VALUES
('1234567890', 'Juan Perez', '3001234567', 'juan.perez@empresa.com', '1980-05-15', 'Profesional', 'Finanzas', 'Analista', FALSE),
('0987654321', 'Maria Gomez', '3007654321', 'maria.gomez@empresa.com', '1975-08-20', 'Maestria', 'Finanzas', 'Lider de Area', TRUE);

-- Insertar solicitudes de ejemplo
INSERT INTO solicitudes (usuario_id, estado_id, nivel_estudios, fecha_nacimiento, cedula, nombres, telefono, correo_electronico) VALUES
(1, 1, 'Profesional', '1980-05-15', '1234567890', 'Juan Perez', '3001234567', 'juan.perez@empresa.com');

-- Insertar aprobación ejemplo
INSERT INTO aprobaciones (solicitud_id, aprobador_id, aprobado) VALUES
(1, 2, TRUE);

-- Comentarios:
-- La validación de edad y nivel de estudios se realiza con restricciones CHECK.
-- El motivo de rechazo es obligatorio solo si aprobado = FALSE, se debe validar en la lógica de aplicación.
-- La tabla usuarios incluye campo es_lider para distinguir roles.