-- supabase/tests/sql/20_rls_by_role.sql
-- Fase 2 — data-model — 23 asertos
--
-- RLS por rol de negocio (contrato §7), simulando la sesion con
-- `set local role` + `request.jwt.claim.sub` (lo que lee auth.uid()).
-- Lo mas importante que se prueba aqui: `sales_*` e `inventory_*` no los puede
-- escribir NADIE que llegue por el navegador, ni siquiera un admin; solo el
-- pipeline con `service_role`.

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

-- ============================ C. RLS POR ROL ============================
-- viewer -----------------------------------------------------------------
select set_config('request.jwt.claim.sub','33333333-3333-3333-3333-333333333333', true);
set local role authenticated;

-- Cuenta solo las filas de _data.sql (prefijo dddd0000): seed.sql agrega sus
-- propias importaciones sinteticas y un total global seria fragil.
select test.expect_true('C01 viewer lee import_jobs',
  $$select count(*) = 4 from public.import_jobs where id::text like 'dddd0000%'$$);
select test.expect_true('C02 viewer lee import_issues', $$select count(*) >= 1 from public.import_issues$$);
select test.expect_true('C03 viewer lee sales_lines e inventory_lines',
  $$select (select count(*) from public.sales_lines) = 1 and (select count(*) from public.inventory_lines) = 1$$);
select test.expect_fail('C04 viewer NO crea import_jobs',
  $$insert into public.import_jobs (type,file_id,status,created_by)
    values ('sdos_inventory','cccccccc-0000-0000-0000-000000000001','pending','33333333-3333-3333-3333-333333333333')$$);
select test.expect_fail('C05 viewer NO crea price_lists',
  $$insert into public.price_lists (supplier_id,version,status,created_by)
    values ('aaaaaaaa-0000-0000-0000-000000000001',9,'draft','33333333-3333-3333-3333-333333333333')$$);

reset role;

-- buyer ------------------------------------------------------------------
select set_config('request.jwt.claim.sub','22222222-2222-2222-2222-222222222222', true);
set local role authenticated;

select test.expect_ok('C06 buyer crea import_job pending a su nombre',
  $$insert into public.import_jobs (type,file_id,status,created_by)
    values ('sdos_inventory','cccccccc-0000-0000-0000-000000000001','pending','22222222-2222-2222-2222-222222222222')$$);
select test.expect_fail('C07 buyer NO crea import_job a nombre de otro',
  $$insert into public.import_jobs (type,file_id,status,created_by)
    values ('sdos_inventory','cccccccc-0000-0000-0000-000000000001','pending','11111111-1111-1111-1111-111111111111')$$);
select test.expect_fail('C08 buyer NO crea un import_job ya completed (solo nace pending)',
  $$insert into public.import_jobs (type,file_id,status,created_by)
    values ('sdos_inventory','cccccccc-0000-0000-0000-000000000001','completed','22222222-2222-2222-2222-222222222222')$$);
select test.expect_fail('C09 buyer NO avanza el estado de un import_job (lo hace el servidor)',
  $$update public.import_jobs set status='completed' where id='dddd0000-0000-0000-0000-000000000001'$$);
select test.expect_fail('C10 buyer NO registra incidencias a mano',
  $$insert into public.import_issues (import_job_id,severity,code,detail)
    values ('dddd0000-0000-0000-0000-000000000001','error','ean_invalido','x')$$);
select test.expect_fail('C11 buyer NO escribe en sales_lines (escritura de service_role)',
  $$insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
    values ('eeee0000-0000-0000-0000-000000000001','7700000000042',(select id from public.locations where code='AV19'),3)$$);
select test.expect_fail('C12 buyer NO actualiza sales_imports',
  $$update public.sales_imports set status='superseded' where id='eeee0000-0000-0000-0000-000000000001'$$);
select test.expect_fail('C13 buyer NO escribe en inventory_lines',
  $$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand)
    values ('eeee0000-0000-0000-0000-000000000002','7700000000042',(select id from public.locations where code='AV19'),1)$$);
select test.expect_fail('C14 buyer NO borra sales_lines',
  $$delete from public.sales_lines$$);

reset role;

-- admin ------------------------------------------------------------------
select set_config('request.jwt.claim.sub','11111111-1111-1111-1111-111111111111', true);
set local role authenticated;
select test.expect_ok('C15 admin registra una incidencia manual',
  $$insert into public.import_issues (import_job_id,severity,code,detail)
    values ('dddd0000-0000-0000-0000-000000000001','warning','tisuc_desconocido','TISUC 99999 sin ubicacion')$$);
select test.expect_fail('C16 admin tampoco escribe en inventory_lines (solo service_role)',
  $$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand)
    values ('eeee0000-0000-0000-0000-000000000002','7700000000042',(select id from public.locations where code='AV19'),1)$$);
reset role;

-- usuario inactivo -------------------------------------------------------
select set_config('request.jwt.claim.sub','44444444-4444-4444-4444-444444444444', true);
set local role authenticated;
select test.expect_true('C17 usuario inactivo no ve ninguna fila de Fase 2',
  $$select (select count(*) from public.import_jobs) = 0
       and (select count(*) from public.sales_lines) = 0
       and (select count(*) from public.price_lists) = 0$$);
reset role;

-- anon -------------------------------------------------------------------
set local role anon;
select test.expect_fail('C18 anon no puede leer import_jobs', $$select 1 from public.import_jobs$$);
select test.expect_fail('C19 anon no puede leer price_list_items', $$select 1 from public.price_list_items$$);
select test.expect_fail('C20 anon no puede leer sales_lines', $$select 1 from public.sales_lines$$);
reset role;

-- service_role -----------------------------------------------------------
set local role service_role;
select test.expect_ok('C21 service_role escribe sales_lines (pipeline de importacion)',
  $$insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
    values ('eeee0000-0000-0000-0000-000000000001','7700000000042',(select id from public.locations where code='AV19'),3)$$);
select test.expect_ok('C22 service_role escribe inventory_lines',
  $$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand)
    values ('eeee0000-0000-0000-0000-000000000002','7700000000042',(select id from public.locations where code='AV19'),1)$$);
select test.expect_ok('C23 service_role marca el import_job como completed',
  $$update public.import_jobs set status='completed', finished_at=now()
    where id='dddd0000-0000-0000-0000-000000000002'$$);
reset role;

rollback;
