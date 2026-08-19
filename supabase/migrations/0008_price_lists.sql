-- 0008_price_lists.sql
-- Fase 2 — data-model
-- `price_lists` y `price_list_items` con inmutabilidad por trigger
-- (contrato §6.2, §6.3, §7, §9.1).
--
-- Historia que protege este archivo: el costo de una orden emitida se lee
-- siempre del snapshot en `purchase_order_items`, nunca de aqui; y una lista
-- que ya salio de `draft` no puede cambiar de contenido para nadie -- ni para
-- `service_role`, porque el guardia es un trigger de tabla y no una policy.

do $$
begin
  if not exists (select 1 from pg_type where typname = 'price_list_status') then
    create type public.price_list_status as enum ('draft', 'active', 'superseded', 'archived');
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- price_lists
-- ---------------------------------------------------------------------------
create table if not exists public.price_lists (
  id              uuid primary key default gen_random_uuid(),
  supplier_id     uuid not null references public.suppliers (id) on delete restrict,
  -- Nullable: una lista capturada a mano no proviene de un archivo.
  source_file_id  uuid references public.files (id) on delete restrict,
  version         integer not null check (version > 0),
  effective_date  date not null default current_date,
  status          public.price_list_status not null default 'draft',
  supersedes_id   uuid references public.price_lists (id) on delete set null,
  imported_at     timestamptz not null default now(),
  import_job_id   uuid references public.import_jobs (id) on delete restrict,
  created_by      uuid references public.profiles (id) on delete set null,
  updated_by      uuid references public.profiles (id) on delete set null,
  created_at      timestamptz not null default now(),
  updated_at      timestamptz not null default now(),
  constraint price_lists_supplier_version_key unique (supplier_id, version),
  constraint price_lists_no_self_supersede_check check (supersedes_id is distinct from id)
);

comment on table public.price_lists is
  'Versiones de lista de precios por proveedor. Inmutable fuera de draft: una correccion es una version nueva con supersedes_id (contrato §9.1).';

-- Una sola lista vigente por proveedor.
create unique index if not exists price_lists_one_active_per_supplier_idx
  on public.price_lists (supplier_id) where status = 'active';

create index if not exists price_lists_supplier_status_idx
  on public.price_lists (supplier_id, status);
create index if not exists price_lists_import_job_id_idx on public.price_lists (import_job_id);
create index if not exists price_lists_supersedes_id_idx on public.price_lists (supersedes_id);

drop trigger if exists price_lists_set_updated_at on public.price_lists;
create trigger price_lists_set_updated_at
  before update on public.price_lists
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- price_list_items
-- ---------------------------------------------------------------------------
create table if not exists public.price_list_items (
  id                   uuid primary key default gen_random_uuid(),
  price_list_id        uuid not null references public.price_lists (id) on delete cascade,
  supplier_product_id  uuid references public.supplier_products (id) on delete set null,
  ean                  text not null check (ean ~ '^[0-9]+$'),
  supplier_cost        numeric(14,2) not null check (supplier_cost >= 0),
  source_row_number    integer check (source_row_number > 0),
  raw                  jsonb,
  created_at           timestamptz not null default now(),
  constraint price_list_items_list_ean_key unique (price_list_id, ean)
);

comment on table public.price_list_items is
  'Renglones de una lista de precios. `raw` conserva la fila original del archivo para auditoria.';
comment on column public.price_list_items.ean is
  'Texto exacto, solo digitos, cualquier longitud (contrato §3.4). Nunca pasa por numeric.';

create index if not exists price_list_items_ean_idx on public.price_list_items (ean);
create index if not exists price_list_items_supplier_product_id_idx
  on public.price_list_items (supplier_product_id);

-- ---------------------------------------------------------------------------
-- Inmutabilidad (contrato §9.1)
-- ---------------------------------------------------------------------------
-- Lectura literal del contrato ("abortar update/delete si status <> draft")
-- haria imposible pasar de 'active' a 'superseded', que el mismo punto exige.
-- Por eso fuera de draft se permite EXCLUSIVAMENTE la transicion de estado, y
-- solo por la lista blanca de abajo, con todas las demas columnas intactas.
-- La comparacion se hace sobre to_jsonb(...) para que una columna agregada en
-- el futuro quede protegida sin tener que acordarse de este trigger.
create or replace function public.price_lists_enforce_immutability()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
declare
  old_rest jsonb;
  new_rest jsonb;
begin
  if tg_op = 'DELETE' then
    if old.status <> 'draft' then
      raise exception
        'La lista de precios % esta en estado % y no se puede borrar: el historial de costos es inmutable.',
        old.id, old.status
        using errcode = 'restrict_violation';
    end if;
    return old;
  end if;

  -- draft: totalmente editable, incluida su publicacion (draft -> active).
  if old.status = 'draft' then
    return new;
  end if;

  old_rest := to_jsonb(old) - 'status' - 'updated_at' - 'updated_by';
  new_rest := to_jsonb(new) - 'status' - 'updated_at' - 'updated_by';

  if old_rest is distinct from new_rest then
    raise exception
      'La lista de precios % esta en estado % y es inmutable: solo se permite cambiar su estado.',
      old.id, old.status
      using errcode = 'restrict_violation';
  end if;

  if not ((old.status, new.status) in
          (('active', 'superseded'), ('active', 'archived'), ('superseded', 'archived'))) then
    raise exception
      'Transicion de estado no permitida en price_lists: % -> %.', old.status, new.status
      using errcode = 'restrict_violation';
  end if;

  return new;
end;
$$;

comment on function public.price_lists_enforce_immutability() is
  'Guardia de inmutabilidad de price_lists. Trigger de tabla y no policy: aplica tambien a service_role y al owner.';

drop trigger if exists price_lists_immutability on public.price_lists;
create trigger price_lists_immutability
  before update or delete on public.price_lists
  for each row execute function public.price_lists_enforce_immutability();

-- Un renglon solo se toca mientras su lista padre esta en draft.
-- SECURITY DEFINER para leer `price_lists` sin depender de RLS: el guardia debe
-- fallar por el estado real de la lista, nunca por visibilidad de filas.
create or replace function public.price_list_items_enforce_parent_draft()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_list_id uuid := case when tg_op = 'DELETE' then old.price_list_id else new.price_list_id end;
  v_status  public.price_list_status;
begin
  select pl.status into v_status from public.price_lists pl where pl.id = v_list_id;

  -- El padre ya no existe: es el borrado en cascada de una lista draft, que el
  -- trigger de price_lists ya autorizo.
  if v_status is null and tg_op = 'DELETE' then
    return old;
  end if;

  if v_status is distinct from 'draft' then
    raise exception
      'La lista de precios % no esta en draft (estado %): sus renglones son inmutables.',
      v_list_id, coalesce(v_status::text, 'inexistente')
      using errcode = 'restrict_violation';
  end if;

  -- Mover un renglon de lista tambien exige que la lista ORIGEN siga en draft.
  if tg_op = 'UPDATE' and new.price_list_id is distinct from old.price_list_id then
    select pl.status into v_status from public.price_lists pl where pl.id = old.price_list_id;
    if v_status is distinct from 'draft' then
      raise exception
        'La lista de precios origen % no esta en draft (estado %).',
        old.price_list_id, coalesce(v_status::text, 'inexistente')
        using errcode = 'restrict_violation';
    end if;
  end if;

  return case when tg_op = 'DELETE' then old else new end;
end;
$$;

drop trigger if exists price_list_items_parent_draft on public.price_list_items;
create trigger price_list_items_parent_draft
  before insert or update or delete on public.price_list_items
  for each row execute function public.price_list_items_enforce_parent_draft();

-- ---------------------------------------------------------------------------
-- RLS (contrato §7: todos leen; buyer/admin escriben solo mientras esta draft)
-- ---------------------------------------------------------------------------
alter table public.price_lists      enable row level security;
alter table public.price_list_items enable row level security;

revoke all on table public.price_lists      from anon;
revoke all on table public.price_list_items from anon;

drop policy if exists price_lists_select_authenticated on public.price_lists;
create policy price_lists_select_authenticated on public.price_lists
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists price_lists_insert_writer on public.price_lists;
create policy price_lists_insert_writer on public.price_lists
  for insert to authenticated
  with check (
    (select public.can_write())
    and status = 'draft'
    and created_by = (select auth.uid())
  );

drop policy if exists price_lists_update_writer_draft on public.price_lists;
create policy price_lists_update_writer_draft on public.price_lists
  for update to authenticated
  using ((select public.can_write()) and status = 'draft')
  -- Publicar (draft -> active) si se permite desde la UI; marcar 'superseded'
  -- es trabajo del servidor, que ademas encadena el supersedes_id.
  with check ((select public.can_write()) and status in ('draft', 'active', 'archived'));

-- Sin policy de DELETE: una lista no se borra desde el navegador.

drop policy if exists price_list_items_select_authenticated on public.price_list_items;
create policy price_list_items_select_authenticated on public.price_list_items
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists price_list_items_insert_writer_draft on public.price_list_items;
create policy price_list_items_insert_writer_draft on public.price_list_items
  for insert to authenticated
  with check (
    (select public.can_write())
    and exists (select 1 from public.price_lists pl
                where pl.id = price_list_id and pl.status = 'draft')
  );

drop policy if exists price_list_items_update_writer_draft on public.price_list_items;
create policy price_list_items_update_writer_draft on public.price_list_items
  for update to authenticated
  using (
    (select public.can_write())
    and exists (select 1 from public.price_lists pl
                where pl.id = price_list_id and pl.status = 'draft')
  )
  with check (
    (select public.can_write())
    and exists (select 1 from public.price_lists pl
                where pl.id = price_list_id and pl.status = 'draft')
  );

-- Corregir un draft implica poder quitar renglones. Fuera de draft, el trigger
-- lo impide para todos.
drop policy if exists price_list_items_delete_writer_draft on public.price_list_items;
create policy price_list_items_delete_writer_draft on public.price_list_items
  for delete to authenticated
  using (
    (select public.can_write())
    and exists (select 1 from public.price_lists pl
                where pl.id = price_list_id and pl.status = 'draft')
  );

-- ---------------------------------------------------------------------------
-- GRANT explicitos (leccion de 0006)
-- ---------------------------------------------------------------------------
-- Se revoca primero (ver la nota extensa en 0007): los privilegios efectivos
-- deben ser exactamente los del contrato §7, no los que herede la instalacion.
revoke all on table public.price_lists      from anon, authenticated, service_role;
revoke all on table public.price_list_items from anon, authenticated, service_role;

grant select, insert, update         on table public.price_lists      to authenticated;
grant select, insert, update, delete on table public.price_list_items to authenticated;

grant select, insert, update, delete on table public.price_lists      to service_role;
grant select, insert, update, delete on table public.price_list_items to service_role;
