-- 0002_profiles.sql
-- Fase 1 — db-auth
-- Tabla `profiles`, alta automatica desde auth.users y helpers de autorizacion.
--
-- Contrato §6.3 (columnas), §7 (RLS por rol), plan §10.
-- Desviacion aprobada por el lead: el helper del contrato llamado
-- `current_role()` se implementa como `public.current_user_role()`, porque
-- CURRENT_ROLE es palabra reservada en Postgres y una llamada sin calificar se
-- resolveria al keyword nativo (devolveria el rol de Postgres, no el de negocio).

-- ---------------------------------------------------------------------------
-- Tabla
-- ---------------------------------------------------------------------------
create table if not exists public.profiles (
  id          uuid primary key references auth.users (id) on delete cascade,
  full_name   text not null check (length(btrim(full_name)) > 0),
  role        public.user_role not null default 'viewer',
  active      boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

comment on table public.profiles is
  'Identidad de negocio. `id` es siempre auth.users.id; el rol de aqui, no el rol de Postgres, decide permisos.';

create index if not exists profiles_role_idx on public.profiles (role) where active;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
  before update on public.profiles
  for each row execute function public.set_updated_at();

-- ---------------------------------------------------------------------------
-- Alta automatica al registrarse un usuario
-- ---------------------------------------------------------------------------
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
begin
  insert into public.profiles (id, full_name)
  values (
    new.id,
    coalesce(
      nullif(btrim(new.raw_user_meta_data ->> 'full_name'), ''),
      nullif(btrim(new.raw_user_meta_data ->> 'name'), ''),
      new.email,
      'Usuario sin nombre'
    )
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

comment on function public.handle_new_user() is
  'Crea el profile (rol viewer) cuando Supabase Auth registra un usuario. El primer admin se promueve a mano.';

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();

-- ---------------------------------------------------------------------------
-- Helpers de autorizacion
-- ---------------------------------------------------------------------------
-- SECURITY DEFINER a proposito: al ejecutarse como el owner de `profiles`
-- (postgres), leen la tabla sin disparar RLS y evitan la recursion infinita que
-- se produciria si una policy de `profiles` consultara `profiles` con RLS activo.
-- Por eso mismo NUNCA se debe ejecutar `alter table public.profiles force row
-- level security`: forzaria RLS tambien para el owner y romperia estos helpers.

create or replace function public.current_user_role()
returns public.user_role
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select p.role
  from public.profiles p
  where p.id = auth.uid()
    and p.active;
$$;

comment on function public.current_user_role() is
  'Rol de negocio del usuario autenticado, o NULL si no tiene profile o esta inactivo.';

create or replace function public.is_admin()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select coalesce(public.current_user_role() = 'admin', false);
$$;

create or replace function public.can_write()
returns boolean
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select coalesce(public.current_user_role() in ('admin', 'buyer'), false);
$$;

revoke execute on function public.current_user_role() from public, anon;
revoke execute on function public.is_admin() from public, anon;
revoke execute on function public.can_write() from public, anon;
grant execute on function public.current_user_role() to authenticated;
grant execute on function public.is_admin() to authenticated;
grant execute on function public.can_write() to authenticated;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table public.profiles enable row level security;

revoke all on table public.profiles from anon;

-- viewer/buyer: solo su propia fila. admin: todas.
drop policy if exists profiles_select_own on public.profiles;
create policy profiles_select_own on public.profiles
  for select to authenticated
  using (id = (select auth.uid()));

drop policy if exists profiles_select_admin on public.profiles;
create policy profiles_select_admin on public.profiles
  for select to authenticated
  using ((select public.is_admin()));

drop policy if exists profiles_insert_admin on public.profiles;
create policy profiles_insert_admin on public.profiles
  for insert to authenticated
  with check ((select public.is_admin()));

drop policy if exists profiles_update_admin on public.profiles;
create policy profiles_update_admin on public.profiles
  for update to authenticated
  using ((select public.is_admin()))
  with check ((select public.is_admin()));

-- Sin policy de DELETE para ningun rol: una persona se desactiva
-- (`active = false`), no se borra. El borrado real solo ocurre en cascada
-- cuando se elimina el usuario de auth.users.
