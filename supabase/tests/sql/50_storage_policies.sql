-- supabase/tests/sql/50_storage_policies.sql
-- Fase 2 — data-model — 15 asertos
--
-- Policies de los 3 buckets privados (contrato §8). ATENCION: la imagen de
-- Postgres NO trae `storage.buckets`/`storage.objects` (los crea el servicio
-- Storage), asi que 01_fixtures.sql monta un stub con las mismas columnas.
-- Esto valida la LOGICA de las policies, no la integracion real con Storage:
-- eso solo se puede comprobar en el proyecto Supabase de verdad.

set client_min_messages = notice;
begin;
\i /tmp/supabase/tests/sql/_data.sql

-- ============================ F. STORAGE (sobre stub de storage.objects) ============================
select test.expect_true('F01 los 3 buckets existen y ninguno es publico',
  $sql$select count(*) = 3 from storage.buckets
       where id in ('source-files','purchase-order-pdfs','exports') and public = false$sql$);
select test.expect_true('F02 los buckets tienen limite de tamano',
  $sql$select bool_and(file_size_limit > 0) from storage.buckets
       where id in ('source-files','purchase-order-pdfs','exports')$sql$);

select set_config('request.jwt.claim.sub','22222222-2222-2222-2222-222222222222', true);
set local role authenticated;
select test.expect_ok('F03 buyer sube a source-files bajo su propio uuid',
  $sql$insert into storage.objects (bucket_id,name,owner)
       values ('source-files','2026/08/22222222-2222-2222-2222-222222222222/x.xlsx','22222222-2222-2222-2222-222222222222')$sql$);
select test.expect_fail('F04 buyer NO sube a la carpeta de otra persona',
  $sql$insert into storage.objects (bucket_id,name,owner)
       values ('source-files','2026/08/11111111-1111-1111-1111-111111111111/x.xlsx','22222222-2222-2222-2222-222222222222')$sql$);
select test.expect_fail('F05 buyer NO sube declarando otro owner',
  $sql$insert into storage.objects (bucket_id,name,owner)
       values ('source-files','2026/08/22222222-2222-2222-2222-222222222222/y.xlsx','11111111-1111-1111-1111-111111111111')$sql$);
select test.expect_fail('F06 nadie autenticado escribe en purchase-order-pdfs (solo service_role)',
  $sql$insert into storage.objects (bucket_id,name,owner)
       values ('purchase-order-pdfs','aaaa/bbbb/OC-1-r1.pdf','22222222-2222-2222-2222-222222222222')$sql$);
select test.expect_true('F07 buyer ve su archivo de origen pero no el ajeno',
  $sql$select (select count(*) from storage.objects
               where bucket_id='source-files' and owner='22222222-2222-2222-2222-222222222222') >= 1
         and (select count(*) from storage.objects
               where bucket_id='source-files' and owner='11111111-1111-1111-1111-111111111111') = 0$sql$);
select test.expect_true('F08 buyer no ve ningun PDF de orden por acceso directo',
  $sql$select count(*) = 0 from storage.objects where bucket_id='purchase-order-pdfs'$sql$);
select test.expect_true('F09 buyer ve su export y no el de otro usuario',
  $sql$select (select count(*) from storage.objects
               where bucket_id='exports' and name like '22222222-2222-2222-2222-222222222222/%') = 1
         and (select count(*) from storage.objects
               where bucket_id='exports' and name like '11111111-1111-1111-1111-111111111111/%') = 0$sql$);
select test.expect_fail('F10 buyer NO escribe exports (los genera el servidor)',
  $sql$insert into storage.objects (bucket_id,name,owner)
       values ('exports','22222222-2222-2222-2222-222222222222/20260818/z.xlsx','22222222-2222-2222-2222-222222222222')$sql$);
select test.expect_true('F11 buyer no puede borrar su archivo de origen (evidencia de importacion)',
  $sql$with d as (delete from storage.objects
                  where bucket_id='source-files' and owner='22222222-2222-2222-2222-222222222222' returning 1)
       select count(*) = 0 from d$sql$);
reset role;

select set_config('request.jwt.claim.sub','33333333-3333-3333-3333-333333333333', true);
set local role authenticated;
select test.expect_fail('F12 viewer NO sube archivos de origen',
  $sql$insert into storage.objects (bucket_id,name,owner)
       values ('source-files','2026/08/33333333-3333-3333-3333-333333333333/v.xlsx','33333333-3333-3333-3333-333333333333')$sql$);
select test.expect_true('F13 viewer no ve archivos de origen ajenos',
  $sql$select count(*) = 0 from storage.objects where bucket_id='source-files'$sql$);
reset role;

select set_config('request.jwt.claim.sub','11111111-1111-1111-1111-111111111111', true);
set local role authenticated;
select test.expect_true('F14 admin ve todos los archivos de origen y todos los exports',
  $sql$select (select count(*) from storage.objects where bucket_id='source-files') >= 1
         and (select count(*) from storage.objects where bucket_id='exports') = 2$sql$);
reset role;

set local role anon;
select test.expect_true('F15 anon no ve ningun objeto de Storage',
  $sql$select count(*) = 0 from storage.objects$sql$);
reset role;
rollback;
