BEGIN;

CREATE TABLE roles (
    codigo text PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    CHECK (codigo IN ('empleado', 'jefe_inmediato', 'talento_humano', 'administrador'))
);

CREATE TABLE usuarios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identidad_externa text NOT NULL UNIQUE CHECK (btrim(identidad_externa) <> ''),
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    documento text NOT NULL UNIQUE CHECK (btrim(documento) <> ''),
    correo text NOT NULL CHECK (correo ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
    area text NOT NULL CHECK (btrim(area) <> ''),
    cargo text NOT NULL CHECK (btrim(cargo) <> ''),
    turno text CHECK (turno IS NULL OR btrim(turno) <> ''),
    jefe_inmediato_id bigint REFERENCES usuarios(id) ON DELETE RESTRICT,
    activo boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT current_timestamp,
    CHECK (jefe_inmediato_id IS NULL OR jefe_inmediato_id <> id)
);
CREATE UNIQUE INDEX usuarios_correo_unico ON usuarios (lower(correo));
CREATE INDEX usuarios_jefe_idx ON usuarios (jefe_inmediato_id);
CREATE INDEX usuarios_nombre_idx ON usuarios (lower(nombre) text_pattern_ops);

CREATE TABLE usuario_roles (
    usuario_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    rol_codigo text NOT NULL REFERENCES roles(codigo) ON DELETE RESTRICT,
    PRIMARY KEY (usuario_id, rol_codigo)
);
CREATE INDEX usuario_roles_rol_idx ON usuario_roles (rol_codigo, usuario_id);

CREATE TABLE flujo_aprobacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE,
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    activo boolean NOT NULL DEFAULT true,
    CHECK (codigo IN ('JEFE', 'JEFE_TH', 'TH'))
);

CREATE TABLE etapas_flujo (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id) ON DELETE RESTRICT,
    orden smallint NOT NULL CHECK (orden BETWEEN 1 AND 2),
    rol_codigo text NOT NULL REFERENCES roles(codigo) ON DELETE RESTRICT,
    requiere_validacion boolean NOT NULL DEFAULT false,
    UNIQUE (flujo_id, orden),
    UNIQUE (flujo_id, rol_codigo),
    UNIQUE (id, flujo_id, rol_codigo),
    CHECK (rol_codigo IN ('jefe_inmediato', 'talento_humano')),
    CHECK (NOT requiere_validacion OR rol_codigo = 'talento_humano')
);

CREATE TABLE tipos_ausencia (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    estado text NOT NULL DEFAULT 'Activo' CHECK (estado IN ('Activo', 'Inactivo')),
    requiere_motivo boolean NOT NULL DEFAULT false,
    permite_horas boolean NOT NULL DEFAULT false,
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id) ON DELETE RESTRICT,
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT current_timestamp,
    actualizado_en timestamptz NOT NULL DEFAULT current_timestamp
);
CREATE UNIQUE INDEX tipos_ausencia_nombre_unico ON tipos_ausencia (lower(nombre));
CREATE INDEX tipos_ausencia_estado_nombre_idx ON tipos_ausencia (estado, lower(nombre));
CREATE INDEX tipos_ausencia_flujo_idx ON tipos_ausencia (flujo_id);

CREATE TABLE estados (
    codigo text PRIMARY KEY,
    nombre text NOT NULL UNIQUE CHECK (btrim(nombre) <> ''),
    terminal boolean NOT NULL,
    CHECK (codigo IN ('ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA')),
    CHECK (terminal = (codigo IN ('APROBADA', 'RECHAZADA')))
);

CREATE TABLE solicitudes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitante_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    tipo_ausencia_id bigint NOT NULL REFERENCES tipos_ausencia(id) ON DELETE RESTRICT,
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id) ON DELETE RESTRICT,
    estado_codigo text NOT NULL DEFAULT 'ENVIADA' REFERENCES estados(codigo) ON DELETE RESTRICT,
    origen text NOT NULL DEFAULT 'PORTAL' CHECK (origen IN ('PORTAL', 'FORMATO_OFICIAL')),
    fecha_inicio date NOT NULL,
    fecha_fin date NOT NULL,
    hora_inicio time,
    hora_fin time,
    motivo text,
    requiere_motivo boolean NOT NULL,
    permite_horas boolean NOT NULL,
    requiere_revision_adicional boolean NOT NULL DEFAULT false,
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT current_timestamp,
    actualizado_en timestamptz NOT NULL DEFAULT current_timestamp,
    eliminado_en timestamptz,
    UNIQUE (id, flujo_id),
    CHECK (isfinite(fecha_inicio) AND isfinite(fecha_fin)),
    CHECK (fecha_fin >= fecha_inicio),
    CHECK ((hora_inicio IS NULL) = (hora_fin IS NULL)),
    CHECK (hora_inicio IS NULL OR permite_horas),
    CHECK (hora_inicio IS NULL OR fecha_fin > fecha_inicio OR hora_fin > hora_inicio),
    CHECK (motivo IS NULL OR btrim(motivo) <> ''),
    CHECK (NOT requiere_motivo OR (motivo IS NOT NULL AND btrim(motivo) <> '')),
    CHECK (actualizado_en >= creado_en),
    CHECK (eliminado_en IS NULL OR eliminado_en >= creado_en)
);
CREATE INDEX solicitudes_solicitante_estado_idx ON solicitudes (solicitante_id, estado_codigo, creado_en DESC) WHERE eliminado_en IS NULL;
CREATE INDEX solicitudes_estado_fecha_idx ON solicitudes (estado_codigo, creado_en DESC) WHERE eliminado_en IS NULL;
CREATE INDEX solicitudes_tipo_idx ON solicitudes (tipo_ausencia_id);
CREATE INDEX solicitudes_flujo_idx ON solicitudes (flujo_id);
CREATE INDEX solicitudes_fechas_idx ON solicitudes (fecha_inicio, fecha_fin) WHERE eliminado_en IS NULL;

CREATE TABLE revisiones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL,
    flujo_id bigint NOT NULL,
    etapa_id bigint NOT NULL,
    rol_codigo text NOT NULL,
    aprobador_id bigint NOT NULL,
    estado text NOT NULL DEFAULT 'PENDIENTE' CHECK (estado IN ('PENDIENTE', 'EN_REVISION', 'COMPLETADA', 'CANCELADA')),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    asignada_en timestamptz NOT NULL DEFAULT current_timestamp,
    cerrada_en timestamptz,
    UNIQUE (solicitud_id, etapa_id),
    UNIQUE (id, solicitud_id, aprobador_id),
    FOREIGN KEY (solicitud_id, flujo_id) REFERENCES solicitudes(id, flujo_id) ON DELETE RESTRICT,
    FOREIGN KEY (etapa_id, flujo_id, rol_codigo) REFERENCES etapas_flujo(id, flujo_id, rol_codigo) ON DELETE RESTRICT,
    FOREIGN KEY (aprobador_id, rol_codigo) REFERENCES usuario_roles(usuario_id, rol_codigo) ON DELETE RESTRICT,
    CHECK ((estado IN ('COMPLETADA', 'CANCELADA')) = (cerrada_en IS NOT NULL)),
    CHECK (cerrada_en IS NULL OR cerrada_en >= asignada_en)
);
CREATE INDEX revisiones_bandeja_idx ON revisiones (aprobador_id, asignada_en, solicitud_id) WHERE estado IN ('PENDIENTE', 'EN_REVISION');
CREATE INDEX revisiones_etapa_idx ON revisiones (etapa_id);
CREATE INDEX revisiones_flujo_rol_idx ON revisiones (etapa_id, flujo_id, rol_codigo);
CREATE INDEX revisiones_aprobador_rol_idx ON revisiones (aprobador_id, rol_codigo);

CREATE TABLE aprobaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    revision_id bigint NOT NULL UNIQUE,
    solicitud_id bigint NOT NULL,
    actor_id bigint NOT NULL,
    decision text NOT NULL CHECK (decision IN ('APROBAR', 'RECHAZAR', 'VALIDAR_Y_APROBAR')),
    version_solicitud_esperada bigint NOT NULL CHECK (version_solicitud_esperada > 0),
    version_revision_esperada bigint NOT NULL CHECK (version_revision_esperada > 0),
    decidida_en timestamptz NOT NULL DEFAULT current_timestamp,
    UNIQUE (id, solicitud_id, actor_id),
    FOREIGN KEY (revision_id, solicitud_id, actor_id) REFERENCES revisiones(id, solicitud_id, aprobador_id) ON DELETE RESTRICT
);
CREATE INDEX aprobaciones_solicitud_fecha_idx ON aprobaciones (solicitud_id, decidida_en);
CREATE INDEX aprobaciones_actor_idx ON aprobaciones (actor_id);

CREATE TABLE observaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id) ON DELETE RESTRICT,
    actor_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    aprobacion_id bigint,
    clase text NOT NULL CHECK (clase IN ('REVISION', 'APROBACION', 'RECHAZO', 'VALIDACION')),
    contenido text NOT NULL CHECK (btrim(contenido) <> ''),
    creada_en timestamptz NOT NULL DEFAULT current_timestamp,
    FOREIGN KEY (aprobacion_id, solicitud_id, actor_id) REFERENCES aprobaciones(id, solicitud_id, actor_id) ON DELETE RESTRICT,
    CHECK (clase = 'REVISION' OR aprobacion_id IS NOT NULL)
);
CREATE INDEX observaciones_solicitud_fecha_idx ON observaciones (solicitud_id, creada_en, id);
CREATE INDEX observaciones_aprobacion_idx ON observaciones (aprobacion_id);
CREATE INDEX observaciones_actor_idx ON observaciones (actor_id);

CREATE TABLE versiones (
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id) ON DELETE RESTRICT,
    numero bigint NOT NULL CHECK (numero > 0),
    actor_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    datos jsonb NOT NULL CHECK (jsonb_typeof(datos) = 'object'),
    registrada_en timestamptz NOT NULL DEFAULT current_timestamp,
    PRIMARY KEY (solicitud_id, numero)
);
CREATE INDEX versiones_actor_idx ON versiones (actor_id);

CREATE TABLE historial_solicitud (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id) ON DELETE RESTRICT,
    version bigint NOT NULL,
    actor_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    estado_anterior text REFERENCES estados(codigo) ON DELETE RESTRICT,
    estado_nuevo text NOT NULL REFERENCES estados(codigo) ON DELETE RESTRICT,
    evento text NOT NULL CHECK (evento IN ('CREACION', 'MODIFICACION', 'CAMBIO_ESTADO', 'BAJA')),
    ocurrido_en timestamptz NOT NULL DEFAULT current_timestamp,
    UNIQUE (solicitud_id, version),
    FOREIGN KEY (solicitud_id, version) REFERENCES versiones(solicitud_id, numero) ON DELETE RESTRICT,
    CHECK ((evento = 'CREACION') = (estado_anterior IS NULL)),
    CHECK (evento <> 'CAMBIO_ESTADO' OR estado_anterior <> estado_nuevo)
);
CREATE INDEX historial_solicitud_fecha_idx ON historial_solicitud (solicitud_id, ocurrido_en, id);
CREATE INDEX historial_actor_idx ON historial_solicitud (actor_id);

CREATE TABLE notificaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id) ON DELETE RESTRICT,
    destinatario_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    revision_id bigint REFERENCES revisiones(id) ON DELETE RESTRICT,
    historial_id bigint REFERENCES historial_solicitud(id) ON DELETE RESTRICT,
    tipo text NOT NULL CHECK (tipo IN ('CAMBIO_ESTADO', 'PENDIENTE_REVISION')),
    canal text NOT NULL DEFAULT 'CORREO' CHECK (canal IN ('CORREO', 'PORTAL')),
    prioridad text NOT NULL DEFAULT 'Normal' CHECK (prioridad IN ('Normal', 'Alta')),
    asunto text NOT NULL CHECK (btrim(asunto) <> ''),
    mensaje text NOT NULL CHECK (btrim(mensaje) <> ''),
    estado_envio text NOT NULL DEFAULT 'PENDIENTE' CHECK (estado_envio IN ('PENDIENTE', 'EN_PROCESO', 'ENVIADA', 'ERROR')),
    intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    creada_en timestamptz NOT NULL DEFAULT current_timestamp,
    proximo_intento_en timestamptz NOT NULL DEFAULT current_timestamp,
    enviada_en timestamptz,
    leida_en timestamptz,
    ultimo_error text,
    CHECK ((tipo = 'CAMBIO_ESTADO' AND historial_id IS NOT NULL AND revision_id IS NULL) OR (tipo = 'PENDIENTE_REVISION' AND revision_id IS NOT NULL AND historial_id IS NULL)),
    CHECK ((estado_envio = 'ENVIADA') = (enviada_en IS NOT NULL)),
    CHECK (enviada_en IS NULL OR enviada_en >= creada_en),
    CHECK (leida_en IS NULL OR leida_en >= creada_en),
    CHECK (ultimo_error IS NULL OR btrim(ultimo_error) <> '')
);
CREATE UNIQUE INDEX notificaciones_cambio_unico ON notificaciones (historial_id, destinatario_id, canal) WHERE tipo = 'CAMBIO_ESTADO';
CREATE UNIQUE INDEX notificaciones_pendiente_unico ON notificaciones (revision_id, destinatario_id, canal) WHERE tipo = 'PENDIENTE_REVISION';
CREATE INDEX notificaciones_destinatario_idx ON notificaciones (destinatario_id, creada_en DESC);
CREATE INDEX notificaciones_cola_idx ON notificaciones (proximo_intento_en, id) WHERE estado_envio IN ('PENDIENTE', 'ERROR');
CREATE INDEX notificaciones_solicitud_idx ON notificaciones (solicitud_id);

CREATE TABLE auditoria_acceso (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint REFERENCES usuarios(id) ON DELETE RESTRICT,
    identidad_declarada text,
    solicitud_id bigint REFERENCES solicitudes(id) ON DELETE RESTRICT,
    operacion text NOT NULL CHECK (operacion IN ('AUTENTICACION', 'CONSULTA_SOLICITUD', 'CONSULTA_HISTORIAL', 'CONSULTA_BANDEJA', 'CONSULTA_CATALOGO', 'CONSULTA_AUDITORIA', 'ACCION_SENSIBLE')),
    resultado text NOT NULL CHECK (resultado IN ('PERMITIDO', 'DENEGADO', 'ERROR')),
    direccion_ip inet,
    correlacion_id uuid,
    ocurrido_en timestamptz NOT NULL DEFAULT current_timestamp,
    CHECK (resultado <> 'PERMITIDO' OR actor_id IS NOT NULL),
    CHECK (operacion <> 'CONSULTA_HISTORIAL' OR solicitud_id IS NOT NULL),
    CHECK (identidad_declarada IS NULL OR btrim(identidad_declarada) <> '')
);
CREATE INDEX auditoria_acceso_actor_fecha_idx ON auditoria_acceso (actor_id, ocurrido_en DESC);
CREATE INDEX auditoria_acceso_solicitud_fecha_idx ON auditoria_acceso (solicitud_id, ocurrido_en DESC);
CREATE INDEX auditoria_acceso_operacion_fecha_idx ON auditoria_acceso (operacion, ocurrido_en DESC);

CREATE TABLE auditoria_modificacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES usuarios(id) ON DELETE RESTRICT,
    entidad text NOT NULL CHECK (entidad IN ('usuarios', 'usuario_roles', 'flujo_aprobacion', 'etapas_flujo', 'tipos_ausencia', 'solicitudes', 'revisiones', 'aprobaciones', 'observaciones', 'notificaciones')),
    clave jsonb NOT NULL CHECK (jsonb_typeof(clave) = 'object'),
    operacion text NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    datos_anteriores jsonb,
    datos_nuevos jsonb,
    ocurrido_en timestamptz NOT NULL DEFAULT current_timestamp,
    CHECK (datos_anteriores IS NULL OR jsonb_typeof(datos_anteriores) = 'object'),
    CHECK (datos_nuevos IS NULL OR jsonb_typeof(datos_nuevos) = 'object'),
    CHECK ((operacion = 'INSERT' AND datos_anteriores IS NULL AND datos_nuevos IS NOT NULL) OR (operacion = 'UPDATE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NOT NULL) OR (operacion = 'DELETE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NULL))
);
CREATE INDEX auditoria_modificacion_actor_fecha_idx ON auditoria_modificacion (actor_id, ocurrido_en DESC);
CREATE INDEX auditoria_modificacion_entidad_fecha_idx ON auditoria_modificacion (entidad, ocurrido_en DESC);
CREATE INDEX auditoria_modificacion_clave_idx ON auditoria_modificacion USING gin (clave);

-- Solo catálogos técnicos, sin personas ni solicitudes de ejemplo.
INSERT INTO roles (codigo, nombre) VALUES
('empleado', 'Empleado'), ('jefe_inmediato', 'Jefe inmediato'),
('talento_humano', 'Talento Humano'), ('administrador', 'Administrador');
INSERT INTO estados (codigo, nombre, terminal) VALUES
('ENVIADA', 'Enviada', false), ('EN_REVISION', 'En revisión', false),
('APROBADA', 'Aprobada', true), ('RECHAZADA', 'Rechazada', true);
INSERT INTO flujo_aprobacion (codigo, nombre) VALUES
('JEFE', 'Jefe inmediato'), ('JEFE_TH', 'Jefe inmediato > Talento Humano'), ('TH', 'Talento Humano');
INSERT INTO etapas_flujo (flujo_id, orden, rol_codigo, requiere_validacion)
SELECT id, 1, 'jefe_inmediato', false FROM flujo_aprobacion WHERE codigo IN ('JEFE', 'JEFE_TH');
INSERT INTO etapas_flujo (flujo_id, orden, rol_codigo, requiere_validacion)
SELECT id, CASE WHEN codigo = 'TH' THEN 1 ELSE 2 END, 'talento_humano', true
FROM flujo_aprobacion WHERE codigo IN ('TH', 'JEFE_TH');

CREATE FUNCTION actor_actual() RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_actor bigint;
BEGIN
    v_actor := nullif(current_setting('app.usuario_id', true), '')::bigint;
    IF v_actor IS NULL OR NOT EXISTS (SELECT 1 FROM usuarios WHERE id = v_actor AND activo) THEN
        RAISE EXCEPTION 'Se requiere un actor autenticado activo' USING ERRCODE = '42501';
    END IF;
    RETURN v_actor;
END;
$$;

CREATE FUNCTION controlar_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NEW.version <> 1 THEN
            RAISE EXCEPTION 'La versión inicial debe ser 1' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION 'Conflicto de versión' USING ERRCODE = '40001';
        END IF;
        IF TG_TABLE_NAME <> 'revisiones' THEN
            NEW.actualizado_en := clock_timestamp();
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_version BEFORE INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION controlar_version();
CREATE TRIGGER tipos_ausencia_version BEFORE INSERT OR UPDATE ON tipos_ausencia FOR EACH ROW EXECUTE FUNCTION controlar_version();
CREATE TRIGGER revisiones_version BEFORE INSERT OR UPDATE ON revisiones FOR EACH ROW EXECUTE FUNCTION controlar_version();

CREATE FUNCTION validar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_tipo tipos_ausencia%ROWTYPE; v_flujo bigint;
BEGIN
    IF TG_OP = 'INSERT' OR NEW.tipo_ausencia_id <> OLD.tipo_ausencia_id THEN
        SELECT * INTO v_tipo FROM tipos_ausencia WHERE id = NEW.tipo_ausencia_id FOR SHARE;
        IF NOT FOUND OR v_tipo.estado <> 'Activo' THEN
            RAISE EXCEPTION 'El tipo de ausencia debe estar activo' USING ERRCODE = '23514';
        END IF;
        v_flujo := v_tipo.flujo_id;
        IF NEW.requiere_revision_adicional THEN
            SELECT id INTO v_flujo FROM flujo_aprobacion
            WHERE codigo = CASE WHEN EXISTS (SELECT 1 FROM etapas_flujo WHERE flujo_id = v_tipo.flujo_id AND rol_codigo = 'jefe_inmediato') THEN 'JEFE_TH' ELSE 'TH' END;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM flujo_aprobacion WHERE id = v_flujo AND activo) THEN
            RAISE EXCEPTION 'El flujo debe estar activo' USING ERRCODE = '23514';
        END IF;
        NEW.flujo_id := v_flujo;
        NEW.requiere_motivo := v_tipo.requiere_motivo;
        NEW.permite_horas := v_tipo.permite_horas;
    ELSE
        IF NEW.flujo_id <> OLD.flujo_id OR NEW.requiere_motivo <> OLD.requiere_motivo OR NEW.permite_horas <> OLD.permite_horas OR NEW.requiere_revision_adicional <> OLD.requiere_revision_adicional THEN
            RAISE EXCEPTION 'La configuración aplicada a la solicitud es inmutable' USING ERRCODE = '23514';
        END IF;
    END IF;
    IF TG_OP = 'UPDATE' THEN
        IF NEW.solicitante_id <> OLD.solicitante_id THEN
            RAISE EXCEPTION 'El solicitante es inmutable' USING ERRCODE = '23514';
        END IF;
        IF NEW.estado_codigo <> OLD.estado_codigo AND NOT (
            (OLD.estado_codigo = 'ENVIADA' AND NEW.estado_codigo IN ('EN_REVISION', 'RECHAZADA')) OR
            (OLD.estado_codigo = 'EN_REVISION' AND NEW.estado_codigo IN ('APROBADA', 'RECHAZADA'))
        ) THEN
            RAISE EXCEPTION 'Transición de estado inválida' USING ERRCODE = '23514';
        END IF;
        IF OLD.estado_codigo IN ('APROBADA', 'RECHAZADA') AND (to_jsonb(NEW) - ARRAY['version', 'actualizado_en', 'eliminado_en']) IS DISTINCT FROM (to_jsonb(OLD) - ARRAY['version', 'actualizado_en', 'eliminado_en']) THEN
            RAISE EXCEPTION 'Una solicitud finalizada no admite modificaciones' USING ERRCODE = '23514';
        END IF;
    ELSIF NEW.estado_codigo <> 'ENVIADA' THEN
        RAISE EXCEPTION 'La solicitud debe iniciar enviada' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_validacion BEFORE INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION validar_solicitud();

CREATE FUNCTION registrar_version_historial() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_actor bigint; v_anterior text; v_evento text;
BEGIN
    v_actor := actor_actual();
    IF TG_OP = 'INSERT' THEN
        v_evento := 'CREACION';
    ELSE
        v_anterior := OLD.estado_codigo;
        v_evento := CASE WHEN NEW.eliminado_en IS DISTINCT FROM OLD.eliminado_en THEN 'BAJA' WHEN NEW.estado_codigo <> OLD.estado_codigo THEN 'CAMBIO_ESTADO' ELSE 'MODIFICACION' END;
    END IF;
    INSERT INTO versiones (solicitud_id, numero, actor_id, datos) VALUES (NEW.id, NEW.version, v_actor, to_jsonb(NEW));
    INSERT INTO historial_solicitud (solicitud_id, version, actor_id, estado_anterior, estado_nuevo, evento)
    VALUES (NEW.id, NEW.version, v_actor, v_anterior, NEW.estado_codigo, v_evento);
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_historial AFTER INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION registrar_version_historial();

-- La decisión bloquea la revisión y actualiza ambas versiones atómicamente.
CREATE FUNCTION aplicar_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_revision revisiones%ROWTYPE; v_solicitud solicitudes%ROWTYPE; v_etapa etapas_flujo%ROWTYPE; v_estado text;
BEGIN
    SELECT * INTO v_solicitud FROM solicitudes WHERE id = NEW.solicitud_id FOR UPDATE;
    SELECT * INTO v_revision FROM revisiones WHERE id = NEW.revision_id FOR UPDATE;
    IF NOT FOUND OR v_revision.solicitud_id <> NEW.solicitud_id OR v_revision.aprobador_id <> NEW.actor_id OR NEW.actor_id <> actor_actual() THEN
        RAISE EXCEPTION 'Revisión no autorizada' USING ERRCODE = '42501';
    END IF;
    IF v_solicitud.version <> NEW.version_solicitud_esperada OR v_revision.version <> NEW.version_revision_esperada OR v_revision.estado NOT IN ('PENDIENTE', 'EN_REVISION') THEN
        RAISE EXCEPTION 'Conflicto de revisión' USING ERRCODE = '40001';
    END IF;
    IF v_solicitud.eliminado_en IS NOT NULL OR v_solicitud.estado_codigo <> 'EN_REVISION' THEN
        RAISE EXCEPTION 'La solicitud no está en revisión' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO v_etapa FROM etapas_flujo WHERE id = v_revision.etapa_id;
    IF EXISTS (
        SELECT 1 FROM etapas_flujo e WHERE e.flujo_id = v_solicitud.flujo_id AND e.orden < v_etapa.orden
        AND NOT EXISTS (SELECT 1 FROM revisiones r JOIN aprobaciones a ON a.revision_id = r.id WHERE r.solicitud_id = v_solicitud.id AND r.etapa_id = e.id AND a.decision IN ('APROBAR', 'VALIDAR_Y_APROBAR'))
    ) THEN
        RAISE EXCEPTION 'Falta aprobar una etapa previa' USING ERRCODE = '23514';
    END IF;
    IF NEW.decision = 'VALIDAR_Y_APROBAR' AND v_etapa.rol_codigo <> 'talento_humano' THEN
        RAISE EXCEPTION 'Solo Talento Humano puede validar' USING ERRCODE = '23514';
    END IF;
    IF v_etapa.requiere_validacion AND NEW.decision = 'APROBAR' THEN
        RAISE EXCEPTION 'La etapa requiere validar y aprobar' USING ERRCODE = '23514';
    END IF;
    UPDATE revisiones SET estado = 'COMPLETADA', cerrada_en = clock_timestamp(), version = version + 1 WHERE id = v_revision.id;
    v_estado := CASE WHEN NEW.decision = 'RECHAZAR' THEN 'RECHAZADA' WHEN EXISTS (SELECT 1 FROM etapas_flujo WHERE flujo_id = v_solicitud.flujo_id AND orden > v_etapa.orden) THEN 'EN_REVISION' ELSE 'APROBADA' END;
    UPDATE solicitudes SET estado_codigo = v_estado, version = version + 1 WHERE id = v_solicitud.id;
    IF v_estado = 'RECHAZADA' THEN
        UPDATE revisiones SET estado = 'CANCELADA', cerrada_en = clock_timestamp(), version = version + 1
        WHERE solicitud_id = v_solicitud.id AND id <> v_revision.id AND estado IN ('PENDIENTE', 'EN_REVISION');
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER aprobaciones_decision BEFORE INSERT ON aprobaciones FOR EACH ROW EXECUTE FUNCTION aplicar_decision();

CREATE FUNCTION validar_notificacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.tipo = 'CAMBIO_ESTADO' THEN
        IF NOT EXISTS (SELECT 1 FROM historial_solicitud h JOIN solicitudes s ON s.id = h.solicitud_id WHERE h.id = NEW.historial_id AND h.solicitud_id = NEW.solicitud_id AND s.solicitante_id = NEW.destinatario_id AND h.evento = 'CAMBIO_ESTADO') THEN
            RAISE EXCEPTION 'Notificación de cambio inconsistente' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF NOT EXISTS (SELECT 1 FROM revisiones WHERE id = NEW.revision_id AND solicitud_id = NEW.solicitud_id AND aprobador_id = NEW.destinatario_id) THEN
            RAISE EXCEPTION 'Notificación de revisión inconsistente' USING ERRCODE = '23514';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER notificaciones_validacion BEFORE INSERT OR UPDATE ON notificaciones FOR EACH ROW EXECUTE FUNCTION validar_notificacion();

CREATE FUNCTION auditar_modificacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_anterior jsonb; v_nuevo jsonb; v_datos jsonb; v_clave jsonb;
BEGIN
    IF TG_OP <> 'INSERT' THEN v_anterior := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN v_nuevo := to_jsonb(NEW); END IF;
    v_datos := coalesce(v_nuevo, v_anterior);
    v_clave := CASE WHEN TG_TABLE_NAME = 'usuario_roles' THEN jsonb_build_object('usuario_id', v_datos->'usuario_id', 'rol_codigo', v_datos->'rol_codigo') ELSE jsonb_build_object('id', v_datos->'id') END;
    INSERT INTO auditoria_modificacion (actor_id, entidad, clave, operacion, datos_anteriores, datos_nuevos)
    VALUES (actor_actual(), TG_TABLE_NAME, v_clave, TG_OP, v_anterior, v_nuevo);
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
DO $$
DECLARE v_tabla text;
BEGIN
    FOREACH v_tabla IN ARRAY ARRAY['usuarios', 'usuario_roles', 'flujo_aprobacion', 'etapas_flujo', 'tipos_ausencia', 'solicitudes', 'revisiones', 'aprobaciones', 'observaciones', 'notificaciones'] LOOP
        EXECUTE format('CREATE TRIGGER auditoria_cambios AFTER INSERT OR UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION auditar_modificacion()', v_tabla);
    END LOOP;
END;
$$;

CREATE FUNCTION impedir_cambio_historico() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro histórico es inmutable' USING ERRCODE = '42501';
END;
$$;
DO $$
DECLARE v_tabla text;
BEGIN
    FOREACH v_tabla IN ARRAY ARRAY['aprobaciones', 'observaciones', 'versiones', 'historial_solicitud', 'auditoria_acceso', 'auditoria_modificacion'] LOOP
        EXECUTE format('CREATE TRIGGER proteger_historial BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico()', v_tabla);
    END LOOP;
END;
$$;
CREATE TRIGGER solicitudes_sin_borrado BEFORE DELETE ON solicitudes FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();

COMMIT;