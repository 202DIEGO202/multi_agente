BEGIN;

-- Corrige bases persistentes que conservan el aprovisionamiento inicial anterior.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'migraciones') THEN
        CREATE ROLE migraciones NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF current_user <> 'migraciones' THEN
        EXECUTE pg_catalog.format('GRANT migraciones TO %I', current_user);
    END IF;
END;
$$;

CREATE OR REPLACE PROCEDURE public.aprovisionar_primer_usuario(
    IN p_identidad_externa text,
    IN p_nombre text,
    IN p_documento text,
    IN p_correo text,
    IN p_area text,
    IN p_cargo text,
    IN p_turno text,
    INOUT p_usuario_id bigint
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, public, pg_temp
AS $$
DECLARE
    v_usuario public.usuarios%ROWTYPE;
    v_actor_previo text;
BEGIN
    IF NOT pg_catalog.pg_has_role(session_user, 'migraciones', 'MEMBER') THEN
        RAISE EXCEPTION 'El aprovisionamiento inicial requiere el rol de migraciones' USING ERRCODE = '42501';
    END IF;

    LOCK TABLE public.usuarios IN ACCESS EXCLUSIVE MODE;
    IF EXISTS (SELECT 1 FROM public.usuarios) THEN
        RAISE EXCEPTION 'La primera identidad ya fue aprovisionada' USING ERRCODE = '42501';
    END IF;

    v_actor_previo := pg_catalog.current_setting('app.usuario_id', true);

    -- La suspensión queda limitada a la transacción bloqueada.
    ALTER TABLE public.usuarios DISABLE TRIGGER auditoria_cambios;
    INSERT INTO public.usuarios (
        identidad_externa, nombre, documento, correo, area, cargo, turno, activo
    ) VALUES (
        p_identidad_externa, p_nombre, p_documento, p_correo, p_area, p_cargo, p_turno, true
    ) RETURNING * INTO v_usuario;
    ALTER TABLE public.usuarios ENABLE TRIGGER auditoria_cambios;

    PERFORM pg_catalog.set_config('app.usuario_id', v_usuario.id::text, true);
    INSERT INTO public.auditoria_modificacion (
        actor_id, entidad, clave, operacion, datos_anteriores, datos_nuevos
    ) VALUES (
        public.actor_actual(), 'usuarios',
        pg_catalog.jsonb_build_object('id', v_usuario.id),
        'INSERT', NULL, pg_catalog.to_jsonb(v_usuario)
    );

    -- Los roles iniciales conservan la auditoría ordinaria.
    INSERT INTO public.usuario_roles (usuario_id, rol_codigo)
    VALUES (v_usuario.id, 'administrador');

    p_usuario_id := v_usuario.id;
    PERFORM pg_catalog.set_config('app.usuario_id', coalesce(v_actor_previo, ''), true);
END;
$$;

REVOKE ALL ON PROCEDURE public.aprovisionar_primer_usuario(text, text, text, text, text, text, text, bigint) FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO migraciones;
GRANT EXECUTE ON PROCEDURE public.aprovisionar_primer_usuario(text, text, text, text, text, text, text, bigint) TO migraciones;

COMMIT;