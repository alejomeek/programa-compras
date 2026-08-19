-- supabase/tests/sql/70_fase1_hardening.sql
-- lead
--
-- Verifica 0012_harden_fase1_grants.sql: privilegio EFECTIVO de authenticated
-- y service_role sobre las 6 tablas de Fase 1, exactamente igual a lo que
-- permiten sus policies (misma regresion que 10_structure_and_grants.sql ya
-- hace para las tablas de Fase 2, aplicada aqui a las de Fase 1).

select test.expect_true('F01 authenticated: profiles select/insert/update, sin delete',
  $$select has_table_privilege('authenticated','public.profiles','select')
       and has_table_privilege('authenticated','public.profiles','insert')
       and has_table_privilege('authenticated','public.profiles','update')
       and not has_table_privilege('authenticated','public.profiles','delete')$$);

select test.expect_true('F02 authenticated: locations select/insert/update, sin delete',
  $$select has_table_privilege('authenticated','public.locations','select')
       and has_table_privilege('authenticated','public.locations','insert')
       and has_table_privilege('authenticated','public.locations','update')
       and not has_table_privilege('authenticated','public.locations','delete')$$);

select test.expect_true('F03 authenticated: suppliers select/insert/update, sin delete',
  $$select has_table_privilege('authenticated','public.suppliers','select')
       and has_table_privilege('authenticated','public.suppliers','insert')
       and has_table_privilege('authenticated','public.suppliers','update')
       and not has_table_privilege('authenticated','public.suppliers','delete')$$);

select test.expect_true('F04 authenticated: products select/insert/update, sin delete',
  $$select has_table_privilege('authenticated','public.products','select')
       and has_table_privilege('authenticated','public.products','insert')
       and has_table_privilege('authenticated','public.products','update')
       and not has_table_privilege('authenticated','public.products','delete')$$);

select test.expect_true('F05 authenticated: supplier_products select/insert/update, sin delete',
  $$select has_table_privilege('authenticated','public.supplier_products','select')
       and has_table_privilege('authenticated','public.supplier_products','insert')
       and has_table_privilege('authenticated','public.supplier_products','update')
       and not has_table_privilege('authenticated','public.supplier_products','delete')$$);

select test.expect_true('F06 authenticated: files select/insert, sin update ni delete',
  $$select has_table_privilege('authenticated','public.files','select')
       and has_table_privilege('authenticated','public.files','insert')
       and not has_table_privilege('authenticated','public.files','update')
       and not has_table_privilege('authenticated','public.files','delete')$$);

select test.expect_true('F07 service_role: select en las 5 tablas de catalogo',
  $$select has_table_privilege('service_role','public.profiles','select')
       and has_table_privilege('service_role','public.locations','select')
       and has_table_privilege('service_role','public.suppliers','select')
       and has_table_privilege('service_role','public.products','select')
       and has_table_privilege('service_role','public.supplier_products','select')$$);

select test.expect_true('F08 service_role: sin insert/update en el catalogo (solo lectura)',
  $$select not has_table_privilege('service_role','public.suppliers','insert')
       and not has_table_privilege('service_role','public.products','insert')
       and not has_table_privilege('service_role','public.supplier_products','insert')
       and not has_table_privilege('service_role','public.locations','insert')$$);

select test.expect_true('F09 service_role: files select/insert/update (backfill de sha256), sin delete',
  $$select has_table_privilege('service_role','public.files','select')
       and has_table_privilege('service_role','public.files','insert')
       and has_table_privilege('service_role','public.files','update')
       and not has_table_privilege('service_role','public.files','delete')$$);

select test.expect_true('F10 anon: sin ningun privilegio en las 6 tablas de Fase 1',
  $$select not has_table_privilege('anon','public.profiles','select')
       and not has_table_privilege('anon','public.locations','select')
       and not has_table_privilege('anon','public.suppliers','select')
       and not has_table_privilege('anon','public.products','select')
       and not has_table_privilege('anon','public.supplier_products','select')
       and not has_table_privilege('anon','public.files','select')$$);

-- Regresion funcional (no solo catalogo pg_): un viewer real sigue pudiendo
-- leer su propio profile y locations tras el revoke+grant de 0012.
do $do$
declare
  v_viewer uuid := '33333333-3333-3333-3333-333333333333';
begin
  insert into auth.users (id, email, raw_user_meta_data, aud, role)
  values (v_viewer, 'hardening-viewer@example.invalid', '{"full_name":"Hardening Viewer"}'::jsonb, 'authenticated', 'authenticated')
  on conflict (id) do nothing;
end $do$;

begin;
set local role authenticated;
set local request.jwt.claim.sub = '33333333-3333-3333-3333-333333333333';
select test.expect_true('F11 viewer real: sigue leyendo su propio profile tras 0012',
  $$select count(*) = 1 from public.profiles where id = '33333333-3333-3333-3333-333333333333'$$);
select test.expect_true('F12 viewer real: sigue leyendo locations tras 0012',
  $$select count(*) = 9 from public.locations$$);
select test.expect_fail('F13 viewer real: sigue sin poder insertar suppliers tras 0012',
  $$insert into public.suppliers (name, tbc_code) values ('Hardening Test', '777')$$);
rollback;
