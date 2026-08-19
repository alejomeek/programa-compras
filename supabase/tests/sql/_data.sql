-- supabase/tests/sql/_data.sql
-- Fase 2 — data-model
--
-- Datos de trabajo de las tablas de Fase 2, compartidos por varias suites.
-- Se incluye con \i dentro de la transaccion de cada suite, que termina en
-- ROLLBACK: ninguna suite ve el estado que dejo otra.

insert into public.import_jobs (id, type, supplier_id, file_id, status, period_start, period_end, created_by)
values
  ('dddd0000-0000-0000-0000-000000000001','inveptos_sales',      null,                                   'cccccccc-0000-0000-0000-000000000001','completed','2026-01-01','2026-01-31','22222222-2222-2222-2222-222222222222'),
  ('dddd0000-0000-0000-0000-000000000002','sdos_inventory',      null,                                   'cccccccc-0000-0000-0000-000000000003','completed',null,null,'22222222-2222-2222-2222-222222222222'),
  ('dddd0000-0000-0000-0000-000000000003','supplier_price_list', 'aaaaaaaa-0000-0000-0000-000000000001', 'cccccccc-0000-0000-0000-000000000002','completed',null,null,'22222222-2222-2222-2222-222222222222'),
  ('dddd0000-0000-0000-0000-000000000004','supplier_price_list', 'aaaaaaaa-0000-0000-0000-000000000002', 'cccccccc-0000-0000-0000-000000000004','completed',null,null,'22222222-2222-2222-2222-222222222222');

insert into public.sales_imports (id, import_job_id, supplier_id, period_start, period_end, status, created_by)
values ('eeee0000-0000-0000-0000-000000000001','dddd0000-0000-0000-0000-000000000001',null,'2026-01-01','2026-01-31','active','22222222-2222-2222-2222-222222222222');

insert into public.sales_lines (sales_import_id, ean, location_id, units_sold, tbc_cost, source_row_number)
values ('eeee0000-0000-0000-0000-000000000001','7700000000011',(select id from public.locations where code='CEDI'),10,15000.00,2);

insert into public.inventory_snapshots (id, import_job_id, snapshot_date, fair_mode, status)
values ('eeee0000-0000-0000-0000-000000000002','dddd0000-0000-0000-0000-000000000002','2026-02-01',false,'active');

insert into public.inventory_lines (snapshot_id, ean, tbc_sku, location_id, on_hand, pvp, supplier_tbc_code)
values ('eeee0000-0000-0000-0000-000000000002','7700000000011','TST-0001',(select id from public.locations where code='CEDI'),5,45900.00,'801');

insert into public.price_lists (id, supplier_id, source_file_id, version, effective_date, status, import_job_id, created_by)
values
  ('ffff0000-0000-0000-0000-000000000001','aaaaaaaa-0000-0000-0000-000000000001','cccccccc-0000-0000-0000-000000000002',1,'2026-01-15','draft', 'dddd0000-0000-0000-0000-000000000003','22222222-2222-2222-2222-222222222222'),
  ('ffff0000-0000-0000-0000-000000000002','aaaaaaaa-0000-0000-0000-000000000002','cccccccc-0000-0000-0000-000000000004',1,'2026-01-15','active','dddd0000-0000-0000-0000-000000000004','22222222-2222-2222-2222-222222222222');

insert into public.price_list_items (price_list_id, ean, supplier_cost, source_row_number, raw)
values ('ffff0000-0000-0000-0000-000000000001','7700000000011',12000.00,9,'{"origen":"sintetico"}'::jsonb);

alter table public.price_list_items disable trigger price_list_items_parent_draft;
insert into public.price_list_items (id, price_list_id, ean, supplier_cost, source_row_number)
values ('ffff0000-0000-0000-0000-0000000000aa','ffff0000-0000-0000-0000-000000000002','7700000000028',9000.00,3);
alter table public.price_list_items enable trigger price_list_items_parent_draft;

insert into public.import_issues (import_job_id, severity, code, source, row_number, ean, detail)
values ('dddd0000-0000-0000-0000-000000000001','error','ean_invalido','INVEPTOS',7,'77000 00011','EAN con espacio interno');

-- objetos de Storage sintéticos (uno del admin, uno del buyer)
insert into storage.objects (bucket_id, name, owner) values
  ('source-files','2026/08/11111111-1111-1111-1111-111111111111/adm.xls','11111111-1111-1111-1111-111111111111'),
  ('exports','11111111-1111-1111-1111-111111111111/20260818/adm.xlsx','11111111-1111-1111-1111-111111111111'),
  ('exports','22222222-2222-2222-2222-222222222222/20260818/buy.xlsx','22222222-2222-2222-2222-222222222222');
