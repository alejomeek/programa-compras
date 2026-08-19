-- supabase/tests/sql/01_fixtures.sql
-- Fase 2 — data-model
--
-- Actores y catalogo minimo para las suites: 4 usuarios (admin, buyer, viewer,
-- inactivo), 2 proveedores, 2 productos y 4 archivos. Todo 100% sintetico: ni
-- un nombre, EAN, NIT o costo real de la empresa.
insert into auth.users (id, email, raw_user_meta_data) values
  ('11111111-1111-1111-1111-111111111111', 'admin@example.invalid',    '{"full_name":"Admin Prueba"}'::jsonb),
  ('22222222-2222-2222-2222-222222222222', 'buyer@example.invalid',    '{"full_name":"Buyer Prueba"}'::jsonb),
  ('33333333-3333-3333-3333-333333333333', 'viewer@example.invalid',   '{"full_name":"Viewer Prueba"}'::jsonb),
  ('44444444-4444-4444-4444-444444444444', 'inactivo@example.invalid', '{"full_name":"Inactivo Prueba"}'::jsonb)
on conflict (id) do nothing;

update public.profiles set role = 'admin'  where id = '11111111-1111-1111-1111-111111111111';
update public.profiles set role = 'buyer'  where id = '22222222-2222-2222-2222-222222222222';
update public.profiles set role = 'viewer' where id = '33333333-3333-3333-3333-333333333333';
update public.profiles set role = 'buyer', active = false where id = '44444444-4444-4444-4444-444444444444';

insert into public.suppliers (id, name, tbc_code) values
  ('aaaaaaaa-0000-0000-0000-000000000001', 'Proveedor Prueba Uno', '801'),
  ('aaaaaaaa-0000-0000-0000-000000000002', 'Proveedor Prueba Dos', '802')
on conflict (tbc_code) do nothing;

insert into public.products (id, tbc_sku, ean, name) values
  ('bbbbbbbb-0000-0000-0000-000000000001', 'TST-0001', '7700000000011', 'Producto Prueba Uno'),
  ('bbbbbbbb-0000-0000-0000-000000000002', 'TST-0002', '0123456789012', 'Producto Prueba Cero Inicial')
on conflict (ean) do nothing;

insert into public.files (id, bucket, object_path, original_name, size_bytes, sha256, uploaded_by) values
  ('cccccccc-0000-0000-0000-000000000001', 'source-files', '2026/08/22222222-2222-2222-2222-222222222222/f1.xls', 'inv.xls', 100, repeat('a',64), '22222222-2222-2222-2222-222222222222'),
  ('cccccccc-0000-0000-0000-000000000002', 'source-files', '2026/08/22222222-2222-2222-2222-222222222222/f2.xlsx','lista.xlsx',100, repeat('b',64), '22222222-2222-2222-2222-222222222222'),
  ('cccccccc-0000-0000-0000-000000000003', 'source-files', '2026/08/22222222-2222-2222-2222-222222222222/f3.csv', 'sdos.csv', 100, repeat('c',64), '22222222-2222-2222-2222-222222222222'),
  ('cccccccc-0000-0000-0000-000000000004', 'source-files', '2026/08/22222222-2222-2222-2222-222222222222/f4.csv', 'sdos2.csv',100, repeat('d',64), '22222222-2222-2222-2222-222222222222')
on conflict (bucket, object_path) do nothing;
