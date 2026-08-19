-- supabase/tests/sql/30_price_list_immutability.sql
-- Fase 2 — data-model — 25 asertos
--
-- Inmutabilidad del historial de costos (contrato §9.1). El guardia es un
-- TRIGGER de tabla, no una policy: por eso las pruebas verifican que tambien
-- bloquea a `service_role`. La lista blanca de transiciones (draft libre;
-- active->superseded/archived; superseded->archived) existe porque bloquear
-- todo update fuera de draft haria imposible el propio relevo de versiones que
-- pide el contrato. D23 reproduce el flujo completo de `engine/persistence.py`.

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

-- ============================ D. INMUTABILIDAD DE price_lists ============================
select set_config('request.jwt.claim.sub','22222222-2222-2222-2222-222222222222', true);
set local role authenticated;

select test.expect_ok('D01 buyer crea una lista draft a su nombre',
  $$insert into public.price_lists (id,supplier_id,version,status,created_by)
    values ('ffff0000-0000-0000-0000-000000000003','aaaaaaaa-0000-0000-0000-000000000001',2,'draft','22222222-2222-2222-2222-222222222222')$$);
select test.expect_fail('D02 buyer NO crea una lista naciendo active',
  $$insert into public.price_lists (supplier_id,version,status,created_by)
    values ('aaaaaaaa-0000-0000-0000-000000000001',3,'active','22222222-2222-2222-2222-222222222222')$$);
select test.expect_ok('D03 buyer edita una lista draft',
  $$update public.price_lists set effective_date='2026-02-01' where id='ffff0000-0000-0000-0000-000000000001'$$);
select test.expect_ok('D04 buyer inserta renglon en lista draft',
  $$insert into public.price_list_items (price_list_id,ean,supplier_cost)
    values ('ffff0000-0000-0000-0000-000000000001','7700000000042',7500.00)$$);
select test.expect_ok('D05 buyer corrige un renglon de lista draft',
  $$update public.price_list_items set supplier_cost=7600.00
    where price_list_id='ffff0000-0000-0000-0000-000000000001' and ean='7700000000042'$$);
select test.expect_true('D06 buyer borra un renglon de lista draft',
  $$with d as (delete from public.price_list_items
               where price_list_id='ffff0000-0000-0000-0000-000000000001' and ean='7700000000042' returning 1)
    select count(*) = 1 from d$$);
select test.expect_fail('D07 buyer NO inserta renglon en lista active',
  $$insert into public.price_list_items (price_list_id,ean,supplier_cost)
    values ('ffff0000-0000-0000-0000-000000000002','7700000000042',7500.00)$$);
select test.expect_true('D08 buyer no afecta ninguna fila al editar una lista active (policy)',
  $$with u as (update public.price_lists set effective_date='2026-09-09'
               where id='ffff0000-0000-0000-0000-000000000002' returning 1)
    select count(*) = 0 from u$$);
select test.expect_ok('D09 buyer publica su lista draft (draft -> active)',
  $$update public.price_lists set status='active' where id='ffff0000-0000-0000-0000-000000000001'$$);
select test.expect_fail('D10 dos listas active del mismo proveedor colisionan',
  $$update public.price_lists set status='active' where id='ffff0000-0000-0000-0000-000000000003'$$);
reset role;

set local role service_role;
select test.expect_fail('D11 service_role NO puede cambiar contenido de una lista active (trigger)',
  $$update public.price_lists set version=99 where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_fail('D12 service_role NO puede cambiar el proveedor de una lista active',
  $$update public.price_lists set supplier_id='aaaaaaaa-0000-0000-0000-000000000001'
    where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_ok('D13 transicion active -> superseded permitida',
  $$update public.price_lists set status='superseded' where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_fail('D14 transicion superseded -> active bloqueada',
  $$update public.price_lists set status='active' where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_ok('D15 transicion superseded -> archived permitida',
  $$update public.price_lists set status='archived' where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_fail('D16 reabrir una lista archivada a draft bloqueada',
  $$update public.price_lists set status='draft' where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_fail('D17 borrar una lista fuera de draft bloqueado incluso para service_role',
  $$delete from public.price_lists where id='ffff0000-0000-0000-0000-000000000002'$$);
select test.expect_fail('D18 service_role NO puede editar renglones de una lista no-draft',
  $$update public.price_list_items set supplier_cost=1.00 where id='ffff0000-0000-0000-0000-0000000000aa'$$);
select test.expect_fail('D19 service_role NO puede borrar renglones de una lista no-draft',
  $$delete from public.price_list_items where id='ffff0000-0000-0000-0000-0000000000aa'$$);
select test.expect_fail('D20 service_role NO puede insertar renglones en una lista no-draft',
  $$insert into public.price_list_items (price_list_id,ean,supplier_cost)
    values ('ffff0000-0000-0000-0000-000000000002','7700000000059',100.00)$$);
select test.expect_ok('D21 borrar una lista draft si se permite (arrastra sus renglones)',
  $$delete from public.price_lists where id='ffff0000-0000-0000-0000-000000000003'$$);
select test.expect_true('D22 la cascada de la lista draft borrada no dejo renglones huerfanos',
  $$select count(*) = 0 from public.price_list_items where price_list_id='ffff0000-0000-0000-0000-000000000003'$$);
select test.expect_ok('D23 flujo real del pipeline: superseder la anterior y publicar la nueva',
  $sql$
    do $x$
    declare v_old uuid;
    begin
      update public.price_lists set status='superseded'
        where supplier_id='aaaaaaaa-0000-0000-0000-000000000001' and status='active'
        returning id into v_old;
      insert into public.price_lists (id,supplier_id,version,status,supersedes_id)
        values ('ffff0000-0000-0000-0000-000000000004','aaaaaaaa-0000-0000-0000-000000000001',3,'draft',v_old);
      insert into public.price_list_items (price_list_id,ean,supplier_cost)
        values ('ffff0000-0000-0000-0000-000000000004','7700000000011',11000.00);
      update public.price_lists set status='active' where id='ffff0000-0000-0000-0000-000000000004';
    end
    $x$
  $sql$);
select test.expect_true('D24 tras el relevo queda una sola lista active del proveedor y encadenada',
  $sql$select count(*) = 1 from public.price_lists
    where supplier_id='aaaaaaaa-0000-0000-0000-000000000001' and status='active'
      and supersedes_id is not null$sql$);
select test.expect_true('D25 la lista relevada conserva sus renglones intactos (historial)',
  $sql$select count(*) >= 1 from public.price_list_items i join public.price_lists l on l.id=i.price_list_id
       where l.supplier_id='aaaaaaaa-0000-0000-0000-000000000001' and l.status='superseded'$sql$);
reset role;

rollback;
