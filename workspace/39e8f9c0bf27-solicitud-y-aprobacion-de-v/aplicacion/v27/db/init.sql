BEGIN;

-- Identidades externas; no se almacenan credenciales.
CREATE TABLE usuarios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identidad_externa text NOT NULL UNIQUE CHECK (btrim(identidad_externa) <> ''),
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    documento text NOT NULL UNIQUE CHECK (btrim(documento) <> ''),
    correo text NOT NULL CHECK (correo ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
    area text NOT NULL CHECK (btrim(area) <> ''),
    cargo text NOT NULL CHECK (btrim(cargo) <> ''),
    turno text CHECK (turno IS NULL OR btrim(turno) <> ''),
    jefe_inmediato_id bigint REFERENCES usuarios(id),
    activo boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jefe_inmediato_id IS NULL OR jefe_inmediato_id <> id)
);
CREATE UNIQUE INDEX usuarios_correo_unico ON usuarios (lower(correo));
CREATE INDEX usuarios_jefe_idx ON usuarios(jefe_inmediato_id);

CREATE TABLE roles (
    codigo text PRIMARY KEY CHECK (codigo IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    nombre text NOT NULL UNIQUE CHECK (btrim(nombre) <> '')
);
INSERT INTO roles(codigo, nombre) VALUES
    ('EMPLEADO', 'Empleado'),
    ('JEFE_INMEDIATO', 'Jefe inmediato'),
    ('TALENTO_HUMANO', 'Talento Humano');

CREATE TABLE usuarios_roles (
    usuario_id bigint NOT NULL REFERENCES usuarios(id),
    rol_codigo text NOT NULL REFERENCES roles(codigo),
    PRIMARY KEY (usuario_id, rol_codigo)
);
CREATE INDEX usuarios_roles_rol_idx ON usuarios_roles(rol_codigo, usuario_id);

CREATE TABLE estados_solicitud (
    codigo text PRIMARY KEY CHECK (codigo IN ('ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA')),
    nombre text NOT NULL UNIQUE,
    terminal boolean NOT NULL,
    CHECK (terminal = (codigo IN ('APROBADA', 'RECHAZADA')))
);
INSERT INTO estados_solicitud(codigo, nombre, terminal) VALUES
    ('ENVIADA', 'Enviada', false),
    ('EN_REVISION', 'En revisión', false),
    ('APROBADA', 'Aprobada', true),
    ('RECHAZADA', 'Rechazada', true);

CREATE TABLE flujo_aprobacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (codigo IN ('JEFE', 'JEFE_TH', 'TH')),
    nombre text NOT NULL UNIQUE CHECK (btrim(nombre) <> ''),
    activo boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
INSERT INTO flujo_aprobacion(codigo, nombre) VALUES
    ('JEFE', 'Jefe inmediato'),
    ('JEFE_TH', 'Jefe inmediato > Talento Humano'),
    ('TH', 'Talento Humano');

CREATE TABLE pasos_flujo (
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    orden smallint NOT NULL CHECK (orden BETWEEN 1 AND 2),
    rol_codigo text NOT NULL REFERENCES roles(codigo) CHECK (rol_codigo IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    requiere_validacion boolean NOT NULL DEFAULT false,
    PRIMARY KEY (flujo_id, orden),
    UNIQUE (flujo_id, rol_codigo),
    CHECK (NOT requiere_validacion OR rol_codigo = 'TALENTO_HUMANO')
);
INSERT INTO pasos_flujo(flujo_id, orden, rol_codigo, requiere_validacion)
SELECT id, 1, CASE WHEN codigo = 'TH' THEN 'TALENTO_HUMANO' ELSE 'JEFE_INMEDIATO' END, codigo = 'TH'
FROM flujo_aprobacion;
INSERT INTO pasos_flujo(flujo_id, orden, rol_codigo, requiere_validacion)
SELECT id, 2, 'TALENTO_HUMANO', true FROM flujo_aprobacion WHERE codigo = 'JEFE_TH';

CREATE TABLE tipos_ausencia (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    estado text NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO')),
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    requiere_motivo boolean NOT NULL DEFAULT false,
    modalidad_horas text NOT NULL DEFAULT 'OPCIONAL' CHECK (modalidad_horas IN ('NO_APLICA', 'OPCIONAL', 'OBLIGATORIA')),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX tipos_ausencia_nombre_unico ON tipos_ausencia(lower(nombre));
CREATE INDEX tipos_ausencia_estado_idx ON tipos_ausencia(estado, lower(nombre));
CREATE INDEX tipos_ausencia_flujo_idx ON tipos_ausencia(flujo_id);

-- Las reglas y el flujo se conservan como instantánea de la solicitud.
CREATE TABLE solicitudes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitante_id bigint NOT NULL REFERENCES usuarios(id),
    tipo_ausencia_id bigint NOT NULL REFERENCES tipos_ausencia(id),
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    estado_codigo text NOT NULL DEFAULT 'ENVIADA' REFERENCES estados_solicitud(codigo),
    origen text NOT NULL DEFAULT 'PORTAL' CHECK (origen IN ('PORTAL', 'FORMATO_OFICIAL')),
    referencia_formato text CHECK (referencia_formato IS NULL OR btrim(referencia_formato) <> ''),
    fecha_inicio date NOT NULL,
    fecha_fin date NOT NULL,
    hora_inicio time without time zone,
    hora_fin time without time zone,
    motivo text CHECK (motivo IS NULL OR btrim(motivo) <> ''),
    requiere_motivo boolean NOT NULL,
    modalidad_horas text NOT NULL CHECK (modalidad_horas IN ('NO_APLICA', 'OPCIONAL', 'OBLIGATORIA')),
    requiere_revision_adicional boolean NOT NULL DEFAULT false,
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    eliminado_en timestamptz,
    CHECK (fecha_fin >= fecha_inicio),
    CHECK ((hora_inicio IS NULL) = (hora_fin IS NULL)),
    CHECK (hora_inicio IS NULL OR fecha_fin + hora_fin > fecha_inicio + hora_inicio),
    CHECK (NOT requiere_motivo OR (motivo IS NOT NULL AND btrim(motivo) <> '')),
    CHECK (modalidad_horas <> 'NO_APLICA' OR hora_inicio IS NULL),
    CHECK (modalidad_horas <> 'OBLIGATORIA' OR hora_inicio IS NOT NULL),
    CHECK (actualizado_en >= creado_en),
    CHECK (eliminado_en IS NULL OR eliminado_en >= creado_en)
);
CREATE INDEX solicitudes_empleado_estado_idx ON solicitudes(solicitante_id, estado_codigo, creado_en DESC) WHERE eliminado_en IS NULL;
CREATE INDEX solicitudes_estado_idx ON solicitudes(estado_codigo, creado_en) WHERE eliminado_en IS NULL;
CREATE INDEX solicitudes_tipo_fechas_idx ON solicitudes(tipo_ausencia_id, fecha_inicio, fecha_fin);
CREATE INDEX solicitudes_flujo_idx ON solicitudes(flujo_id);

-- Una fila por revisión; una sola decisión final por fila.
CREATE TABLE aprobaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    orden smallint NOT NULL CHECK (orden BETWEEN 1 AND 2),
    rol_codigo text NOT NULL REFERENCES roles(codigo) CHECK (rol_codigo IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    aprobador_id bigint NOT NULL REFERENCES usuarios(id),
    requiere_validacion boolean NOT NULL DEFAULT false,
    estado text NOT NULL DEFAULT 'BLOQUEADA' CHECK (estado IN ('BLOQUEADA', 'PENDIENTE', 'APROBADA', 'RECHAZADA', 'CANCELADA')),
    validada_por bigint REFERENCES usuarios(id),
    validada_en timestamptz,
    decision_por bigint REFERENCES usuarios(id),
    decidida_en timestamptz,
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (solicitud_id, orden),
    UNIQUE (solicitud_id, rol_codigo),
    UNIQUE (solicitud_id, id),
    FOREIGN KEY (aprobador_id, rol_codigo) REFERENCES usuarios_roles(usuario_id, rol_codigo),
    CHECK (NOT requiere_validacion OR rol_codigo = 'TALENTO_HUMANO'),
    CHECK ((validada_por IS NULL) = (validada_en IS NULL)),
    CHECK (validada_por IS NULL OR validada_por = aprobador_id),
    CHECK ((estado IN ('APROBADA', 'RECHAZADA')) = (decision_por IS NOT NULL AND decidida_en IS NOT NULL)),
    CHECK ((decision_por IS NULL) = (decidida_en IS NULL)),
    CHECK (decision_por IS NULL OR decision_por = aprobador_id),
    CHECK (estado <> 'APROBADA' OR NOT requiere_validacion OR validada_en IS NOT NULL),
    CHECK (validada_en IS NULL OR validada_en >= creado_en),
    CHECK (decidida_en IS NULL OR decidida_en >= creado_en)
);
CREATE UNIQUE INDEX aprobaciones_pendiente_unica ON aprobaciones(solicitud_id) WHERE estado = 'PENDIENTE';
CREATE INDEX aprobaciones_bandeja_idx ON aprobaciones(aprobador_id, creado_en, solicitud_id) WHERE estado = 'PENDIENTE';

CREATE TABLE observaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    aprobacion_id bigint,
    autor_id bigint NOT NULL REFERENCES usuarios(id),
    accion text NOT NULL CHECK (accion IN ('REVISION', 'VALIDACION', 'APROBACION', 'RECHAZO')),
    contenido text NOT NULL CHECK (btrim(contenido) <> ''),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (solicitud_id, aprobacion_id) REFERENCES aprobaciones(solicitud_id, id)
);
CREATE INDEX observaciones_solicitud_idx ON observaciones(solicitud_id, creado_en, id);
CREATE INDEX observaciones_aprobacion_idx ON observaciones(aprobacion_id);
CREATE INDEX observaciones_autor_idx ON observaciones(autor_id);

CREATE TABLE historial_solicitud (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    operacion text NOT NULL CHECK (operacion IN ('CREACION', 'MODIFICACION', 'CAMBIO_ESTADO', 'ELIMINACION')),
    estado_anterior text REFERENCES estados_solicitud(codigo),
    estado_nuevo text NOT NULL REFERENCES estados_solicitud(codigo),
    version bigint NOT NULL CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (solicitud_id, version)
);
CREATE INDEX historial_solicitud_orden_idx ON historial_solicitud(solicitud_id, creado_en, id);
CREATE INDEX historial_actor_idx ON historial_solicitud(actor_id);

CREATE TABLE versiones (
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    numero bigint NOT NULL CHECK (numero > 0),
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    datos jsonb NOT NULL CHECK (jsonb_typeof(datos) = 'object'),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (solicitud_id, numero)
);
CREATE INDEX versiones_actor_idx ON versiones(actor_id);

CREATE TABLE notificaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    destinatario_id bigint NOT NULL REFERENCES usuarios(id),
    historial_id bigint REFERENCES historial_solicitud(id),
    aprobacion_id bigint REFERENCES aprobaciones(id),
    tipo text NOT NULL CHECK (tipo IN ('CAMBIO_ESTADO', 'PENDIENTE_REVISION')),
    canal text NOT NULL DEFAULT 'CORREO' CHECK (canal = 'CORREO'),
    prioridad text NOT NULL DEFAULT 'NORMAL' CHECK (prioridad = 'NORMAL'),
    estado_envio text NOT NULL DEFAULT 'PENDIENTE' CHECK (estado_envio IN ('PENDIENTE', 'PROCESANDO', 'ENVIADA', 'ERROR')),
    intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    proximo_intento_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueada_hasta timestamptz,
    enviada_en timestamptz,
    leida_en timestamptz,
    ultimo_error text,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((tipo = 'CAMBIO_ESTADO' AND historial_id IS NOT NULL AND aprobacion_id IS NULL) OR (tipo = 'PENDIENTE_REVISION' AND aprobacion_id IS NOT NULL AND historial_id IS NULL)),
    CHECK ((estado_envio = 'ENVIADA') = (enviada_en IS NOT NULL)),
    CHECK (enviada_en IS NULL OR enviada_en >= creado_en),
    CHECK (leida_en IS NULL OR leida_en >= creado_en),
    UNIQUE (historial_id, destinatario_id),
    UNIQUE (aprobacion_id, destinatario_id)
);
CREATE INDEX notificaciones_destinatario_idx ON notificaciones(destinatario_id, creado_en DESC);
CREATE INDEX notificaciones_cola_idx ON notificaciones(proximo_intento_en, id) WHERE estado_envio IN ('PENDIENTE', 'ERROR', 'PROCESANDO');
CREATE INDEX notificaciones_solicitud_idx ON notificaciones(solicitud_id);

CREATE TABLE auditoria_acceso (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    solicitud_id bigint REFERENCES solicitudes(id),
    operacion text NOT NULL CHECK (operacion IN ('ACCESO', 'CONSULTA_DETALLE', 'CONSULTA_ESTADO', 'CONSULTA_HISTORIAL', 'CONSULTA_BANDEJA', 'CONSULTA_CATALOGO', 'ACCION_SENSIBLE')),
    autorizado boolean NOT NULL,
    direccion_ip inet,
    recurso text NOT NULL CHECK (btrim(recurso) <> ''),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX auditoria_acceso_solicitud_idx ON auditoria_acceso(solicitud_id, creado_en DESC);
CREATE INDEX auditoria_acceso_actor_idx ON auditoria_acceso(actor_id, creado_en DESC);

CREATE TABLE auditoria_modificacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    entidad text NOT NULL CHECK (entidad IN ('solicitudes', 'tipos_ausencia', 'flujo_aprobacion', 'pasos_flujo', 'aprobaciones', 'observaciones', 'usuarios', 'usuarios_roles')),
    clave jsonb NOT NULL CHECK (jsonb_typeof(clave) = 'object'),
    operacion text NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    antes jsonb,
    despues jsonb,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (antes IS NULL OR jsonb_typeof(antes) = 'object'),
    CHECK (despues IS NULL OR jsonb_typeof(despues) = 'object'),
    CHECK ((operacion = 'INSERT' AND antes IS NULL AND despues IS NOT NULL) OR (operacion = 'UPDATE' AND antes IS NOT NULL AND despues IS NOT NULL) OR (operacion = 'DELETE' AND antes IS NOT NULL AND despues IS NULL))
);
CREATE INDEX auditoria_modificacion_actor_idx ON auditoria_modificacion(actor_id, creado_en DESC);
CREATE INDEX auditoria_modificacion_entidad_idx ON auditoria_modificacion(entidad, creado_en DESC);
CREATE INDEX auditoria_modificacion_clave_idx ON auditoria_modificacion USING gin(clave);

-- El backend fija app.usuario_id localmente en cada transacción autenticada.
CREATE FUNCTION actor_actual() RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_actor bigint;
BEGIN
    v_actor := NULLIF(current_setting('app.usuario_id', true), '')::bigint;
    IF v_actor IS NULL OR NOT EXISTS (SELECT 1 FROM usuarios WHERE id = v_actor AND activo) THEN
        RAISE EXCEPTION 'Se requiere un actor autenticado y activo' USING ERRCODE = '42501';
    END IF;
    RETURN v_actor;
END;
$$;

CREATE FUNCTION auditar_modificacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_antes jsonb; v_despues jsonb; v_fila jsonb; v_clave jsonb;
BEGIN
    IF TG_OP <> 'INSERT' THEN v_antes := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN v_despues := to_jsonb(NEW); END IF;
    v_fila := COALESCE(v_despues, v_antes);
    IF TG_TABLE_NAME = 'pasos_flujo' THEN
        v_clave := jsonb_build_object('flujo_id', v_fila->'flujo_id', 'orden', v_fila->'orden');
    ELSIF TG_TABLE_NAME = 'usuarios_roles' THEN
        v_clave := jsonb_build_object('usuario_id', v_fila->'usuario_id', 'rol_codigo', v_fila->'rol_codigo');
    ELSE
        v_clave := jsonb_build_object('id', v_fila->'id');
    END IF;
    INSERT INTO auditoria_modificacion(actor_id, entidad, clave, operacion, antes, despues)
    VALUES (actor_actual(), TG_TABLE_NAME, v_clave, TG_OP, v_antes, v_despues);
    RETURN NULL;
END;
$$;

CREATE FUNCTION preparar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_tipo tipos_ausencia%ROWTYPE;
BEGIN
    IF TG_OP = 'INSERT' OR NEW.tipo_ausencia_id <> OLD.tipo_ausencia_id THEN
        SELECT * INTO STRICT v_tipo FROM tipos_ausencia WHERE id = NEW.tipo_ausencia_id FOR SHARE;
        IF v_tipo.estado <> 'ACTIVO' THEN RAISE EXCEPTION 'Tipo de ausencia inactivo'; END IF;
        IF NOT EXISTS (SELECT 1 FROM flujo_aprobacion WHERE id = v_tipo.flujo_id AND activo) THEN
            RAISE EXCEPTION 'Flujo de aprobación inactivo';
        END IF;
        NEW.flujo_id := v_tipo.flujo_id;
        IF NEW.requiere_revision_adicional THEN
            SELECT id INTO STRICT NEW.flujo_id FROM flujo_aprobacion WHERE codigo = 'JEFE_TH' AND activo;
        END IF;
        NEW.requiere_motivo := v_tipo.requiere_motivo;
        NEW.modalidad_horas := v_tipo.modalidad_horas;
    ELSIF (NEW.flujo_id, NEW.requiere_motivo, NEW.modalidad_horas, NEW.requiere_revision_adicional) IS DISTINCT FROM
          (OLD.flujo_id, OLD.requiere_motivo, OLD.modalidad_horas, OLD.requiere_revision_adicional) THEN
        RAISE EXCEPTION 'Las reglas de una solicitud existente son inmutables';
    END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.version <> 1 OR NEW.estado_codigo <> 'ENVIADA' THEN RAISE EXCEPTION 'Estado o versión inicial inválidos'; END IF;
    ELSE
        IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION 'Conflicto de versión de solicitud' USING ERRCODE = '40001';
        END IF;
        IF NEW.solicitante_id <> OLD.solicitante_id OR NEW.creado_en <> OLD.creado_en THEN
            RAISE EXCEPTION 'El solicitante y la fecha de creación son inmutables';
        END IF;
        IF OLD.estado_codigo IN ('APROBADA', 'RECHAZADA') OR OLD.eliminado_en IS NOT NULL THEN
            RAISE EXCEPTION 'La solicitud ya está cerrada';
        END IF;
        IF NEW.estado_codigo <> OLD.estado_codigo AND NOT (
            (OLD.estado_codigo = 'ENVIADA' AND NEW.estado_codigo = 'EN_REVISION') OR
            (OLD.estado_codigo = 'EN_REVISION' AND NEW.estado_codigo IN ('APROBADA', 'RECHAZADA'))
        ) THEN RAISE EXCEPTION 'Transición de estado inválida'; END IF;
        IF OLD.estado_codigo <> 'ENVIADA' AND
           (NEW.tipo_ausencia_id, NEW.fecha_inicio, NEW.fecha_fin, NEW.hora_inicio, NEW.hora_fin, NEW.motivo, NEW.origen, NEW.referencia_formato) IS DISTINCT FROM
           (OLD.tipo_ausencia_id, OLD.fecha_inicio, OLD.fecha_fin, OLD.hora_inicio, OLD.hora_fin, OLD.motivo, OLD.origen, OLD.referencia_formato) THEN
            RAISE EXCEPTION 'No se pueden editar los datos durante la revisión';
        END IF;
        NEW.actualizado_en := clock_timestamp();
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_preparar BEFORE INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION preparar_solicitud();

CREATE FUNCTION registrar_historial() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_actor bigint; v_historial bigint; v_operacion text; v_anterior text;
BEGIN
    v_actor := actor_actual();
    IF TG_OP = 'INSERT' THEN
        v_operacion := 'CREACION';
    ELSE
        v_anterior := OLD.estado_codigo;
        v_operacion := CASE WHEN NEW.eliminado_en IS NOT NULL THEN 'ELIMINACION'
            WHEN NEW.estado_codigo <> OLD.estado_codigo THEN 'CAMBIO_ESTADO' ELSE 'MODIFICACION' END;
    END IF;
    INSERT INTO historial_solicitud(solicitud_id, actor_id, operacion, estado_anterior, estado_nuevo, version)
    VALUES (NEW.id, v_actor, v_operacion, v_anterior, NEW.estado_codigo, NEW.version) RETURNING id INTO v_historial;
    INSERT INTO versiones(solicitud_id, numero, actor_id, datos) VALUES (NEW.id, NEW.version, v_actor, to_jsonb(NEW));
    IF v_operacion = 'CAMBIO_ESTADO' THEN
        INSERT INTO notificaciones(solicitud_id, destinatario_id, historial_id, tipo)
        VALUES (NEW.id, NEW.solicitante_id, v_historial, 'CAMBIO_ESTADO');
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER solicitudes_historial AFTER INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION registrar_historial();

CREATE FUNCTION preparar_revision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE v_solicitud solicitudes%ROWTYPE;
BEGIN
    SELECT * INTO STRICT v_solicitud FROM solicitudes WHERE id = NEW.solicitud_id FOR UPDATE;
    IF v_solicitud.eliminado_en IS NOT NULL OR v_solicitud.estado_codigo IN ('APROBADA', 'RECHAZADA') THEN
        RAISE EXCEPTION 'La solicitud no admite revisiones';
    END IF;
    IF NEW.aprobador_id = v_solicitud.solicitante_id THEN RAISE EXCEPTION 'No se permite la autoaprobación'; END IF;
    IF NOT EXISTS (SELECT 1 FROM usuarios WHERE id = NEW.aprobador_id AND activo) THEN RAISE EXCEPTION 'Aprobador inactivo'; END IF;
    IF TG_OP = 'INSERT' THEN
        IF NEW.version <> 1 OR NEW.estado <> 'BLOQUEADA' THEN RAISE EXCEPTION 'Revisión inicial inválida'; END IF;
        IF NOT EXISTS (SELECT 1 FROM pasos_flujo WHERE flujo_id = v_solicitud.flujo_id AND orden = NEW.orden AND rol_codigo = NEW.rol_codigo AND requiere_validacion = NEW.requiere_validacion) THEN
            RAISE EXCEPTION 'La revisión no corresponde al flujo';
        END IF;
        IF NEW.rol_codigo = 'JEFE_INMEDIATO' AND NOT EXISTS (SELECT 1 FROM usuarios WHERE id = v_solicitud.solicitante_id AND jefe_inmediato_id = NEW.aprobador_id) THEN
            RAISE EXCEPTION 'El aprobador no es el jefe inmediato';
        END IF;
    ELSE
        IF NEW.version <> OLD.version + 1 THEN RAISE EXCEPTION 'Conflicto de versión de revisión' USING ERRCODE = '40001'; END IF;
        IF (NEW.solicitud_id, NEW.orden, NEW.rol_codigo, NEW.aprobador_id, NEW.requiere_validacion, NEW.creado_en) IS DISTINCT FROM
           (OLD.solicitud_id, OLD.orden, OLD.rol_codigo, OLD.aprobador_id, OLD.requiere_validacion, OLD.creado_en) THEN
            RAISE EXCEPTION 'La asignación de revisión es inmutable';
        END IF;
        IF OLD.estado IN ('APROBADA', 'RECHAZADA', 'CANCELADA') THEN RAISE EXCEPTION 'La revisión ya está cerrada'; END IF;
        IF NEW.estado <> OLD.estado AND NOT (
            (OLD.estado = 'BLOQUEADA' AND NEW.estado IN ('PENDIENTE', 'CANCELADA')) OR
            (OLD.estado = 'PENDIENTE' AND NEW.estado IN ('APROBADA', 'RECHAZADA', 'CANCELADA'))
        ) THEN RAISE EXCEPTION 'Transición de revisión inválida'; END IF;
        IF OLD.validada_en IS NOT NULL AND (NEW.validada_en, NEW.validada_por) IS DISTINCT FROM (OLD.validada_en, OLD.validada_por) THEN
            RAISE EXCEPTION 'La validación es inmutable';
        END IF;
    END IF;
    IF NEW.estado = 'PENDIENTE' AND EXISTS (SELECT 1 FROM aprobaciones WHERE solicitud_id = NEW.solicitud_id AND orden < NEW.orden AND estado <> 'APROBADA') THEN
        RAISE EXCEPTION 'Existe una revisión anterior sin aprobar';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER aprobaciones_preparar BEFORE INSERT OR UPDATE ON aprobaciones FOR EACH ROW EXECUTE FUNCTION preparar_revision();

CREATE FUNCTION notificar_pendiente() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.estado = 'PENDIENTE' AND OLD.estado <> 'PENDIENTE' THEN
        INSERT INTO notificaciones(solicitud_id, destinatario_id, aprobacion_id, tipo)
        VALUES (NEW.solicitud_id, NEW.aprobador_id, NEW.id, 'PENDIENTE_REVISION') ON CONFLICT DO NOTHING;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER aprobaciones_notificar AFTER UPDATE ON aprobaciones FOR EACH ROW EXECUTE FUNCTION notificar_pendiente();

-- Compare-and-swap: todas las decisiones comparten la versión de solicitud.
CREATE FUNCTION registrar_decision(p_aprobacion_id bigint, p_version_solicitud bigint, p_version_revision bigint, p_accion text, p_observacion text DEFAULT NULL)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_revision aprobaciones%ROWTYPE; v_solicitud solicitudes%ROWTYPE; v_actor bigint; v_nueva_version bigint; v_siguiente bigint;
BEGIN
    v_actor := actor_actual();
    IF p_accion NOT IN ('VALIDAR', 'APROBAR', 'RECHAZAR', 'VALIDAR_APROBAR') OR p_accion IS NULL THEN RAISE EXCEPTION 'Acción inválida'; END IF;
    SELECT s.* INTO STRICT v_solicitud FROM solicitudes s JOIN aprobaciones a ON a.solicitud_id = s.id WHERE a.id = p_aprobacion_id FOR UPDATE OF s;
    SELECT * INTO STRICT v_revision FROM aprobaciones WHERE id = p_aprobacion_id FOR UPDATE;
    IF v_solicitud.version <> p_version_solicitud OR v_revision.version <> p_version_revision OR p_version_solicitud IS NULL OR p_version_revision IS NULL THEN
        RAISE EXCEPTION 'Conflicto de versión' USING ERRCODE = '40001';
    END IF;
    IF v_revision.aprobador_id <> v_actor OR NOT EXISTS (SELECT 1 FROM usuarios_roles WHERE usuario_id = v_actor AND rol_codigo = v_revision.rol_codigo) THEN
        RAISE EXCEPTION 'Actor no autorizado para esta revisión' USING ERRCODE = '42501';
    END IF;
    IF v_revision.estado <> 'PENDIENTE' OR v_solicitud.estado_codigo <> 'EN_REVISION' THEN RAISE EXCEPTION 'La revisión no está pendiente'; END IF;
    IF p_accion IN ('VALIDAR', 'VALIDAR_APROBAR') AND v_revision.rol_codigo <> 'TALENTO_HUMANO' THEN RAISE EXCEPTION 'La validación corresponde a Talento Humano'; END IF;
    IF p_accion = 'VALIDAR' AND v_revision.validada_en IS NOT NULL THEN RAISE EXCEPTION 'La revisión ya está validada'; END IF;
    UPDATE aprobaciones SET
        validada_por = CASE WHEN p_accion IN ('VALIDAR', 'VALIDAR_APROBAR') THEN v_actor ELSE validada_por END,
        validada_en = CASE WHEN p_accion IN ('VALIDAR', 'VALIDAR_APROBAR') THEN COALESCE(validada_en, clock_timestamp()) ELSE validada_en END,
        estado = CASE WHEN p_accion = 'RECHAZAR' THEN 'RECHAZADA' WHEN p_accion IN ('APROBAR', 'VALIDAR_APROBAR') THEN 'APROBADA' ELSE estado END,
        decision_por = CASE WHEN p_accion <> 'VALIDAR' THEN v_actor ELSE NULL END,
        decidida_en = CASE WHEN p_accion <> 'VALIDAR' THEN clock_timestamp() ELSE NULL END,
        version = version + 1
    WHERE id = p_aprobacion_id;
    IF p_observacion IS NOT NULL THEN
        INSERT INTO observaciones(solicitud_id, aprobacion_id, autor_id, accion, contenido)
        VALUES (v_solicitud.id, v_revision.id, v_actor,
            CASE WHEN p_accion = 'RECHAZAR' THEN 'RECHAZO' WHEN p_accion = 'VALIDAR' THEN 'VALIDACION' ELSE 'APROBACION' END, p_observacion);
    END IF;
    IF p_accion = 'RECHAZAR' THEN
        UPDATE aprobaciones SET estado = 'CANCELADA', version = version + 1 WHERE solicitud_id = v_solicitud.id AND estado = 'BLOQUEADA';
        UPDATE solicitudes SET estado_codigo = 'RECHAZADA', version = version + 1 WHERE id = v_solicitud.id RETURNING version INTO v_nueva_version;
    ELSIF p_accion IN ('APROBAR', 'VALIDAR_APROBAR') THEN
        SELECT id INTO v_siguiente FROM aprobaciones WHERE solicitud_id = v_solicitud.id AND estado = 'BLOQUEADA' ORDER BY orden LIMIT 1;
        IF v_siguiente IS NOT NULL THEN
            UPDATE aprobaciones SET estado = 'PENDIENTE', version = version + 1 WHERE id = v_siguiente;
            UPDATE solicitudes SET version = version + 1 WHERE id = v_solicitud.id RETURNING version INTO v_nueva_version;
        ELSE
            IF EXISTS (SELECT 1 FROM pasos_flujo p WHERE p.flujo_id = v_solicitud.flujo_id AND NOT EXISTS (SELECT 1 FROM aprobaciones a WHERE a.solicitud_id = v_solicitud.id AND a.orden = p.orden AND a.estado = 'APROBADA')) THEN
                RAISE EXCEPTION 'Faltan revisiones aprobadas del flujo';
            END IF;
            UPDATE solicitudes SET estado_codigo = 'APROBADA', version = version + 1 WHERE id = v_solicitud.id RETURNING version INTO v_nueva_version;
        END IF;
    ELSE
        UPDATE solicitudes SET version = version + 1 WHERE id = v_solicitud.id RETURNING version INTO v_nueva_version;
    END IF;
    RETURN v_nueva_version;
END;
$$;

CREATE FUNCTION proteger_registro() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro histórico no se puede modificar ni eliminar';
END;
$$;
CREATE TRIGGER historial_inmutable BEFORE UPDATE OR DELETE ON historial_solicitud FOR EACH ROW EXECUTE FUNCTION proteger_registro();
CREATE TRIGGER versiones_inmutables BEFORE UPDATE OR DELETE ON versiones FOR EACH ROW EXECUTE FUNCTION proteger_registro();
CREATE TRIGGER auditoria_acceso_inmutable BEFORE UPDATE OR DELETE ON auditoria_acceso FOR EACH ROW EXECUTE FUNCTION proteger_registro();
CREATE TRIGGER auditoria_modificacion_inmutable BEFORE UPDATE OR DELETE ON auditoria_modificacion FOR EACH ROW EXECUTE FUNCTION proteger_registro();
CREATE TRIGGER observaciones_inmutables BEFORE UPDATE OR DELETE ON observaciones FOR EACH ROW EXECUTE FUNCTION proteger_registro();
CREATE TRIGGER solicitudes_no_borrar BEFORE DELETE ON solicitudes FOR EACH ROW EXECUTE FUNCTION proteger_registro();
CREATE TRIGGER aprobaciones_no_borrar BEFORE DELETE ON aprobaciones FOR EACH ROW EXECUTE FUNCTION proteger_registro();

CREATE TRIGGER solicitudes_auditar AFTER INSERT OR UPDATE OR DELETE ON solicitudes FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER tipos_ausencia_auditar AFTER INSERT OR UPDATE OR DELETE ON tipos_ausencia FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER flujo_aprobacion_auditar AFTER INSERT OR UPDATE OR DELETE ON flujo_aprobacion FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER pasos_flujo_auditar AFTER INSERT OR UPDATE OR DELETE ON pasos_flujo FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER aprobaciones_auditar AFTER INSERT OR UPDATE OR DELETE ON aprobaciones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER observaciones_auditar AFTER INSERT OR UPDATE OR DELETE ON observaciones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER usuarios_auditar AFTER INSERT OR UPDATE OR DELETE ON usuarios FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER usuarios_roles_auditar AFTER INSERT OR UPDATE OR DELETE ON usuarios_roles FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();

REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

COMMIT;