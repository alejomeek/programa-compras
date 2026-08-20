-- 0013_retire_feria_bodega.sql
-- lead (cierre de Fase 2, hotfix de produccion — ver docs/IMPLEMENTATION_CONTRACT.md §15)
--
-- Decision de negocio (contrato §2, hallazgo de domain-auditor en Fase 0):
-- sin redistribucion (fuera de alcance de este proyecto, contrato §1), ni
-- Modo Feria ni Bodega Bqlla tienen ya ningun efecto operativo — Bodega
-- Bqlla no reabastece nada y Modo Feria no cambia ningun calculo porque el
-- inventario nunca entra a la formula. Confirmado con el usuario: se
-- retiran del modelo.
--
-- No se edita 0003/0010 (ya aplicadas, inmutables): esta migracion desactiva
-- y altera, no reescribe el pasado.

-- ---------------------------------------------------------------------------
-- locations: nunca se borran filas (0003_locations.sql), se desactivan.
-- ---------------------------------------------------------------------------
-- El indice parcial `locations_active_order_idx` ya filtra por `active`, asi
-- que esto las saca de cualquier listado/selector que respete ese indice sin
-- tocar ninguna fila de `sales_lines`/`inventory_lines` que ya las referencie
-- (esas quedan intactas: son historia, no catalogo).
update public.locations
   set active = false
 where code in ('FERIA', 'BODBQLLA');

-- ---------------------------------------------------------------------------
-- inventory_snapshots.fair_mode: deja de tener consumidor.
-- ---------------------------------------------------------------------------
-- engine/pipeline.py ya no acepta `fair_mode` como parametro (ningun caller
-- del repo lo paso nunca: la UI tampoco llego a exponer el selector). La
-- columna quedaria como metadato inerte para siempre; se elimina en vez de
-- dejarla como plomeria muerta.
alter table public.inventory_snapshots
  drop column if exists fair_mode;
