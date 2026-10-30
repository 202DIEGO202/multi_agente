-- Esquema inicial para PostgreSQL 16
-- Tablas por entidad del dominio, restricciones e índices para búsquedas habituales

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Catálogo de estados de solicitud
CREATE TABLE IF NOT EXISTS estado_solicitud (
  id SMALLSERIAL PRIMARY KEY,
  codigo VARCHAR(30) NOT NULL UNIQUE,
  nombre VARCHAR(80) NOT NULL UNIQUE,
  es_final BOOLEAN NOT NULL DEFAULT FALSE,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  CONSTRAINT ck_estado_solicitud_codigo CHECK (codigo <> ''),
  CONSTRAINT ck_estado_solicitud_nombre CHECK (nombre <> '')
);

INSERT INTO estado_solicitud (codigo, nombre, es_final, activo)
VALUES
  ('ENVIADA', 'Enviada', FALSE, TRUE),
  ('EN_REVISION', 'En revisión', FALSE, TRUE),
  ('APROBADA', 'Aprobada', TRUE, TRUE),
  ('RECHAZADA', 'Rechazada', TRUE, TRUE),
  ('CANCELADA', 'Cancelada', TRUE, TRUE)
ON CONFLICT (codigo) DO NOTHING;

-- Actores/usuarios referenciales del dominio (sin datos de ejemplo)
CREATE TABLE IF NOT EXISTS usuario_aplicacion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  correo VARCHAR(254) NOT NULL UNIQUE,
  nombre_completo VARCHAR(200) NOT NULL,
  aplicacion VARCHAR(20) NOT NULL,
  es_administrador BOOLEAN NOT NULL DEFAULT FALSE,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_usuario_aplicacion_correo CHECK (correo <> ''),
  CONSTRAINT ck_usuario_aplicacion_nombre CHECK (nombre_completo <> ''),
  CONSTRAINT ck_usuario_aplicacion_app CHECK (aplicacion IN ('portal', 'panel'))
);

-- Catálogo de tipos de ausencia
CREATE TABLE IF NOT EXISTS tipo_ausencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  nombre VARCHAR(120) NOT NULL UNIQUE,
  descripcion TEXT,
  requiere_motivo BOOLEAN NOT NULL DEFAULT FALSE,
  requiere_observacion BOOLEAN NOT NULL DEFAULT FALSE,
  permite_horas BOOLEAN NOT NULL DEFAULT FALSE,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  version INTEGER NOT NULL DEFAULT 1,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_tipo_ausencia_nombre CHECK (nombre <> ''),
  CONSTRAINT ck_tipo_ausencia_version CHECK (version > 0)
);

-- Flujo de aprobación por tipo de ausencia
CREATE TABLE IF NOT EXISTS flujo_aprobacion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tipo_ausencia_id UUID NOT NULL REFERENCES tipo_ausencia(id) ON DELETE CASCADE,
  orden SMALLINT NOT NULL,
  rol_aprobador VARCHAR(30) NOT NULL,
  activo BOOLEAN NOT NULL DEFAULT TRUE,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT uq_flujo_aprobacion_tipo_orden UNIQUE (tipo_ausencia_id, orden),
  CONSTRAINT ck_flujo_aprobacion_orden CHECK (orden > 0),
  CONSTRAINT ck_flujo_aprobacion_rol CHECK (rol_aprobador IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO'))
);

-- Solicitudes de ausencia
CREATE TABLE IF NOT EXISTS solicitud_ausencia (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  solicitante_id UUID NOT NULL REFERENCES usuario_aplicacion(id),
  tipo_ausencia_id UUID NOT NULL REFERENCES tipo_ausencia(id),
  estado_id SMALLINT NOT NULL REFERENCES estado_solicitud(id),
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL,
  hora_inicio TIME,
  hora_fin TIME,
  motivo TEXT,
  observacion TEXT,
  version INTEGER NOT NULL DEFAULT 1,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  actualizado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_solicitud_fechas CHECK (fecha_fin >= fecha_inicio),
  CONSTRAINT ck_solicitud_horas CHECK (
    (hora_inicio IS NULL AND hora_fin IS NULL) OR
    (hora_inicio IS NOT NULL AND hora_fin IS NOT NULL AND hora_fin > hora_inicio)
  ),
  CONSTRAINT ck_solicitud_version CHECK (version > 0),
  CONSTRAINT ck_solicitud_motivo_no_vacio CHECK (motivo IS NULL OR btrim(motivo) <> ''),
  CONSTRAINT ck_solicitud_observacion_no_vacia CHECK (observacion IS NULL OR btrim(observacion) <> '')
);

-- Historial y trazabilidad de la solicitud
CREATE TABLE IF NOT EXISTS historial_solicitud (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  solicitud_id UUID NOT NULL REFERENCES solicitud_ausencia(id) ON DELETE CASCADE,
  estado_id SMALLINT REFERENCES estado_solicitud(id),
  actor_id UUID REFERENCES usuario_aplicacion(id),
  operacion VARCHAR(40) NOT NULL,
  observacion TEXT,
  detalle JSONB NOT NULL DEFAULT '{}'::jsonb,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_historial_operacion CHECK (operacion <> ''),
  CONSTRAINT ck_historial_observacion CHECK (observacion IS NULL OR btrim(observacion) <> '')
);

-- Decisiones de aprobación/rechazo/validación
CREATE TABLE IF NOT EXISTS revision_solicitud (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  solicitud_id UUID NOT NULL REFERENCES solicitud_ausencia(id) ON DELETE CASCADE,
  revisor_id UUID NOT NULL REFERENCES usuario_aplicacion(id),
  estado_resultante_id SMALLINT NOT NULL REFERENCES estado_solicitud(id),
  observacion TEXT,
  version_solicitud INTEGER NOT NULL,
  creada_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_revision_observacion CHECK (observacion IS NULL OR btrim(observacion) <> ''),
  CONSTRAINT ck_revision_version CHECK (version_solicitud > 0)
);

-- Notificaciones generadas por cambios de estado o pendientes
CREATE TABLE IF NOT EXISTS notificacion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id UUID NOT NULL REFERENCES usuario_aplicacion(id),
  solicitud_id UUID REFERENCES solicitud_ausencia(id) ON DELETE CASCADE,
  tipo VARCHAR(30) NOT NULL,
  asunto VARCHAR(200) NOT NULL,
  cuerpo TEXT NOT NULL,
  leida BOOLEAN NOT NULL DEFAULT FALSE,
  creada_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  leida_en TIMESTAMPTZ,
  CONSTRAINT ck_notificacion_tipo CHECK (tipo IN ('CAMBIO_ESTADO', 'PENDIENTE_REVISION', 'OTRA')),
  CONSTRAINT ck_notificacion_asunto CHECK (asunto <> ''),
  CONSTRAINT ck_notificacion_cuerpo CHECK (btrim(cuerpo) <> ''),
  CONSTRAINT ck_notificacion_leida_en CHECK ((leida = FALSE AND leida_en IS NULL) OR (leida = TRUE AND leida_en IS NOT NULL))
);

-- Auditoría de accesos
CREATE TABLE IF NOT EXISTS auditoria_acceso (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id UUID REFERENCES usuario_aplicacion(id),
  accion VARCHAR(60) NOT NULL,
  recurso VARCHAR(120) NOT NULL,
  referencia_id UUID,
  ip INET,
  usuario_agente TEXT,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_auditoria_acceso_accion CHECK (accion <> ''),
  CONSTRAINT ck_auditoria_acceso_recurso CHECK (recurso <> '')
);

-- Auditoría de modificaciones
CREATE TABLE IF NOT EXISTS auditoria_modificacion (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  usuario_id UUID REFERENCES usuario_aplicacion(id),
  entidad VARCHAR(80) NOT NULL,
  entidad_id UUID NOT NULL,
  operacion VARCHAR(30) NOT NULL,
  antes JSONB,
  despues JSONB,
  creado_en TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT ck_auditoria_modificacion_entidad CHECK (entidad <> ''),
  CONSTRAINT ck_auditoria_modificacion_operacion CHECK (operacion IN ('CREAR', 'ACTUALIZAR', 'ELIMINAR', 'APROBAR', 'RECHAZAR', 'VALIDAR'))
);

-- Índices para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_solicitud_ausencia_solicitante_estado_fecha
  ON solicitud_ausencia (solicitante_id, estado_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_solicitud_ausencia_tipo_estado
  ON solicitud_ausencia (tipo_ausencia_id, estado_id);

CREATE INDEX IF NOT EXISTS idx_historial_solicitud_solicitud_fecha
  ON historial_solicitud (solicitud_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_revision_solicitud_solicitud_revisor
  ON revision_solicitud (solicitud_id, revisor_id, creada_en DESC);

CREATE INDEX IF NOT EXISTS idx_revision_solicitud_estado_resultante
  ON revision_solicitud (estado_resultante_id);

CREATE INDEX IF NOT EXISTS idx_notificacion_usuario_leida_fecha
  ON notificacion (usuario_id, leida, creada_en DESC);

CREATE INDEX IF NOT EXISTS idx_flujo_aprobacion_tipo_activo
  ON flujo_aprobacion (tipo_ausencia_id, activo, orden);

CREATE INDEX IF NOT EXISTS idx_auditoria_acceso_usuario_fecha
  ON auditoria_acceso (usuario_id, creado_en DESC);

CREATE INDEX IF NOT EXISTS idx_auditoria_modificacion_entidad_fecha
  ON auditoria_modificacion (entidad, entidad_id, creado_en DESC);

-- Comentario: el backend debe exponer vistas/DTOs limitados según el rol.