-- supabase/tests/sql/10_structure_and_grants.sql
-- Fase 2 — data-model — 27 asertos
--
-- A. Estructura: tablas, columnas generadas, CHECK de periodo, indices unicos
--    parciales y enums de las migraciones 0007-0010.
-- B. GRANT: el privilegio EFECTIVO de cada rol tiene que coincidir exactamente
--    con lo que permiten sus policies. Es la prueba de regresion del bug que
--    corrigio 0006 ("permission denied" antes de evaluar RLS) y de su reverso:
--    una instalacion de Supabase con `alter default privileges` concede ALL
--    sobre las tablas nuevas de `public`, asi que las migraciones revocan antes
--    de conceder.

set client_min_messages = notice;
begin;

\i /tmp/supabase/tests/sql/_data.sql

-- ============================ A. ESTRUCTURA ============================
select test.expect_true('A01 las 8 tablas de Fase 2 existen con RLS activa',
  $$select count(*) = 8 from pg_class c join pg_namespace n on n.oid=c.relnamespace
    where n.nspname='public' and c.relrowsecurity
      and c.relname in ('import_jobs','import_issues','price_lists','price_list_items',
                        'sales_imports','sales_lines','inventory_snapshots','inventory_lines')$$);

select test.expect_true('A02 import_jobs.period_days es generada e inclusiva (31 dias en enero)',
  $$select period_days = 31 from public.import_jobs where id='dddd0000-0000-0000-0000-000000000001'$$);

select test.expect_true('A03 period_days de un solo dia vale 1, no 0',
  $$select (period_end - period_start + 1) = 1 from (select '2026-03-05'::date period_start, '2026-03-05'::date period_end) t$$);

select test.expect_fail('A04 fechas invertidas rechazadas (nunca period_days<=0)',
  $$insert into public.import_jobs (type,file_id,period_start,period_end)
    values ('inveptos_sales','cccccccc-0000-0000-0000-000000000001','2026-03-31','2026-03-01')$$);

select test.expect_fail('A05 period_days no es asignable a mano (columna generada)',
  $$insert into public.import_jobs (type,file_id,period_start,period_end,period_days)
    values ('inveptos_sales','cccccccc-0000-0000-0000-000000000001','2026-03-01','2026-03-31',999)$$);

select test.expect_fail('A06 media fecha de periodo rechazada',
  $$insert into public.import_jobs (type,file_id,period_start) 
    values ('inveptos_sales','cccccccc-0000-0000-0000-000000000001','2026-03-01')$$);

select test.expect_true('A07 sales_imports.period_days generada = 31',
  $$select period_days = 31 from public.sales_imports where id='eeee0000-0000-0000-0000-000000000001'$$);

select test.expect_true('A08 indice unico parcial: una price_list active por proveedor',
  $$select count(*)=1 from pg_indexes where schemaname='public'
      and indexname='price_lists_one_active_per_supplier_idx'
      and indexdef ilike '%unique%' and indexdef ilike '%where (status = ''active''::price_list_status)%'$$);

select test.expect_true('A09 indice de sales_imports usa NULLS NOT DISTINCT',
  $$select indexdef ilike '%nulls not distinct%' from pg_indexes
    where indexname='sales_imports_one_active_per_period_idx'$$);

select test.expect_true('A10 indice unico parcial: un inventory_snapshot active por fecha',
  $$select count(*)=1 from pg_indexes where indexname='inventory_snapshots_one_active_per_date_idx'
      and indexdef ilike '%unique%' and indexdef ilike '%status = ''active''%'$$);

select test.expect_true('A11 enum import_type tiene exactamente los 3 valores del contrato',
  $$select array_agg(e.enumlabel::text order by e.enumsortorder) = array['sdos_inventory','inveptos_sales','supplier_price_list']
    from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='import_type'$$);

select test.expect_true('A12 enum import_status tiene los 4 estados del contrato',
  $$select array_agg(e.enumlabel::text order by e.enumsortorder) = array['pending','processing','completed','failed']
    from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='import_status'$$);

select test.expect_true('A13 enum issue_severity incluye info (lo emite engine/validation.py)',
  $$select array_agg(e.enumlabel::text order by e.enumsortorder) = array['error','warning','info']
    from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='issue_severity'$$);

select test.expect_true('A14 enum price_list_status con los 4 estados',
  $$select array_agg(e.enumlabel::text order by e.enumsortorder) = array['draft','active','superseded','archived']
    from pg_enum e join pg_type t on t.oid=e.enumtypid where t.typname='price_list_status'$$);

select test.expect_ok('A15 los 9 codigos de incidencia del motor caben en import_issues.code',
  $$insert into public.import_issues (import_job_id, severity, code, detail)
    select 'dddd0000-0000-0000-0000-000000000001', 'error', c, 'sintetico'
    from unnest(array['ean_invalido','ean_duplicado','costo_invalido','comodin_invalido','fecha_invalida',
                      'tisuc_desconocido','columna_faltante','total_inconsistente','cantidad_invalida']) c$$);

select test.expect_fail('A16 codigo de incidencia con formato invalido rechazado',
  $$insert into public.import_issues (import_job_id, severity, code, detail)
    values ('dddd0000-0000-0000-0000-000000000001','error','EAN Invalido!','x')$$);

-- ============================ B. GRANTS (regresion de 0006) ============================
select test.expect_true('B01 authenticated: select+insert en import_jobs, sin update/delete',
  $$select has_table_privilege('authenticated','public.import_jobs','select')
       and has_table_privilege('authenticated','public.import_jobs','insert')
       and not has_table_privilege('authenticated','public.import_jobs','update')
       and not has_table_privilege('authenticated','public.import_jobs','delete')$$);

select test.expect_true('B02 authenticated: select+insert en import_issues, sin update/delete',
  $$select has_table_privilege('authenticated','public.import_issues','select')
       and has_table_privilege('authenticated','public.import_issues','insert')
       and not has_table_privilege('authenticated','public.import_issues','update')
       and not has_table_privilege('authenticated','public.import_issues','delete')$$);

select test.expect_true('B03 authenticated: select/insert/update en price_lists, sin delete',
  $$select has_table_privilege('authenticated','public.price_lists','select')
       and has_table_privilege('authenticated','public.price_lists','insert')
       and has_table_privilege('authenticated','public.price_lists','update')
       and not has_table_privilege('authenticated','public.price_lists','delete')$$);

select test.expect_true('B04 authenticated: las 4 operaciones en price_list_items',
  $$select has_table_privilege('authenticated','public.price_list_items','select')
       and has_table_privilege('authenticated','public.price_list_items','insert')
       and has_table_privilege('authenticated','public.price_list_items','update')
       and has_table_privilege('authenticated','public.price_list_items','delete')$$);

select test.expect_true('B05 authenticated: SOLO select en sales_imports',
  $$select has_table_privilege('authenticated','public.sales_imports','select')
       and not has_table_privilege('authenticated','public.sales_imports','insert')
       and not has_table_privilege('authenticated','public.sales_imports','update')
       and not has_table_privilege('authenticated','public.sales_imports','delete')$$);

select test.expect_true('B06 authenticated: SOLO select en sales_lines',
  $$select has_table_privilege('authenticated','public.sales_lines','select')
       and not has_table_privilege('authenticated','public.sales_lines','insert')
       and not has_table_privilege('authenticated','public.sales_lines','update')
       and not has_table_privilege('authenticated','public.sales_lines','delete')$$);

select test.expect_true('B07 authenticated: SOLO select en inventory_snapshots',
  $$select has_table_privilege('authenticated','public.inventory_snapshots','select')
       and not has_table_privilege('authenticated','public.inventory_snapshots','insert')
       and not has_table_privilege('authenticated','public.inventory_snapshots','update')
       and not has_table_privilege('authenticated','public.inventory_snapshots','delete')$$);

select test.expect_true('B08 authenticated: SOLO select en inventory_lines',
  $$select has_table_privilege('authenticated','public.inventory_lines','select')
       and not has_table_privilege('authenticated','public.inventory_lines','insert')
       and not has_table_privilege('authenticated','public.inventory_lines','update')
       and not has_table_privilege('authenticated','public.inventory_lines','delete')$$);

select test.expect_true('B09 service_role puede escribir en las 8 tablas (pipeline de importacion)',
  $$select bool_and(has_table_privilege('service_role','public.'||t,'insert'))
    from unnest(array['import_jobs','import_issues','price_lists','price_list_items',
                      'sales_imports','sales_lines','inventory_snapshots','inventory_lines']) t$$);

select test.expect_true('B10 service_role puede actualizar cabeceras (superseded/completed)',
  $$select bool_and(has_table_privilege('service_role','public.'||t,'update'))
    from unnest(array['import_jobs','price_lists','sales_imports','inventory_snapshots']) t$$);

select test.expect_true('B11 anon no tiene ningun privilegio en las 8 tablas',
  $$select not bool_or(has_table_privilege('anon','public.'||t,p))
    from unnest(array['import_jobs','import_issues','price_lists','price_list_items',
                      'sales_imports','sales_lines','inventory_snapshots','inventory_lines']) t,
         unnest(array['select','insert','update','delete']) p$$);

rollback;
