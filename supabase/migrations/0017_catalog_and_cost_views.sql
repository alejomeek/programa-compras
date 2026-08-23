-- 0017_catalog_and_cost_views.sql
-- Catálogo y cambios de costo derivados de fuentes inmutables.
--
-- No se duplica ni se reescribe historial: `price_lists` activas y las
-- importaciones TBC ya son fotografías versionadas. Estas vistas exponen la
-- comparación vigente con el último costo TBC y el estado operativo de cada
-- EAN por proveedor.

create or replace view public.latest_tbc_costs
with (security_invoker = true)
as
select distinct on (sl.ean)
  sl.ean,
  sl.tbc_cost,
  si.id as sales_import_id,
  si.period_start,
  si.period_end,
  si.created_at as imported_at
from public.sales_lines sl
join public.sales_imports si on si.id = sl.sales_import_id
where si.status = 'active'
  and sl.tbc_cost is not null
order by sl.ean, si.period_end desc, si.created_at desc, sl.created_at desc;

comment on view public.latest_tbc_costs is
  'Último costo TBC disponible por EAN, tomado de importaciones de ventas activas. Base de comparación sin tolerancia contra la lista de proveedor.';

create or replace view public.latest_supplier_inventory
with (security_invoker = true)
as
select distinct on (il.supplier_tbc_code, il.ean)
  il.supplier_tbc_code,
  il.ean,
  il.tbc_sku,
  isnap.id as inventory_snapshot_id,
  isnap.snapshot_date,
  isnap.created_at as imported_at
from public.inventory_lines il
join public.inventory_snapshots isnap on isnap.id = il.snapshot_id
where isnap.status = 'active'
  and il.supplier_tbc_code is not null
order by il.supplier_tbc_code, il.ean, isnap.snapshot_date desc, isnap.created_at desc, il.created_at desc;

comment on view public.latest_supplier_inventory is
  'EANs TBC vigentes por comodín de proveedor. Solo clasifica disponibilidad; nunca afecta la fórmula de compra.';

create or replace view public.cost_changes
with (security_invoker = true)
as
select
  s.id as supplier_id,
  s.name as supplier_name,
  pl.id as price_list_id,
  pl.version as price_list_version,
  pl.effective_date,
  pli.ean,
  coalesce(nullif(btrim(pli.raw ->> 'Nombre'), ''), p.name, pli.ean) as product_name,
  pli.supplier_cost,
  tbc.tbc_cost,
  pli.supplier_cost - tbc.tbc_cost as difference,
  tbc.sales_import_id,
  tbc.period_end as tbc_period_end
from public.price_lists pl
join public.suppliers s on s.id = pl.supplier_id
join public.price_list_items pli on pli.price_list_id = pl.id
left join public.products p on p.ean = pli.ean
join public.latest_tbc_costs tbc on tbc.ean = pli.ean
where pl.status = 'active'
  and pli.supplier_cost <> tbc.tbc_cost;

comment on view public.cost_changes is
  'Diferencias exactas entre el costo de cada lista de proveedor vigente y el último costo TBC por EAN. No aplica tolerancia.';

create or replace view public.catalog_items
with (security_invoker = true)
as
with active_supplier_items as (
  select
    s.id as supplier_id,
    s.name as supplier_name,
    s.tbc_code,
    pl.id as price_list_id,
    pl.version as price_list_version,
    pli.ean,
    coalesce(nullif(btrim(pli.raw ->> 'Nombre'), ''), p.name, pli.ean) as product_name,
    pli.supplier_cost
  from public.price_lists pl
  join public.suppliers s on s.id = pl.supplier_id
  join public.price_list_items pli on pli.price_list_id = pl.id
  left join public.products p on p.ean = pli.ean
  where pl.status = 'active'
)
select
  active.supplier_id,
  active.supplier_name,
  active.price_list_id,
  active.price_list_version,
  active.ean,
  active.product_name,
  active.supplier_cost,
  inventory.tbc_sku,
  case when inventory.ean is null then 'new' else 'matched' end as status
from active_supplier_items active
left join public.latest_supplier_inventory inventory
  on inventory.supplier_tbc_code = active.tbc_code and inventory.ean = active.ean

union all

select
  s.id as supplier_id,
  s.name as supplier_name,
  null::uuid as price_list_id,
  null::integer as price_list_version,
  inventory.ean,
  coalesce(inventory.tbc_sku, inventory.ean) as product_name,
  null::numeric(14,2) as supplier_cost,
  inventory.tbc_sku,
  'not_available'::text as status
from public.latest_supplier_inventory inventory
join public.suppliers s on s.tbc_code = inventory.supplier_tbc_code
left join active_supplier_items active
  on active.supplier_id = s.id and active.ean = inventory.ean
where active.ean is null;

comment on view public.catalog_items is
  'Catálogo operativo por proveedor: matched si está en TBC y lista vigente, new si está solo en lista, not_available si TBC lo tiene pero no está disponible en lista vigente.';

revoke all on public.latest_tbc_costs, public.latest_supplier_inventory,
  public.cost_changes, public.catalog_items from anon;
grant select on public.latest_tbc_costs, public.latest_supplier_inventory,
  public.cost_changes, public.catalog_items to authenticated, service_role;
