-- Esquema inicial para PostgreSQL 16
-- Comentarios breves en español.

BEGIN;

CREATE SCHEMA IF NOT EXISTS vacaciones;
SET search_path TO vacaciones, public;

-- Catálogo de estados para solicitudes y decisiones
CREATE TABLE IF NOT EXISTS solicitud_estado (
    id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL,
    es_final BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_solicitud_estado_codigo CHECK (codigo IN (
        'borrador',
        'enviada',
        'en_revision',
        'aprobada_jefe',
        'aprobada_th',
        'rechazada_jefe',
        'rechazada_th',
        'cancelada'
    ))
);

CREATE TABLE IF NOT EXISTS rol_aprobador (
    id SMALLINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT ck_rol_aprobador_codigo CHECK (codigo IN (
        'jefe_inmediato',
        'talento_humano'
    ))
);

CREATE TABLE IF NOT EXISTS tipo_ausencia (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    requiere_motivo BOOLEAN NOT NULL DEFAULT FALSE,
    permite_horas BOOLEAN NOT NULL DEFAULT FALSE,
    estado VARCHAR(15) NOT NULL,
    activo BOOLEAN GENERATED ALWAYS AS (estado = 'activo') STORED,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_tipo_ausencia_estado CHECK (estado IN ('activo', 'inactivo')),
    CONSTRAINT ck_tipo_ausencia_nombre CHECK (btrim(nombre) <> ''),
    CONSTRAINT ck_tipo_ausencia_codigo CHECK (btrim(codigo) <> '')
);

CREATE TABLE IF NOT EXISTS flujo_aprobacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tipo_ausencia_id BIGINT NOT NULL UNIQUE REFERENCES tipo_ausencia(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_flujo_aprobacion_version CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS flujo_aprobacion_paso (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    flujo_aprobacion_id BIGINT NOT NULL REFERENCES flujo_aprobacion(id) ON DELETE CASCADE,
    orden SMALLINT NOT NULL,
    rol_aprobador_id SMALLINT NOT NULL REFERENCES rol_aprobador(id),
    obligatorio BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_flujo_paso UNIQUE (flujo_aprobacion_id, orden),
    CONSTRAINT ck_flujo_paso_orden CHECK (orden > 0)
);

CREATE TABLE IF NOT EXISTS solicitud (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo VARCHAR(40) NOT NULL UNIQUE,
    solicitante_id BIGINT NOT NULL,
    solicitante_nombre VARCHAR(160) NOT NULL,
    solicitante_documento VARCHAR(40) NOT NULL,
    solicitante_area VARCHAR(120) NOT NULL,
    solicitante_cargo VARCHAR(120) NOT NULL,
    tipo_ausencia_id BIGINT NOT NULL REFERENCES tipo_ausencia(id),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    hora_inicio TIME,
    hora_fin TIME,
    motivo_observacion TEXT,
    estado_id SMALLINT NOT NULL REFERENCES solicitud_estado(id),
    version INTEGER NOT NULL DEFAULT 1,
    enviada_en TIMESTAMPTZ,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actualizada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cancelada_en TIMESTAMPTZ,
    CONSTRAINT ck_solicitud_fechas CHECK (fecha_fin >= fecha_inicio),
    CONSTRAINT ck_solicitud_horas CHECK (
        (hora_inicio IS NULL AND hora_fin IS NULL)
        OR (hora_inicio IS NOT NULL AND hora_fin IS NOT NULL AND hora_fin > hora_inicio)
    ),
    CONSTRAINT ck_solicitud_motivo CHECK (motivo_observacion IS NULL OR btrim(motivo_observacion) <> ''),
    CONSTRAINT ck_solicitud_version CHECK (version > 0)
);

CREATE TABLE IF NOT EXISTS solicitud_historico (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    estado_id SMALLINT NOT NULL REFERENCES solicitud_estado(id),
    actor_id BIGINT,
    actor_nombre VARCHAR(160),
    accion VARCHAR(40) NOT NULL,
    observacion TEXT,
    version_anterior INTEGER,
    version_nueva INTEGER,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_solicitud_historico_accion CHECK (accion IN (
        'creacion',
        'envio',
        'aprobacion',
        'rechazo',
        'validacion',
        'cancelacion',
        'actualizacion'
    )),
    CONSTRAINT ck_solicitud_historico_observacion CHECK (observacion IS NULL OR btrim(observacion) <> ''),
    CONSTRAINT ck_solicitud_historico_version CHECK (
        (version_anterior IS NULL AND version_nueva IS NULL)
        OR (version_anterior IS NOT NULL AND version_nueva IS NOT NULL AND version_nueva > 0)
    )
);

CREATE TABLE IF NOT EXISTS revision_solicitud (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES solicitud(id) ON DELETE CASCADE,
    paso_orden SMALLINT NOT NULL,
    rol_aprobador_id SMALLINT NOT NULL REFERENCES rol_aprobador(id),
    aprobador_id BIGINT,
    aprobador_nombre VARCHAR(160),
    estado VARCHAR(20) NOT NULL,
    observacion TEXT,
    version_objetivo INTEGER NOT NULL,
    resuelta_en TIMESTAMPTZ,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_revision_solicitud UNIQUE (solicitud_id, paso_orden),
    CONSTRAINT ck_revision_estado CHECK (estado IN ('pendiente', 'aprobada', 'rechazada', 'validada')),
    CONSTRAINT ck_revision_observacion CHECK (observacion IS NULL OR btrim(observacion) <> ''),
    CONSTRAINT ck_revision_paso CHECK (paso_orden > 0),
    CONSTRAINT ck_revision_version CHECK (version_objetivo > 0)
);

CREATE TABLE IF NOT EXISTS notificacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id BIGINT REFERENCES solicitud(id) ON DELETE CASCADE,
    destinatario_id BIGINT NOT NULL,
    destinatario_tipo VARCHAR(20) NOT NULL,
    tipo VARCHAR(30) NOT NULL,
    titulo VARCHAR(160) NOT NULL,
    cuerpo TEXT NOT NULL,
    estado_envio VARCHAR(20) NOT NULL,
    creada_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    enviada_en TIMESTAMPTZ,
    leida_en TIMESTAMPTZ,
    CONSTRAINT ck_notificacion_destinatario_tipo CHECK (destinatario_tipo IN ('empleado', 'aprobador', 'th')),
    CONSTRAINT ck_notificacion_tipo CHECK (tipo IN ('cambio_estado', 'pendiente_revision', 'sistema')),
    CONSTRAINT ck_notificacion_estado_envio CHECK (estado_envio IN ('pendiente', 'enviada', 'fallida', 'leida')),
    CONSTRAINT ck_notificacion_titulo CHECK (btrim(titulo) <> ''),
    CONSTRAINT ck_notificacion_cuerpo CHECK (btrim(cuerpo) <> '')
);

CREATE TABLE IF NOT EXISTS auditoria_acceso (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id BIGINT,
    actor_nombre VARCHAR(160),
    actor_rol VARCHAR(30) NOT NULL,
    aplicacion VARCHAR(20) NOT NULL,
    recurso VARCHAR(120) NOT NULL,
    operacion VARCHAR(40) NOT NULL,
    exito BOOLEAN NOT NULL DEFAULT TRUE,
    ip_origen INET,
    detalle TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_auditoria_acceso_aplicacion CHECK (aplicacion IN ('portal', 'panel')),
    CONSTRAINT ck_auditoria_acceso_rol CHECK (actor_rol IN ('empleado', 'jefe_inmediato', 'talento_humano', 'sistema')),
    CONSTRAINT ck_auditoria_acceso_operacion CHECK (btrim(operacion) <> ''),
    CONSTRAINT ck_auditoria_acceso_recurso CHECK (btrim(recurso) <> '')
);

CREATE TABLE IF NOT EXISTS auditoria_modificacion (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id BIGINT,
    actor_nombre VARCHAR(160),
    actor_rol VARCHAR(30) NOT NULL,
    entidad VARCHAR(80) NOT NULL,
    entidad_id BIGINT,
    operacion VARCHAR(40) NOT NULL,
    datos_antes JSONB,
    datos_despues JSONB,
    observacion TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT ck_auditoria_modificacion_rol CHECK (actor_rol IN ('empleado', 'jefe_inmediato', 'talento_humano', 'sistema')),
    CONSTRAINT ck_auditoria_modificacion_operacion CHECK (operacion IN ('insertar', 'actualizar', 'eliminar', 'aprobar', 'rechazar', 'validar', 'consultar')),
    CONSTRAINT ck_auditoria_modificacion_observacion CHECK (observacion IS NULL OR btrim(observacion) <> '')
);

-- Índices para búsquedas frecuentes
CREATE INDEX IF NOT EXISTS idx_solicitud_solicitante_estado_fecha ON solicitud (solicitante_id, estado_id, fecha_inicio DESC);
CREATE INDEX IF NOT EXISTS idx_solicitud_tipo_fecha ON solicitud (tipo_ausencia_id, fecha_inicio DESC);
CREATE INDEX IF NOT EXISTS idx_solicitud_estado_creada ON solicitud (estado_id, creada_en DESC);
CREATE INDEX IF NOT EXISTS idx_solicitud_historico_solicitud_fecha ON solicitud_historico (solicitud_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_revision_pendiente ON revision_solicitud (rol_aprobador_id, estado, creada_en DESC) WHERE estado = 'pendiente';
CREATE INDEX IF NOT EXISTS idx_revision_solicitud ON revision_solicitud (solicitud_id, paso_orden);
CREATE INDEX IF NOT EXISTS idx_notificacion_destinatario_estado ON notificacion (destinatario_id, estado_envio, creada_en DESC);
CREATE INDEX IF NOT EXISTS idx_notificacion_solicitud ON notificacion (solicitud_id, creada_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_acceso_actor_fecha ON auditoria_acceso (actor_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_modificacion_entidad_fecha ON auditoria_modificacion (entidad, entidad_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_tipo_ausencia_estado ON tipo_ausencia (estado, nombre);

COMMIT;