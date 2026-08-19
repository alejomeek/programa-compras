-- supabase/tests/sql/40_constraints_and_history.sql
-- Fase 2 — data-model — 28 asertos
--
-- Constraints de dominio y reglas de historial (contrato §3.4, §9.2, §9.3).
-- Incluye dos asertos estructurales anti-regresion: que no exista ninguna
-- columna de redistribucion/objetivo/excedente/quiebre en el esquema (§5.1) y
-- que ninguna columna `ean` sea numerica (§9.6).

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql
set local role service_role;

-- ============================ E. CONSTRAINTS E HISTORIAL ============================
select test.expect_fail('E01 EAN no numerico rechazado en price_list_items',
  $sql$insert into public.price_list_items (price_list_id,ean,supplier_cost)
       values ('ffff0000-0000-0000-0000-000000000001','77A0000000011',100.00)$sql$);
select test.expect_fail('E02 EAN con espacio rechazado en sales_lines (no se limpia, se rechaza)',
  $sql$insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
       values ('eeee0000-0000-0000-0000-000000000001','7700000 000011',(select id from public.locations where code='AV19'),1)$sql$);
select test.expect_fail('E03 EAN vacio rechazado en inventory_lines',
  $sql$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand)
       values ('eeee0000-0000-0000-0000-000000000002','',(select id from public.locations where code='AV19'),1)$sql$);
select test.expect_true('E04 EAN con cero inicial sobrevive intacto (regresion §3.4)',
  $sql$with i as (
        insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
        values ('eeee0000-0000-0000-0000-000000000001','0123456789012',(select id from public.locations where code='AV19'),4)
        returning ean)
      select ean = '0123456789012' and length(ean) = 13 from i$sql$);
select test.expect_fail('E05 costo de proveedor negativo rechazado',
  $sql$insert into public.price_list_items (price_list_id,ean,supplier_cost)
       values ('ffff0000-0000-0000-0000-000000000001','7700000000059',-1.00)$sql$);
select test.expect_fail('E06 unidades vendidas negativas rechazadas',
  $sql$insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
       values ('eeee0000-0000-0000-0000-000000000001','7700000000059',(select id from public.locations where code='AV19'),-1)$sql$);
select test.expect_fail('E07 existencia negativa rechazada (no se recorta a 0)',
  $sql$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand)
       values ('eeee0000-0000-0000-0000-000000000002','7700000000059',(select id from public.locations where code='AV19'),-5)$sql$);
select test.expect_fail('E08 comodin de proveedor no numerico rechazado en inventory_lines',
  $sql$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand,supplier_tbc_code)
       values ('eeee0000-0000-0000-0000-000000000002','7700000000059',(select id from public.locations where code='AV19'),1,'A01')$sql$);
select test.expect_fail('E09 EAN duplicado dentro de una lista de precios rechazado',
  $sql$insert into public.price_list_items (price_list_id,ean,supplier_cost)
       values ('ffff0000-0000-0000-0000-000000000001','7700000000011',999.00)$sql$);
select test.expect_fail('E10 (importacion, EAN, ubicacion) duplicado rechazado en ventas',
  $sql$insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
       values ('eeee0000-0000-0000-0000-000000000001','7700000000011',(select id from public.locations where code='CEDI'),99)$sql$);
select test.expect_fail('E11 (snapshot, EAN, ubicacion) duplicado rechazado en inventario',
  $sql$insert into public.inventory_lines (snapshot_id,ean,location_id,on_hand)
       values ('eeee0000-0000-0000-0000-000000000002','7700000000011',(select id from public.locations where code='CEDI'),9)$sql$);
select test.expect_ok('E12 el mismo EAN en otra ubicacion si se admite',
  $sql$insert into public.sales_lines (sales_import_id,ean,location_id,units_sold)
       values ('eeee0000-0000-0000-0000-000000000001','7700000000011',(select id from public.locations where code='BULEVAR'),7)$sql$);

-- historial: no sobrescribir importaciones
select test.expect_fail('E13 dos importaciones de ventas active del mismo periodo sin proveedor colisionan (nulls not distinct)',
  $sql$with j as (
         insert into public.import_jobs (type,file_id,status,period_start,period_end)
         values ('inveptos_sales','cccccccc-0000-0000-0000-000000000004','completed','2026-01-01','2026-01-31') returning id)
       insert into public.sales_imports (import_job_id,supplier_id,period_start,period_end,status)
       select id,null,'2026-01-01','2026-01-31','active' from j$sql$);
select test.expect_ok('E14 la version anterior superseded libera el periodo para la nueva',
  $sql$do $x$
      declare v_job uuid;
      begin
        update public.sales_imports set status='superseded' where id='eeee0000-0000-0000-0000-000000000001';
        insert into public.import_jobs (type,file_id,status,period_start,period_end)
          values ('inveptos_sales','cccccccc-0000-0000-0000-000000000004','completed','2026-01-01','2026-01-31')
          returning id into v_job;
        insert into public.sales_imports (import_job_id,period_start,period_end,status)
          values (v_job,'2026-01-01','2026-01-31','active');
      end $x$$sql$);
select test.expect_fail('E15 dos snapshots de inventario active de la misma fecha colisionan',
  $sql$with j as (
         insert into public.import_jobs (type,file_id,status)
         values ('sdos_inventory','cccccccc-0000-0000-0000-000000000004','completed') returning id)
       insert into public.inventory_snapshots (import_job_id,snapshot_date,status)
       select id,'2026-02-01','active' from j$sql$);
select test.expect_ok('E16 un snapshot active de otra fecha si se admite',
  $sql$with j as (
         insert into public.import_jobs (type,file_id,status)
         values ('sdos_inventory','cccccccc-0000-0000-0000-000000000004','completed') returning id)
       insert into public.inventory_snapshots (import_job_id,snapshot_date,status)
       select id,'2026-02-02','active' from j$sql$);
select test.expect_fail('E17 un import_job no puede alimentar dos sales_imports (unique)',
  $sql$insert into public.sales_imports (import_job_id,period_start,period_end,status)
       values ('dddd0000-0000-0000-0000-000000000001','2026-04-01','2026-04-30','active')$sql$);
select test.expect_fail('E18 failed sin error_message rechazado (§9.3)',
  $sql$update public.import_jobs set status='failed' where id='dddd0000-0000-0000-0000-000000000003'$sql$);
select test.expect_ok('E19 failed con motivo legible aceptado',
  $sql$update public.import_jobs set status='failed', error_message='Fecha FDESDE ilegible en la fila 1.'
       where id='dddd0000-0000-0000-0000-000000000003'$sql$);
select test.expect_fail('E20 lista de precios sin proveedor rechazada',
  $sql$insert into public.import_jobs (type,file_id,status)
       values ('supplier_price_list','cccccccc-0000-0000-0000-000000000004','pending')$sql$);
-- E21-E23 se ejecutan como owner (postgres): probamos el comportamiento de las
-- FK (restrict/cascade), no los privilegios, que ya cubre el grupo B.
reset role;
select test.expect_fail('E21 no se puede borrar un import_job usado por una importacion (restrict)',
  $sql$delete from public.import_jobs where id='dddd0000-0000-0000-0000-000000000001'$sql$);
select test.expect_ok('E22 borrar la cabecera de ventas es posible',
  $sql$delete from public.sales_imports where id='eeee0000-0000-0000-0000-000000000001'$sql$);
select test.expect_true('E22b y arrastra sus lineas (cascade)',
  $sql$select count(*) = 0 from public.sales_lines
       where sales_import_id='eeee0000-0000-0000-0000-000000000001'$sql$);
select test.expect_ok('E23 borrar el import_job ya sin dependientes',
  $sql$delete from public.import_jobs where id='dddd0000-0000-0000-0000-000000000001'$sql$);
select test.expect_true('E23b y arrastra sus incidencias (cascade)',
  $sql$select count(*) = 0 from public.import_issues
       where import_job_id='dddd0000-0000-0000-0000-000000000001'$sql$);
select test.expect_true('E23c ni authenticated ni service_role pueden borrar import_jobs (historial)',
  $sql$select not has_table_privilege('authenticated','public.import_jobs','delete')
        and not has_table_privilege('service_role','public.import_jobs','delete')$sql$);
select test.expect_true('E24 sin columnas de redistribucion/objetivo de inventario en el esquema (§5.1)',
  $sql$select count(*) = 0 from information_schema.columns
       where table_schema='public'
         and (column_name ilike '%transfer%' or column_name ilike '%redistrib%'
              or column_name ilike '%objetivo%' or column_name ilike '%inventory_objective%'
              or column_name ilike '%stockout%' or column_name ilike '%surplus%')$sql$);
select test.expect_true('E25 ninguna columna EAN es numerica en todo el esquema (§9.6)',
  $sql$select count(*) = 0 from information_schema.columns
       where table_schema='public' and column_name='ean' and data_type <> 'text'$sql$);
reset role;
rollback;
