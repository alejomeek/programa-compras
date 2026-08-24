-- Fase 4 — comportamiento de órdenes, snapshots, consecutivo y permisos.
set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

insert into public.purchase_runs
  (id, supplier_id, sales_import_id, price_list_id, period_start, period_end,
   status, engine_version, params_hash, created_by, calculated_at)
values
  ('11119999-0000-0000-0000-000000000010',
   'aaaaaaaa-0000-0000-0000-000000000001',
   'eeee0000-0000-0000-0000-000000000001',
   'ffff0000-0000-0000-0000-000000000001',
   '2026-01-01', '2026-01-31', 'calculated', '3.0.1', repeat('b', 64),
   '22222222-2222-2222-2222-222222222222', now());

insert into public.purchase_run_lines
  (id, purchase_run_id, product_id, ean, location_id, sales_units, period_days,
   daily_sales, suggested_quantity, final_quantity, unit_cost, status)
values
  ('22229999-0000-0000-0000-000000000010',
   '11119999-0000-0000-0000-000000000010',
   'bbbbbbbb-0000-0000-0000-000000000001', '7700000000011',
   (select id from public.locations where code = 'CEDI'),
   10, 31, 0.3226, 15, 15, 12000.00, 'ok');

update public.price_list_items
set raw = jsonb_build_object('Nombre', 'Producto desde lista')
where price_list_id = 'ffff0000-0000-0000-0000-000000000001'
  and ean = '7700000000011';

-- Estructura: no se cuela IVA/flete ni se repite el número por ubicación.
select test.expect_true('H01 snapshot de item y totales presentes',
  $$select count(*) = 0 from information_schema.columns
    where table_schema = 'public' and table_name in ('purchase_orders', 'purchase_order_items')
      and column_name = any(array['tax_amount','freight_amount','total_with_tax'])$$);
select test.expect_true('H02 order_number conserva números históricos y admite el formato nuevo',
  $$select exists(select 1 from pg_constraint where conname = 'purchase_orders_order_number_check')$$);

-- Viewer lee, pero no crea. La excepción de negocio solo aplica a cancelar.
select set_config('request.jwt.claim.sub', '33333333-3333-3333-3333-333333333333', true);
set local role authenticated;
select test.expect_fail('H03 viewer no crea borrador',
  $$select * from public.create_purchase_order_drafts(array['22229999-0000-0000-0000-000000000010'::uuid])$$);
reset role;

-- Buyer crea el borrador y la función fotografía nombre/costo/cantidad.
select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);
set local role authenticated;
select test.expect_ok('H04 buyer crea borrador desde línea final',
  $$select * from public.create_purchase_order_drafts(array['22229999-0000-0000-0000-000000000010'::uuid])$$);
select test.expect_true('H05 borrador copia nombre, cantidad, costo y total',
  $$select po.status = 'draft' and po.total_units = 15 and po.subtotal = 180000.00
      and poi.product_name = 'Producto desde lista' and poi.quantity = 15 and poi.unit_cost = 12000.00
    from public.purchase_orders po
    join public.purchase_order_items poi on poi.purchase_order_id = po.id
    where po.purchase_run_id = '11119999-0000-0000-0000-000000000010'$$);
select test.expect_fail('H06 línea no se reutiliza en otro borrador activo',
  $$select * from public.create_purchase_order_drafts(array['22229999-0000-0000-0000-000000000010'::uuid])$$);
select test.expect_fail('H07 buyer no puede mutar estado directo',
  $$update public.purchase_orders set status = 'issued'
    where purchase_run_id = '11119999-0000-0000-0000-000000000010'$$);
reset role;

-- El archivo de PDF lo crea el servidor privilegiado antes de emitir.
set local role service_role;
insert into public.files
  (id, bucket, object_path, original_name, size_bytes, sha256, uploaded_by)
values
  ('cccccccc-0000-0000-0000-000000000010', 'purchase-order-pdfs',
   'proveedor/orden/orden.pdf', 'orden.pdf', 100, repeat('e', 64),
   '22222222-2222-2222-2222-222222222222');
reset role;

select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);
set local role authenticated;
select test.expect_ok('H08 buyer emite con PDF válido',
  $$select public.issue_purchase_order(
      (select id from public.purchase_orders where purchase_run_id = '11119999-0000-0000-0000-000000000010'),
      'cccccccc-0000-0000-0000-000000000010')$$);
select test.expect_true('H09 emisión asigna número sin año, con destino y congela PDF',
  $$select status = 'issued' and order_number ~ '^OC-CEDI-0001$'
      and pdf_file_id = 'cccccccc-0000-0000-0000-000000000010'
    from public.purchase_orders where purchase_run_id = '11119999-0000-0000-0000-000000000010'$$);
reset role;

-- Decisión explícita del usuario: viewer activo también puede cancelar, con
-- razón obligatoria; no puede hacerlo anónimo ni omitir la razón.
select set_config('request.jwt.claim.sub', '33333333-3333-3333-3333-333333333333', true);
set local role authenticated;
select test.expect_fail('H10 viewer no cancela sin motivo',
  $$select public.cancel_purchase_order(
      (select id from public.purchase_orders where purchase_run_id = '11119999-0000-0000-0000-000000000010'), ' ')$$);
select test.expect_ok('H11 viewer cancela con motivo obligatorio',
  $$select public.cancel_purchase_order(
      (select id from public.purchase_orders where purchase_run_id = '11119999-0000-0000-0000-000000000010'), 'Proveedor suspendió disponibilidad')$$);
select test.expect_true('H12 cancelación guarda actor y razón',
  $$select status = 'cancelled' and cancelled_by = '33333333-3333-3333-3333-333333333333'
      and cancel_reason = 'Proveedor suspendió disponibilidad'
    from public.purchase_orders where purchase_run_id = '11119999-0000-0000-0000-000000000010'$$);
reset role;

-- El audit es append-only: admin lo puede consultar, nadie autenticado lo edita.
select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);
set local role authenticated;
select test.expect_true('H13 auditoría registra creación, emisión y cancelación',
  $$select array_agg(action order by created_at, id) @> array['draft_created','issued','cancelled']
    from public.audit_events
    where entity_table = 'purchase_orders'
      and entity_id = (select id from public.purchase_orders where purchase_run_id = '11119999-0000-0000-0000-000000000010')$$);
select test.expect_fail('H14 ni admin edita auditoría',
  $$update public.audit_events set action = 'altered'$$);
reset role;

set local role anon;
select test.expect_fail('H15 anon no lee ni ejecuta órdenes',
  $$select * from public.purchase_orders$$);
select test.expect_fail('H16 anon no ejecuta cancelación',
  $$select public.cancel_purchase_order('00000000-0000-0000-0000-000000000000', 'intento')$$);
reset role;

rollback;
