-- Esquema inicial para PostgreSQL 16
-- Comentarios breves en español.

BEGIN;

CREATE TABLE IF NOT EXISTS catalogo_estado_solicitud (
    id SMALLSERIAL PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    es_final BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_catalogo_estado_codigo CHECK (codigo ~ '^[A-Z0-9_]+$')
);

CREATE TABLE IF NOT EXISTS flujo_aprobacion (
    id BIGSERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_flujo_aprobacion_codigo CHECK (codigo ~ '^[A-Z0-9_\-]+$')
);

CREATE TABLE IF NOT EXISTS tipo_ausencia (
    id BIGSERIAL PRIMARY KEY,
    codigo VARCHAR(50) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    requiere_motivo BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_horas BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_aprobacion_th BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_aprobacion_jefe BOOLEAN NOT NULL DEFAULT TRUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    flujo_aprobacion_id BIGINT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_tipo_ausencia_codigo CHECK (codigo ~ '^[A-Z0-9_\-]+$')
);

CREATE TABLE IF NOT EXISTS solicitud_ausencia (
    id BIGSERIAL PRIMARY KEY,
    solicitante_nombre VARCHAR(200) NOT NULL,
    solicitante_documento VARCHAR(30) NOT NULL,
    area VARCHAR(120) NOT NULL,
    cargo VARCHAR(120) NOT NULL,
    tipo_ausencia_id BIGINT NOT NULL,
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    hora_inicio TIME,
    hora_fin TIME,
    motivo_observacion TEXT,
    estado_codigo VARCHAR(30) NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    creado_por VARCHAR(120) NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    eliminado_en TIMESTAMPTZ,
    CONSTRAINT fk_solicitud_tipo_ausencia FOREIGN KEY (tipo_ausencia_id) REFERENCES tipo_ausencia(id),
    CONSTRAINT fk_solicitud_estado FOREIGN KEY (estado_codigo) REFERENCES catalogo_estado_solicitud(codigo),
    CONSTRAINT ck_solicitud_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_solicitud_horas CHECK (
        (hora_inicio IS NULL AND hora_fin IS NULL)
        OR (hora_inicio IS NOT NULL AND hora_fin IS NOT NULL AND hora_fin > hora_inicio)
    )
);

CREATE TABLE IF NOT EXISTS historial_solicitud (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id BIGINT NOT NULL,
    estado_codigo VARCHAR(30) NOT NULL,
    accion VARCHAR(30) NOT NULL,
    observacion TEXT,
    actor_usuario VARCHAR(120) NOT NULL,
    actor_rol VARCHAR(60) NOT NULL,
    version_resultante INTEGER NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_historial_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitud_ausencia(id) ON DELETE CASCADE,
    CONSTRAINT fk_historial_estado FOREIGN KEY (estado_codigo) REFERENCES catalogo_estado_solicitud(codigo),
    CONSTRAINT ck_historial_accion CHECK (accion IN ('CREADA', 'ACTUALIZADA', 'APROBADA', 'RECHAZADA', 'VALIDADA', 'CONSULTADA')),
    CONSTRAINT ck_historial_rol CHECK (actor_rol IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO', 'SISTEMA'))
);

CREATE TABLE IF NOT EXISTS revision_solicitud (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id BIGINT NOT NULL,
    secuencia SMALLINT NOT NULL,
    rol_revisor VARCHAR(30) NOT NULL,
    revisor_usuario VARCHAR(120),
    decision VARCHAR(20),
    observacion TEXT,
    version_esperada INTEGER NOT NULL,
    version_real INTEGER,
    decidido_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT fk_revision_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitud_ausencia(id) ON DELETE CASCADE,
    CONSTRAINT uq_revision_solicitud_secuencia UNIQUE (solicitud_id, secuencia),
    CONSTRAINT ck_revision_rol CHECK (rol_revisor IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    CONSTRAINT ck_revision_decision CHECK (decision IS NULL OR decision IN ('PENDIENTE', 'APROBADA', 'RECHAZADA', 'VALIDADA'))
);

CREATE TABLE IF NOT EXISTS notificacion (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id BIGINT,
    destinatario_usuario VARCHAR(120) NOT NULL,
    tipo VARCHAR(40) NOT NULL,
    canal VARCHAR(20) NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    mensaje TEXT NOT NULL,
    estado_envio VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    intentos SMALLINT NOT NULL DEFAULT 0,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    enviado_en TIMESTAMPTZ,
    CONSTRAINT fk_notificacion_solicitud FOREIGN KEY (solicitud_id) REFERENCES solicitud_ausencia(id) ON DELETE SET NULL,
    CONSTRAINT ck_notificacion_tipo CHECK (tipo IN ('CAMBIO_ESTADO', 'PENDIENTE_REVISION')),
    CONSTRAINT ck_notificacion_canal CHECK (canal IN ('CORREO')),
    CONSTRAINT ck_notificacion_estado CHECK (estado_envio IN ('PENDIENTE', 'ENVIADA', 'FALLIDA')),
    CONSTRAINT ck_notificacion_intentos CHECK (intentos >= 0)
);

CREATE TABLE IF NOT EXISTS auditoria_acceso (
    id BIGSERIAL PRIMARY KEY,
    usuario VARCHAR(120) NOT NULL,
    rol VARCHAR(60) NOT NULL,
    accion VARCHAR(80) NOT NULL,
    entidad VARCHAR(80) NOT NULL,
    entidad_id VARCHAR(80),
    detalle JSONB,
    ip INET,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_auditoria_acceso_rol CHECK (rol IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO', 'ADMINISTRADOR', 'SISTEMA'))
);

CREATE TABLE IF NOT EXISTS auditoria_modificacion (
    id BIGSERIAL PRIMARY KEY,
    usuario VARCHAR(120) NOT NULL,
    rol VARCHAR(60) NOT NULL,
    operacion VARCHAR(40) NOT NULL,
    entidad VARCHAR(80) NOT NULL,
    entidad_id VARCHAR(80),
    antes JSONB,
    despues JSONB,
    detalle TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_auditoria_modificacion_rol CHECK (rol IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO', 'ADMINISTRADOR', 'SISTEMA')),
    CONSTRAINT ck_auditoria_modificacion_operacion CHECK (operacion IN ('CREAR', 'ACTUALIZAR', 'APROBAR', 'RECHAZAR', 'VALIDAR', 'ELIMINAR', 'ASIGNAR_FLUJO'))
);

ALTER TABLE tipo_ausencia
    ADD CONSTRAINT fk_tipo_ausencia_flujo
    FOREIGN KEY (flujo_aprobacion_id) REFERENCES flujo_aprobacion(id);

CREATE INDEX IF NOT EXISTS idx_tipo_ausencia_activo_nombre ON tipo_ausencia (activo, nombre);
CREATE INDEX IF NOT EXISTS idx_tipo_ausencia_flujo ON tipo_ausencia (flujo_aprobacion_id);

CREATE INDEX IF NOT EXISTS idx_solicitud_solicitante_estado ON solicitud_ausencia (solicitante_documento, estado_codigo, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_solicitud_tipo_fecha ON solicitud_ausencia (tipo_ausencia_id, fecha_inicio, fecha_fin);
CREATE INDEX IF NOT EXISTS idx_solicitud_estado_fecha ON solicitud_ausencia (estado_codigo, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_solicitud_version ON solicitud_ausencia (id, version);

CREATE INDEX IF NOT EXISTS idx_historial_solicitud_fecha ON historial_solicitud (solicitud_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_historial_actor ON historial_solicitud (actor_usuario, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_revision_pendientes ON revision_solicitud (rol_revisor, decision, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_revision_solicitud ON revision_solicitud (solicitud_id, secuencia);
CREATE INDEX IF NOT EXISTS idx_revision_revisor_estado ON revision_solicitud (revisor_usuario, decision, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_notificacion_destinatario_estado ON notificacion (destinatario_usuario, estado_envio, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_notificacion_solicitud_tipo ON notificacion (solicitud_id, tipo, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_auditoria_acceso_usuario_fecha ON auditoria_acceso (usuario, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_acceso_entidad ON auditoria_acceso (entidad, entidad_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_modificacion_usuario_fecha ON auditoria_modificacion (usuario, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_modificacion_entidad ON auditoria_modificacion (entidad, entidad_id, creado_en DESC);

INSERT INTO catalogo_estado_solicitud (codigo, nombre, es_final, activo)
VALUES
    ('BORRADOR', 'Borrador', FALSE, TRUE),
    ('ENVIADA', 'Enviada', FALSE, TRUE),
    ('EN_REVISION', 'En revisión', FALSE, TRUE),
    ('APROBADA', 'Aprobada', TRUE, TRUE),
    ('RECHAZADA', 'Rechazada', TRUE, TRUE),
    ('VALIDADA', 'Validada', FALSE, TRUE),
    ('CANCELADA', 'Cancelada', TRUE, TRUE)
ON CONFLICT (codigo) DO NOTHING;

COMMIT;