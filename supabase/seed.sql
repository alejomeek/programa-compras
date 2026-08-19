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
insert into public.locations
  (code, name, tisuc_code, type, is_purchase_target, display_order)
values
  ('AV19',     'Av. 19',            '10000', 'store',       true,  1),
  ('BULEVAR',  'Bulevar',           '10010', 'store',       true,  2),
  ('CALLE74',  'Calle 74',          '10500', 'store',       true,  3),
  ('BVISTA',   'Bvista',            '10510', 'store',       true,  4),
  ('OVIEDO',   'Oviedo',            '10800', 'store',       true,  5),
  ('CEDI',     'CEDI',              '20010', 'warehouse',   true,  6),
  ('FERIA',    'Feria',             '10600', 'fair',        false, 7),
  ('FULLML',   'Full MercadoLibre', '20020', 'marketplace', false, 8),
  ('BODBQLLA', 'Bodega Bqlla',      '20030', 'warehouse',   false, 9)
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
