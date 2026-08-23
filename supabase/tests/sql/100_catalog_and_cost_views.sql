-- Fase catálogo/costos — vistas derivadas y respetuosas de RLS.

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

-- Completa la lista del proveedor 801 antes de activarla. El primer EAN tiene
-- costo TBC 15.000, por lo que permite comprobar comparación exacta; el
-- segundo no existe en TBC y es un producto nuevo para este proveedor.
insert into public.price_list_items (price_list_id, ean, supplier_cost, raw)
values ('ffff0000-0000-0000-0000-000000000001', '0123456789012', 8000.00,
        '{"Nombre":"Producto Nuevo Prueba"}'::jsonb);
update public.price_lists set status = 'active'
where id = 'ffff0000-0000-0000-0000-000000000001';

insert into public.inventory_lines
  (snapshot_id, ean, tbc_sku, location_id, on_hand, supplier_tbc_code)
values ('eeee0000-0000-0000-0000-000000000002', '7700000000097', 'TST-0097',
        (select id from public.locations where code = 'CEDI'), 2, '801');

select test.expect_true('J01 latest_tbc_costs conserva el costo TBC por EAN',
  $$select tbc_cost = 15000.00 and period_end = '2026-01-31'
    from public.latest_tbc_costs where ean = '7700000000011'$$);
select test.expect_true('J02 cost_changes compara sin tolerancia y expone la diferencia',
  $$select supplier_cost = 12000.00 and tbc_cost = 15000.00 and difference = -3000.00
    from public.cost_changes where supplier_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      and ean = '7700000000011'$$);
select test.expect_true('J03 catalog_items marca nuevo solo si falta en TBC',
  $$select status = 'new' and product_name = 'Producto Nuevo Prueba'
    from public.catalog_items where supplier_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      and ean = '0123456789012'$$);
select test.expect_true('J04 catalog_items no llama comprable al EAN ausente de lista vigente',
  $$select status = 'not_available' and supplier_cost is null
    from public.catalog_items where supplier_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      and ean = '7700000000097'$$);

select set_config('request.jwt.claim.sub', '33333333-3333-3333-3333-333333333333', true);
set local role authenticated;
select test.expect_true('J05 viewer puede leer cambios de costo derivados',
  $$select count(*) = 1 from public.cost_changes where ean = '7700000000011'$$);
select test.expect_true('J06 viewer puede leer catálogo derivado',
  $$select count(*) >= 3 from public.catalog_items where supplier_id = 'aaaaaaaa-0000-0000-0000-000000000001'$$);
reset role;

set local role anon;
select test.expect_fail('J07 anon no puede leer cost_changes',
  $$select 1 from public.cost_changes$$);
select test.expect_fail('J08 anon no puede leer catalog_items',
  $$select 1 from public.catalog_items$$);
reset role;

rollback;
