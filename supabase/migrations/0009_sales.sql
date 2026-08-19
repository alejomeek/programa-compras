-- 0009_sales.sql
-- Fase 2 — data-model
-- `sales_imports` y `sales_lines`: las unidades vendidas por ubicacion, unico
-- insumo de la formula de compra (contrato §6.2, §6.3, §7, §9.2).
--
-- Escritura EXCLUSIVA de `service_role` (contrato §7): estas tablas no tienen
-- ninguna policy de insert/update/delete para `authenticated`, y su GRANT es
-- solo `select`. Un dato de ventas alterado desde el navegador cambiaria toda
-- la sugerencia de compra sin dejar rastro.

do $$
begin
  if not exists (select 1 from pg_type where typname = 'dataset_status') then
    -- Compartido con `inventory_snapshots` (0010): una cabecera de datos
    -- historicos nunca se actualiza in-place; se reemplaza por otra y la
    -- anterior queda `superseded` (contrato §9.2).
    create type public.dataset_status as enum ('active', 'superseded');
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- sales_imports
-- ---------------------------------------------------------------------------
create table if not exists public.sales_imports (
  id             uuid primary key default gen_random_uuid(),
  import_job_id  uuid not null unique references public.import_jobs (id) on delete restrict,
  -- Nullable: INVEPTOS suele venir global, sin proveedor.
  supplier_id    uuid references public.suppliers (id) on delete restrict,
  period_start   date not null,
  period_end     date not null,
  period_days    integer generated always as (period_end - period_start + 1) stored,
  status         public.dataset_status not null default 'active',
  created_by     uuid references public.profiles (id) on delete set null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  -- Periodo inclusivo, piso 1 y bloqueante (contrato §3.4 / plan §6.4).
  constraint sales_imports_period_days_positive_check check (period_days > 0)
);

comment on table public.sales_imports is
  'Cabecera de una importacion de ventas TBC. Nunca se actualiza in-place: archivo nuevo = fila nueva active y la anterior superseded (contrato §9.2).';
comment on column public.sales_imports.period_days is
  'Generada e inclusiva. El CHECK > 0 impide el period_days = 1 silencioso que el motor viejo producia ante fechas ilegibles.';

-- Una sola importacion vigente por (proveedor, periodo). `nulls not distinct`
-- es imprescindible: sin el, dos importaciones activas con supplier_id NULL
-- -- el caso normal de INVEPTOS -- no colisionarian y §9.2 se romperia en
-- silencio.
create unique index if not exists sales_imports_one_active_per_period_idx
  on public.sales_imports (supplier_id, period_start, period_end) nulls not distinct
  where status = 'active';

create index if not exists sales_imports_status_period_idx
  on public.sales_imports (status, period_end desc);

drop trigger if exists sales_imports_set_updated_at on public.sales_imports;
create trigger sales_imports_set_updated_at
  before update on public.sales_imports
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- sales_lines
-- ---------------------------------------------------------------------------
create table if not exists public.sales_lines (
  id                 uuid primary key default gen_random_uuid(),
  sales_import_id    uuid not null references public.sales_imports (id) on delete cascade,
  ean                text not null check (ean ~ '^[0-9]+$'),
  location_id        uuid not null references public.locations (id) on delete restrict,
  -- Nullable: el EAN puede no existir todavia en el catalogo `products`.
  product_id         uuid references public.products (id) on delete set null,
  units_sold         integer not null check (units_sold >= 0),
  tbc_cost           numeric(14,2) check (tbc_cost >= 0),
  source_row_number  integer check (source_row_number > 0),
  created_at         timestamptz not null default now(),
  constraint sales_lines_import_ean_location_key unique (sales_import_id, ean, location_id)
);

comment on table public.sales_lines is
  'Unidades vendidas por EAN y ubicacion (UNSUC# de INVEPTOS). Es el unico insumo de compra_sugerida; el inventario nunca resta.';
comment on column public.sales_lines.ean is
  'Texto exacto, solo digitos (contrato §3.4 / §9.6). Un EAN invalido no llega aqui: queda como import_issue.';
comment on column public.sales_lines.tbc_cost is
  'VALCOS de INVEPTOS: costo TBC, base de la comparacion contra el costo del proveedor.';

create index if not exists sales_lines_import_location_idx
  on public.sales_lines (sales_import_id, location_id);
create index if not exists sales_lines_ean_idx        on public.sales_lines (ean);
create index if not exists sales_lines_product_id_idx on public.sales_lines (product_id);

-- ---------------------------------------------------------------------------
-- RLS (contrato §7: solo lectura para todo autenticado; escritura service_role)
-- ---------------------------------------------------------------------------
alter table public.sales_imports enable row level security;
alter table public.sales_lines   enable row level security;

revoke all on table public.sales_imports from anon;
revoke all on table public.sales_lines   from anon;

drop policy if exists sales_imports_select_authenticated on public.sales_imports;
create policy sales_imports_select_authenticated on public.sales_imports
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists sales_lines_select_authenticated on public.sales_lines;
create policy sales_lines_select_authenticated on public.sales_lines
  for select to authenticated
  using ((select public.current_user_role()) is not null);

-- Deliberadamente NO existen policies de insert/update/delete: el pipeline de
-- importacion escribe con `service_role`, que omite RLS.

-- ---------------------------------------------------------------------------
-- GRANT explicitos (leccion de 0006)
-- ---------------------------------------------------------------------------
-- El revoke es la parte critica en estas dos tablas (ver nota en 0007): la
-- escritura es exclusiva de `service_role` (contrato §7), asi que `authenticated`
-- no debe conservar ni el privilegio de insert/update/delete que una
-- instalacion con `alter default privileges` le daria automaticamente.
revoke all on table public.sales_imports from anon, authenticated, service_role;
revoke all on table public.sales_lines   from anon, authenticated, service_role;

-- Solo select: aunque manana alguien agregara una policy de escritura por
-- error, sin GRANT no habria forma de escribir desde `authenticated`.
grant select on table public.sales_imports to authenticated;
grant select on table public.sales_lines   to authenticated;

-- `service_role` omite RLS pero NO los GRANT de tabla; sin esto el pipeline
-- falla con "permission denied" (mismo bug que corrigio 0006).
grant select, insert, update, delete on table public.sales_imports to service_role;
grant select, insert, update, delete on table public.sales_lines   to service_role;
