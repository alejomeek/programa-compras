-- supabase/tests/sql/_storage_stub.sql
-- Fase 2 — data-model
--
-- SOLO PARA EL CONTENEDOR DE PRUEBA. La imagen `supabase/postgres` trae el
-- esquema `storage` VACIO: `storage.buckets` y `storage.objects` los crea el
-- servicio Storage, que no corre aqui. Sin este stub, la migracion 0011 ni
-- siquiera se puede aplicar en el contenedor.
--
-- Reproduce las columnas que usan las policies de 0011, nada mas. Por eso la
-- suite 50 valida la LOGICA de esas policies y no la integracion real con
-- Storage: eso solo se comprueba en el proyecto Supabase de verdad.
-- Este archivo NUNCA forma parte de una migracion.

-- Stub de Storage: la imagen supabase/postgres NO trae storage.buckets/objects
-- (los crea el servicio Storage). Reproducimos lo minimo para poder ejercitar
-- las policies de 0011. NUNCA forma parte de una migracion.
create table if not exists storage.buckets (
  id text primary key,
  name text not null unique,
  public boolean not null default false,
  file_size_limit bigint,
  allowed_mime_types text[],
  created_at timestamptz default now()
);
create table if not exists storage.objects (
  id uuid primary key default gen_random_uuid(),
  bucket_id text not null references storage.buckets (id),
  name text not null,
  owner uuid,
  created_at timestamptz default now(),
  metadata jsonb
);
create or replace function storage.foldername(name text)
returns text[] language sql immutable as $$
  select (string_to_array(name, '/'))[1:array_length(string_to_array(name,'/'),1)-1];
$$;
alter table storage.objects enable row level security;
grant usage on schema storage to authenticated, anon, service_role;
grant select, insert, update, delete on storage.objects to authenticated, service_role;
grant select on storage.buckets to authenticated, service_role;
