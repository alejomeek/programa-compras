-- 0015_purchase_orders.sql
-- Fase 4 — órdenes de compra por ubicación destino.
--
-- Las órdenes nacen como borradores desde líneas de una corrida y conservan
-- una fotografía de producto, costo y cantidad. El consecutivo se asigna al
-- emitir (no al crear el borrador): OC-YYYY-UBICACION-NNNN.

do $$
begin
  if not exists (select 1 from pg_type where typname = 'purchase_order_status') then
    create type public.purchase_order_status as enum ('draft', 'issued', 'cancelled');
  end if;
end
$$;

-- Contador privado y atómico por año. No es parte de la API de lectura.
create table if not exists public.purchase_order_counters (
  order_year  smallint primary key check (order_year between 2000 and 9999),
  last_value  integer not null check (last_value > 0)
);

create table if not exists public.purchase_orders (
  id                    uuid primary key default gen_random_uuid(),
  supplier_id           uuid not null references public.suppliers (id) on delete restrict,
  location_id           uuid not null references public.locations (id) on delete restrict,
  purchase_run_id       uuid references public.purchase_runs (id) on delete set null,
  order_number          text unique check (order_number is null or order_number ~ '^OC-[0-9]{4}-[A-Z0-9]+-[0-9]+$'),
  status                public.purchase_order_status not null default 'draft',
  notes                 text not null default '',
  total_units           integer not null default 0 check (total_units >= 0),
  subtotal              numeric(14,2) not null default 0 check (subtotal >= 0),
  pdf_file_id           uuid references public.files (id) on delete restrict,
  created_by            uuid not null references public.profiles (id) on delete restrict,
  created_at            timestamptz not null default now(),
  updated_at            timestamptz not null default now(),
  issued_at             timestamptz,
  issued_by             uuid references public.profiles (id) on delete restrict,
  cancelled_at          timestamptz,
  cancelled_by          uuid references public.profiles (id) on delete restrict,
  cancel_reason         text,
  constraint purchase_orders_state_check check (
    (status = 'draft'
      and order_number is null and issued_at is null and issued_by is null
      and pdf_file_id is null and cancelled_at is null and cancelled_by is null
      and cancel_reason is null)
    or (status = 'issued'
      and order_number is not null and issued_at is not null and issued_by is not null
      and pdf_file_id is not null and cancelled_at is null and cancelled_by is null
      and cancel_reason is null)
    or (status = 'cancelled'
      and order_number is not null and issued_at is not null and issued_by is not null
      and pdf_file_id is not null and cancelled_at is not null and cancelled_by is not null
      and length(btrim(cancel_reason)) > 0)
  )
);

comment on table public.purchase_orders is
  'Órdenes de compra por proveedor y ubicación. Un borrador no tiene consecutivo; al emitir recibe OC-YYYY-UBICACION-NNNN y queda fotografiado.';
comment on column public.purchase_orders.order_number is
  'Consecutivo único asignado al emitir: OC-YYYY-UBICACION-NNNN. NNNN es global por año y no se reutiliza.';

create index if not exists purchase_orders_supplier_created_idx
  on public.purchase_orders (supplier_id, created_at desc);
create index if not exists purchase_orders_location_created_idx
  on public.purchase_orders (location_id, created_at desc);
create index if not exists purchase_orders_status_created_idx
  on public.purchase_orders (status, created_at desc);

drop trigger if exists purchase_orders_set_updated_at on public.purchase_orders;
create trigger purchase_orders_set_updated_at
  before update on public.purchase_orders
  for each row execute function public.set_updated_at();

create table if not exists public.purchase_order_items (
  id                    uuid primary key default gen_random_uuid(),
  purchase_order_id     uuid not null references public.purchase_orders (id) on delete cascade,
  purchase_run_line_id  uuid references public.purchase_run_lines (id) on delete set null,
  tbc_sku               text,
  ean                   text not null check (ean ~ '^[0-9]+$'),
  product_name          text not null check (length(btrim(product_name)) > 0),
  unit_cost             numeric(14,2) not null check (unit_cost >= 0),
  quantity              integer not null check (quantity > 0),
  line_total            numeric(14,2) generated always as (unit_cost * quantity) stored,
  created_at            timestamptz not null default now(),
  constraint purchase_order_items_order_ean_key unique (purchase_order_id, ean)
);

comment on table public.purchase_order_items is
  'Fotografía inmutable al emitir: conserva EAN, nombre, SKU, costo y cantidad aunque cambien las fuentes originales.';

create index if not exists purchase_order_items_order_idx
  on public.purchase_order_items (purchase_order_id);
create index if not exists purchase_order_items_run_line_idx
  on public.purchase_order_items (purchase_run_line_id)
  where purchase_run_line_id is not null;

-- Solo los borradores admiten cambiar líneas. El trigger también protege de
-- escrituras accidentales de service_role después de emitir.
create or replace function public.purchase_order_items_require_draft()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_order_id uuid := coalesce(new.purchase_order_id, old.purchase_order_id);
begin
  if not exists (
    select 1 from public.purchase_orders where id = v_order_id and status = 'draft'
  ) then
    raise exception 'La orden % ya no es un borrador y sus líneas son inmutables.', v_order_id
      using errcode = 'check_violation';
  end if;
  if tg_op = 'DELETE' then
    return old;
  end if;
  return new;
end;
$$;

drop trigger if exists purchase_order_items_require_draft on public.purchase_order_items;
create trigger purchase_order_items_require_draft
  before insert or update or delete on public.purchase_order_items
  for each row execute function public.purchase_order_items_require_draft();

create or replace function public.purchase_order_recalculate_totals()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
declare
  v_order_id uuid := coalesce(new.purchase_order_id, old.purchase_order_id);
begin
  update public.purchase_orders
  set total_units = coalesce((
        select sum(quantity) from public.purchase_order_items where purchase_order_id = v_order_id
      ), 0),
      subtotal = coalesce((
        select sum(line_total) from public.purchase_order_items where purchase_order_id = v_order_id
      ), 0)
  where id = v_order_id;
  return null;
end;
$$;

drop trigger if exists purchase_order_items_recalculate_totals on public.purchase_order_items;
create trigger purchase_order_items_recalculate_totals
  after insert or update or delete on public.purchase_order_items
  for each row execute function public.purchase_order_recalculate_totals();

-- Crea un borrador por cada ubicación contenida en la selección. Solo buyer
-- y admin pueden crear; viewer participa después únicamente en cancelación.
create or replace function public.create_purchase_order_drafts(p_line_ids uuid[])
returns table (purchase_order_id uuid)
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_count integer;
  v_distinct_count integer;
  v_run_count integer;
  v_order_id uuid;
  v_group record;
begin
  if not public.can_write() then
    raise exception 'No tienes permiso para crear borradores de orden.' using errcode = 'insufficient_privilege';
  end if;
  if coalesce(cardinality(p_line_ids), 0) = 0 then
    raise exception 'Selecciona al menos una línea de compra.' using errcode = 'check_violation';
  end if;

  select count(*), count(distinct line_id)
  into v_count, v_distinct_count
  from unnest(p_line_ids) as selected(line_id);
  if v_count <> v_distinct_count then
    raise exception 'Una línea de compra se seleccionó más de una vez.' using errcode = 'check_violation';
  end if;

  perform 1 from public.purchase_run_lines where id = any(p_line_ids) for update;
  select count(*), count(distinct purchase_run_id)
  into v_count, v_run_count
  from public.purchase_run_lines
  where id = any(p_line_ids);
  if v_count <> cardinality(p_line_ids) then
    raise exception 'Una o más líneas seleccionadas no existen.' using errcode = 'foreign_key_violation';
  end if;
  if v_run_count <> 1 then
    raise exception 'Todas las líneas deben pertenecer a la misma corrida.' using errcode = 'check_violation';
  end if;
  if exists (
    select 1
    from public.purchase_run_lines prl
    join public.purchase_runs pr on pr.id = prl.purchase_run_id
    where prl.id = any(p_line_ids) and pr.status <> 'calculated'
  ) then
    raise exception 'Solo se pueden ordenar líneas de una corrida calculada.' using errcode = 'check_violation';
  end if;
  if exists (
    select 1 from public.purchase_run_lines
    where id = any(p_line_ids) and (final_quantity <= 0 or unit_cost is null)
  ) then
    raise exception 'Cada línea seleccionada debe tener cantidad final mayor que cero y costo vigente.'
      using errcode = 'check_violation';
  end if;
  if exists (
    select 1
    from public.purchase_run_lines prl
    join public.locations l on l.id = prl.location_id
    where prl.id = any(p_line_ids) and (not l.active or not l.is_purchase_target)
  ) then
    raise exception 'Las líneas seleccionadas deben pertenecer a una ubicación operativa activa.'
      using errcode = 'check_violation';
  end if;
  if exists (
    select 1
    from public.purchase_order_items poi
    join public.purchase_orders po on po.id = poi.purchase_order_id
    where poi.purchase_run_line_id = any(p_line_ids)
      and po.status in ('draft', 'issued')
  ) then
    raise exception 'Una línea seleccionada ya pertenece a un borrador u orden emitida.'
      using errcode = 'unique_violation';
  end if;

  for v_group in
    select prl.purchase_run_id, pr.supplier_id, prl.location_id
    from public.purchase_run_lines prl
    join public.purchase_runs pr on pr.id = prl.purchase_run_id
    where prl.id = any(p_line_ids)
    group by prl.purchase_run_id, pr.supplier_id, prl.location_id
  loop
    insert into public.purchase_orders (supplier_id, location_id, purchase_run_id, created_by)
    values (v_group.supplier_id, v_group.location_id, v_group.purchase_run_id, auth.uid())
    returning id into v_order_id;

    insert into public.purchase_order_items
      (purchase_order_id, purchase_run_line_id, tbc_sku, ean, product_name, unit_cost, quantity)
    select
      v_order_id,
      prl.id,
      product.tbc_sku,
      prl.ean,
      coalesce(nullif(btrim(pli.raw ->> 'Nombre'), ''), product.name, prl.ean),
      prl.unit_cost,
      prl.final_quantity
    from public.purchase_run_lines prl
    join public.purchase_runs pr on pr.id = prl.purchase_run_id
    left join public.products product on product.id = prl.product_id
    left join public.price_list_items pli
      on pli.price_list_id = pr.price_list_id and pli.ean = prl.ean
    where prl.id = any(p_line_ids) and prl.location_id = v_group.location_id;

    purchase_order_id := v_order_id;
    return next;
  end loop;

end;
$$;

comment on function public.create_purchase_order_drafts(uuid[]) is
  'Crea un borrador por ubicación desde líneas finales de una sola corrida. Copia datos de producto/costo/cantidad; no permite líneas cero, sin costo ni reutilizadas en órdenes activas.';

-- RLS: el navegador solo lee. Las mutaciones pasan por RPC para no permitir
-- que alguien cambie estado, total o consecutivo de forma directa.
alter table public.purchase_order_counters enable row level security;
alter table public.purchase_orders enable row level security;
alter table public.purchase_order_items enable row level security;

revoke all on table public.purchase_order_counters from anon, authenticated;
revoke all on table public.purchase_orders from anon, authenticated;
revoke all on table public.purchase_order_items from anon, authenticated;

drop policy if exists purchase_orders_select_authenticated on public.purchase_orders;
create policy purchase_orders_select_authenticated on public.purchase_orders
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists purchase_order_items_select_authenticated on public.purchase_order_items;
create policy purchase_order_items_select_authenticated on public.purchase_order_items
  for select to authenticated
  using ((select public.current_user_role()) is not null);

grant select on table public.purchase_orders to authenticated;
grant select on table public.purchase_order_items to authenticated;
grant select, insert, update on table public.purchase_order_counters to service_role;
grant select, insert, update, delete on table public.purchase_orders to service_role;
grant select, insert, update, delete on table public.purchase_order_items to service_role;

revoke execute on function public.create_purchase_order_drafts(uuid[]) from public, anon;
grant execute on function public.create_purchase_order_drafts(uuid[]) to authenticated;
