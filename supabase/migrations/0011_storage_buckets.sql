-- 0011_storage_buckets.sql
-- Fase 2 — data-model
-- Los 3 buckets privados y sus policies sobre `storage.objects` (contrato §8).
--
-- Ubicacion en la secuencia: el contrato §6.2 los planificaba como 0015, pero
-- `import-ui` necesita `source-files` ya en la Fase 2. Se adelantan a 0011 y
-- las migraciones de Fase 3/4 corren un numero (purchase_runs -> 0012, etc.).
--
-- Ningun bucket es publico. El acceso del usuario es SIEMPRE por URL firmada de
-- vida corta generada en servidor (60-120 s para PDFs y archivos de origen,
-- 300 s para exports); la URL nunca se persiste.

-- ---------------------------------------------------------------------------
-- Buckets
-- ---------------------------------------------------------------------------
-- `allowed_mime_types` queda NULL a proposito: un .xls legado llega como
-- application/octet-stream en varios navegadores y una lista blanca aqui
-- bloquearia cargas legitimas. El tipo se valida en la ruta POST /api/imports,
-- que ya conoce el `type` de importacion. El limite de tamano si se fija.
insert into storage.buckets (id, name, public, file_size_limit)
values
  ('source-files',        'source-files',        false, 52428800),  -- 50 MB
  ('purchase-order-pdfs', 'purchase-order-pdfs', false, 20971520),  -- 20 MB
  ('exports',             'exports',             false, 52428800)   -- 50 MB
on conflict (id) do nothing;

-- ---------------------------------------------------------------------------
-- source-files  ({yyyy}/{mm}/{uploader_id}/{file_uuid}.{ext})
-- ---------------------------------------------------------------------------
-- Sube buyer/admin, siempre bajo su propio uuid: asi la ruta no puede usarse
-- para escribir en la carpeta de otra persona.
drop policy if exists source_files_insert_writer on storage.objects;
create policy source_files_insert_writer on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'source-files'
    and (select public.can_write())
    and owner = (select auth.uid())
    and (storage.foldername(name))[3] = (select auth.uid())::text
  );

-- Lectura directa solo del propio archivo (o admin). Para cualquier otro caso
-- el servidor firma la URL con `service_role`, que omite RLS (contrato §8).
drop policy if exists source_files_select_owner on storage.objects;
create policy source_files_select_owner on storage.objects
  for select to authenticated
  using (
    bucket_id = 'source-files'
    and (
      owner = (select auth.uid())
      or (select public.is_admin())
    )
  );

-- Sin update ni delete: un archivo de origen es evidencia de una importacion.

-- ---------------------------------------------------------------------------
-- purchase-order-pdfs  ({supplier_id}/{purchase_order_id}/{order_number}-r{n}.pdf)
-- ---------------------------------------------------------------------------
-- Sin ninguna policy para `authenticated`: lo escribe y lo lee unicamente
-- `service_role` (contrato §8), que omite RLS. El usuario llega al PDF por una
-- URL firmada emitida tras verificar en servidor su acceso a la orden. La
-- ausencia de policy NO es un olvido: con RLS activa equivale a denegar.

-- ---------------------------------------------------------------------------
-- exports  ({user_id}/{yyyymmdd}/{uuid}.xlsx)
-- ---------------------------------------------------------------------------
-- Lee el propietario de la carpeta (primer segmento de la ruta) o un admin.
drop policy if exists exports_select_owner on storage.objects;
create policy exports_select_owner on storage.objects
  for select to authenticated
  using (
    bucket_id = 'exports'
    and (
      (storage.foldername(name))[1] = (select auth.uid())::text
      or (select public.is_admin())
    )
  );

-- Sin insert para `authenticated`: el export lo genera el servidor a nombre del
-- usuario. Sin delete: la purga (propuesta de 7 dias, pendiente en §2) tambien
-- es del servidor.

-- ---------------------------------------------------------------------------
-- Nota sobre GRANT en `storage.objects`
-- ---------------------------------------------------------------------------
-- A diferencia de las tablas de `public`, aqui NO se hace `grant`: en Supabase
-- los privilegios sobre `storage.objects` los concede el propio servicio de
-- Storage al crear el esquema, y una migracion de `public` que intente
-- modificarlos puede fallar por ownership (`storage` pertenece a
-- `supabase_storage_admin`). Si al aplicar esta migracion en el proyecto real
-- apareciera "permission denied for schema storage" o "must be owner of table
-- objects", los buckets se crean desde el panel de Supabase y estas policies se
-- ejecutan desde el SQL editor, que corre con privilegios suficientes.
