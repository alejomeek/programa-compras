-- 0014_purchase_runs.sql
-- Fase 3 — recommendation-engineer
-- `purchase_runs`, `purchase_run_target_days`, `purchase_run_lines`,
-- `purchase_line_adjustments` (contrato §6.3, §7, §9, §11).
--
-- Una corrida calcula `suggested_quantity` una sola vez (motor Python,
-- `service_role`) y esa columna queda inmutable por trigger de ahi en
-- adelante. `final_quantity` es la cantidad editable, protegida por
-- concurrencia optimista: la UNICA via de escritura es el RPC
-- `update_final_quantity`, que compara `row_version` y nunca hace
-- last-write-wins silencioso (contrato §9). Por eso `purchase_run_lines` NO
-- tiene policy de UPDATE para `authenticated` mas abajo: si la tuviera, un
-- PATCH directo por PostgREST saltaria el chequeo de version. El trigger de
-- auditoria (tambien `security definer`) es quien deja constancia en
-- `purchase_line_adjustments`, append-only, ni admin la edita ni la borra.

do $$
begin
  if not exists (select 1 from pg_type where typname = 'purchase_run_status') then
    create type public.purchase_run_status as enum ('draft', 'calculated', 'locked', 'cancelled');
  end if;
end
$$;

do $$
begin
  if not exists (select 1 from pg_type where typname = 'purchase_run_line_status') then
    -- 'ok': hubo precio vigente y se calculo con normalidad (la sugerencia
    -- puede igual ser 0 por falta de ventas). 'no_price': elegible por
    -- comodin TBC o por lista de precios, pero sin precio vigente en la
    -- lista elegida -> sugerencia forzada a 0, se guarda igual para que el
    -- comprador la agregue a mano (contrato: "agregable manualmente").
    create type public.purchase_run_line_status as enum ('ok', 'no_price');
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- purchase_runs
-- ---------------------------------------------------------------------------
create table if not exists public.purchase_runs (
  id                     uuid primary key default gen_random_uuid(),
  supplier_id            uuid not null references public.suppliers (id) on delete restrict,
  sales_import_id        uuid not null references public.sales_imports (id) on delete restrict,
  price_list_id          uuid not null references public.price_lists (id) on delete restrict,
  -- Nullable: sin inventario de referencia, la corrida igual calcula (caso
  -- "producto nuevo sin historia TBC", elegible solo por lista de precios).
  inventory_snapshot_id  uuid references public.inventory_snapshots (id) on delete restrict,
  period_start           date not null,
  period_end             date not null,
  period_days            integer generated always as (period_end - period_start + 1) stored,
  status                 public.purchase_run_status not null default 'draft',
  -- engine.__version__ en el momento del calculo (reproducibilidad).
  engine_version         text not null check (length(btrim(engine_version)) > 0),
  -- sha256 de los parametros de entrada; mismos parametros = mismo hash.
  params_hash            text not null check (params_hash ~ '^[0-9a-f]{64}$'),
  created_by             uuid references public.profiles (id) on delete set null,
  calculated_at          timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint purchase_runs_period_days_positive_check check (period_days > 0)
);

comment on table public.purchase_runs is
  'Una ejecucion reproducible del calculo de compra sugerida. Guarda las fuentes exactas y el periodo/dias objetivo usados.';
comment on column public.purchase_runs.params_hash is
  'sha256 hex de los parametros de entrada (fuentes + dias objetivo por ubicacion), para verificar reproducibilidad sin comparar todas las lineas.';

create index if not exists purchase_runs_supplier_status_idx
  on public.purchase_runs (supplier_id, status);
create index if not exists purchase_runs_created_at_idx
  on public.purchase_runs (created_at desc);

drop trigger if exists purchase_runs_set_updated_at on public.purchase_runs;
create trigger purchase_runs_set_updated_at
  before update on public.purchase_runs
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- purchase_run_target_days
-- ---------------------------------------------------------------------------
create table if not exists public.purchase_run_target_days (
  id               uuid primary key default gen_random_uuid(),
  purchase_run_id  uuid not null references public.purchase_runs (id) on delete cascade,
  location_id      uuid not null references public.locations (id) on delete restrict,
  target_days      smallint not null check (target_days > 0),
  constraint purchase_run_target_days_run_location_key unique (purchase_run_id, location_id)
);

comment on table public.purchase_run_target_days is
  'Fotografia de los dias objetivo por ubicacion realmente usados en la corrida (contrato D2: global por ubicacion, editable por corrida).';

create index if not exists purchase_run_target_days_run_idx
  on public.purchase_run_target_days (purchase_run_id);

-- ---------------------------------------------------------------------------
-- purchase_run_lines
-- ---------------------------------------------------------------------------
create table if not exists public.purchase_run_lines (
  id                  uuid primary key default gen_random_uuid(),
  purchase_run_id     uuid not null references public.purchase_runs (id) on delete cascade,
  -- Nullable: el cruce es por EAN (contrato: "ean es la llave real porque
  -- product_id puede ser nulo"), igual que sales_lines/inventory_lines.
  product_id          uuid references public.products (id) on delete set null,
  ean                 text not null check (ean ~ '^[0-9]+$'),
  location_id         uuid not null references public.locations (id) on delete restrict,
  sales_units         integer not null check (sales_units >= 0),
  period_days         integer not null check (period_days > 0),
  daily_sales         numeric(14,4) not null check (daily_sales >= 0),
  -- Inmutable por trigger mas abajo: "nunca se sobrescribe".
  suggested_quantity  integer not null check (suggested_quantity >= 0),
  -- Editable via RPC unicamente. Default = la sugerida al nacer la fila.
  final_quantity      integer not null check (final_quantity >= 0),
  -- Solo referencia visual (contrato): nunca resta, nunca es minimo.
  stock_reference     integer check (stock_reference >= 0),
  unit_cost           numeric(14,2) check (unit_cost >= 0),
  note                text,
  status              public.purchase_run_line_status not null default 'ok',
  row_version         integer not null default 1 check (row_version > 0),
  updated_at          timestamptz not null default now(),
  updated_by          uuid references public.profiles (id) on delete set null,
  constraint purchase_run_lines_run_ean_location_key unique (purchase_run_id, ean, location_id)
);

comment on table public.purchase_run_lines is
  'Resultado por EAN x ubicacion: sugerencia inmutable + cantidad final editable. row_version habilita concurrencia optimista (contrato §9).';
comment on column public.purchase_run_lines.suggested_quantity is
  'ceil((ventas_historicas / dias_del_periodo) x dias_objetivo). Inmutable: ver trigger purchase_run_lines_immutable_suggested.';
comment on column public.purchase_run_lines.final_quantity is
  'Cantidad editable. Escritura EXCLUSIVA via el RPC update_final_quantity: no hay policy de UPDATE directa para authenticated.';

create index if not exists purchase_run_lines_run_location_idx
  on public.purchase_run_lines (purchase_run_id, location_id);
create index if not exists purchase_run_lines_ean_idx on public.purchase_run_lines (ean);
create index if not exists purchase_run_lines_status_idx
  on public.purchase_run_lines (purchase_run_id, status);

-- ---------------------------------------------------------------------------
-- purchase_line_adjustments (append-only, contrato §9: "ni admin edita/borra")
-- ---------------------------------------------------------------------------
create table if not exists public.purchase_line_adjustments (
  id                    uuid primary key default gen_random_uuid(),
  purchase_run_line_id  uuid not null references public.purchase_run_lines (id) on delete cascade,
  previous_quantity     integer not null check (previous_quantity >= 0),
  new_quantity          integer not null check (new_quantity >= 0),
  reason                text,
  adjusted_by           uuid not null references public.profiles (id) on delete restrict,
  created_at            timestamptz not null default now()
);

comment on table public.purchase_line_adjustments is
  'Historial append-only de cambios a final_quantity. Lo inserta unicamente el trigger de auditoria, nunca a mano (contrato §9).';

create index if not exists purchase_line_adjustments_line_idx
  on public.purchase_line_adjustments (purchase_run_line_id, created_at desc);

-- ---------------------------------------------------------------------------
-- Inmutabilidad de suggested_quantity
-- ---------------------------------------------------------------------------
-- Trigger de tabla, no policy: aplica tambien a service_role y al owner
-- (mismo criterio que price_lists_enforce_immutability en 0008).
create or replace function public.purchase_run_lines_immutable_suggested()
returns trigger
language plpgsql
set search_path = public, pg_temp
as $$
begin
  if new.suggested_quantity is distinct from old.suggested_quantity then
    raise exception
      'suggested_quantity de purchase_run_lines % es inmutable: nunca se sobrescribe (contrato §6.3).',
      old.id
      using errcode = 'restrict_violation';
  end if;
  return new;
end;
$$;

drop trigger if exists purchase_run_lines_immutable_suggested on public.purchase_run_lines;
create trigger purchase_run_lines_immutable_suggested
  before update on public.purchase_run_lines
  for each row execute function public.purchase_run_lines_immutable_suggested();

-- ---------------------------------------------------------------------------
-- Auditoria de final_quantity (trazabilidad que no se puede saltar)
-- ---------------------------------------------------------------------------
-- SECURITY DEFINER: inserta en purchase_line_adjustments aunque el rol que
-- dispara el UPDATE no tenga insert directo ahi (no lo tiene, ver RLS abajo).
-- `reason` llega por un GUC de transaccion que el RPC fija antes del UPDATE;
-- si algo mas actualiza final_quantity sin pasar por el RPC (ej. un fix
-- manual de admin en el SQL editor), el ajuste igual queda registrado, solo
-- que sin motivo.
create or replace function public.purchase_run_lines_audit_final_quantity()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  insert into public.purchase_line_adjustments
    (purchase_run_line_id, previous_quantity, new_quantity, reason, adjusted_by)
  values
    (new.id, old.final_quantity, new.final_quantity,
     nullif(current_setting('purchase_runs.reason', true), ''),
     auth.uid());
  return new;
end;
$$;

drop trigger if exists purchase_run_lines_audit_final_quantity on public.purchase_run_lines;
create trigger purchase_run_lines_audit_final_quantity
  after update of final_quantity on public.purchase_run_lines
  for each row execute function public.purchase_run_lines_audit_final_quantity();

-- ---------------------------------------------------------------------------
-- RPC update_final_quantity: unica via de escritura de final_quantity
-- ---------------------------------------------------------------------------
-- SECURITY DEFINER para poder hacer el UPDATE sin una policy de UPDATE en
-- purchase_run_lines (a proposito, ver comentario de cabecera). Repite las
-- comprobaciones de autorizacion adentro porque bypassa RLS.
create or replace function public.update_final_quantity(
  p_line_id uuid,
  p_new_quantity integer,
  p_expected_row_version integer,
  p_reason text default null
)
returns public.purchase_run_lines
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_run_status public.purchase_run_status;
  v_row        public.purchase_run_lines;
begin
  if not (select public.can_write()) then
    raise exception 'Tu rol no tiene permiso para ajustar cantidades.'
      using errcode = 'insufficient_privilege';
  end if;

  if p_new_quantity < 0 then
    raise exception 'La cantidad final no puede ser negativa.'
      using errcode = 'check_violation';
  end if;

  select pr.status into v_run_status
    from public.purchase_run_lines prl
    join public.purchase_runs pr on pr.id = prl.purchase_run_id
   where prl.id = p_line_id;

  if v_run_status is null then
    raise exception 'LINE_NOT_FOUND: la linea % no existe.', p_line_id
      using errcode = 'no_data_found';
  end if;

  if v_run_status in ('locked', 'cancelled') then
    raise exception 'La corrida esta % y no admite ajustes.', v_run_status
      using errcode = 'object_not_in_prerequisite_state';
  end if;

  perform set_config('purchase_runs.reason', coalesce(p_reason, ''), true);

  update public.purchase_run_lines
     set final_quantity = p_new_quantity,
         row_version = row_version + 1,
         updated_at = now(),
         updated_by = auth.uid()
   where id = p_line_id
     and row_version = p_expected_row_version
   returning * into v_row;

  if v_row.id is null then
    raise exception
      'ROW_VERSION_CONFLICT: la linea % cambio desde que se cargo (version esperada %).',
      p_line_id, p_expected_row_version
      using errcode = 'serialization_failure';
  end if;

  return v_row;
end;
$$;

comment on function public.update_final_quantity(uuid, integer, integer, text) is
  'Unica via de escritura de purchase_run_lines.final_quantity. Concurrencia optimista por row_version (contrato §9): 0 filas afectadas -> ROW_VERSION_CONFLICT explicito, nunca last-write-wins silencioso.';

revoke execute on function public.update_final_quantity(uuid, integer, integer, text) from public, anon;
grant execute on function public.update_final_quantity(uuid, integer, integer, text) to authenticated;

-- ---------------------------------------------------------------------------
-- RLS (contrato §7)
-- ---------------------------------------------------------------------------
alter table public.purchase_runs             enable row level security;
alter table public.purchase_run_target_days  enable row level security;
alter table public.purchase_run_lines        enable row level security;
alter table public.purchase_line_adjustments enable row level security;

revoke all on table public.purchase_runs             from anon;
revoke all on table public.purchase_run_target_days  from anon;
revoke all on table public.purchase_run_lines        from anon;
revoke all on table public.purchase_line_adjustments from anon;

-- purchase_runs: viewer select; buyer select+insert+update mientras
-- draft/calculated; admin ademas cancela/borra.
drop policy if exists purchase_runs_select_authenticated on public.purchase_runs;
create policy purchase_runs_select_authenticated on public.purchase_runs
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists purchase_runs_insert_writer on public.purchase_runs;
create policy purchase_runs_insert_writer on public.purchase_runs
  for insert to authenticated
  with check ((select public.can_write()) and created_by = (select auth.uid()));

-- `using` necesita el mismo bypass de admin que `with check`: sin el, un admin
-- no podria ni empezar a actualizar una fila ya `locked` (cancelarla), porque
-- `using` decide que filas son candidatas ANTES de evaluar el nuevo valor.
drop policy if exists purchase_runs_update_writer on public.purchase_runs;
create policy purchase_runs_update_writer on public.purchase_runs
  for update to authenticated
  using (
    (select public.is_admin())
    or ((select public.can_write()) and status in ('draft', 'calculated'))
  )
  with check (
    (select public.is_admin())
    or ((select public.can_write()) and status in ('draft', 'calculated', 'locked'))
  );

-- Sin trigger prevent_delete a proposito (a diferencia de locations): una
-- corrida completa SI se puede eliminar, solo admin. Las FK "on delete
-- cascade" de sus tablas hijas ya protegen la integridad: borrar una corrida
-- arrastra sus lineas y ajustes, aceptable porque es un resultado calculado,
-- no un dato fuente.
drop policy if exists purchase_runs_delete_admin on public.purchase_runs;
create policy purchase_runs_delete_admin on public.purchase_runs
  for delete to authenticated
  using ((select public.is_admin()));

-- purchase_run_target_days: solo lectura para authenticated. Se escribe una
-- sola vez junto con la corrida, por service_role.
drop policy if exists purchase_run_target_days_select_authenticated on public.purchase_run_target_days;
create policy purchase_run_target_days_select_authenticated on public.purchase_run_target_days
  for select to authenticated
  using ((select public.current_user_role()) is not null);

-- purchase_run_lines: solo lectura para authenticated. La unica escritura de
-- final_quantity es el RPC (arriba); el INSERT inicial lo hace service_role.
drop policy if exists purchase_run_lines_select_authenticated on public.purchase_run_lines;
create policy purchase_run_lines_select_authenticated on public.purchase_run_lines
  for select to authenticated
  using ((select public.current_user_role()) is not null);

-- purchase_line_adjustments: solo lectura para authenticated. Lo inserta
-- unicamente el trigger de auditoria (security definer); nadie mas escribe.
drop policy if exists purchase_line_adjustments_select_authenticated on public.purchase_line_adjustments;
create policy purchase_line_adjustments_select_authenticated on public.purchase_line_adjustments
  for select to authenticated
  using ((select public.current_user_role()) is not null);

-- ---------------------------------------------------------------------------
-- GRANT explicitos (leccion de 0006/0012)
-- ---------------------------------------------------------------------------
revoke all on table public.purchase_runs             from anon, authenticated, service_role;
revoke all on table public.purchase_run_target_days  from anon, authenticated, service_role;
revoke all on table public.purchase_run_lines        from anon, authenticated, service_role;
revoke all on table public.purchase_line_adjustments from anon, authenticated, service_role;

grant select, insert, update, delete on table public.purchase_runs             to authenticated;
grant select                         on table public.purchase_run_target_days  to authenticated;
grant select                         on table public.purchase_run_lines        to authenticated;
grant select                         on table public.purchase_line_adjustments to authenticated;

-- service_role: el motor Python calcula e inserta header+target_days+lines
-- en una sola transaccion (engine/purchase_runs.py). No necesita `delete` en
-- purchase_run_lines/purchase_line_adjustments (nunca borra lineas sueltas;
-- borrar una corrida completa es cascada desde purchase_runs, y ese delete
-- ya requiere is_admin() via RLS incluso para service_role... salvo que
-- service_role bypassa RLS por diseno de Postgres/Supabase, igual que en
-- sales_lines/inventory_lines -- documentado, no un descuido).
grant select, insert, update, delete on table public.purchase_runs             to service_role;
grant select, insert                 on table public.purchase_run_target_days  to service_role;
grant select, insert, update         on table public.purchase_run_lines        to service_role;
grant select, insert                 on table public.purchase_line_adjustments to service_role;
