-- Esquema inicial para PostgreSQL 16
-- Tablas por entidad del dominio de solicitudes de ausencia, revisión, catálogo y auditoría.

CREATE SCHEMA IF NOT EXISTS vacaciones;

-- Catálogos de soporte
CREATE TABLE IF NOT EXISTS vacaciones.rol_aprobador (
    id SMALLSERIAL PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (codigo <> ''),
    CHECK (nombre <> '')
);

CREATE TABLE IF NOT EXISTS vacaciones.estado_solicitud (
    id SMALLSERIAL PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    es_final BOOLEAN NOT NULL DEFAULT FALSE,
    orden SMALLINT NOT NULL,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (codigo <> ''),
    CHECK (nombre <> ''),
    CHECK (orden > 0)
);

CREATE TABLE IF NOT EXISTS vacaciones.estado_catalogo (
    id SMALLSERIAL PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(80) NOT NULL UNIQUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (codigo <> ''),
    CHECK (nombre <> '')
);

-- Catálogo de tipos de ausencia
CREATE TABLE IF NOT EXISTS vacaciones.tipo_ausencia (
    id BIGSERIAL PRIMARY KEY,
    codigo VARCHAR(30) NOT NULL UNIQUE,
    nombre VARCHAR(120) NOT NULL,
    descripcion TEXT,
    requiere_motivo BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_observacion BOOLEAN NOT NULL DEFAULT FALSE,
    permite_horas BOOLEAN NOT NULL DEFAULT FALSE,
    requiere_validacion_th BOOLEAN NOT NULL DEFAULT FALSE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    visible_portal BOOLEAN NOT NULL DEFAULT TRUE,
    visible_publico BOOLEAN NOT NULL DEFAULT FALSE,
    version INTEGER NOT NULL DEFAULT 1,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (codigo <> ''),
    CHECK (nombre <> ''),
    CHECK (version > 0)
);

CREATE INDEX IF NOT EXISTS ix_tipo_ausencia_activo_visible_portal
    ON vacaciones.tipo_ausencia (activo, visible_portal);

-- Flujo de aprobación configurado por tipo
CREATE TABLE IF NOT EXISTS vacaciones.flujo_aprobacion (
    id BIGSERIAL PRIMARY KEY,
    tipo_ausencia_id BIGINT NOT NULL REFERENCES vacaciones.tipo_ausencia(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (version > 0),
    UNIQUE (tipo_ausencia_id, version)
);

CREATE TABLE IF NOT EXISTS vacaciones.flujo_aprobacion_paso (
    id BIGSERIAL PRIMARY KEY,
    flujo_aprobacion_id BIGINT NOT NULL REFERENCES vacaciones.flujo_aprobacion(id) ON DELETE CASCADE,
    secuencia SMALLINT NOT NULL,
    rol_aprobador_id SMALLINT NOT NULL REFERENCES vacaciones.rol_aprobador(id),
    es_obligatorio BOOLEAN NOT NULL DEFAULT TRUE,
    activo BOOLEAN NOT NULL DEFAULT TRUE,
    CHECK (secuencia > 0),
    UNIQUE (flujo_aprobacion_id, secuencia)
);

CREATE INDEX IF NOT EXISTS ix_flujo_aprobacion_tipo_activo
    ON vacaciones.flujo_aprobacion (tipo_ausencia_id, activo);

CREATE INDEX IF NOT EXISTS ix_flujo_aprobacion_paso_flujo
    ON vacaciones.flujo_aprobacion_paso (flujo_aprobacion_id, secuencia);

-- Personas mínimas referenciales para solicitud y revisión
CREATE TABLE IF NOT EXISTS vacaciones.persona (
    id BIGSERIAL PRIMARY KEY,
    documento VARCHAR(30) NOT NULL UNIQUE,
    nombres VARCHAR(120) NOT NULL,
    apellidos VARCHAR(120) NOT NULL,
    correo VARCHAR(254) NOT NULL UNIQUE,
    area VARCHAR(120),
    cargo VARCHAR(120),
    es_activo BOOLEAN NOT NULL DEFAULT TRUE,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (documento <> ''),
    CHECK (nombres <> ''),
    CHECK (apellidos <> ''),
    CHECK (correo <> '')
);

CREATE INDEX IF NOT EXISTS ix_persona_activo_area
    ON vacaciones.persona (es_activo, area);

-- Solicitudes
CREATE TABLE IF NOT EXISTS vacaciones.solicitud (
    id BIGSERIAL PRIMARY KEY,
    solicitante_id BIGINT NOT NULL REFERENCES vacaciones.persona(id),
    tipo_ausencia_id BIGINT NOT NULL REFERENCES vacaciones.tipo_ausencia(id),
    fecha_inicio DATE NOT NULL,
    fecha_fin DATE NOT NULL,
    hora_inicio TIME,
    hora_fin TIME,
    motivo TEXT,
    observacion TEXT,
    estado_id SMALLINT NOT NULL REFERENCES vacaciones.estado_solicitud(id),
    version INTEGER NOT NULL DEFAULT 1,
    enviado_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (fecha_fin >= fecha_inicio),
    CHECK ((hora_inicio IS NULL AND hora_fin IS NULL) OR (hora_inicio IS NOT NULL AND hora_fin IS NOT NULL)),
    CHECK (version > 0),
    CHECK (motivo IS NULL OR btrim(motivo) <> ''),
    CHECK (observacion IS NULL OR btrim(observacion) <> '')
);

CREATE INDEX IF NOT EXISTS ix_solicitud_solicitante_estado_fecha
    ON vacaciones.solicitud (solicitante_id, estado_id, fecha_inicio DESC);

CREATE INDEX IF NOT EXISTS ix_solicitud_tipo_estado
    ON vacaciones.solicitud (tipo_ausencia_id, estado_id);

CREATE INDEX IF NOT EXISTS ix_solicitud_enviado_en
    ON vacaciones.solicitud (enviado_en DESC);

CREATE TABLE IF NOT EXISTS vacaciones.solicitud_historial (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES vacaciones.solicitud(id) ON DELETE CASCADE,
    estado_id SMALLINT NOT NULL REFERENCES vacaciones.estado_solicitud(id),
    actor_id BIGINT REFERENCES vacaciones.persona(id),
    accion VARCHAR(40) NOT NULL,
    comentario TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (accion <> ''),
    CHECK (comentario IS NULL OR btrim(comentario) <> '')
);

CREATE INDEX IF NOT EXISTS ix_solicitud_historial_solicitud_fecha
    ON vacaciones.solicitud_historial (solicitud_id, creado_en DESC);

CREATE TABLE IF NOT EXISTS vacaciones.solicitud_decision (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id BIGINT NOT NULL REFERENCES vacaciones.solicitud(id) ON DELETE CASCADE,
    flujo_aprobacion_paso_id BIGINT NOT NULL REFERENCES vacaciones.flujo_aprobacion_paso(id),
    decisor_id BIGINT NOT NULL REFERENCES vacaciones.persona(id),
    estado_resultante_id SMALLINT NOT NULL REFERENCES vacaciones.estado_solicitud(id),
    observacion TEXT,
    version_solicitud INTEGER NOT NULL,
    decidido_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (solicitud_id, flujo_aprobacion_paso_id),
    CHECK (version_solicitud > 0),
    CHECK (observacion IS NULL OR btrim(observacion) <> '')
);

CREATE INDEX IF NOT EXISTS ix_solicitud_decision_solicitud_decidido
    ON vacaciones.solicitud_decision (solicitud_id, decidido_en DESC);

-- Notificaciones
CREATE TABLE IF NOT EXISTS vacaciones.notificacion (
    id BIGSERIAL PRIMARY KEY,
    solicitud_id BIGINT REFERENCES vacaciones.solicitud(id) ON DELETE CASCADE,
    destinatario_id BIGINT NOT NULL REFERENCES vacaciones.persona(id),
    tipo VARCHAR(40) NOT NULL,
    asunto VARCHAR(200) NOT NULL,
    cuerpo TEXT NOT NULL,
    estado_envio VARCHAR(20) NOT NULL DEFAULT 'pendiente',
    resultado_envio TEXT,
    programada_en TIMESTAMPTZ,
    enviada_en TIMESTAMPTZ,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (tipo <> ''),
    CHECK (asunto <> ''),
    CHECK (cuerpo <> ''),
    CHECK (estado_envio IN ('pendiente', 'enviada', 'fallida'))
);

CREATE INDEX IF NOT EXISTS ix_notificacion_destinatario_estado
    ON vacaciones.notificacion (destinatario_id, estado_envio, creado_en DESC);

-- Auditoría
CREATE TABLE IF NOT EXISTS vacaciones.auditoria_acceso (
    id BIGSERIAL PRIMARY KEY,
    actor_id BIGINT REFERENCES vacaciones.persona(id),
    recurso VARCHAR(120) NOT NULL,
    operacion VARCHAR(60) NOT NULL,
    detalle JSONB,
    ip_origen INET,
    usuario_agente TEXT,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (recurso <> ''),
    CHECK (operacion <> '')
);

CREATE INDEX IF NOT EXISTS ix_auditoria_acceso_recurso_fecha
    ON vacaciones.auditoria_acceso (recurso, creado_en DESC);

CREATE TABLE IF NOT EXISTS vacaciones.auditoria_modificacion (
    id BIGSERIAL PRIMARY KEY,
    actor_id BIGINT REFERENCES vacaciones.persona(id),
    entidad VARCHAR(120) NOT NULL,
    entidad_id BIGINT,
    operacion VARCHAR(60) NOT NULL,
    valor_anterior JSONB,
    valor_nuevo JSONB,
    creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (entidad <> ''),
    CHECK (operacion <> '')
);

CREATE INDEX IF NOT EXISTS ix_auditoria_modificacion_entidad_fecha
    ON vacaciones.auditoria_modificacion (entidad, creado_en DESC);

-- Restricciones de negocio por tipo de ausencia
CREATE OR REPLACE FUNCTION vacaciones.fn_validar_solicitud_tipo()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    v_requiere_motivo BOOLEAN;
    v_requiere_observacion BOOLEAN;
    v_permite_horas BOOLEAN;
BEGIN
    SELECT requiere_motivo, requiere_observacion, permite_horas
      INTO v_requiere_motivo, v_requiere_observacion, v_permite_horas
      FROM vacaciones.tipo_ausencia
     WHERE id = NEW.tipo_ausencia_id;

    IF v_requiere_motivo AND (NEW.motivo IS NULL OR btrim(NEW.motivo) = '') THEN
        RAISE EXCEPTION 'El tipo de ausencia requiere motivo';
    END IF;

    IF v_requiere_observacion AND (NEW.observacion IS NULL OR btrim(NEW.observacion) = '') THEN
        RAISE EXCEPTION 'El tipo de ausencia requiere observación';
    END IF;

    IF NOT v_permite_horas AND (NEW.hora_inicio IS NOT NULL OR NEW.hora_fin IS NOT NULL) THEN
        RAISE EXCEPTION 'El tipo de ausencia no permite registro de horas';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_solicitud_tipo ON vacaciones.solicitud;
CREATE TRIGGER trg_validar_solicitud_tipo
BEFORE INSERT OR UPDATE OF tipo_ausencia_id, motivo, observacion, hora_inicio, hora_fin
ON vacaciones.solicitud
FOR EACH ROW
EXECUTE FUNCTION vacaciones.fn_validar_solicitud_tipo();

-- Evita decisiones duplicadas válidas por la misma revisión
CREATE UNIQUE INDEX IF NOT EXISTS ux_solicitud_decision_version_paso
    ON vacaciones.solicitud_decision (solicitud_id, flujo_aprobacion_paso_id, version_solicitud);

-- Vista pública restringida para /api/tipos-ausencia
CREATE OR REPLACE VIEW vacaciones.v_tipo_ausencia_publico AS
SELECT
    id,
    codigo,
    nombre,
    descripcion,
    permite_horas,
    activo,
    visible_portal
FROM vacaciones.tipo_ausencia
WHERE activo = TRUE
  AND visible_portal = TRUE;

-- Comentario: esta vista separa los datos públicos de los administrativos.