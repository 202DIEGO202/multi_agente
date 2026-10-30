BEGIN;

-- Identidades externas; no se almacenan credenciales.
CREATE TABLE usuarios (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identidad_externa text NOT NULL UNIQUE CHECK (btrim(identidad_externa) <> ''),
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    documento varchar(50) NOT NULL UNIQUE CHECK (btrim(documento) <> ''),
    correo text NOT NULL CHECK (correo ~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'),
    area text NOT NULL CHECK (btrim(area) <> ''),
    cargo text NOT NULL CHECK (btrim(cargo) <> ''),
    turno text CHECK (turno IS NULL OR btrim(turno) <> ''),
    jefe_inmediato_id bigint REFERENCES usuarios(id),
    activo boolean NOT NULL DEFAULT true,
    creado_en timestamptz NOT NULL DEFAULT now(),
    CHECK (jefe_inmediato_id IS NULL OR jefe_inmediato_id <> id)
);
CREATE UNIQUE INDEX usuarios_correo_uq ON usuarios (lower(correo));
CREATE INDEX usuarios_jefe_idx ON usuarios (jefe_inmediato_id);

CREATE TABLE roles (
    codigo varchar(30) PRIMARY KEY CHECK (codigo IN ('EMPLEADO', 'JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    nombre text NOT NULL CHECK (btrim(nombre) <> '')
);
INSERT INTO roles (codigo, nombre) VALUES
    ('EMPLEADO', 'Empleado'),
    ('JEFE_INMEDIATO', 'Jefe inmediato'),
    ('TALENTO_HUMANO', 'Talento Humano');

CREATE TABLE usuario_roles (
    usuario_id bigint NOT NULL REFERENCES usuarios(id),
    rol_codigo varchar(30) NOT NULL REFERENCES roles(codigo),
    PRIMARY KEY (usuario_id, rol_codigo)
);
CREATE INDEX usuario_roles_rol_idx ON usuario_roles (rol_codigo, usuario_id);

CREATE TABLE estados_solicitud (
    codigo varchar(30) PRIMARY KEY CHECK (codigo IN ('ENVIADA', 'EN_REVISION', 'APROBADA', 'RECHAZADA')),
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    terminal boolean NOT NULL,
    CHECK (terminal = (codigo IN ('APROBADA', 'RECHAZADA')))
);
INSERT INTO estados_solicitud (codigo, nombre, terminal) VALUES
    ('ENVIADA', 'Enviada', false),
    ('EN_REVISION', 'En revisión', false),
    ('APROBADA', 'Aprobada', true),
    ('RECHAZADA', 'Rechazada', true);

CREATE TABLE flujo_aprobacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    codigo varchar(40) NOT NULL UNIQUE CHECK (codigo IN ('JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO', 'TALENTO_HUMANO')),
    nombre text NOT NULL CHECK (btrim(nombre) <> '')
);
INSERT INTO flujo_aprobacion (codigo, nombre) VALUES
    ('JEFE_INMEDIATO', 'Jefe inmediato'),
    ('JEFE_Y_TALENTO_HUMANO', 'Jefe inmediato > Talento Humano'),
    ('TALENTO_HUMANO', 'Talento Humano');

CREATE TABLE etapas_flujo (
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    orden smallint NOT NULL CHECK (orden BETWEEN 1 AND 2),
    rol_codigo varchar(30) NOT NULL REFERENCES roles(codigo) CHECK (rol_codigo IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    requiere_validacion boolean NOT NULL DEFAULT false,
    PRIMARY KEY (flujo_id, orden),
    UNIQUE (flujo_id, orden, rol_codigo),
    CHECK (NOT requiere_validacion OR rol_codigo = 'TALENTO_HUMANO')
);
INSERT INTO etapas_flujo (flujo_id, orden, rol_codigo, requiere_validacion)
SELECT id, 1, 'JEFE_INMEDIATO', false FROM flujo_aprobacion
WHERE codigo IN ('JEFE_INMEDIATO', 'JEFE_Y_TALENTO_HUMANO');
INSERT INTO etapas_flujo (flujo_id, orden, rol_codigo, requiere_validacion)
SELECT id, CASE WHEN codigo = 'TALENTO_HUMANO' THEN 1 ELSE 2 END, 'TALENTO_HUMANO', true
FROM flujo_aprobacion WHERE codigo IN ('TALENTO_HUMANO', 'JEFE_Y_TALENTO_HUMANO');

CREATE TABLE tipos_ausencia (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nombre text NOT NULL CHECK (btrim(nombre) <> ''),
    estado varchar(10) NOT NULL DEFAULT 'ACTIVO' CHECK (estado IN ('ACTIVO', 'INACTIVO')),
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    requiere_motivo boolean NOT NULL DEFAULT false,
    modalidad_horas varchar(15) NOT NULL DEFAULT 'OPCIONAL' CHECK (modalidad_horas IN ('NO_APLICA', 'OPCIONAL', 'OBLIGATORIA')),
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX tipos_ausencia_nombre_uq ON tipos_ausencia (lower(btrim(nombre)));
CREATE INDEX tipos_ausencia_estado_idx ON tipos_ausencia (estado, nombre);
CREATE INDEX tipos_ausencia_flujo_idx ON tipos_ausencia (flujo_id);

-- Las reglas y el flujo se conservan como instantánea de la solicitud.
CREATE TABLE solicitudes (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitante_id bigint NOT NULL REFERENCES usuarios(id),
    tipo_ausencia_id bigint NOT NULL REFERENCES tipos_ausencia(id),
    flujo_id bigint NOT NULL REFERENCES flujo_aprobacion(id),
    estado_codigo varchar(30) NOT NULL DEFAULT 'ENVIADA' REFERENCES estados_solicitud(codigo),
    origen varchar(20) NOT NULL DEFAULT 'PORTAL_INTERNO' CHECK (origen IN ('PORTAL_INTERNO', 'FORMATO_OFICIAL')),
    referencia_formato text CHECK (referencia_formato IS NULL OR btrim(referencia_formato) <> ''),
    fecha_inicio date NOT NULL,
    fecha_fin date NOT NULL,
    hora_inicio time without time zone,
    hora_fin time without time zone,
    motivo text CHECK (motivo IS NULL OR btrim(motivo) <> ''),
    requiere_motivo boolean NOT NULL,
    modalidad_horas varchar(15) NOT NULL CHECK (modalidad_horas IN ('NO_APLICA', 'OPCIONAL', 'OBLIGATORIA')),
    requiere_revision_adicional boolean NOT NULL DEFAULT false,
    version bigint NOT NULL DEFAULT 1 CHECK (version > 0),
    creado_en timestamptz NOT NULL DEFAULT now(),
    actualizado_en timestamptz NOT NULL DEFAULT now(),
    UNIQUE (id, flujo_id),
    CHECK (fecha_fin >= fecha_inicio),
    CHECK ((hora_inicio IS NULL) = (hora_fin IS NULL)),
    CHECK (hora_inicio IS NULL OR fecha_fin + hora_fin > fecha_inicio + hora_inicio),
    CHECK (NOT requiere_motivo OR (motivo IS NOT NULL AND btrim(motivo) <> '')),
    CHECK (modalidad_horas <> 'NO_APLICA' OR hora_inicio IS NULL),
    CHECK (modalidad_horas <> 'OBLIGATORIA' OR hora_inicio IS NOT NULL),
    CHECK (actualizado_en >= creado_en)
);
CREATE INDEX solicitudes_empleado_estado_idx ON solicitudes (solicitante_id, estado_codigo, creado_en DESC, id DESC);
CREATE INDEX solicitudes_estado_idx ON solicitudes (estado_codigo, creado_en, id);
CREATE INDEX solicitudes_tipo_fechas_idx ON solicitudes (tipo_ausencia_id, fecha_inicio, fecha_fin);
CREATE INDEX solicitudes_flujo_idx ON solicitudes (flujo_id);

CREATE TABLE revisiones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL,
    flujo_id bigint NOT NULL,
    orden smallint NOT NULL CHECK (orden BETWEEN 1 AND 2),
    rol_codigo varchar(30) NOT NULL CHECK (rol_codigo IN ('JEFE_INMEDIATO', 'TALENTO_HUMANO')),
    aprobador_id bigint NOT NULL,
    estado varchar(15) NOT NULL DEFAULT 'EN_ESPERA' CHECK (estado IN ('EN_ESPERA', 'PENDIENTE', 'APROBADA', 'RECHAZADA', 'OMITIDA')),
    requiere_validacion boolean NOT NULL DEFAULT false,
    validada_por_id bigint REFERENCES usuarios(id),
    validada_en timestamptz,
    creado_en timestamptz NOT NULL DEFAULT now(),
    resuelta_en timestamptz,
    UNIQUE (solicitud_id, orden),
    UNIQUE (id, solicitud_id),
    FOREIGN KEY (solicitud_id, flujo_id) REFERENCES solicitudes(id, flujo_id),
    FOREIGN KEY (flujo_id, orden, rol_codigo) REFERENCES etapas_flujo(flujo_id, orden, rol_codigo),
    FOREIGN KEY (aprobador_id, rol_codigo) REFERENCES usuario_roles(usuario_id, rol_codigo),
    CHECK (NOT requiere_validacion OR rol_codigo = 'TALENTO_HUMANO'),
    CHECK ((validada_por_id IS NULL) = (validada_en IS NULL)),
    CHECK (validada_por_id IS NULL OR validada_por_id = aprobador_id),
    CHECK ((estado IN ('APROBADA', 'RECHAZADA', 'OMITIDA')) = (resuelta_en IS NOT NULL)),
    CHECK (estado <> 'APROBADA' OR NOT requiere_validacion OR validada_en IS NOT NULL),
    CHECK (validada_en IS NULL OR validada_en >= creado_en),
    CHECK (resuelta_en IS NULL OR resuelta_en >= creado_en)
);
CREATE INDEX revisiones_bandeja_idx ON revisiones (aprobador_id, creado_en, solicitud_id) WHERE estado = 'PENDIENTE';
CREATE INDEX revisiones_flujo_idx ON revisiones (flujo_id, orden);
CREATE INDEX revisiones_rol_usuario_idx ON revisiones (aprobador_id, rol_codigo);

CREATE TABLE aprobaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    revision_id bigint NOT NULL UNIQUE REFERENCES revisiones(id),
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    decision varchar(20) NOT NULL CHECK (decision IN ('APROBAR', 'RECHAZAR', 'VALIDAR_APROBAR')),
    version_esperada bigint NOT NULL CHECK (version_esperada > 0),
    decidido_en timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX aprobaciones_actor_fecha_idx ON aprobaciones (actor_id, decidido_en DESC);

CREATE TABLE observaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    revision_id bigint,
    aprobacion_id bigint REFERENCES aprobaciones(id),
    autor_id bigint NOT NULL REFERENCES usuarios(id),
    texto text NOT NULL CHECK (btrim(texto) <> ''),
    creado_en timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (revision_id, solicitud_id) REFERENCES revisiones(id, solicitud_id),
    CHECK (aprobacion_id IS NULL OR revision_id IS NOT NULL)
);
CREATE INDEX observaciones_solicitud_fecha_idx ON observaciones (solicitud_id, creado_en, id);
CREATE INDEX observaciones_revision_idx ON observaciones (revision_id);
CREATE INDEX observaciones_aprobacion_idx ON observaciones (aprobacion_id);
CREATE INDEX observaciones_autor_idx ON observaciones (autor_id);

CREATE TABLE historial_solicitud (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    operacion varchar(20) NOT NULL CHECK (operacion IN ('CREAR', 'MODIFICAR', 'CAMBIAR_ESTADO', 'VALIDAR')),
    estado_anterior varchar(30) REFERENCES estados_solicitud(codigo),
    estado_nuevo varchar(30) NOT NULL REFERENCES estados_solicitud(codigo),
    version bigint NOT NULL CHECK (version > 0),
    detalle jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detalle) = 'object'),
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    CHECK (operacion <> 'CREAR' OR estado_anterior IS NULL)
);
CREATE INDEX historial_solicitud_fecha_idx ON historial_solicitud (solicitud_id, ocurrido_en, id);
CREATE INDEX historial_actor_idx ON historial_solicitud (actor_id);

CREATE TABLE notificaciones (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    solicitud_id bigint NOT NULL REFERENCES solicitudes(id),
    destinatario_id bigint NOT NULL REFERENCES usuarios(id),
    historial_id bigint REFERENCES historial_solicitud(id),
    revision_id bigint,
    tipo varchar(20) NOT NULL CHECK (tipo IN ('CAMBIO_ESTADO', 'REVISION_PENDIENTE')),
    canal varchar(10) NOT NULL DEFAULT 'CORREO' CHECK (canal = 'CORREO'),
    prioridad varchar(10) NOT NULL DEFAULT 'NORMAL' CHECK (prioridad = 'NORMAL'),
    correo_destino text NOT NULL CHECK (correo_destino ~ '^[^[:space:]@]+@[^[:space:]@]+[.][^[:space:]@]+$'),
    asunto text NOT NULL CHECK (btrim(asunto) <> ''),
    contenido text NOT NULL CHECK (btrim(contenido) <> ''),
    estado_envio varchar(15) NOT NULL DEFAULT 'PENDIENTE' CHECK (estado_envio IN ('PENDIENTE', 'EN_PROCESO', 'ENVIADA', 'FALLIDA')),
    intentos integer NOT NULL DEFAULT 0 CHECK (intentos >= 0),
    ultimo_error text,
    creado_en timestamptz NOT NULL DEFAULT now(),
    proximo_intento_en timestamptz NOT NULL DEFAULT now(),
    enviada_en timestamptz,
    leida_en timestamptz,
    FOREIGN KEY (revision_id, solicitud_id) REFERENCES revisiones(id, solicitud_id),
    CHECK ((tipo = 'CAMBIO_ESTADO' AND historial_id IS NOT NULL AND revision_id IS NULL) OR (tipo = 'REVISION_PENDIENTE' AND revision_id IS NOT NULL AND historial_id IS NULL)),
    CHECK ((estado_envio = 'ENVIADA') = (enviada_en IS NOT NULL)),
    CHECK (enviada_en IS NULL OR enviada_en >= creado_en),
    CHECK (leida_en IS NULL OR leida_en >= creado_en)
);
CREATE UNIQUE INDEX notificaciones_historial_uq ON notificaciones (historial_id, destinatario_id) WHERE historial_id IS NOT NULL;
CREATE UNIQUE INDEX notificaciones_revision_uq ON notificaciones (revision_id, destinatario_id) WHERE revision_id IS NOT NULL;
CREATE INDEX notificaciones_cola_idx ON notificaciones (proximo_intento_en, id) WHERE estado_envio IN ('PENDIENTE', 'FALLIDA');
CREATE INDEX notificaciones_destinatario_idx ON notificaciones (destinatario_id, creado_en DESC, id DESC);
CREATE INDEX notificaciones_solicitud_idx ON notificaciones (solicitud_id);

CREATE TABLE auditoria_acceso (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    solicitud_id bigint REFERENCES solicitudes(id),
    operacion varchar(30) NOT NULL CHECK (operacion IN ('ACCESO', 'CONSULTAR_DETALLE', 'CONSULTAR_HISTORIAL', 'CONSULTAR_BANDEJA', 'CONSULTAR_CATALOGO', 'CONSULTAR_AUDITORIA')),
    autorizado boolean NOT NULL,
    direccion_ip inet,
    identificador_peticion text CHECK (identificador_peticion IS NULL OR btrim(identificador_peticion) <> ''),
    detalle jsonb NOT NULL DEFAULT '{}'::jsonb CHECK (jsonb_typeof(detalle) = 'object'),
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    CHECK (operacion NOT IN ('CONSULTAR_DETALLE', 'CONSULTAR_HISTORIAL') OR solicitud_id IS NOT NULL)
);
CREATE INDEX auditoria_acceso_actor_fecha_idx ON auditoria_acceso (actor_id, ocurrido_en DESC);
CREATE INDEX auditoria_acceso_solicitud_fecha_idx ON auditoria_acceso (solicitud_id, ocurrido_en DESC);

CREATE TABLE auditoria_modificacion (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    actor_id bigint NOT NULL REFERENCES usuarios(id),
    entidad varchar(40) NOT NULL CHECK (entidad IN ('usuarios', 'usuario_roles', 'tipos_ausencia', 'solicitudes', 'revisiones', 'aprobaciones', 'observaciones')),
    entidad_clave jsonb NOT NULL CHECK (jsonb_typeof(entidad_clave) = 'object'),
    operacion varchar(10) NOT NULL CHECK (operacion IN ('INSERT', 'UPDATE', 'DELETE')),
    datos_anteriores jsonb,
    datos_nuevos jsonb,
    ocurrido_en timestamptz NOT NULL DEFAULT now(),
    CHECK (datos_anteriores IS NULL OR jsonb_typeof(datos_anteriores) = 'object'),
    CHECK (datos_nuevos IS NULL OR jsonb_typeof(datos_nuevos) = 'object'),
    CHECK ((operacion = 'INSERT' AND datos_anteriores IS NULL AND datos_nuevos IS NOT NULL) OR (operacion = 'UPDATE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NOT NULL) OR (operacion = 'DELETE' AND datos_anteriores IS NOT NULL AND datos_nuevos IS NULL))
);
CREATE INDEX auditoria_modificacion_actor_fecha_idx ON auditoria_modificacion (actor_id, ocurrido_en DESC);
CREATE INDEX auditoria_modificacion_entidad_fecha_idx ON auditoria_modificacion (entidad, ocurrido_en DESC);
CREATE INDEX auditoria_modificacion_clave_idx ON auditoria_modificacion USING gin (entidad_clave);

-- El backend establece app.usuario_id con set_config(..., true).
CREATE FUNCTION actor_actual() RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_actor bigint;
BEGIN
    v_actor := nullif(current_setting('app.usuario_id', true), '')::bigint;
    IF v_actor IS NULL OR NOT EXISTS (SELECT 1 FROM usuarios WHERE id = v_actor AND activo) THEN
        RAISE EXCEPTION 'Se requiere un actor autenticado y activo' USING ERRCODE = '42501';
    END IF;
    RETURN v_actor;
END;
$$;

CREATE FUNCTION auditar_modificacion() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_anterior jsonb;
    v_nuevo jsonb;
    v_fila jsonb;
    v_clave jsonb;
BEGIN
    IF TG_OP <> 'INSERT' THEN v_anterior := to_jsonb(OLD); END IF;
    IF TG_OP <> 'DELETE' THEN v_nuevo := to_jsonb(NEW); END IF;
    v_fila := coalesce(v_nuevo, v_anterior);
    IF TG_TABLE_NAME = 'usuario_roles' THEN
        v_clave := jsonb_build_object('usuario_id', v_fila->'usuario_id', 'rol_codigo', v_fila->'rol_codigo');
    ELSE
        v_clave := jsonb_build_object('id', v_fila->'id');
    END IF;
    INSERT INTO auditoria_modificacion (actor_id, entidad, entidad_clave, operacion, datos_anteriores, datos_nuevos)
    VALUES (actor_actual(), TG_TABLE_NAME, v_clave, TG_OP, v_anterior, v_nuevo);
    RETURN NULL;
END;
$$;

CREATE FUNCTION preparar_solicitud() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_tipo tipos_ausencia%ROWTYPE;
    v_flujo bigint;
BEGIN
    PERFORM actor_actual();
    IF TG_OP = 'INSERT' THEN
        SELECT * INTO STRICT v_tipo FROM tipos_ausencia WHERE id = NEW.tipo_ausencia_id FOR SHARE;
        IF v_tipo.estado <> 'ACTIVO' THEN
            RAISE EXCEPTION 'El tipo de ausencia está inactivo' USING ERRCODE = '23514';
        END IF;
        IF NEW.estado_codigo <> 'ENVIADA' THEN
            RAISE EXCEPTION 'La solicitud debe comenzar enviada' USING ERRCODE = '23514';
        END IF;
        v_flujo := v_tipo.flujo_id;
        IF NEW.requiere_revision_adicional THEN
            SELECT id INTO v_flujo FROM flujo_aprobacion
            WHERE codigo = CASE WHEN (SELECT codigo FROM flujo_aprobacion WHERE id = v_tipo.flujo_id) = 'JEFE_INMEDIATO'
                                THEN 'JEFE_Y_TALENTO_HUMANO'
                                ELSE (SELECT codigo FROM flujo_aprobacion WHERE id = v_tipo.flujo_id) END;
        END IF;
        NEW.flujo_id := v_flujo;
        NEW.requiere_motivo := v_tipo.requiere_motivo;
        NEW.modalidad_horas := v_tipo.modalidad_horas;
        NEW.version := 1;
        NEW.creado_en := now();
    ELSE
        IF (NEW.solicitante_id, NEW.tipo_ausencia_id, NEW.flujo_id, NEW.requiere_motivo, NEW.modalidad_horas, NEW.requiere_revision_adicional, NEW.creado_en)
           IS DISTINCT FROM (OLD.solicitante_id, OLD.tipo_ausencia_id, OLD.flujo_id, OLD.requiere_motivo, OLD.modalidad_horas, OLD.requiere_revision_adicional, OLD.creado_en) THEN
            RAISE EXCEPTION 'No se puede alterar la instantánea de una solicitud' USING ERRCODE = '23514';
        END IF;
        IF NEW.version <> OLD.version THEN
            RAISE EXCEPTION 'La versión es administrada por la base de datos' USING ERRCODE = '40001';
        END IF;
        IF NEW.estado_codigo IS DISTINCT FROM OLD.estado_codigo THEN
            IF OLD.estado_codigo IN ('APROBADA', 'RECHAZADA') OR NEW.estado_codigo = 'ENVIADA' THEN
                RAISE EXCEPTION 'Transición de estado no permitida' USING ERRCODE = '23514';
            END IF;
            IF NEW.estado_codigo IN ('APROBADA', 'RECHAZADA') AND NOT EXISTS (
                SELECT 1 FROM aprobaciones a JOIN revisiones r ON r.id = a.revision_id
                WHERE r.solicitud_id = OLD.id AND a.version_esperada = OLD.version
                  AND ((NEW.estado_codigo = 'RECHAZADA' AND a.decision = 'RECHAZAR') OR
                       (NEW.estado_codigo = 'APROBADA' AND a.decision IN ('APROBAR', 'VALIDAR_APROBAR')
                        AND NOT EXISTS (SELECT 1 FROM revisiones r2 WHERE r2.solicitud_id = OLD.id AND r2.estado <> 'APROBADA')))
            ) THEN
                RAISE EXCEPTION 'El estado final requiere una decisión válida' USING ERRCODE = '23514';
            END IF;
        END IF;
        NEW.version := OLD.version + 1;
    END IF;
    NEW.actualizado_en := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER solicitudes_preparar BEFORE INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION preparar_solicitud();

CREATE FUNCTION registrar_historial() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_historial bigint;
    v_anterior varchar(30);
    v_operacion varchar(20);
BEGIN
    IF TG_OP = 'INSERT' THEN
        v_operacion := 'CREAR';
    ELSE
        v_anterior := OLD.estado_codigo;
        v_operacion := CASE WHEN OLD.estado_codigo IS DISTINCT FROM NEW.estado_codigo THEN 'CAMBIAR_ESTADO' ELSE 'MODIFICAR' END;
    END IF;
    INSERT INTO historial_solicitud (solicitud_id, actor_id, operacion, estado_anterior, estado_nuevo, version, detalle)
    VALUES (NEW.id, actor_actual(), v_operacion, v_anterior, NEW.estado_codigo, NEW.version,
            jsonb_build_object('datos_nuevos', to_jsonb(NEW))) RETURNING id INTO v_historial;
    IF TG_OP = 'INSERT' OR NEW.estado_codigo IS DISTINCT FROM v_anterior THEN
        INSERT INTO notificaciones (solicitud_id, destinatario_id, historial_id, tipo, correo_destino, asunto, contenido)
        SELECT NEW.id, u.id, v_historial, 'CAMBIO_ESTADO', u.correo, 'Estado de solicitud de ausencia',
               format('Solicitud %s: %s', NEW.id, NEW.estado_codigo)
        FROM usuarios u WHERE u.id = NEW.solicitante_id;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER solicitudes_historial AFTER INSERT OR UPDATE ON solicitudes FOR EACH ROW EXECUTE FUNCTION registrar_historial();

CREATE FUNCTION preparar_revision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_requiere boolean;
    v_jefe bigint;
BEGIN
    IF TG_OP = 'INSERT' THEN
        SELECT e.requiere_validacion, u.jefe_inmediato_id INTO STRICT v_requiere, v_jefe
        FROM solicitudes s JOIN usuarios u ON u.id = s.solicitante_id
        JOIN etapas_flujo e ON e.flujo_id = s.flujo_id AND e.orden = NEW.orden
        WHERE s.id = NEW.solicitud_id AND s.flujo_id = NEW.flujo_id AND e.rol_codigo = NEW.rol_codigo;
        NEW.requiere_validacion := v_requiere;
        IF NEW.rol_codigo = 'JEFE_INMEDIATO' AND NEW.aprobador_id IS DISTINCT FROM v_jefe THEN
            RAISE EXCEPTION 'La revisión debe asignarse al jefe inmediato' USING ERRCODE = '23514';
        END IF;
        IF NEW.estado <> 'EN_ESPERA' THEN
            RAISE EXCEPTION 'La revisión debe crearse en espera' USING ERRCODE = '23514';
        END IF;
    ELSE
        IF (NEW.solicitud_id, NEW.flujo_id, NEW.orden, NEW.rol_codigo, NEW.aprobador_id, NEW.requiere_validacion, NEW.creado_en)
           IS DISTINCT FROM (OLD.solicitud_id, OLD.flujo_id, OLD.orden, OLD.rol_codigo, OLD.aprobador_id, OLD.requiere_validacion, OLD.creado_en) THEN
            RAISE EXCEPTION 'No se puede alterar la asignación de una revisión' USING ERRCODE = '23514';
        END IF;
        IF NEW.estado = 'PENDIENTE' AND OLD.estado <> 'PENDIENTE' THEN
            IF OLD.estado <> 'EN_ESPERA' OR EXISTS (
                SELECT 1 FROM revisiones WHERE solicitud_id = NEW.solicitud_id AND orden < NEW.orden AND estado <> 'APROBADA'
            ) THEN
                RAISE EXCEPTION 'La etapa anterior no está aprobada' USING ERRCODE = '23514';
            END IF;
        END IF;
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER revisiones_preparar BEFORE INSERT OR UPDATE ON revisiones FOR EACH ROW EXECUTE FUNCTION preparar_revision();

CREATE FUNCTION notificar_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.estado = 'PENDIENTE' AND OLD.estado IS DISTINCT FROM NEW.estado THEN
        INSERT INTO notificaciones (solicitud_id, destinatario_id, revision_id, tipo, correo_destino, asunto, contenido)
        SELECT NEW.solicitud_id, u.id, NEW.id, 'REVISION_PENDIENTE', u.correo,
               'Solicitud pendiente de revisión', format('Debe revisar la solicitud %s.', NEW.solicitud_id)
        FROM usuarios u WHERE u.id = NEW.aprobador_id
        ON CONFLICT DO NOTHING;
    END IF;
    RETURN NULL;
END;
$$;
CREATE TRIGGER revisiones_notificar AFTER UPDATE ON revisiones FOR EACH ROW EXECUTE FUNCTION notificar_revision();

-- Bloqueo de solicitud y comparación explícita de versión.
CREATE FUNCTION comprobar_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_revision revisiones%ROWTYPE;
    v_solicitud solicitudes%ROWTYPE;
BEGIN
    SELECT * INTO STRICT v_revision FROM revisiones WHERE id = NEW.revision_id;
    SELECT * INTO STRICT v_solicitud FROM solicitudes WHERE id = v_revision.solicitud_id FOR UPDATE;
    SELECT * INTO STRICT v_revision FROM revisiones WHERE id = NEW.revision_id FOR UPDATE;
    IF NEW.actor_id <> actor_actual() OR NEW.actor_id <> v_revision.aprobador_id THEN
        RAISE EXCEPTION 'Actor no autorizado para esta revisión' USING ERRCODE = '42501';
    END IF;
    IF v_solicitud.version <> NEW.version_esperada THEN
        RAISE EXCEPTION 'Conflicto de versión de solicitud' USING ERRCODE = '40001';
    END IF;
    IF v_revision.estado <> 'PENDIENTE' OR v_solicitud.estado_codigo NOT IN ('ENVIADA', 'EN_REVISION') THEN
        RAISE EXCEPTION 'La revisión no admite decisiones' USING ERRCODE = '23514';
    END IF;
    IF (SELECT count(*) FROM revisiones WHERE solicitud_id = v_solicitud.id) <>
       (SELECT count(*) FROM etapas_flujo WHERE flujo_id = v_solicitud.flujo_id) THEN
        RAISE EXCEPTION 'El flujo de la solicitud está incompleto' USING ERRCODE = '23514';
    END IF;
    IF EXISTS (SELECT 1 FROM revisiones WHERE solicitud_id = v_solicitud.id AND orden < v_revision.orden AND estado <> 'APROBADA') THEN
        RAISE EXCEPTION 'Existe una etapa anterior sin aprobar' USING ERRCODE = '23514';
    END IF;
    IF NEW.decision = 'VALIDAR_APROBAR' AND v_revision.rol_codigo <> 'TALENTO_HUMANO' THEN
        RAISE EXCEPTION 'La validación corresponde a Talento Humano' USING ERRCODE = '23514';
    END IF;
    IF NEW.decision = 'APROBAR' AND v_revision.requiere_validacion AND v_revision.validada_en IS NULL THEN
        RAISE EXCEPTION 'Se requiere validación previa o validar y aprobar' USING ERRCODE = '23514';
    END IF;
    NEW.decidido_en := now();
    RETURN NEW;
END;
$$;
CREATE TRIGGER aprobaciones_comprobar BEFORE INSERT ON aprobaciones FOR EACH ROW EXECUTE FUNCTION comprobar_decision();

CREATE FUNCTION aplicar_decision() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    v_revision revisiones%ROWTYPE;
    v_estado varchar(30);
BEGIN
    SELECT * INTO STRICT v_revision FROM revisiones WHERE id = NEW.revision_id;
    UPDATE revisiones SET
        estado = CASE WHEN NEW.decision = 'RECHAZAR' THEN 'RECHAZADA' ELSE 'APROBADA' END,
        resuelta_en = NEW.decidido_en,
        validada_por_id = CASE WHEN NEW.decision = 'VALIDAR_APROBAR' THEN NEW.actor_id ELSE validada_por_id END,
        validada_en = CASE WHEN NEW.decision = 'VALIDAR_APROBAR' THEN NEW.decidido_en ELSE validada_en END
    WHERE id = NEW.revision_id;
    IF NEW.decision = 'RECHAZAR' THEN
        UPDATE revisiones SET estado = 'OMITIDA', resuelta_en = NEW.decidido_en
        WHERE solicitud_id = v_revision.solicitud_id AND orden > v_revision.orden AND estado = 'EN_ESPERA';
        v_estado := 'RECHAZADA';
    ELSE
        UPDATE revisiones SET estado = 'PENDIENTE'
        WHERE solicitud_id = v_revision.solicitud_id AND orden = v_revision.orden + 1 AND estado = 'EN_ESPERA';
        v_estado := CASE WHEN EXISTS (SELECT 1 FROM revisiones WHERE solicitud_id = v_revision.solicitud_id AND estado <> 'APROBADA')
                         THEN 'EN_REVISION' ELSE 'APROBADA' END;
    END IF;
    UPDATE solicitudes SET estado_codigo = v_estado WHERE id = v_revision.solicitud_id;
    RETURN NULL;
END;
$$;
CREATE TRIGGER aprobaciones_aplicar AFTER INSERT ON aprobaciones FOR EACH ROW EXECUTE FUNCTION aplicar_decision();

CREATE FUNCTION iniciar_revision(p_solicitud_id bigint, p_version_esperada bigint)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_solicitud solicitudes%ROWTYPE;
    v_version bigint;
BEGIN
    PERFORM actor_actual();
    SELECT * INTO STRICT v_solicitud FROM solicitudes WHERE id = p_solicitud_id FOR UPDATE;
    IF v_solicitud.version <> p_version_esperada THEN
        RAISE EXCEPTION 'Conflicto de versión de solicitud' USING ERRCODE = '40001';
    END IF;
    IF v_solicitud.estado_codigo <> 'ENVIADA' OR
       (SELECT count(*) FROM revisiones WHERE solicitud_id = p_solicitud_id) <>
       (SELECT count(*) FROM etapas_flujo WHERE flujo_id = v_solicitud.flujo_id) THEN
        RAISE EXCEPTION 'La solicitud no está lista para revisión' USING ERRCODE = '23514';
    END IF;
    UPDATE revisiones SET estado = 'PENDIENTE' WHERE solicitud_id = p_solicitud_id AND orden = 1 AND estado = 'EN_ESPERA';
    IF NOT FOUND THEN
        RAISE EXCEPTION 'La primera revisión ya fue iniciada' USING ERRCODE = '23514';
    END IF;
    UPDATE solicitudes SET estado_codigo = 'EN_REVISION' WHERE id = p_solicitud_id RETURNING version INTO v_version;
    RETURN v_version;
END;
$$;

CREATE FUNCTION validar_revision(p_revision_id bigint, p_version_esperada bigint)
RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE
    v_revision revisiones%ROWTYPE;
    v_solicitud solicitudes%ROWTYPE;
    v_actor bigint := actor_actual();
    v_version bigint;
BEGIN
    SELECT * INTO STRICT v_revision FROM revisiones WHERE id = p_revision_id;
    SELECT * INTO STRICT v_solicitud FROM solicitudes WHERE id = v_revision.solicitud_id FOR UPDATE;
    SELECT * INTO STRICT v_revision FROM revisiones WHERE id = p_revision_id FOR UPDATE;
    IF v_solicitud.version <> p_version_esperada THEN
        RAISE EXCEPTION 'Conflicto de versión de solicitud' USING ERRCODE = '40001';
    END IF;
    IF v_revision.aprobador_id <> v_actor OR v_revision.rol_codigo <> 'TALENTO_HUMANO' THEN
        RAISE EXCEPTION 'Actor no autorizado para validar' USING ERRCODE = '42501';
    END IF;
    IF v_revision.estado <> 'PENDIENTE' OR v_revision.validada_en IS NOT NULL OR v_solicitud.estado_codigo <> 'EN_REVISION' THEN
        RAISE EXCEPTION 'La revisión no admite validación' USING ERRCODE = '23514';
    END IF;
    UPDATE revisiones SET validada_por_id = v_actor, validada_en = now() WHERE id = p_revision_id;
    UPDATE solicitudes SET actualizado_en = now() WHERE id = v_solicitud.id RETURNING version INTO v_version;
    INSERT INTO historial_solicitud (solicitud_id, actor_id, operacion, estado_anterior, estado_nuevo, version, detalle)
    VALUES (v_solicitud.id, v_actor, 'VALIDAR', v_solicitud.estado_codigo, v_solicitud.estado_codigo, v_version,
            jsonb_build_object('revision_id', p_revision_id));
    RETURN v_version;
END;
$$;

CREATE FUNCTION comprobar_observacion() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.autor_id <> actor_actual() THEN
        RAISE EXCEPTION 'El autor debe coincidir con el actor' USING ERRCODE = '42501';
    END IF;
    IF NEW.aprobacion_id IS NOT NULL AND NOT EXISTS (
        SELECT 1 FROM aprobaciones WHERE id = NEW.aprobacion_id AND revision_id = NEW.revision_id AND actor_id = NEW.autor_id
    ) THEN
        RAISE EXCEPTION 'La observación no corresponde a la decisión indicada' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER observaciones_comprobar BEFORE INSERT OR UPDATE ON observaciones FOR EACH ROW EXECUTE FUNCTION comprobar_observacion();

CREATE FUNCTION impedir_cambio() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'El registro es inmutable' USING ERRCODE = '55000';
END;
$$;
CREATE TRIGGER aprobaciones_inmutables BEFORE UPDATE OR DELETE ON aprobaciones FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER historial_inmutable BEFORE UPDATE OR DELETE ON historial_solicitud FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER auditoria_acceso_inmutable BEFORE UPDATE OR DELETE ON auditoria_acceso FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER auditoria_modificacion_inmutable BEFORE UPDATE OR DELETE ON auditoria_modificacion FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER estados_inmutables BEFORE INSERT OR UPDATE OR DELETE ON estados_solicitud FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER roles_inmutables BEFORE INSERT OR UPDATE OR DELETE ON roles FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER flujos_inmutables BEFORE INSERT OR UPDATE OR DELETE ON flujo_aprobacion FOR EACH ROW EXECUTE FUNCTION impedir_cambio();
CREATE TRIGGER etapas_inmutables BEFORE INSERT OR UPDATE OR DELETE ON etapas_flujo FOR EACH ROW EXECUTE FUNCTION impedir_cambio();

CREATE TRIGGER usuarios_auditar AFTER INSERT OR UPDATE OR DELETE ON usuarios FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER usuario_roles_auditar AFTER INSERT OR UPDATE OR DELETE ON usuario_roles FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER tipos_ausencia_auditar AFTER INSERT OR UPDATE OR DELETE ON tipos_ausencia FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER solicitudes_auditar AFTER INSERT OR UPDATE OR DELETE ON solicitudes FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER revisiones_auditar AFTER INSERT OR UPDATE OR DELETE ON revisiones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER aprobaciones_auditar AFTER INSERT ON aprobaciones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();
CREATE TRIGGER observaciones_auditar AFTER INSERT OR UPDATE OR DELETE ON observaciones FOR EACH ROW EXECUTE FUNCTION auditar_modificacion();

-- El rol de ejecución se provisiona fuera de este archivo.
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM PUBLIC;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM PUBLIC;
REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA public FROM PUBLIC;

COMMIT;