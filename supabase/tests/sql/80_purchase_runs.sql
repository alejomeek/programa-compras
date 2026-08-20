-- supabase/tests/sql/80_purchase_runs.sql
-- Fase 3 — recommendation-engineer
--
-- Comportamiento de purchase_runs/purchase_run_target_days/purchase_run_lines/
-- purchase_line_adjustments (contrato §7, §9): RLS por rol, inmutabilidad de
-- `suggested_quantity`, el RPC `update_final_quantity` (unica via de escritura
-- de `final_quantity`, concurrencia optimista por `row_version`), y una prueba
-- estructural anti-regresion que confirma que ningun campo de redistribucion
-- (prohibido por el contrato §1) se coló en el esquema real.

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

-- Fixture propia de esta suite: una corrida ya "calculada" (como la dejaria
-- engine/purchase_runs.py), sin depender de que otra suite no la haya tocado.
insert into public.purchase_runs
  (id, supplier_id, sales_import_id, price_list_id, inventory_snapshot_id,
   period_start, period_end, status, engine_version, params_hash, created_by, calculated_at)
values
  ('11119999-0000-0000-0000-000000000001',
   'aaaaaaaa-0000-0000-0000-000000000001',
   'eeee0000-0000-0000-0000-000000000001',
   'ffff0000-0000-0000-0000-000000000001',
   'eeee0000-0000-0000-0000-000000000002',
   '2026-01-01', '2026-01-31', 'calculated', '3.0.0', repeat('a', 64),
   '22222222-2222-2222-2222-222222222222', now());

insert into public.purchase_run_target_days (purchase_run_id, location_id, target_days)
values ('11119999-0000-0000-0000-000000000001',
        (select id from public.locations where code = 'CEDI'), 45);

insert into public.purchase_run_lines
  (id, purchase_run_id, ean, location_id, sales_units, period_days, daily_sales,
   suggested_quantity, final_quantity, stock_reference, unit_cost, status)
values
  ('22229999-0000-0000-0000-000000000001', '11119999-0000-0000-0000-000000000001',
   '7700000000011', (select id from public.locations where code = 'CEDI'),
   10, 31, 0.3226, 15, 15, 5, 12000.00, 'ok');

-- ============================ G. ESTRUCTURA ANTI-REGRESION ============================
-- Autoritativa (columnas reales de Postgres, no lo que dice un dict de Python):
-- ninguna de las 4 tablas nuevas puede tener un campo de redistribucion.
select test.expect_true('G01 purchase_run_lines sin campos de redistribucion',
  $$select count(*) = 0 from information_schema.columns
    where table_schema = 'public' and table_name = 'purchase_run_lines'
      and column_name = any(array['stockout_minimum','inventory_target','transfer_quantity','redistribution_flag','minimum_quantity'])$$);
select test.expect_true('G02 purchase_runs sin campos de redistribucion',
  $$select count(*) = 0 from information_schema.columns
    where table_schema = 'public' and table_name = 'purchase_runs'
      and column_name = any(array['stockout_minimum','inventory_target','transfer_quantity','redistribution_flag'])$$);
select test.expect_true('G03 purchase_run_target_days sin campos de redistribucion',
  $$select count(*) = 0 from information_schema.columns
    where table_schema = 'public' and table_name = 'purchase_run_target_days'
      and column_name = any(array['stockout_minimum','inventory_target','transfer_quantity','redistribution_flag'])$$);
select test.expect_true('G04 purchase_line_adjustments sin campos de redistribucion',
  $$select count(*) = 0 from information_schema.columns
    where table_schema = 'public' and table_name = 'purchase_line_adjustments'
      and column_name = any(array['stockout_minimum','inventory_target','transfer_quantity','redistribution_flag'])$$);

-- ============================ G. RLS POR ROL ============================
select set_config('request.jwt.claim.sub', '33333333-3333-3333-3333-333333333333', true);
set local role authenticated;

select test.expect_true('G05 viewer lee purchase_runs',
  $$select count(*) = 1 from public.purchase_runs where id = '11119999-0000-0000-0000-000000000001'$$);
select test.expect_true('G06 viewer lee purchase_run_lines',
  $$select count(*) = 1 from public.purchase_run_lines where purchase_run_id = '11119999-0000-0000-0000-000000000001'$$);
select test.expect_true('G07 viewer lee purchase_run_target_days',
  $$select count(*) = 1 from public.purchase_run_target_days where purchase_run_id = '11119999-0000-0000-0000-000000000001'$$);
select test.expect_fail('G08 viewer NO crea purchase_runs',
  $$insert into public.purchase_runs
      (supplier_id, sales_import_id, price_list_id, period_start, period_end, engine_version, params_hash, created_by)
    values ('aaaaaaaa-0000-0000-0000-000000000001','eeee0000-0000-0000-0000-000000000001',
            'ffff0000-0000-0000-0000-000000000001','2026-01-01','2026-01-31','3.0.0',repeat('b',64),
            '33333333-3333-3333-3333-333333333333')$$);
select test.expect_fail('G09 viewer NO puede ajustar cantidad final (can_write() falso en el RPC)',
  $$select public.update_final_quantity('22229999-0000-0000-0000-000000000001', 20, 1, 'intento viewer')$$);
reset role;

select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);
set local role authenticated;

select test.expect_ok('G10 buyer crea una corrida a su nombre',
  $$insert into public.purchase_runs
      (id, supplier_id, sales_import_id, price_list_id, period_start, period_end, engine_version, params_hash, created_by)
    values ('11119999-0000-0000-0000-000000000002','aaaaaaaa-0000-0000-0000-000000000001',
            'eeee0000-0000-0000-0000-000000000001','ffff0000-0000-0000-0000-000000000001',
            '2026-01-01','2026-01-31','3.0.0',repeat('c',64),
            '22222222-2222-2222-2222-222222222222')$$);
select test.expect_fail('G11 buyer NO crea una corrida a nombre de otro',
  $$insert into public.purchase_runs
      (supplier_id, sales_import_id, price_list_id, period_start, period_end, engine_version, params_hash, created_by)
    values ('aaaaaaaa-0000-0000-0000-000000000001','eeee0000-0000-0000-0000-000000000001',
            'ffff0000-0000-0000-0000-000000000001','2026-01-01','2026-01-31','3.0.0',repeat('d',64),
            '11111111-1111-1111-1111-111111111111')$$);
select test.expect_fail('G12 buyer NO puede UPDATE directo de purchase_run_lines (sin policy, sin GRANT)',
  $$update public.purchase_run_lines set final_quantity = 99
    where id = '22229999-0000-0000-0000-000000000001'$$);

-- RPC, caso feliz.
select test.expect_ok('G13 buyer ajusta la cantidad final via el RPC',
  $$select public.update_final_quantity('22229999-0000-0000-0000-000000000001', 20, 1, 'ajuste de prueba')$$);
select test.expect_true('G14 la linea quedo con final_quantity/row_version actualizados',
  $$select final_quantity = 20 and row_version = 2
    from public.purchase_run_lines where id = '22229999-0000-0000-0000-000000000001'$$);
select test.expect_true('G15 el ajuste quedo registrado con el usuario y el motivo correctos',
  $$select count(*) = 1 from public.purchase_line_adjustments
    where purchase_run_line_id = '22229999-0000-0000-0000-000000000001'
      and previous_quantity = 15 and new_quantity = 20
      and reason = 'ajuste de prueba'
      and adjusted_by = '22222222-2222-2222-2222-222222222222'$$);

-- RPC, conflicto de row_version (version desactualizada: la fila ya esta en 2).
select test.expect_fail('G16 RPC con row_version desactualizado da conflicto explicito',
  $$select public.update_final_quantity('22229999-0000-0000-0000-000000000001', 30, 1, 'version vieja')$$);
select test.expect_true('G17 el conflicto NO cambio la fila ni sumo un ajuste extra',
  $$select (select final_quantity from public.purchase_run_lines where id = '22229999-0000-0000-0000-000000000001') = 20
      and (select count(*) from public.purchase_line_adjustments
           where purchase_run_line_id = '22229999-0000-0000-0000-000000000001') = 1$$);
reset role;

-- admin bloquea la corrida; el RPC debe rechazar ajustes sobre una corrida locked.
select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);
set local role authenticated;
select test.expect_ok('G18 admin bloquea la corrida (calculated -> locked)',
  $$update public.purchase_runs set status = 'locked' where id = '11119999-0000-0000-0000-000000000001'$$);
reset role;

select set_config('request.jwt.claim.sub', '22222222-2222-2222-2222-222222222222', true);
set local role authenticated;
select test.expect_fail('G19 RPC rechaza ajustar una linea de una corrida locked',
  $$select public.update_final_quantity('22229999-0000-0000-0000-000000000001', 25, 2, 'corrida bloqueada')$$);
reset role;

-- ============================ G. INMUTABILIDAD DE suggested_quantity ============================
-- Incluso service_role (que si tiene GRANT update) queda bloqueado por el
-- trigger, no solo por RLS/GRANT (mismo criterio que D11 en 30_price_list_immutability.sql).
set local role service_role;
select test.expect_fail('G20 ni service_role puede sobrescribir suggested_quantity (trigger)',
  $$update public.purchase_run_lines set suggested_quantity = suggested_quantity + 1
    where id = '22229999-0000-0000-0000-000000000001'$$);
select test.expect_ok('G21 service_role SI puede tocar otras columnas (ej. note) de purchase_run_lines',
  $$update public.purchase_run_lines set note = 'nota de prueba'
    where id = '22229999-0000-0000-0000-000000000001'$$);
reset role;

-- ============================ G. ADMIN: cancelar y borrar una corrida ============================
select set_config('request.jwt.claim.sub', '11111111-1111-1111-1111-111111111111', true);
set local role authenticated;
select test.expect_ok('G22 admin cancela una corrida bloqueada',
  $$update public.purchase_runs set status = 'cancelled' where id = '11119999-0000-0000-0000-000000000001'$$);
select test.expect_ok('G23 admin borra una corrida completa',
  $$delete from public.purchase_runs where id = '11119999-0000-0000-0000-000000000001'$$);
select test.expect_true('G24 borrar la corrida arrastro sus lineas, dias objetivo y ajustes (cascade)',
  $$select (select count(*) from public.purchase_run_lines where purchase_run_id = '11119999-0000-0000-0000-000000000001') = 0
      and (select count(*) from public.purchase_run_target_days where purchase_run_id = '11119999-0000-0000-0000-000000000001') = 0
      and (select count(*) from public.purchase_line_adjustments pla
           join public.purchase_run_lines prl on prl.id = pla.purchase_run_line_id
           where prl.purchase_run_id = '11119999-0000-0000-0000-000000000001') = 0$$);
reset role;

-- ============================ G. anon ============================
set local role anon;
select test.expect_fail('G25 anon no puede leer purchase_runs',
  $$select 1 from public.purchase_runs$$);
select test.expect_fail('G26 anon no puede ejecutar el RPC',
  $$select public.update_final_quantity('11119999-0000-0000-0000-000000000002', 1, 1, null)$$);
reset role;

rollback;
