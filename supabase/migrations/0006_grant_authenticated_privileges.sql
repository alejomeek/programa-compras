-- 0006_grant_authenticated_privileges.sql
-- lead
--
-- Corrige "permission denied for table X" observado en produccion: las
-- migraciones 0002-0005 activan RLS y crean policies, pero nunca hacen
-- GRANT explicito a `authenticated` sobre las tablas. RLS filtra FILAS; sin
-- un GRANT de tabla, Postgres deniega la operacion antes de evaluar RLS.
--
-- El supuesto original (documentado como riesgo por db-auth en la Fase 1) era
-- que los privilegios por defecto de Supabase cubren esto automaticamente
-- para tablas nuevas de `public`. En este proyecto no se cumplio -- probable-
-- mente por como se aplicaron las migraciones -- asi que se hace explicito en
-- vez de depender de configuracion implicita.
--
-- Los GRANT de aqui son exactamente las operaciones que cada tabla ya permite
-- por policy (contrato §7): no amplian el acceso, solo destraban en la capa de
-- privilegios lo que RLS ya autoriza a nivel de fila. Ninguna tabla tiene
-- policy de DELETE, asi que no se concede DELETE en ninguna.

grant usage on schema public to authenticated;

grant select, insert, update on table public.profiles          to authenticated;
grant select, insert, update on table public.locations         to authenticated;
grant select, insert, update on table public.suppliers         to authenticated;
grant select, insert, update on table public.products          to authenticated;
grant select, insert, update on table public.supplier_products to authenticated;
grant select, insert         on table public.files             to authenticated;
