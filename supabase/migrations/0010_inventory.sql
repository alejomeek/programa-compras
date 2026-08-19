-- 0010_inventory.sql
-- Fase 2 — data-model
-- `inventory_snapshots` e `inventory_lines` (contrato §6.2, §6.3, §7, §9.2).
--
-- El inventario es SOLO REFERENCIA (decision bloqueada del contrato §1): no
-- resta de la sugerencia, no es minimo y no se redistribuye. Este esquema no
-- tiene ninguna columna que permita reintroducir esas ideas (ni objetivo de
-- inventario, ni transferencias, ni excedentes).
--
-- Escritura EXCLUSIVA de `service_role`, igual que 0009.

-- ---------------------------------------------------------------------------
-- inventory_snapshots
-- ---------------------------------------------------------------------------
create table if not exists public.inventory_snapshots (
  id             uuid primary key default gen_random_uuid(),
  import_job_id  uuid not null unique references public.import_jobs (id) on delete restrict,
  snapshot_date  date not null default current_date,
  -- Metadato de la importacion, NO parametro de calculo (contrato §5.1): con
  -- redistribucion eliminada, el Modo Feria ya no cambia ningun resultado.
  fair_mode      boolean not null default false,
  status         public.dataset_status not null default 'active',
  created_by     uuid references public.profiles (id) on delete set null,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);

comment on table public.inventory_snapshots is
  'Fotografia de existencias (SDOSXSUC). Referencia visual unicamente: jamas entra en la formula de compra.';
comment on column public.inventory_snapshots.fair_mode is
  'Solo metadato del archivo importado. Pendiente confirmar con negocio si se conserva (contrato §2).';

-- Una sola fotografia vigente por fecha: cargar otra vez el archivo del mismo
-- dia deja la anterior `superseded` en vez de sobrescribirla (contrato §9.2).
-- La clave es `snapshot_date` -- y no "una sola activa en todo el sistema" --
-- para que coincida con `supersede_keys=('snapshot_date',)` del pipeline de
-- `import-backend` (engine/persistence.py).
create unique index if not exists inventory_snapshots_one_active_per_date_idx
  on public.inventory_snapshots (snapshot_date) where status = 'active';

create index if not exists inventory_snapshots_status_date_idx
  on public.inventory_snapshots (status, snapshot_date desc);

drop trigger if exists inventory_snapshots_set_updated_at on public.inventory_snapshots;
create trigger inventory_snapshots_set_updated_at
  before update on public.inventory_snapshots
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- inventory_lines
-- ---------------------------------------------------------------------------
create table if not exists public.inventory_lines (
  id                 uuid primary key default gen_random_uuid(),
  snapshot_id        uuid not null references public.inventory_snapshots (id) on delete cascade,
  ean                text not null check (ean ~ '^[0-9]+$'),
  tbc_sku            text,
  location_id        uuid not null references public.locations (id) on delete restrict,
  -- `>= 0`: una existencia negativa de TBC no se guarda ni se recorta a 0
  -- (seria inventar un dato); se registra como incidencia de importacion.
  on_hand            integer not null check (on_hand >= 0),
  pvp                numeric(14,2) check (pvp >= 0),
  supplier_tbc_code  char(3) check (supplier_tbc_code ~ '^[0-9]{3}$'),
  created_at         timestamptz not null default now(),
  constraint inventory_lines_snapshot_ean_location_key unique (snapshot_id, ean, location_id)
);

comment on table public.inventory_lines is
  'Existencias por EAN y ubicacion (us01..us09 de SDOSXSUC). Referencia visual: el motor no las usa para calcular.';
comment on column public.inventory_lines.ean is
  'not null a proposito: es parte de la clave del renglon y un EAN invalido nunca crea fila (queda como import_issue).';
comment on column public.inventory_lines.supplier_tbc_code is
  'Comodin de 3 digitos del proveedor (Codea2/COMODI), tal como lo extrae el motor.';

create index if not exists inventory_lines_snapshot_location_idx
  on public.inventory_lines (snapshot_id, location_id);
create index if not exists inventory_lines_ean_idx      on public.inventory_lines (ean);
create index if not exists inventory_lines_supplier_idx on public.inventory_lines (supplier_tbc_code);

-- ---------------------------------------------------------------------------
-- RLS (contrato §7)
-- ---------------------------------------------------------------------------
alter table public.inventory_snapshots enable row level security;
alter table public.inventory_lines     enable row level security;

revoke all on table public.inventory_snapshots from anon;
revoke all on table public.inventory_lines     from anon;

drop policy if exists inventory_snapshots_select_authenticated on public.inventory_snapshots;
create policy inventory_snapshots_select_authenticated on public.inventory_snapshots
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists inventory_lines_select_authenticated on public.inventory_lines;
create policy inventory_lines_select_authenticated on public.inventory_lines
  for select to authenticated
  using ((select public.current_user_role()) is not null);

-- Sin policies de escritura: solo `service_role`.

-- ---------------------------------------------------------------------------
-- GRANT explicitos (leccion de 0006)
-- ---------------------------------------------------------------------------
-- Mismo motivo que en 0009: sin revoke, `authenticated` heredaria escritura
-- sobre datos que el contrato §7 reserva a `service_role`.
revoke all on table public.inventory_snapshots from anon, authenticated, service_role;
revoke all on table public.inventory_lines     from anon, authenticated, service_role;

grant select on table public.inventory_snapshots to authenticated;
grant select on table public.inventory_lines     to authenticated;

grant select, insert, update, delete on table public.inventory_snapshots to service_role;
grant select, insert, update, delete on table public.inventory_lines     to service_role;
