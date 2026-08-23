-- Cambios de costo: vistas derivadas y respetuosas de RLS.

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

-- Completa y activa la lista del proveedor 801. Su primer EAN tiene costo
-- TBC 15.000 y permite verificar que no existe tolerancia en la comparación.
insert into public.price_list_items (price_list_id, ean, supplier_cost, raw)
values ('ffff0000-0000-0000-0000-000000000001', '0123456789012', 8000.00,
        '{"Nombre":"Producto Nuevo Prueba"}'::jsonb);
update public.price_lists set status = 'active'
where id = 'ffff0000-0000-0000-0000-000000000001';

select test.expect_true('J01 latest_tbc_costs conserva el costo TBC por EAN',
  $$select tbc_cost = 15000.00 and period_end = '2026-01-31'
    from public.latest_tbc_costs where ean = '7700000000011'$$);
select test.expect_true('J02 cost_changes compara sin tolerancia y expone la diferencia',
  $$select supplier_cost = 12000.00 and tbc_cost = 15000.00 and difference = -3000.00
    from public.cost_changes where supplier_id = 'aaaaaaaa-0000-0000-0000-000000000001'
      and ean = '7700000000011'$$);

select set_config('request.jwt.claim.sub', '33333333-3333-3333-3333-333333333333', true);
set local role authenticated;
select test.expect_true('J03 viewer puede leer cambios de costo derivados',
  $$select count(*) = 1 from public.cost_changes where ean = '7700000000011'$$);
reset role;

set local role anon;
select test.expect_fail('J04 anon no puede leer cost_changes',
  $$select 1 from public.cost_changes$$);
reset role;

rollback;
