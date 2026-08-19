-- 0001_extensions_and_enums.sql
-- Fase 1 — db-auth
-- Extensiones, enums de estado y funcion de trigger transversal.
--
-- Alcance: solo los enums que consumen las migraciones 0002-0005. Las fases 2-4
-- declaran sus propios enums en sus propias migraciones, para no fijar hoy
-- valores que dependen de decisiones abiertas (D3/D4 del contrato §2).
--
-- Regla del contrato §6.1: una migracion aplicada NUNCA se edita; se corrige
-- con una migracion nueva de numero superior.

-- ---------------------------------------------------------------------------
-- Extensiones
-- ---------------------------------------------------------------------------
-- gen_random_uuid() es nativo desde Postgres 13, pero pgcrypto se declara
-- explicitamente para no depender de la version del servidor. En Supabase la
-- extension ya existe (esquema `extensions`) y este statement es un no-op.
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------------
-- Enums de estado
-- ---------------------------------------------------------------------------

-- Rol de negocio (contrato §6.3 / plan §10). No confundir con los roles de
-- Postgres (`authenticated`, `service_role`).
do $$
begin
  if not exists (select 1 from pg_type where typname = 'user_role') then
    create type public.user_role as enum ('admin', 'buyer', 'viewer');
  end if;
end
$$;

-- Tipo de ubicacion. `fair` = Modo Feria, `marketplace` = Full MercadoLibre.
-- Ninguno de los dos es destino de compra (ver `locations.is_purchase_target`).
do $$
begin
  if not exists (select 1 from pg_type where typname = 'location_type') then
    create type public.location_type as enum ('store', 'warehouse', 'marketplace', 'fair');
  end if;
end
$$;

-- Estado del cruce proveedor-producto (contrato §6.3 `supplier_products`).
-- 'new' reemplaza al marcador literal "NUEVO" del Excel actual (contrato §6.5).
do $$
begin
  if not exists (select 1 from pg_type where typname = 'supplier_product_status') then
    create type public.supplier_product_status as enum ('matched', 'new', 'unmatched', 'discontinued');
  end if;
end
$$;

-- ---------------------------------------------------------------------------
-- Funcion de trigger transversal
-- ---------------------------------------------------------------------------
-- Mantiene `updated_at` al dia. No es security definer: solo toca la fila NEW.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = pg_temp
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

comment on function public.set_updated_at() is
  'Trigger BEFORE UPDATE: refresca updated_at con now().';
