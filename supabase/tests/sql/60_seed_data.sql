-- supabase/tests/sql/60_seed_data.sql
-- Fase 2 — data-model — 8 asertos
--
-- `supabase/seed.sql` no es una migracion (no corre en produccion), pero si se
-- rompe deja a cualquiera sin base de desarrollo. El runner lo aplica DOS veces
-- antes de esta suite: si no fuera idempotente, aqui se veria duplicado.

set client_min_messages = notice;
begin;

select test.expect_true('S01 seed.sql es idempotente: una sola importacion completada de lista de precios',
  $sql$select count(*) = 1 from public.import_jobs
       where id = '22220000-0000-4000-8000-000000000001' and status = 'completed'$sql$);

select test.expect_true('S02 la importacion fallida trae motivo legible, no un codigo crudo',
  $sql$select length(error_message) > 20 and error_message not like '%Traceback%'
       from public.import_jobs where id = '22220000-0000-4000-8000-000000000002'$sql$);

select test.expect_true('S03 las 2 incidencias sinteticas existen sin duplicarse',
  $sql$select count(*) = 2 from public.import_issues
       where import_job_id = '22220000-0000-4000-8000-000000000001'$sql$);

select test.expect_true('S04 la lista de precios del seed sigue en draft (editable)',
  $sql$select status = 'draft' from public.price_lists
       where id = '44440000-0000-4000-8000-000000000001'$sql$);

select test.expect_true('S05 la lista trae sus 3 renglones, sin duplicar tras el segundo seed',
  $sql$select count(*) = 3 from public.price_list_items
       where price_list_id = '44440000-0000-4000-8000-000000000001'$sql$);

select test.expect_true('S06 el EAN con cero inicial del seed sobrevive intacto',
  $sql$select ean = '0123456789012' from public.price_list_items
       where price_list_id = '44440000-0000-4000-8000-000000000001' and supplier_cost = 56400.00$sql$);

select test.expect_true('S07 el seed no escribe en auth.users (los usuarios se crean registrandose)',
  $sql$select count(*) = 4 from auth.users$sql$);  -- solo los 4 de 01_fixtures.sql

select test.expect_true('S08 ningun dato del seed queda huerfano de proveedor',
  $sql$select count(*) = 0 from public.price_lists pl
       left join public.suppliers s on s.id = pl.supplier_id where s.id is null$sql$);

rollback;
