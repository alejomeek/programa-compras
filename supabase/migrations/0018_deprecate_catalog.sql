-- 0018_deprecate_catalog.sql
-- Retira el catálogo operativo: no genera una acción adicional de compra y
-- duplica visualmente información ya disponible en Importaciones y listas.
-- Solo se eliminan vistas derivadas, nunca importaciones ni datos históricos.

drop view if exists public.catalog_items;
drop view if exists public.latest_supplier_inventory;
