-- 0005_files.sql
-- Fase 1 — db-auth
-- Metadatos de todo archivo privado en Storage (contrato §6.3 y §8).
--
-- `bucket` se valida con un CHECK y no con un enum: la migracion 0014
-- (buckets de Storage) es del lead, y un enum obligaria a coordinar dos
-- archivos de dueños distintos para agregar un bucket.

create table if not exists public.files (
  id             uuid primary key default gen_random_uuid(),
  bucket         text not null
                   check (bucket in ('source-files', 'purchase-order-pdfs', 'exports')),
  object_path    text not null check (length(btrim(object_path)) > 0),
  original_name  text not null check (length(btrim(original_name)) > 0),
  mime_type      text,
  size_bytes     bigint not null check (size_bytes > 0),
  -- Calculado SIEMPRE en servidor tras la subida (contrato §8): no se confia
  -- en el cliente.
  sha256         char(64) not null check (sha256 ~ '^[0-9a-f]{64}$'),
  uploaded_by    uuid references public.profiles (id) on delete set null,
  created_at     timestamptz not null default now(),
  constraint files_bucket_object_path_key unique (bucket, object_path)
);

comment on table public.files is
  'Metadatos de archivos en buckets privados. El contenido vive en Storage; aqui solo la referencia.';
comment on column public.files.sha256 is
  'Hash en minusculas calculado en servidor. Indice NO unico a proposito: el mismo archivo puede reprocesarse tras un fallo o servir a proveedores distintos (contrato §8).';

-- Deliberadamente NO unico (contrato §8): sirve para avisar "este archivo ya se
-- cargo", no para bloquear la carga.
create index if not exists files_sha256_idx on public.files (sha256);
create index if not exists files_uploaded_by_created_at_idx
  on public.files (uploaded_by, created_at desc);

-- ---------------------------------------------------------------------------
-- RLS (contrato §7: viewer select; buyer/admin select + insert propio)
-- ---------------------------------------------------------------------------
alter table public.files enable row level security;

revoke all on table public.files from anon;

drop policy if exists files_select_authenticated on public.files;
create policy files_select_authenticated on public.files
  for select to authenticated
  using ((select public.current_user_role()) is not null);

drop policy if exists files_insert_writer on public.files;
create policy files_insert_writer on public.files
  for insert to authenticated
  with check (
    (select public.can_write())
    and uploaded_by = (select auth.uid())
  );

-- Sin policies de UPDATE ni DELETE: una fila de `files` es un hecho registrado.
-- La limpieza (p. ej. purga de `exports`) la hace el servidor con `service_role`.
