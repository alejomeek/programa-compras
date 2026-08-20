-- supabase/seed.sql
-- Fase 1 — db-auth
--
-- NO es una migracion: no se versiona en `supabase/migrations/` ni se aplica en
-- produccion. Solo poblacion de bases de DESARROLLO (`supabase db reset`).
--
-- Regla innegociable: cero datos comerciales. Ningun proveedor, cliente, NIT,
-- EAN, SKU ni costo real de la empresa aparece aqui. Todos los nombres son
-- deliberadamente ficticios y los EAN son sinteticos.
--
-- Es idempotente: se puede ejecutar varias veces sin duplicar filas.

-- ---------------------------------------------------------------------------
-- 1. Ubicaciones
-- ---------------------------------------------------------------------------
-- Ya las inserta 0003_locations.sql (son catalogo operativo, no dato comercial).
-- Se reafirman aqui para bases locales creadas por otra via.
--
-- FERIA y BODBQLLA se retiraron del modelo (0013_retire_feria_bodega.sql):
-- nunca se borran filas, asi que siguen naciendo aqui igual que en 0003,
-- pero ya `active = false` desde el insert -- no hace falta un segundo paso
-- que las desactive en una base creada solo con este seed.
insert into public.locations
  (code, name, tisuc_code, type, is_purchase_target, active, display_order)
values
  ('AV19',     'Av. 19',            '10000', 'store',       true,  true,  1),
  ('BULEVAR',  'Bulevar',           '10010', 'store',       true,  true,  2),
  ('CALLE74',  'Calle 74',          '10500', 'store',       true,  true,  3),
  ('BVISTA',   'Bvista',            '10510', 'store',       true,  true,  4),
  ('OVIEDO',   'Oviedo',            '10800', 'store',       true,  true,  5),
  ('CEDI',     'CEDI',              '20010', 'warehouse',   true,  true,  6),
  ('FERIA',    'Feria',             '10600', 'fair',        false, false, 7),
  ('FULLML',   'Full MercadoLibre', '20020', 'marketplace', false, true,  8),
  ('BODBQLLA', 'Bodega Bqlla',      '20030', 'warehouse',   false, false, 9)
on conflict (code) do nothing;

-- ---------------------------------------------------------------------------
-- 2. Proveedores ficticios
-- ---------------------------------------------------------------------------
insert into public.suppliers (name, tbc_code, nit, contact_name, contact_email, active)
values
  ('Proveedor Demo Alfa',           '901', '900000001-1', 'Contacto Demo Alfa', 'demo-alfa@example.invalid', true),
  ('Juguetes Ficticios Beta S.A.S.', '902', '900000002-2', 'Contacto Demo Beta', 'demo-beta@example.invalid', true)
on conflict (tbc_code) do nothing;

-- ---------------------------------------------------------------------------
-- 3. Productos sinteticos
-- ---------------------------------------------------------------------------
-- Casos borde a proposito:
--   - DEMO-0003 tiene EAN con CERO INICIAL: si alguna capa lo pasa por numerico,
--     se corrompe. Es la fixture de regresion del contrato §3.4.
--   - DEMO-0004 no tiene tbc_sku: producto nuevo del proveedor, aun sin SKU TBC.
insert into public.products (tbc_sku, ean, name, current_pvp, active)
values
  ('DEMO-0001', '7700000000011', 'Producto Demo Uno',    45900.00, true),
  ('DEMO-0002', '7700000000028', 'Producto Demo Dos',    12500.00, true),
  ('DEMO-0003', '0123456789012', 'Producto Demo Tres (EAN con cero inicial)', 89900.00, true),
  (null,        '7700000000042', 'Producto Demo Cuatro (nuevo, sin SKU TBC)', null,     true)
on conflict (ean) do nothing;

-- ---------------------------------------------------------------------------
-- 4. Relacion proveedor-producto
-- ---------------------------------------------------------------------------
insert into public.supplier_products (supplier_id, product_id, ean, supplier_name, status)
select s.id, p.id, p.ean, v.supplier_name, v.status::public.supplier_product_status
from (values
  ('901', '7700000000011', 'PROD DEMO UNO',    'matched'),
  ('901', '7700000000028', 'PROD DEMO DOS',    'matched'),
  ('901', '0123456789012', 'PROD DEMO TRES',   'matched'),
  ('902', '7700000000042', 'PROD DEMO CUATRO', 'new')
) as v (tbc_code, ean, supplier_name, status)
join public.suppliers s on s.tbc_code = v.tbc_code
join public.products  p on p.ean      = v.ean
on conflict (supplier_id, ean) do nothing;

-- EAN que el proveedor lista pero que no existe en el catalogo TBC: no tiene
-- product_id. Es el caso 'unmatched' que la UI de catalogo debe mostrar.
insert into public.supplier_products (supplier_id, product_id, ean, supplier_name, status)
select s.id, null, '7700000000059', 'PROD DEMO CINCO', 'unmatched'
from public.suppliers s
where s.tbc_code = '902'
on conflict (supplier_id, ean) do nothing;

-- ---------------------------------------------------------------------------
-- 5. Usuarios y roles  (NO se siembran; paso manual documentado)
-- ---------------------------------------------------------------------------
-- Este seed NO escribe en `auth.users`. Sus columnas cambian entre versiones de
-- Supabase y no hay forma de verificar el insert sin una instancia real; una
-- fila mal formada deja Auth en un estado dificil de diagnosticar.
--
-- El flujo correcto es:
--   1. Registrarse en la aplicacion (o crear el usuario desde el panel de
--      Supabase > Authentication > Users).
--   2. El trigger `on_auth_user_created` (migracion 0002) crea automaticamente
--      el `profiles` con rol 'viewer'.
--   3. Promover ese usuario a admin UNA vez, desde el SQL editor:
--
--        update public.profiles
--        set role = 'admin'
--        where id = (select id from auth.users where email = 'tu-correo@example.com');
--
--      (o, si ya conoces el uuid:  where id = '00000000-0000-0000-0000-000000000000';)
--
--   4. A partir de ahi, ese admin asigna roles al resto desde /settings.
--
-- Los demas roles se asignan con el mismo UPDATE cambiando 'admin' por
-- 'buyer' o 'viewer'.

-- ---------------------------------------------------------------------------
-- 6. Importaciones sinteticas (Fase 2)
-- ---------------------------------------------------------------------------
-- Da algo que dibujar a /imports y /suppliers sin depender de subir un archivo
-- real: una importacion completada con incidencias, una fallida y una lista de
-- precios en borrador. Cero datos comerciales: los EAN, costos y nombres son
-- los mismos ficticios de los bloques anteriores.
--
-- Los ids son fijos para que el bloque sea idempotente (`on conflict do nothing`)
-- y para que las pruebas puedan referirse a ellos sin adivinar.

insert into public.files (id, bucket, object_path, original_name, mime_type, size_bytes, sha256)
values
  ('11110000-0000-4000-8000-000000000001', 'source-files',
   '2026/01/00000000-0000-0000-0000-000000000000/lista-demo-alfa.xlsx',
   'LISTA DEMO ALFA.xlsx',
   'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
   20480, repeat('ab', 32)),
  ('11110000-0000-4000-8000-000000000002', 'source-files',
   '2026/01/00000000-0000-0000-0000-000000000000/sdos-demo.csv',
   'SDOS DEMO.CSV', 'text/csv', 51200, repeat('cd', 32))
on conflict (bucket, object_path) do nothing;

-- Importacion COMPLETADA de lista de precios (3 filas validas, 1 rechazada).
insert into public.import_jobs
  (id, type, supplier_id, file_id, status, rows_total, rows_valid, rows_rejected,
   started_at, finished_at)
select
  '22220000-0000-4000-8000-000000000001', 'supplier_price_list', s.id,
  '11110000-0000-4000-8000-000000000001', 'completed', 4, 3, 1,
  now() - interval '2 hours', now() - interval '2 hours' + interval '11 seconds'
from public.suppliers s
where s.tbc_code = '901'
on conflict (id) do nothing;

-- Importacion FALLIDA de inventario: el caso que la UI debe explicar con causa
-- y accion concreta, no con un codigo crudo (contrato §10.4).
insert into public.import_jobs
  (id, type, file_id, status, rows_total, rows_valid, rows_rejected,
   error_message, started_at, finished_at)
values
  ('22220000-0000-4000-8000-000000000002', 'sdos_inventory',
   '11110000-0000-4000-8000-000000000002', 'failed', 0, 0, 0,
   'La columna Codean no existe en el archivo. Exporta SDOSXSUC de nuevo sin quitar columnas.',
   now() - interval '1 hour', now() - interval '1 hour' + interval '3 seconds')
on conflict (id) do nothing;

insert into public.import_issues
  (id, import_job_id, file_id, severity, code, source, row_number, ean, sku, product_name, detail)
values
  ('33330000-0000-4000-8000-000000000001', '22220000-0000-4000-8000-000000000001',
   '11110000-0000-4000-8000-000000000001', 'error', 'ean_invalido', 'Proveedor', 12,
   '77000 00000059', '', 'PROD DEMO SEIS',
   'El EAN trae un espacio: se excluyo del cruce en vez de limpiarlo.'),
  ('33330000-0000-4000-8000-000000000002', '22220000-0000-4000-8000-000000000001',
   '11110000-0000-4000-8000-000000000001', 'warning', 'costo_invalido', 'Proveedor', 15,
   '7700000000042', '', 'PROD DEMO CUATRO',
   'Costo vacio en la lista del proveedor: el producto quedo sin costo comparable.')
on conflict (id) do nothing;

-- Lista de precios en BORRADOR: editable, todavia sin publicar. Mientras siga
-- en draft se le pueden agregar/quitar renglones; al pasar a 'active' queda
-- inmutable por trigger (migracion 0008).
insert into public.price_lists
  (id, supplier_id, source_file_id, version, effective_date, status, import_job_id)
select
  '44440000-0000-4000-8000-000000000001', s.id,
  '11110000-0000-4000-8000-000000000001', 1, current_date, 'draft',
  '22220000-0000-4000-8000-000000000001'
from public.suppliers s
where s.tbc_code = '901'
on conflict (id) do nothing;

insert into public.price_list_items
  (price_list_id, supplier_product_id, ean, supplier_cost, source_row_number, raw)
select
  '44440000-0000-4000-8000-000000000001', sp.id, v.ean, v.cost, v.row_number,
  jsonb_build_object('origen', 'seed sintetico', 'fila', v.row_number)
from (values
  ('7700000000011', 28900.00, 2),
  ('7700000000028',  7350.00, 3),
  -- EAN con cero inicial: si alguna capa lo pasa por numerico, se corrompe.
  ('0123456789012', 56400.00, 4)
) as v (ean, cost, row_number)
join public.suppliers s on s.tbc_code = '901'
left join public.supplier_products sp on sp.supplier_id = s.id and sp.ean = v.ean
on conflict (price_list_id, ean) do nothing;
