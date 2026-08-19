-- 0004_suppliers_products.sql
-- Fase 1 — db-auth
-- `suppliers`, `products` y `supplier_products` (contrato §6.3, plan §5).
--
-- Regla transversal del contrato §6.1 y §9.6: `ean` es SIEMPRE text con check de
-- digitos, nunca numerico. Un EAN con ceros iniciales debe sobrevivir intacto.
--
-- D5 (contrato §2): se implementa el default "sin restriccion por proveedor":
-- cualquier usuario autenticado y activo lee todos los proveedores. No se crea
-- `user_suppliers`. Si mas adelante se decide restringir, basta reemplazar las
-- policies `*_select_authenticated` de aqui en una migracion nueva; ninguna FK
-- ni constraint de este archivo asume acceso global.

-- ---------------------------------------------------------------------------
-- suppliers
-- ---------------------------------------------------------------------------
create table if not exists public.suppliers (
  id             uuid primary key default gen_random_uuid(),
  name           text not null unique check (length(btrim(name)) > 0),
  -- Comodin TBC: exactamente 3 digitos (contrato §3.4 / §6.3).
  tbc_code       char(3) not null unique check (tbc_code ~ '^[0-9]{3}$'),
  nit            text,
  contact_name   text,
  contact_email  text,
  contact_phone  text,
  active         boolean not null default true,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  created_by     uuid references public.profiles (id) on delete set null,
  updated_by     uuid references public.profiles (id) on delete set null
);

comment on table public.suppliers is
  'Proveedores. `tbc_code` es el comodin de 3 digitos usado para filtrar SDOSXSUC/INVEPTOS.';

create index if not exists suppliers_active_name_idx
  on public.suppliers (name) where active;

drop trigger if exists suppliers_set_updated_at on public.suppliers;
create trigger suppliers_set_updated_at
  before update on public.suppliers
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- products
-- ---------------------------------------------------------------------------
create table if not exists public.products (
  id           uuid primary key default gen_random_uuid(),
  tbc_sku      text unique check (length(btrim(tbc_sku)) > 0),
  ean          text unique check (ean ~ '^[0-9]+$'),
  name         text not null check (length(btrim(name)) > 0),
  current_pvp  numeric(14,2) check (current_pvp >= 0),
  active       boolean not null default true,
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now(),
  -- Una fila sin ningun identificador no es referenciable desde ninguna fuente.
  constraint products_identifier_present_check
    check (tbc_sku is not null or ean is not null)
);

comment on table public.products is
  'Catalogo TBC normalizado. Un EAN invalido nunca crea una fila aqui (queda como incidencia de importacion).';
comment on column public.products.ean is
  'Texto exacto, solo digitos, cualquier longitud. Nunca convertir a numero: se perderian los ceros iniciales.';

drop trigger if exists products_set_updated_at on public.products;
create trigger products_set_updated_at
  before update on public.products
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- supplier_products
-- ---------------------------------------------------------------------------
create table if not exists public.supplier_products (
  id             uuid primary key default gen_random_uuid(),
  supplier_id    uuid not null references public.suppliers (id) on delete restrict,
  -- Nullable: un producto nuevo del proveedor puede no tener aun SKU TBC.
  product_id     uuid references public.products (id) on delete set null,
  ean            text not null check (ean ~ '^[0-9]+$'),
  supplier_name  text,
  status         public.supplier_product_status not null default 'new',
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  constraint supplier_products_supplier_ean_key unique (supplier_id, ean)
);

comment on table public.supplier_products is
  'Relacion proveedor-producto por EAN. status = new reemplaza al marcador literal "NUEVO" del Excel actual.';

create index if not exists supplier_products_product_id_idx
  on public.supplier_products (product_id);
create index if not exists supplier_products_ean_idx
  on public.supplier_products (ean);
create index if not exists supplier_products_supplier_status_idx
  on public.supplier_products (supplier_id, status);

drop trigger if exists supplier_products_set_updated_at on public.supplier_products;
create trigger supplier_products_set_updated_at
  before update on public.supplier_products
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- RLS (contrato §7: todos leen; solo admin escribe; nadie borra)
-- ---------------------------------------------------------------------------
alter table public.suppliers         enable row level security;
alter table public.products          enable row level security;
alter table public.supplier_products enable row level security;

revoke all on table public.suppliers         from anon;
revoke all on table public.products          from anon;
revoke all on table public.supplier_products from anon;

-- suppliers
drop policy if exists suppliers_select_authenticated on public.suppliers;
create policy suppliers_select_authenticated on public.suppliers
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists suppliers_insert_admin on public.suppliers;
create policy suppliers_insert_admin on public.suppliers
  for insert to authenticated
  with check ((select public.is_admin()));

drop policy if exists suppliers_update_admin on public.suppliers;
create policy suppliers_update_admin on public.suppliers
  for update to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));

-- products
drop policy if exists products_select_authenticated on public.products;
create policy products_select_authenticated on public.products
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists products_insert_admin on public.products;
create policy products_insert_admin on public.products
  for insert to authenticated
  with check ((select public.is_admin()));

drop policy if exists products_update_admin on public.products;
create policy products_update_admin on public.products
  for update to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));

-- supplier_products
drop policy if exists supplier_products_select_authenticated on public.supplier_products;
create policy supplier_products_select_authenticated on public.supplier_products
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists supplier_products_insert_admin on public.supplier_products;
create policy supplier_products_insert_admin on public.supplier_products
  for insert to authenticated
  with check ((select public.is_admin()));

drop policy if exists supplier_products_update_admin on public.supplier_products;
create policy supplier_products_update_admin on public.supplier_products
  for update to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));

-- Sin policies de DELETE en ninguna de las tres tablas: baja logica via
-- `active` / `status = 'discontinued'`. Las escrituras de proceso (parseo de
-- importaciones) van por `service_role`, que omite RLS por diseno (contrato §7).
