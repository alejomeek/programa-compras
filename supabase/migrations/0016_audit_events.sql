-- 0016_audit_events.sql
-- Fase 4 — auditoría append-only y mutaciones controladas de órdenes.

create table if not exists public.audit_events (
  id            uuid primary key default gen_random_uuid(),
  actor_id      uuid references public.profiles (id) on delete set null,
  entity_table  text not null check (entity_table ~ '^[a-z_]+$'),
  entity_id     uuid not null,
  action        text not null check (action ~ '^[a-z_]+$'),
  payload       jsonb not null default '{}'::jsonb,
  created_at    timestamptz not null default now()
);

comment on table public.audit_events is
  'Eventos append-only de acciones operativas. Las órdenes registran creación, emisión y cancelación con su actor y contexto.';

create index if not exists audit_events_entity_created_idx
  on public.audit_events (entity_table, entity_id, created_at desc);
create index if not exists audit_events_actor_created_idx
  on public.audit_events (actor_id, created_at desc);

create or replace function public.audit_purchase_order_change()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_actor uuid := coalesce(auth.uid(), new.created_by);
begin
  if tg_op = 'INSERT' then
    insert into public.audit_events (actor_id, entity_table, entity_id, action, payload)
    values (
      v_actor, 'purchase_orders', new.id, 'draft_created',
      jsonb_build_object('supplier_id', new.supplier_id, 'location_id', new.location_id,
                         'purchase_run_id', new.purchase_run_id)
    );
  elsif new.status is distinct from old.status then
    insert into public.audit_events (actor_id, entity_table, entity_id, action, payload)
    values (
      v_actor,
      'purchase_orders',
      new.id,
      case new.status when 'issued' then 'issued' when 'cancelled' then 'cancelled' end,
      case new.status
        when 'issued' then jsonb_build_object('order_number', new.order_number, 'pdf_file_id', new.pdf_file_id)
        when 'cancelled' then jsonb_build_object('order_number', new.order_number, 'reason', new.cancel_reason)
      end
    );
  end if;
  return new;
end;
$$;

drop trigger if exists purchase_orders_audit_change on public.purchase_orders;
create trigger purchase_orders_audit_change
  after insert or update on public.purchase_orders
  for each row execute function public.audit_purchase_order_change();

create or replace function public.update_purchase_order_draft(p_order_id uuid, p_notes text)
returns public.purchase_orders
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_order public.purchase_orders;
begin
  if not public.can_write() then
    raise exception 'No tienes permiso para editar borradores de orden.' using errcode = 'insufficient_privilege';
  end if;
  update public.purchase_orders
  set notes = coalesce(p_notes, '')
  where id = p_order_id and status = 'draft'
  returning * into v_order;
  if v_order.id is null then
    raise exception 'La orden no existe o ya no es un borrador.' using errcode = 'check_violation';
  end if;
  return v_order;
end;
$$;

create or replace function public.add_manual_purchase_order_item(
  p_order_id uuid,
  p_ean text,
  p_product_name text,
  p_tbc_sku text,
  p_unit_cost numeric,
  p_quantity integer
)
returns public.purchase_order_items
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_item public.purchase_order_items;
begin
  if not public.can_write() then
    raise exception 'No tienes permiso para editar borradores de orden.' using errcode = 'insufficient_privilege';
  end if;
  if not exists (select 1 from public.purchase_orders where id = p_order_id and status = 'draft') then
    raise exception 'La orden no existe o ya no es un borrador.' using errcode = 'check_violation';
  end if;
  insert into public.purchase_order_items
    (purchase_order_id, ean, product_name, tbc_sku, unit_cost, quantity)
  values (p_order_id, p_ean, p_product_name, nullif(btrim(p_tbc_sku), ''), p_unit_cost, p_quantity)
  returning * into v_item;
  return v_item;
end;
$$;

create or replace function public.update_purchase_order_item(
  p_item_id uuid,
  p_ean text,
  p_product_name text,
  p_tbc_sku text,
  p_unit_cost numeric,
  p_quantity integer
)
returns public.purchase_order_items
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_item public.purchase_order_items;
begin
  if not public.can_write() then
    raise exception 'No tienes permiso para editar borradores de orden.' using errcode = 'insufficient_privilege';
  end if;
  update public.purchase_order_items poi
  set ean = p_ean,
      product_name = p_product_name,
      tbc_sku = nullif(btrim(p_tbc_sku), ''),
      unit_cost = p_unit_cost,
      quantity = p_quantity
  from public.purchase_orders po
  where poi.id = p_item_id and po.id = poi.purchase_order_id and po.status = 'draft'
  returning poi.* into v_item;
  if v_item.id is null then
    raise exception 'La línea no existe o su orden ya no es un borrador.' using errcode = 'check_violation';
  end if;
  return v_item;
end;
$$;

create or replace function public.delete_purchase_order_item(p_item_id uuid)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  if not public.can_write() then
    raise exception 'No tienes permiso para editar borradores de orden.' using errcode = 'insufficient_privilege';
  end if;
  delete from public.purchase_order_items poi
  using public.purchase_orders po
  where poi.id = p_item_id and po.id = poi.purchase_order_id and po.status = 'draft';
  if not found then
    raise exception 'La línea no existe o su orden ya no es un borrador.' using errcode = 'check_violation';
  end if;
end;
$$;

-- La ruta de servidor genera y almacena el PDF primero, y esta función emite
-- atómicamente la orden con un contador por año. Solo buyer/admin emiten.
create or replace function public.issue_purchase_order(p_order_id uuid, p_pdf_file_id uuid)
returns public.purchase_orders
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_order public.purchase_orders;
  v_location_code text;
  v_year smallint := extract(year from current_date)::smallint;
  v_sequence integer;
begin
  if not public.can_write() then
    raise exception 'No tienes permiso para emitir órdenes.' using errcode = 'insufficient_privilege';
  end if;
  select * into v_order from public.purchase_orders where id = p_order_id for update;
  if v_order.id is null or v_order.status <> 'draft' then
    raise exception 'La orden no existe o ya no es un borrador.' using errcode = 'check_violation';
  end if;
  if v_order.total_units <= 0 or v_order.subtotal < 0
     or not exists (select 1 from public.purchase_order_items where purchase_order_id = p_order_id) then
    raise exception 'La orden debe tener al menos una línea válida antes de emitirse.' using errcode = 'check_violation';
  end if;
  if not exists (
    select 1 from public.files where id = p_pdf_file_id and bucket = 'purchase-order-pdfs'
  ) then
    raise exception 'El PDF de la orden no existe en el bucket permitido.' using errcode = 'foreign_key_violation';
  end if;

  select code into v_location_code from public.locations where id = v_order.location_id;
  insert into public.purchase_order_counters (order_year, last_value)
  values (v_year, 1)
  on conflict (order_year) do update
    set last_value = public.purchase_order_counters.last_value + 1
  returning last_value into v_sequence;

  update public.purchase_orders
  set status = 'issued',
      order_number = format('OC-%s-%s-%s', v_year, v_location_code, lpad(v_sequence::text, 4, '0')),
      issued_at = now(),
      issued_by = auth.uid(),
      pdf_file_id = p_pdf_file_id
  where id = p_order_id
  returning * into v_order;
  return v_order;
end;
$$;

-- Decisión de negocio explícita: cualquier rol autenticado y activo puede
-- cancelar una orden emitida, pero siempre deja un motivo y evento de auditoría.
create or replace function public.cancel_purchase_order(p_order_id uuid, p_reason text)
returns public.purchase_orders
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_order public.purchase_orders;
begin
  if public.current_user_role() is null then
    raise exception 'No tienes permiso para cancelar órdenes.' using errcode = 'insufficient_privilege';
  end if;
  if nullif(btrim(p_reason), '') is null then
    raise exception 'Indica el motivo de cancelación.' using errcode = 'check_violation';
  end if;
  update public.purchase_orders
  set status = 'cancelled',
      cancelled_at = now(),
      cancelled_by = auth.uid(),
      cancel_reason = btrim(p_reason)
  where id = p_order_id and status = 'issued'
  returning * into v_order;
  if v_order.id is null then
    raise exception 'La orden no existe o no está emitida.' using errcode = 'check_violation';
  end if;
  return v_order;
end;
$$;

alter table public.audit_events enable row level security;
revoke all on table public.audit_events from anon, authenticated;

drop policy if exists audit_events_select_admin on public.audit_events;
create policy audit_events_select_admin on public.audit_events
  for select to authenticated
  using ((select public.is_admin()));

grant select on table public.audit_events to authenticated;
grant select, insert on table public.audit_events to service_role;

revoke execute on function public.update_purchase_order_draft(uuid, text) from public, anon;
revoke execute on function public.add_manual_purchase_order_item(uuid, text, text, text, numeric, integer) from public, anon;
revoke execute on function public.update_purchase_order_item(uuid, text, text, text, numeric, integer) from public, anon;
revoke execute on function public.delete_purchase_order_item(uuid) from public, anon;
revoke execute on function public.issue_purchase_order(uuid, uuid) from public, anon;
revoke execute on function public.cancel_purchase_order(uuid, text) from public, anon;

grant execute on function public.update_purchase_order_draft(uuid, text) to authenticated;
grant execute on function public.add_manual_purchase_order_item(uuid, text, text, text, numeric, integer) to authenticated;
grant execute on function public.update_purchase_order_item(uuid, text, text, text, numeric, integer) to authenticated;
grant execute on function public.delete_purchase_order_item(uuid) to authenticated;
grant execute on function public.issue_purchase_order(uuid, uuid) to authenticated;
grant execute on function public.cancel_purchase_order(uuid, text) to authenticated;
