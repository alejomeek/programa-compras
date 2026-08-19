-- 0003_locations.sql
-- Fase 1 — db-auth
-- Catalogo de ubicaciones (contrato §6.3, plan §5).
--
-- Los 9 registros van en la migracion, no solo en seed.sql: son catalogo
-- operativo estable (no dato comercial) y sin ellos ninguna importacion TBC
-- puede mapear TISUC#/us##. seed.sql los reafirma de forma idempotente para
-- bases locales recien creadas. Desviacion aprobada por el lead frente a §6.1.
--
-- Codigos TISUC verificados uno a uno contra TISUC_TO_LOCATION de
-- procurement_engine.py; `is_purchase_target` verificado contra
-- OPERATIVE_LOCATIONS (5 tiendas + CEDI).

-- ---------------------------------------------------------------------------
-- Guardia de borrado reutilizable
-- ---------------------------------------------------------------------------
-- Un trigger, no una policy: `service_role` y el owner omiten RLS, pero no los
-- triggers. Es la unica forma de hacer cumplir "nunca se borran filas".
create or replace function public.prevent_delete()
returns trigger
language plpgsql
set search_path = pg_temp
as $$
begin
  raise exception 'Las filas de %.% no se borran; usa una marca logica (active = false).',
    tg_table_schema, tg_table_name
    using errcode = 'restrict_violation';
end;
$$;

comment on function public.prevent_delete() is
  'Trigger BEFORE DELETE: aborta cualquier borrado fisico, incluido el de service_role.';

-- ---------------------------------------------------------------------------
-- Tabla
-- ---------------------------------------------------------------------------
create table if not exists public.locations (
  id                  uuid primary key default gen_random_uuid(),
  code                text not null unique check (code ~ '^[A-Z0-9]+$'),
  name                text not null unique check (length(btrim(name)) > 0),
  -- Nullable a proposito: una ubicacion futura fuera de TBC no deberia quedar
  -- bloqueada. Las 9 reales si traen codigo.
  tisuc_code          char(5) unique check (tisuc_code ~ '^[0-9]{5}$'),
  type                public.location_type not null,
  is_purchase_target  boolean not null default false,
  active              boolean not null default true,
  display_order       smallint not null unique check (display_order > 0),
  created_at          timestamptz not null default now(),
  updated_at          timestamptz not null default now()
);

comment on table public.locations is
  'Ubicaciones de TBC. Nunca se borran filas: se marcan active = false.';
comment on column public.locations.tisuc_code is
  'Codigo TISUC# de INVEPTOS.XLS. Un TISUC# desconocido en una importacion es incidencia, no descarte silencioso.';
comment on column public.locations.is_purchase_target is
  'true solo en las 6 ubicaciones operativas. Feria / Full MercadoLibre / Bodega Bqlla son referencia.';

create index if not exists locations_active_order_idx
  on public.locations (display_order) where active;

drop trigger if exists locations_set_updated_at on public.locations;
create trigger locations_set_updated_at
  before update on public.locations
  for each row execute function public.set_updated_at();

drop trigger if exists locations_prevent_delete on public.locations;
create trigger locations_prevent_delete
  before delete on public.locations
  for each row execute function public.prevent_delete();

-- ---------------------------------------------------------------------------
-- Catalogo
-- ---------------------------------------------------------------------------
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
-- RLS
-- ---------------------------------------------------------------------------
alter table public.locations enable row level security;

revoke all on table public.locations from anon;

drop policy if exists locations_select_authenticated on public.locations;
create policy locations_select_authenticated on public.locations
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists locations_insert_admin on public.locations;
create policy locations_insert_admin on public.locations
  for insert to authenticated
  with check ((select public.is_admin()));

drop policy if exists locations_update_admin on public.locations;
create policy locations_update_admin on public.locations
  for update to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));

-- Sin policy de DELETE (ademas del trigger locations_prevent_delete).
