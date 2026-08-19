-- 0012_harden_fase1_grants.sql
-- lead
--
-- Endurece los privilegios de tabla de las 6 tablas de Fase 1 (profiles,
-- locations, suppliers, products, supplier_products, files), a partir de un
-- hallazgo real de data-model al verificar 0007-0011: la imagen de Supabase
-- trae `alter default privileges` que concede ALL sobre toda tabla nueva de
-- `public` a anon/authenticated/service_role. RLS lo compensaba (sin policy
-- de UPDATE/DELETE, deniega igual), asi que no era un agujero de seguridad,
-- pero el privilegio EFECTIVO no coincidia con el contrato: `authenticated`
-- podia tener `delete` en `files` aunque ninguna policy lo autorizara y el
-- contrato diga explicitamente "sin delete para nadie".
--
-- 0006 ya habia corregido la ausencia de GRANT a `authenticated`, pero nunca
-- hizo `revoke` primero ni toco `service_role`. Esta migracion cierra ambos
-- huecos, en simetria con el patron que 0007-0011 ya establecieron.
--
-- No se edita 0002-0005 (ya aplicadas, inmutables): esto es una migracion
-- nueva que revoca y vuelve a conceder, no un parche de las anteriores.

revoke all on table public.profiles          from anon, authenticated, service_role;
revoke all on table public.locations         from anon, authenticated, service_role;
revoke all on table public.suppliers         from anon, authenticated, service_role;
revoke all on table public.products          from anon, authenticated, service_role;
revoke all on table public.supplier_products from anon, authenticated, service_role;
revoke all on table public.files             from anon, authenticated, service_role;

-- `authenticated`: exactamente las operaciones que sus propias policies ya
-- permiten (identico a lo que concedia 0006, solo que ahora precedido de un
-- revoke que garantiza que no hay privilegio de sobra sin policy que lo use).
grant select, insert, update on table public.profiles          to authenticated;
grant select, insert, update on table public.locations         to authenticated;
grant select, insert, update on table public.suppliers         to authenticated;
grant select, insert, update on table public.products          to authenticated;
grant select, insert, update on table public.supplier_products to authenticated;
grant select, insert         on table public.files             to authenticated;

-- `service_role`: omite RLS pero no el GRANT de tabla (la leccion de 0006).
-- Lectura completa del catalogo, necesaria para el pipeline de importacion
-- de Fase 2 (import-backend resuelve location_name -> location_id, y las
-- fases futuras cruzan contra suppliers/products/supplier_products).
grant select on table public.profiles          to service_role;
grant select on table public.locations         to service_role;
grant select on table public.suppliers         to service_role;
grant select on table public.products          to service_role;
grant select on table public.supplier_products to service_role;

-- `files`: el servidor calcula `sha256`/`size_bytes` DESPUES de la subida
-- (contrato §8: "no se confia en el cliente"), lo que exige `update` desde el
-- paso de proceso (`service_role`). No se abre esa columna a `authenticated`:
-- el usuario solo inserta la fila inicial al pedir la URL firmada.
grant select, insert, update on table public.files to service_role;
