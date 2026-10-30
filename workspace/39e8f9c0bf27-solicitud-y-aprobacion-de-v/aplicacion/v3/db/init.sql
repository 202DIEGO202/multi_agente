-- Esquema inicial para PostgreSQL 16
-- Comentarios breves en español.

BEGIN;

CREATE SCHEMA IF NOT EXISTS vacaciones;
SET search_path TO vacaciones, public;

-- Catálogo de estados del flujo de solicitudes
CREATE TABLE estado_solicitud (
    id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(60) NOT NULL UNIQUE,
    es_terminal BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_estado_solicitud_codigo CHECK (codigo IN (
        'borrador',
        'enviada',
        'en_revision_jefe',
        'en_revision_th',
        'aprobada',
        'rechazada',
        'cancelada'
    ))
);

CREATE TABLE tipo_ausencia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    requiere_motivo BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_horas BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_revision_jefe BOOLEAN NOT NULL DEFAULT TRUE,
    requiere_revision_th BOOLEAN NOT NULL DEFAULT FALSE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_tipo_ausencia_codigo CHECK (codigo ~ '^[A-Z0-9_\-]{2,30}$')
);

CREATE TABLE flujo_aprobacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_ausencia_id BIGINT NOT NULL REFERENCES tipo_ausencia(id) ON DELETE CASCADE,
    secuencia SMALLINT NOT NULL,
    rol_aprobador VARCHAR(20) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_flujo_tipo_secuencia UNIQUE (tipo_ausencia_id, secuencia),
    CONSTRAINT ck_flujo_rol CHECK (rol_aprobador IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    CONSTRAINT ck_flujo_secuencia CHECK (secuencia > 0)
);

CREATE TABLE solicitud (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitante_id BIGINT NOT NULL,
    tipo_ausencia_id BIGINT NOT NULL REFERENCES tipo_ausencia(id),
    estado_id SMALLINT NOT NULL REFERENCES estado_solicitud(id),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    hora_inicio TIME,
    hora_fin TIME,
    motivo TEXT,
    observacion TEXT,
    formato_oficial BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    cancelado_en TIMESTAMPTZ,
    CONSTRAINT ck_solicitud_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_solicitud_horas CHECK (
        (hora_inicio IS NULL AND hora_fin IS NULL)
        OR (hora_inicio IS NOT NULL AND hora_fin IS NOT NULL AND hora_fin > hora_inicio)
    )
);

CREATE TABLE solicitud_historial (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    estado_id SMALLINT NOT NULL REFERENCES estado_solicitud(id),
    actor_id BIGINT NOT NULL,
    actor_rol VARCHAR(20) NOT NULL,
    observacion TEXT,
    detalle JSONB NOT NULL DEFAULT '{}'::jsonb,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_historial_actor_rol CHECK (actor_rol IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO', 'SISTEMA'))
);

CREATE TABLE solicitud_revision (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    secuencia SMALLINT NOT NULL,
    revisor_id BIGINT NOT NULL,
    revisor_rol VARCHAR(20) NOT NULL,
    decision VARCHAR(20),
    observacion TEXT,
    version_objetivo INTEGER NOT NULL,
    decidido_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_solicitud_revision UNIQUE (solicitud_id, secuencia),
    CONSTRAINT ck_revision_rol CHECK (revisor_rol IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    CONSTRAINT ck_revision_decision CHECK (decision IS NULL OR decision IN ('APROBADA', 'RECHAZADA', 'VALIDADA')),
    CONSTRAINT ck_revision_secuencia CHECK (secuencia > 0)
);

CREATE TABLE solicitud_version (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    snapshot JSONB NOT NULL,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_solicitud_version UNIQUE (solicitud_id, numero),
    CONSTRAINT ck_solicitud_version_numero CHECK (numero > 0)
);

CREATE TABLE notificacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT REFERENCES solicitud(id) ON DELETE CASCADE,
    destinatario_id BIGINT NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    canal VARCHAR(20) NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    cuerpo TEXT NOT NULL,
    estado VARCHAR(20) NOT NULL DEFAULT 'PENDIENTE',
    enviado_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_notificacion_tipo CHECK (tipo IN ('CAMBIO_ESTADO', 'PENDIENTE_REVISION', 'SISTEMA')),
    CONSTRAINT ck_notificacion_canal CHECK (canal IN ('CORREO', 'WEB')),
    CONSTRAINT ck_notificacion_estado CHECK (estado IN ('PENDIENTE', 'ENVIADA', 'ERROR'))
);

CREATE TABLE auditoria_acceso (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id BIGINT NOT NULL,
    actor_rol VARCHAR(20) NOT NULL,
    recurso VARCHAR(80) NOT NULL,
    operacion VARCHAR(40) NOT NULL,
    recurso_id BIGINT,
    ip INET,
    user_agent TEXT,
    exito BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_auditoria_acceso_rol CHECK (actor_rol IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO', 'SISTEMA'))
);

CREATE TABLE auditoria_modificacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id BIGINT NOT NULL,
    actor_rol VARCHAR(20) NOT NULL,
    entidad VARCHAR(80) NOT NULL,
    entidad_id BIGINT,
    operacion VARCHAR(40) NOT NULL,
    antes JSONB,
    despues JSONB,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_auditoria_modificacion_rol CHECK (actor_rol IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO', 'SISTEMA'))
);

-- Índices para búsquedas frecuentes
CREATE INDEX idx_solicitud_solicitante_estado_fecha ON solicitud (solicitante_id, estado_id, creado_en DESC);
CREATE INDEX idx_solicitud_tipo_estado ON solicitud (tipo_ausencia_id, estado_id);
CREATE INDEX idx_solicitud_historial_solicitud_fecha ON solicitud_historial (solicitud_id, creado_en DESC);
CREATE INDEX idx_solicitud_revision_version ON solicitud_revision (solicitud_id, version_objetivo, secuencia);
CREATE INDEX idx_notificacion_destinatario_estado ON notificacion (destinatario_id, estado, creado_en DESC);
CREATE INDEX idx_auditoria_acceso_actor_fecha ON auditoria_acceso (actor_id, creado_en DESC);
CREATE INDEX idx_auditoria_modificacion_entidad_fecha ON auditoria_modificacion (entidad, entidad_id, creado_en DESC);

COMMIT;