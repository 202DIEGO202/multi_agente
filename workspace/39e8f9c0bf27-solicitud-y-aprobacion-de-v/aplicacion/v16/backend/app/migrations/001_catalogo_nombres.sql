BEGIN;
-- Actualiza bases persistentes que conservan la antigua unicidad del nombre.
DROP INDEX IF EXISTS public.tipos_ausencia_nombre_unico;
CREATE INDEX IF NOT EXISTS tipos_ausencia_nombre_idx ON public.tipos_ausencia (lower(nombre));
COMMIT;