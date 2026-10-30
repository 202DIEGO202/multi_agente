BEGIN;

-- Identidad externa; no se almacenan credenciales.
CREATE TABLE areas (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> '')
);
CREATE UNIQUE INDEX areas_nombre_uq ON areas (lower(btrim(nombre)));

CREATE TABLE cargos (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> '')
);
CREATE UNIQUE INDEX cargos_nombre_uq ON cargos (lower(btrim(nombre)));

CREATE TABLE empleados (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identidad_externa text NOT NULL UNIQUE CHECK (btrim(identidad_externa) <> ''),
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    documento text NOT NULL UNIQUE CHECK (btrim(documento) <> ''),
    correo text NOT NULL CHECK (correo ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$'),
    area_id bigint NOT NULL REFERENCES areas(id),
    cargo_id bigint NOT NULL REFERENCES cargos(id),
    jefe_inmediato_id bigint REFERENCES empleados(id),
    turno text CHECK (turno IS NULL OR btrim(turno) <> ''),
    activo boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (jefe_inmediato_id IS NULL OR jefe_inmediato_id <> id)
);
CREATE UNIQUE INDEX empleados_correo_uq ON empleados (lower(correo));
CREATE INDEX empleados_jefe_idx ON empleados (jefe_inmediato_id);
CREATE INDEX empleados_area_idx ON empleados (area_id);
CREATE INDEX empleados_cargo_idx ON empleados (cargo_id);
CREATE INDEX empleados_nombre_idx ON empleados (lower(nombre) text_pattern_ops);

CREATE TABLE roles (
    codigo text PRIMARY KEY CHECK (codigo IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    nombre text NOT NULL CHECK (btrim(nombre) <> '')
);
CREATE TABLE empleado_roles (
    empleado_id bigint NOT NULL REFERENCES empleados(id),
    rol_codigo text NOT NULL REFERENCES roles(codigo),
    PRIMARY KEY (empleado_id, rol_codigo)
);
CREATE INDEX empleado_roles_rol_idx ON empleado_roles (rol_codigo, empleado_id);

CREATE TABLE estados_solicitud (
    codigo text PRIMARY KEY CHECK (codigo IN ('ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA', 'CANCELADA')),
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    es_final boolean NOT NULL,
    CHECK (es_final = (codigo IN ('APROBADA', 'RECHAZADA', 'CANCELADA')))
);

CREATE TABLE flujo_aprobacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo text NOT NULL UNIQUE CHECK (codigo IN ('JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO')),
    nombre text NOT NULL CHECK (btrim(nombre) <> '')
);
CREATE TABLE pasos_flujo (
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    orden smallint NOT NULL CHECK (orden BETWEEN 1 AND 2),
    rol_codigo text NOT NULL REFERENCES roles(codigo) CHECK (rol_codigo IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    PRIMARY KEY (flujo_id, orden),
    UNIQUE (flujo_id, orden, rol_codigo)
);

CREATE TABLE tipos_ausencia (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    estado text NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO')),
    requiere_motivo boolean NOT NULL DEFAULT false,
    permite_horas boolean NOT NULL DEFAULT false,
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX tipos_ausencia_nombre_uq ON tipos_ausencia (lower(btrim(nombre)));
CREATE INDEX tipos_ausencia_estado_nombre_idx ON tipos_ausencia (estado, lower(nombre));
CREATE INDEX tipos_ausencia_flujo_idx ON tipos_ausencia (flujo_id);

CREATE TABLE solicitudes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitante_id bigint NOT NULL REFERENCES empleados(id),
    tipo_ausencia_id bigint NOT NULL REFERENCES tipos_ausencia(id),
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    origen text NOT NULL DEFAULT 'PORTAL' CHECK (origen IN ('PORTAL', 'FORMATO_OFICIAL')),
    referencia_formato text CHECK (referencia_formato IS NULL OR btrim(referencia_formato) <> ''),
    fecha_inicio date NOT NULL,
    fecha_fin date NOT NULL,
    hora_inicio time without time zone,
    hora_fin time without time zone,
    motivo text CHECK (motivo IS NULL OR btrim(motivo) <> ''),
    requiere_motivo boolean NOT NULL,
    permite_horas boolean NOT NULL,
    requiere_revision_adicional boolean NOT NULL DEFAULT false,
    estado_codigo text NOT NULL DEFAULT 'ENVIADA' REFERENCES estados_solicitud(codigo),
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    actualizado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (id, flujo_id),
    CHECK (fecha_fin >= fecha_inicio),
    CHECK ((hora_inicio IS NULL) = (hora_fin IS NULL)),
    CHECK (hora_inicio IS NULL OR fecha_inicio + hora_inicio < fecha_fin + hora_fin),
    CHECK (permite_horas OR hora_inicio IS NULL),
    CHECK (NOT requiere_motivo OR (motivo IS NOT NULL AND btrim(motivo) <> '')),
    CHECK (origen = 'FORMATO_OFICIAL' OR referencia_formato IS NULL),
    CHECK (actualizado_en >= creado_en)
);
CREATE INDEX solicitudes_solicitante_estado_fecha_idx ON solicitudes (solicitante_id, estado_codigo, creado_en DESC, id DESC);
CREATE INDEX solicitudes_estado_fecha_idx ON solicitudes (estado_codigo, creado_en DESC, id DESC);
CREATE INDEX solicitudes_tipo_fechas_idx ON solicitudes (tipo_ausencia_id, fecha_inicio, fecha_fin);
CREATE INDEX solicitudes_flujo_idx ON solicitudes (flujo_id);

CREATE TABLE revisiones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL,
    flujo_id bigint NOT NULL,
    orden smallint NOT NULL,
    rol_codigo text NOT NULL,
    aprobador_id bigint REFERENCES empleados(id),
    estado text NOT NULL CHECK (estado IN ('BLOQUEADA', 'PENDIENTE', 'RESUELTA', 'OMITIDA')),
    validada_en timestamptz,
    resuelta_en timestamptz,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (solicitud_id, orden),
    UNIQUE (id, solicitud_id),
    FOREIGN KEY (solicitud_id, flujo_id) REFERENCES solicitudes(id, flujo_id),
    FOREIGN KEY (flujo_id, orden, rol_codigo) REFERENCES pasos_flujo(flujo_id, orden, rol_codigo),
    CHECK ((estado = 'RESUELTA') = (resuelta_en IS NOT NULL)),
    CHECK (rol_codigo <> 'JEFE_INMEDIATO' OR aprobador_id IS NOT NULL),
    CHECK (validada_en IS NULL OR rol_codigo = 'TALENTO_HUMANO'),
    CHECK (resuelta_en IS NULL OR resuelta_en >= creado_en),
    CHECK (validada_en IS NULL OR validada_en >= creado_en)
);
CREATE INDEX revisiones_bandeja_asignada_idx ON revisiones (aprobador_id, creado_en, solicitud_id) WHERE estado = 'PENDIENTE';
CREATE INDEX revisiones_bandeja_rol_idx ON revisiones (rol_codigo, creado_en, solicitud_id) WHERE estado = 'PENDIENTE';
CREATE INDEX revisiones_paso_idx ON revisiones (flujo_id, orden, rol_codigo);

CREATE TABLE aprobaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    revision_id bigint NOT NULL,
    solicitud_id bigint NOT NULL,
    actor_id bigint NOT NULL REFERENCES empleados(id),
    accion text NOT NULL CHECK (accion IN ('VALIDAR', 'APROBAR', 'RECHAZAR', 'VALIDAR_Y_APROBAR')),
    version_esperada bigint NOT NULL CHECK (version_esperada > 0),
    version_resultante bigint NOT NULL CHECK (version_resultante = version_esperada + 1),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (revision_id, accion),
    UNIQUE (solicitud_id, version_resultante),
    UNIQUE (id, solicitud_id),
    FOREIGN KEY (revision_id, solicitud_id) REFERENCES revisiones(id, solicitud_id)
);
CREATE UNIQUE INDEX aprobaciones_decision_final_uq ON aprobaciones (revision_id) WHERE accion <> 'VALIDAR';
CREATE INDEX aprobaciones_actor_fecha_idx ON aprobaciones (actor_id, creado_en DESC);

CREATE TABLE observaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    aprobacion_id bigint,
    actor_id bigint NOT NULL REFERENCES empleados(id),
    tipo text NOT NULL CHECK (tipo IN ('REVISION', 'VALIDACION', 'APROBACION', 'RECHAZO')),
    texto text NOT NULL CHECK (btrim(texto) <> ''),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aprobacion_id, solicitud_id) REFERENCES aprobaciones(id, solicitud_id)
);
CREATE INDEX observaciones_solicitud_fecha_idx ON observaciones (solicitud_id, creado_en, id);
CREATE INDEX observaciones_aprobacion_idx ON observaciones (aprobacion_id);
CREATE INDEX observaciones_actor_idx ON observaciones (actor_id);

CREATE TABLE versiones (
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    numero bigint NOT NULL CHECK (numero > 0),
    actor_id bigint NOT NULL REFERENCES empleados(id),
    datos jsonb NOT NULL CHECK (jsonb_typeof(datos) = 'object'),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (solicitud_id, numero)
);
CREATE INDEX versiones_actor_idx ON versiones (actor_id);

CREATE TABLE historial_solicitud (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL,
    version bigint NOT NULL,
    actor_id bigint NOT NULL REFERENCES empleados(id),
    estado_anterior text REFERENCES estados_solicitud(codigo),
    estado_nuevo text NOT NULL REFERENCES estados_solicitud(codigo),
    operacion text NOT NULL CHECK (operacion IN ('CREACION', 'ACTUALIZACION', 'CAMBIO_ESTADO')),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (solicitud_id, version),
    UNIQUE (id, solicitud_id),
    FOREIGN KEY (solicitud_id, version) REFERENCES versiones(solicitud_id, numero),
    CHECK ((operacion = 'CREACION') = (estado_anterior IS NULL)),
    CHECK (operacion <> 'CAMBIO_ESTADO' OR estado_anterior <> estado_nuevo)
);
CREATE INDEX historial_solicitud_fecha_idx ON historial_solicitud (solicitud_id, creado_en, id);
CREATE INDEX historial_actor_idx ON historial_solicitud (actor_id);

CREATE TABLE notificaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    destinatario_id bigint NOT NULL REFERENCES empleados(id),
    historial_id bigint,
    revision_id bigint,
    tipo text NOT NULL CHECK (tipo IN ('CAMBIO_ESTADO', 'PENDIENTE_REVISION')),
    canal text NOT NULL DEFAULT 'CORREO' CHECK (canal = 'CORREO'),
    prioridad text NOT NULL DEFAULT 'NORMAL' CHECK (prioridad IN ('BAJA', 'NORMAL', 'ALTA')),
    estado_envio text NOT NULL DEFAULT 'PENDIENTE' CHECK (estado_envio IN ('PENDIENTE', 'EN_PROCESO', 'ENVIADA', 'FALLIDA')),
    intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    proximo_intento_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    bloqueada_hasta timestamptz,
    enviada_en timestamptz,
    leida_en timestamptz,
    ultimo_error text CHECK (ultimo_error IS NULL OR btrim(ultimo_error) <> ''),
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (historial_id, solicitud_id) REFERENCES historial_solicitud(id, solicitud_id),
    FOREIGN KEY (revision_id, solicitud_id) REFERENCES revisiones(id, solicitud_id),
    CHECK ((tipo = 'CAMBIO_ESTADO' AND historial_id IS NOT NULL AND revision_id IS NULL) OR (tipo = 'PENDIENTE_REVISION' AND revision_id IS NOT NULL AND historial_id IS NULL)),
    CHECK ((estado_envio = 'ENVIADA') = (enviada_en IS NOT NULL)),
    CHECK ((estado_envio = 'EN_PROCESO') = (bloqueada_hasta IS NOT NULL)),
    CHECK (enviada_en IS NULL OR enviada_en >= creado_en),
    CHECK (leida_en IS NULL OR leida_en >= creado_en)
);
CREATE UNIQUE INDEX notificaciones_cambio_uq ON notificaciones (historial_id, destinatario_id) WHERE tipo = 'CAMBIO_ESTADO';
CREATE UNIQUE INDEX notificaciones_pendiente_uq ON notificaciones (revision_id, destinatario_id) WHERE tipo = 'PENDIENTE_REVISION';
CREATE INDEX notificaciones_destinatario_fecha_idx ON notificaciones (destinatario_id, creado_en DESC, id DESC);
CREATE INDEX notificaciones_envio_idx ON notificaciones (proximo_intento_en, id) WHERE estado_envio IN ('PENDIENTE', 'FALLIDA');
CREATE INDEX notificaciones_bloqueadas_idx ON notificaciones (bloqueada_hasta) WHERE estado_envio = 'EN_PROCESO';
CREATE INDEX notificaciones_solicitud_idx ON notificaciones (solicitud_id);

CREATE TABLE auditoria_acceso (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES empleados(id),
    solicitud_id bigint REFERENCES solicitudes(id),
    operacion text NOT NULL CHECK (operacion IN ('ACCESO_PORTAL', 'ACCESO_PANEL', 'CONSULTA_DETALLE', 'CONSULTA_HISTORIAL', 'CONSULTA_BANDEJA', 'CONSULTA_CATALOGO', 'ACCESO_DENEGADO')),
    autorizado boolean NOT NULL,
    direccion_ip inet,
    correlacion_id uuid,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK ((operacion = 'ACCESO_DENEGADO') = (NOT autorizado)),
    CHECK (operacion NOT IN ('CONSULTA_DETALLE', 'CONSULTA_HISTORIAL') OR solicitud_id IS NOT NULL)
);
CREATE INDEX auditoria_acceso_actor_fecha_idx ON auditoria_acceso (actor_id, creado_en DESC);
CREATE INDEX auditoria_acceso_solicitud_fecha_idx ON auditoria_acceso (solicitud_id, creado_en DESC);

CREATE TABLE auditoria_modificacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES empleados(id),
    entidad text NOT NULL CHECK (entidad IN ('solicitudes', 'tipos_ausencia', 'flujo_aprobacion', 'pasos_flujo', 'revisiones', 'aprobaciones', 'observaciones')),
    clave jsonb NOT NULL CHECK (jsonb_typeof(clave) = 'object'),
    solicitud_id bigint REFERENCES solicitudes(id),
    operacion text NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    datos_anteriores jsonb,
    datos_nuevos jsonb,
    correlacion_id uuid,
    creado_en timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (datos_anteriores IS NULL OR jsonb_typeof(datos_anteriores) = 'object'),
    CHECK (datos_nuevos IS NULL OR jsonb_typeof(datos_nuevos) = 'object'),
    CHECK ((operacion = 'INSERT' AND datos_anteriores IS NULL AND datos_nuevos IS NOT NULL) OR (operacion = 'UPDATE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NOT NULL) OR (operacion = 'DELETE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NULL))
);
CREATE INDEX auditoria_modificacion_actor_fecha_idx ON auditoria_modificacion (actor_id, creado_en DESC);
CREATE INDEX auditoria_modificacion_solicitud_fecha_idx ON auditoria_modificacion (solicitud_id, creado_en DESC);
CREATE INDEX auditoria_modificacion_entidad_fecha_idx ON auditoria_modificacion (entidad, creado_en DESC);
CREATE INDEX auditoria_modificacion_clave_idx ON auditoria_modificacion USING gin (clave);

-- Solo catálogos estructurales, sin personas ni ejemplos de pantallas.
INSERT INTO roles (codigo, nombre) VALUES
    ('EMPLEADO', 'Empleado'),
    ('JEFE_INMEDIATO', 'Jefe inmediato'),
    ('TALENTO_HUMANO', 'Talento Humano');
INSERT INTO estados_solicitud (codigo, nombre, es_final) VALUES
    ('ENVIADA', 'Enviada', false),
    ('EN_REVISION', 'En revisión', false),
    ('APROBADA', 'Aprobada', true),
    ('RECHAZADA', 'Rechazada', true),
    ('CANCELADA', 'Cancelada', true);
INSERT INTO flujo_aprobacion (codigo, nombre) VALUES
    ('JEFE_INMEDIATO', 'Jefe inmediato'),
    ('JEFE_Y_TALENTO_HUMANO', 'Jefe inmediato > Talento Humano'),
    ('TALENTO_HUMANO', 'Talento Humano');
INSERT INTO pasos_flujo (flujo_id, orden, rol_codigo)
SELECT id, 1, CASE WHEN codigo = 'TALENTO_HUMANO' THEN 'TALENTO_HUMANO' ELSE 'JEFE_INMEDIATO' END
FROM flujo_aprobacion;
INSERT INTO pasos_flujo (flujo_id, orden, rol_codigo)
SELECT id, 2, 'TALENTO_HUMANO' FROM flujo_aprobacion WHERE codigo = 'JEFE_Y_TALENTO_HUMANO';

-- El backend establece este contexto después de autenticar al actor.
CREATE FUNCTION actor_actual() RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_actor bigint;
BEGIN
    v_actor := NULLIF(current_setting('app.actor_id', true), '')::bigint;
    IF v_actor IS NULL OR NOT EXISTS (SELECT 1 FROM empleados WHERE id = v_actor AND activo) THEN
        RAISE EXCEPTION 'Se requiere un actor autenticado y activo' USING ERRCODE = '42501';
    END IF;
    RETURN v_actor;
END;
$$;

CREATE FUNCTION tiene_rol(p_actor bigint, p_rol text) RETURNS boolean
LANGUAGE sql STABLE AS $$
    SELECT EXISTS (SELECT 1 FROM empleado_roles WHERE empleado_id = p_actor AND rol_codigo = p_rol);
$$;

CREATE FUNCTION validar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_tipo tipos_ausencia%ROWTYPE;
    v_actor bigint;
    v_codigo text;
BEGIN
    v_actor := actor_actual();
    IF TG_OP = 'INSERT' THEN
        IF NEW.solicitante_id <> v_actor AND NOT (NEW.origen = 'FORMATO_OFICIAL' AND tiene_rol(v_actor, 'TALENTO_HUMANO')) THEN
            RAISE EXCEPTION 'No puede crear solicitudes para este empleado' USING ERRCODE = '42501';
        END IF;
        IF NOT EXISTS (SELECT 1 FROM empleados WHERE id = NEW.solicitante_id AND activo) THEN
            RAISE EXCEPTION 'El solicitante debe estar activo' USING ERRCODE = '23514';
        END IF;
        SELECT * INTO STRICT v_tipo FROM tipos_ausencia WHERE id = NEW.tipo_ausencia_id FOR SHARE;
        IF v_tipo.estado <> 'ACTIVO' THEN
            RAISE EXCEPTION 'El tipo de ausencia está inactivo' USING ERRCODE = '23514';
        END IF;
        NEW.requiere_motivo := v_tipo.requiere_motivo;
        NEW.permite_horas := v_tipo.permite_horas;
        NEW.flujo_id := v_tipo.flujo_id;
        SELECT codigo INTO v_codigo FROM flujo_aprobacion WHERE id = NEW.flujo_id;
        IF NEW.requiere_revision_adicional AND v_codigo = 'JEFE_INMEDIATO' THEN
            SELECT id INTO NEW.flujo_id FROM flujo_aprobacion WHERE codigo = 'JEFE_Y_TALENTO_HUMANO';
        END IF;
        IF NEW.version <> 1 OR NEW.estado_codigo <> 'ENVIADA' THEN
            RAISE EXCEPTION 'La solicitud debe comenzar enviada y en versión 1' USING ERRCODE = '23514';
        END IF;
        NEW.creado_en := clock_timestamp();
    ELSE
        IF NEW.version <> OLD.version + 1 THEN
            RAISE EXCEPTION 'Conflicto de versión de solicitud' USING ERRCODE = '40001';
        END IF;
        IF OLD.estado_codigo IN ('APROBADA', 'RECHAZADA', 'CANCELADA') THEN
            RAISE EXCEPTION 'La solicitud finalizada no puede modificarse' USING ERRCODE = '23514';
        END IF;
        IF ROW(NEW.solicitante_id, NEW.tipo_ausencia_id, NEW.flujo_id, NEW.requiere_motivo, NEW.permite_horas, NEW.requiere_revision_adicional, NEW.origen, NEW.creado_en)
            IS DISTINCT FROM ROW(OLD.solicitante_id, OLD.tipo_ausencia_id, OLD.flujo_id, OLD.requiere_motivo, OLD.permite_horas, OLD.requiere_revision_adicional, OLD.origen, OLD.creado_en) THEN
            RAISE EXCEPTION 'No pueden cambiarse la identidad ni la política de una solicitud enviada' USING ERRCODE = '23514';
        END IF;
        IF ROW(NEW.fecha_inicio, NEW.fecha_fin, NEW.hora_inicio, NEW.hora_fin, NEW.motivo, NEW.referencia_formato)
            IS DISTINCT FROM ROW(OLD.fecha_inicio, OLD.fecha_fin, OLD.hora_inicio, OLD.hora_fin, OLD.motivo, OLD.referencia_formato) THEN
            IF v_actor <> OLD.solicitante_id OR EXISTS (SELECT 1 FROM aprobaciones WHERE solicitud_id = OLD.id) THEN
                RAISE EXCEPTION 'Solo el solicitante puede editar antes de la primera acción de revisión' USING ERRCODE = '42501';
            END IF;
        END IF;
        IF NEW.estado_codigo = 'CANCELADA' AND v_actor <> OLD.solicitante_id AND NOT tiene_rol(v_actor, 'TALENTO_HUMANO') THEN
            RAISE EXCEPTION 'Cancelación no autorizada' USING ERRCODE = '42501';
        END IF;
        IF NEW.estado_codigo = 'APROBADA' AND EXISTS (SELECT 1 FROM revisiones WHERE solicitud_id = OLD.id AND estado <> 'RESUELTA') THEN
            RAISE EXCEPTION 'Faltan revisiones por resolver' USING ERRCODE = '23514';
        END IF;
        IF NEW.estado_codigo = 'RECHAZADA' AND NOT EXISTS (SELECT 1 FROM revisiones WHERE solicitud_id = OLD.id AND estado = 'RESUELTA') THEN
            RAISE EXCEPTION 'Falta la revisión que rechaza la solicitud' USING ERRCODE = '23514';
        END IF;
    END IF;
    NEW.actualizado_en := clock_timestamp();
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_validar BEFORE INSERT OR UPDATE ON solicitudes
FOR EACH ROW EXECUTE FUNCTION validar_solicitud();

CREATE FUNCTION registrar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_historial bigint;
    v_jefe bigint;
    v_paso record;
    v_anterior text;
    v_operacion text;
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_anterior := NULL;
        v_operacion := 'CREACION';
    ELSE
        v_anterior := OLD.estado_codigo;
        v_operacion := CASE WHEN NEW.estado_codigo <> OLD.estado_codigo THEN 'CAMBIO_ESTADO' ELSE 'ACTUALIZACION' END;
    END IF;
    INSERT INTO versiones (solicitud_id, numero, actor_id, datos)
    VALUES (NEW.id, NEW.version, actor_actual(), to_jsonb(NEW));
    INSERT INTO historial_solicitud (solicitud_id, version, actor_id, estado_anterior, estado_nuevo, operacion)
    VALUES (NEW.id, NEW.version, actor_actual(), v_anterior, NEW.estado_codigo, v_operacion)
    RETURNING id INTO v_historial;
    IF TG_OP = 'UPDATE' AND NEW.estado_codigo <> OLD.estado_codigo THEN
        INSERT INTO notificaciones (solicitud_id, destinatario_id, historial_id, tipo)
        VALUES (NEW.id, NEW.solicitante_id, v_historial, 'CAMBIO_ESTADO');
    END IF;
    IF TG_OP = 'INSERT' THEN
        SELECT jefe_inmediato_id INTO v_jefe FROM empleados WHERE id = NEW.solicitante_id;
        FOR v_paso IN SELECT * FROM pasos_flujo WHERE flujo_id = NEW.flujo_id ORDER BY orden LOOP
            IF v_paso.rol_codigo = 'JEFE_INMEDIATO' AND (v_jefe IS NULL OR NOT tiene_rol(v_jefe, 'JEFE_INMEDIATO') OR NOT EXISTS (SELECT 1 FROM empleados WHERE id = v_jefe AND activo)) THEN
                RAISE EXCEPTION 'El flujo requiere un jefe inmediato activo y autorizado' USING ERRCODE = '23514';
            END IF;
            INSERT INTO revisiones (solicitud_id, flujo_id, orden, rol_codigo, aprobador_id, estado)
            VALUES (NEW.id, NEW.flujo_id, v_paso.orden, v_paso.rol_codigo,
                CASE WHEN v_paso.rol_codigo = 'JEFE_INMEDIATO' THEN v_jefe ELSE NULL END,
                CASE WHEN v_paso.orden = 1 THEN 'PENDIENTE' ELSE 'BLOQUEADA' END);
        END LOOP;
    ELSIF NEW.estado_codigo = 'CANCELADA' THEN
        UPDATE revisiones SET estado = 'OMITIDA' WHERE solicitud_id = NEW.id AND estado IN ('PENDIENTE', 'BLOQUEADA');
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_registrar AFTER INSERT OR UPDATE ON solicitudes
FOR EACH ROW EXECUTE FUNCTION registrar_solicitud();

CREATE FUNCTION notificar_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.estado = 'PENDIENTE' THEN
        IF TG_OP = 'UPDATE' THEN
            IF OLD.estado = 'PENDIENTE' AND OLD.aprobador_id IS NOT DISTINCT FROM NEW.aprobador_id THEN
                RETURN NEW;
            END IF;
        END IF;
        INSERT INTO notificaciones (solicitud_id, destinatario_id, revision_id, tipo)
        SELECT NEW.solicitud_id, e.id, NEW.id, 'PENDIENTE_REVISION'
        FROM empleados e JOIN empleado_roles er ON er.empleado_id = e.id
        WHERE e.activo AND er.rol_codigo = NEW.rol_codigo
          AND (NEW.aprobador_id IS NULL OR e.id = NEW.aprobador_id)
          AND e.id <> (SELECT solicitante_id FROM solicitudes WHERE id = NEW.solicitud_id)
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER revisiones_notificar AFTER INSERT OR UPDATE ON revisiones
FOR EACH ROW EXECUTE FUNCTION notificar_revision();

-- Una validación no cierra la revisión; una decisión final sí.
CREATE FUNCTION procesar_aprobacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_solicitud solicitudes%ROWTYPE;
    v_revision revisiones%ROWTYPE;
    v_estado text;
    v_siguiente bigint;
BEGIN
    IF NEW.actor_id <> actor_actual() THEN
        RAISE EXCEPTION 'El actor de la acción no coincide con la sesión' USING ERRCODE = '42501';
    END IF;
    SELECT * INTO STRICT v_solicitud FROM solicitudes WHERE id = NEW.solicitud_id FOR UPDATE;
    IF v_solicitud.version <> NEW.version_esperada THEN
        RAISE EXCEPTION 'Conflicto concurrente: la versión de la solicitud cambió' USING ERRCODE = '40001';
    END IF;
    IF v_solicitud.estado_codigo NOT IN ('ENVIADA', 'EN_REVISION') THEN
        RAISE EXCEPTION 'La solicitud no admite decisiones' USING ERRCODE = '23514';
    END IF;
    SELECT * INTO STRICT v_revision FROM revisiones WHERE id = NEW.revision_id AND solicitud_id = NEW.solicitud_id FOR UPDATE;
    IF v_revision.estado <> 'PENDIENTE' THEN
        RAISE EXCEPTION 'La revisión no está pendiente' USING ERRCODE = '23514';
    END IF;
    IF NEW.actor_id = v_solicitud.solicitante_id OR NOT tiene_rol(NEW.actor_id, v_revision.rol_codigo)
        OR (v_revision.aprobador_id IS NOT NULL AND v_revision.aprobador_id <> NEW.actor_id) THEN
        RAISE EXCEPTION 'No está autorizado para decidir esta revisión' USING ERRCODE = '42501';
    END IF;
    IF NEW.accion IN ('VALIDAR', 'VALIDAR_Y_APROBAR') AND v_revision.rol_codigo <> 'TALENTO_HUMANO' THEN
        RAISE EXCEPTION 'La validación corresponde a Talento Humano' USING ERRCODE = '42501';
    END IF;
    NEW.version_resultante := NEW.version_esperada + 1;
    NEW.creado_en := clock_timestamp();
    IF NEW.accion = 'VALIDAR' THEN
        IF v_revision.validada_en IS NOT NULL THEN
            RAISE EXCEPTION 'La revisión ya fue validada' USING ERRCODE = '23505';
        END IF;
        UPDATE revisiones SET validada_en = NEW.creado_en WHERE id = v_revision.id;
        v_estado := 'EN_REVISION';
    ELSE
        UPDATE revisiones
        SET estado = 'RESUELTA', resuelta_en = NEW.creado_en,
            validada_en = CASE WHEN NEW.accion = 'VALIDAR_Y_APROBAR' THEN COALESCE(validada_en, NEW.creado_en) ELSE validada_en END
        WHERE id = v_revision.id;
        IF NEW.accion = 'RECHAZAR' THEN
            UPDATE revisiones SET estado = 'OMITIDA' WHERE solicitud_id = NEW.solicitud_id AND estado = 'BLOQUEADA';
            v_estado := 'RECHAZADA';
        ELSE
            SELECT id INTO v_siguiente FROM revisiones
            WHERE solicitud_id = NEW.solicitud_id AND estado = 'BLOQUEADA' ORDER BY orden LIMIT 1;
            IF v_siguiente IS NULL THEN
                v_estado := 'APROBADA';
            ELSE
                UPDATE revisiones SET estado = 'PENDIENTE' WHERE id = v_siguiente;
                v_estado := 'EN_REVISION';
            END IF;
        END IF;
    END IF;
    UPDATE solicitudes SET estado_codigo = v_estado, version = NEW.version_resultante
    WHERE id = NEW.solicitud_id AND version = NEW.version_esperada;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'Conflicto de versión' USING ERRCODE = '40001';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER aprobaciones_procesar BEFORE INSERT ON aprobaciones
FOR EACH ROW EXECUTE FUNCTION procesar_aprobacion();

CREATE FUNCTION validar_observacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_solicitante bigint;
    v_accion text;
    v_actor bigint;
BEGIN
    v_actor := actor_actual();
    IF NEW.actor_id <> v_actor THEN
        RAISE EXCEPTION 'El actor de la observación no coincide con la sesión' USING ERRCODE = '42501';
    END IF;
    SELECT solicitante_id INTO STRICT v_solicitante FROM solicitudes WHERE id = NEW.solicitud_id;
    IF v_actor = v_solicitante OR NOT EXISTS (
        SELECT 1 FROM revisiones r WHERE r.solicitud_id = NEW.solicitud_id
          AND tiene_rol(v_actor, r.rol_codigo)
          AND (r.aprobador_id IS NULL OR r.aprobador_id = v_actor)
    ) THEN
        RAISE EXCEPTION 'Observación de revisión no autorizada' USING ERRCODE = '42501';
    END IF;
    IF NEW.aprobacion_id IS NOT NULL THEN
        SELECT accion INTO STRICT v_accion FROM aprobaciones
        WHERE id = NEW.aprobacion_id AND solicitud_id = NEW.solicitud_id AND actor_id = v_actor;
        IF (NEW.tipo = 'RECHAZO' AND v_accion <> 'RECHAZAR')
            OR (NEW.tipo = 'APROBACION' AND v_accion NOT IN ('APROBAR', 'VALIDAR_Y_APROBAR'))
            OR (NEW.tipo = 'VALIDACION' AND v_accion NOT IN ('VALIDAR', 'VALIDAR_Y_APROBAR')) THEN
            RAISE EXCEPTION 'La observación no corresponde a la acción' USING ERRCODE = '23514';
        END IF;
    END IF;
    NEW.creado_en := clock_timestamp();
    RETURN NEW;
END;
$$;
CREATE TRIGGER observaciones_validar BEFORE INSERT ON observaciones
FOR EACH ROW EXECUTE FUNCTION validar_observacion();

CREATE FUNCTION auditar_modificacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_anterior jsonb;
    v_nuevo jsonb;
    v_fila jsonb;
    v_clave jsonb;
    v_solicitud bigint;
    v_actor bigint;
BEGIN
    v_actor := actor_actual();
    IF TG_OP <> 'INSERT' THEN v_anterior := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN v_nuevo := to_jsonb(NEW); END IF;
    v_fila := COALESCE(v_nuevo, v_anterior);
    IF TG_TABLE_NAME IN ('tipos_ausencia', 'flujo_aprobacion', 'pasos_flujo') AND NOT tiene_rol(v_actor, 'TALENTO_HUMANO') THEN
        RAISE EXCEPTION 'La administración del catálogo requiere Talento Humano' USING ERRCODE = '42501';
    END IF;
    IF TG_TABLE_NAME = 'pasos_flujo' THEN
        v_clave := jsonb_build_object('flujo_id', v_fila->'flujo_id', 'orden', v_fila->'orden');
    ELSE
        v_clave := jsonb_build_object('id', v_fila->'id');
    END IF;
    IF TG_TABLE_NAME = 'solicitudes' THEN
        v_solicitud := (v_fila->>'id')::bigint;
    ELSE
        v_solicitud := (v_fila->>'solicitud_id')::bigint;
    END IF;
    INSERT INTO auditoria_modificacion (actor_id, entidad, clave, solicitud_id, operacion, datos_anteriores, datos_nuevos, correlacion_id)
    VALUES (v_actor, TG_TABLE_NAME, v_clave, v_solicitud, TG_OP, v_anterior, v_nuevo,
        NULLIF(current_setting('app.correlacion_id', true), '')::uuid);
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_auditar AFTER INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER tipos_ausencia_auditar AFTER INSERT OR UPDATE OR DELETE ON tipos_ausencia FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER flujo_aprobacion_auditar AFTER INSERT OR UPDATE OR DELETE ON flujo_aprobacion FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER pasos_flujo_auditar AFTER INSERT OR UPDATE OR DELETE ON pasos_flujo FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER revisiones_auditar AFTER INSERT OR UPDATE ON revisiones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER aprobaciones_auditar AFTER INSERT ON aprobaciones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER observaciones_auditar AFTER INSERT ON observaciones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();

CREATE FUNCTION actualizar_fecha_catalogo() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.actualizado_en := clock_timestamp();
    RETURN NEW;
END;
$$;
CREATE TRIGGER tipos_ausencia_fecha BEFORE UPDATE ON tipos_ausencia FOR EACH ROW EXECUTE FUNCTION actualizar_fecha_catalogo();

CREATE FUNCTION impedir_cambio_historico() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro histórico es inmutable' USING ERRCODE = '42501';
END;
$$;
CREATE TRIGGER solicitudes_no_borrar BEFORE DELETE ON solicitudes FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER revisiones_no_borrar BEFORE DELETE ON revisiones FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER aprobaciones_inmutables BEFORE UPDATE OR DELETE ON aprobaciones FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER observaciones_inmutables BEFORE UPDATE OR DELETE ON observaciones FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER versiones_inmutables BEFORE UPDATE OR DELETE ON versiones FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER historial_inmutable BEFORE UPDATE OR DELETE ON historial_solicitud FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER auditoria_acceso_inmutable BEFORE UPDATE OR DELETE ON auditoria_acceso FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER auditoria_modificacion_inmutable BEFORE UPDATE OR DELETE ON auditoria_modificacion FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();

-- Las lecturas sensibles se auditan explícitamente desde el servicio.
CREATE FUNCTION registrar_acceso(
    p_operacion text,
    p_solicitud_id bigint DEFAULT NULL,
    p_autorizado boolean DEFAULT true,
    p_direccion_ip inet DEFAULT NULL
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_id bigint;
BEGIN
    INSERT INTO auditoria_acceso (actor_id, solicitud_id, operacion, autorizado, direccion_ip, correlacion_id)
    VALUES (actor_actual(), p_solicitud_id, p_operacion, p_autorizado, p_direccion_ip,
        NULLIF(current_setting('app.correlacion_id', true), '')::uuid)
    RETURNING id INTO v_id;
    RETURN v_id;
END;
$$;

-- Los flujos definidos por las pantallas son estructurales e inmutables.
CREATE TRIGGER flujo_aprobacion_inmutable BEFORE UPDATE OR DELETE ON flujo_aprobacion FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();
CREATE TRIGGER pasos_flujo_inmutables BEFORE UPDATE OR DELETE ON pasos_flujo FOR EACH ROW EXECUTE FUNCTION impedir_cambio_historico();

COMMIT;