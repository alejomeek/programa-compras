-- supabase/tests/sql/00_helpers.sql
-- Fase 2 — data-model
--
-- Mini arnes de pruebas de comportamiento para las migraciones. Se ejecuta
-- SIEMPRE contra un contenedor Postgres efimero y descartable (ver
-- ../run_migration_tests.sh), NUNCA contra un proyecto Supabase real.
--
-- Cada aserto reporta por RAISE NOTICE: los avisos ya viajaron al cliente
-- cuando la transaccion hace rollback, asi que las suites pueden probar
-- escrituras destructivas sin dejar rastro y aun asi reportar su resultado.

create schema if not exists test;

create or replace function test.expect_ok(p_name text, p_sql text) returns void language plpgsql as $f$
begin
  begin
    execute p_sql;
    raise notice 'PASS %', p_name;
  exception when others then
    raise notice 'FAIL % -> se esperaba exito, hubo % %', p_name, sqlstate, sqlerrm;
  end;
end $f$;

create or replace function test.expect_fail(p_name text, p_sql text) returns void language plpgsql as $f$
begin
  begin
    execute p_sql;
    raise notice 'FAIL % -> se esperaba error y la operacion paso', p_name;
  exception when others then
    raise notice 'PASS % [%]', p_name, sqlstate;
  end;
end $f$;

create or replace function test.expect_true(p_name text, p_sql text) returns void language plpgsql as $f$
declare v boolean;
begin
  begin
    execute p_sql into v;
    if coalesce(v, false) then
      raise notice 'PASS %', p_name;
    else
      raise notice 'FAIL % -> la condicion resulto falsa/nula', p_name;
    end if;
  exception when others then
    raise notice 'FAIL % -> % %', p_name, sqlstate, sqlerrm;
  end;
end $f$;

grant usage on schema test to authenticated, anon, service_role;
grant execute on all functions in schema test to authenticated, anon, service_role;
