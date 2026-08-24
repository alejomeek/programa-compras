-- 0019_purchase_order_number_without_year.sql
-- El consecutivo visible deja de llevar año. Las órdenes históricas mantienen
-- su número y PDF: el CHECK acepta ambos formatos durante la transición.
-- Las nuevas órdenes consumen una secuencia global que nunca se reinicia.

create sequence if not exists public.purchase_order_number_sequence
  as bigint
  minvalue 1
  start with 1;

do $$
declare
  v_last_value bigint;
begin
  select coalesce(max((regexp_match(order_number, '([0-9]+)$'))[1]::bigint), 0)
  into v_last_value
  from public.purchase_orders
  where order_number is not null;

  if v_last_value = 0 then
    perform setval('public.purchase_order_number_sequence', 1, false);
  else
    perform setval('public.purchase_order_number_sequence', v_last_value, true);
  end if;
end
$$;

alter table public.purchase_orders
  drop constraint if exists purchase_orders_order_number_check;

alter table public.purchase_orders
  add constraint purchase_orders_order_number_check
  check (
    order_number is null
    or order_number ~ '^OC-([0-9]{4}-)?[A-Z0-9]+-[0-9]+$'
  );

comment on column public.purchase_orders.order_number is
  'Consecutivo único asignado al emitir. Las nuevas órdenes usan OC-UBICACION-NNNN; las históricas OC-YYYY-UBICACION-NNNN se preservan intactas.';

create or replace function public.issue_purchase_order(p_order_id uuid, p_pdf_file_id uuid)
returns public.purchase_orders
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_order public.purchase_orders;
  v_location_code text;
  v_sequence bigint;
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
  v_sequence := nextval('public.purchase_order_number_sequence');

  update public.purchase_orders
  set status = 'issued',
      order_number = format('OC-%s-%s', v_location_code, lpad(v_sequence::text, 4, '0')),
      issued_at = now(),
      issued_by = auth.uid(),
      pdf_file_id = p_pdf_file_id
  where id = p_order_id
  returning * into v_order;
  return v_order;
end;
$$;
