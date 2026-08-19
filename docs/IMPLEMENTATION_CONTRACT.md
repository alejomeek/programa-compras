# Contrato de implementación — Programa de Compras Web

> **Estado:** Fase 0 completada (descubrimiento sin escritura). Este documento es la fuente de verdad operativa para las fases 1–5; complementa, no reemplaza, `PLAN_MIGRACION_COMPRAS_WEB.md`.
> **Generado por:** team-lead, sintetizando los informes de `domain-auditor`, `data-architect` y `ui-architect`.
> **Última actualización:** 2026-08-19.

## 0. Cómo usar este contrato

Antes de reclamar una tarea en cualquier fase, un compañero debe leer: `PLAN_MIGRACION_COMPRAS_WEB.md` completo, este contrato completo, y `GUIA_AGENT_TEAMS_CLAUDE_CODE.md`/`agent-teams.md` para las reglas de coordinación. Ningún compañero modifica archivos fuera de su propiedad declarada (sección 4). Toda tabla nueva requiere migración + RLS + política + tipos en el mismo PR (regla del plan §16.4).

---

## 1. Decisiones bloqueadas (no reabrir sin el usuario)

Estas ya están cerradas en `PLAN_MIGRACION_COMPRAS_WEB.md` §1 y no se reinterpretan:

- Next.js + TypeScript (App Router) en Vercel; Supabase (Postgres + Auth + Storage + RLS); motor Python en `engine/`.
- Excel deja de ser mecanismo de edición; inventario es solo referencia, nunca resta ni es mínimo.
- **Cero redistribución** de inventario en ninguna forma (CEDI↔tienda, tienda↔tienda, ciudad↔ciudad).
- Fórmula única: `compra_sugerida = ceil((ventas_históricas / días_del_período) × días_objetivo)`; ventas = 0 ⇒ sugerencia = 0, sin excepción por inventario.

## 2. Decisiones pendientes de confirmación humana

No inventar valores para estas. Los agentes pueden **modelar el esquema de forma que la decisión quepa** (ver columnas marcadas "pendiente" en la sección 6), pero no fijar el comportamiento final sin respuesta del usuario.

| # | Pregunta | Recomendación provisional en el plan | Bloquea |
| --- | --- | --- | --- |
| D1 | **Full Mercado Libre** (§15.1): ¿sus ventas se siguen sumando al CEDI? | Sí, provisionalmente. Guardar `sales_lines` cruda por `location = FULLML` y sumar en el motor (no reasignar al importar), para no destruir el dato de origen. | Fase 3 (motor de recomendación) |
| D2 | **Días objetivo** (§15.2): ¿globales por ubicación, por proveedor o por corrida? | Global por ubicación, editable por corrida, con fotografía guardada (`purchase_run_target_days`). Default provisional: 45 días (como `AnalysisConfig` actual). | Fase 3 |
| D3 | **Productos nuevos** (§15.3): ¿se agregan manualmente a una orden desde el lanzamiento? ¿requieren aprobación previa? | Sí, agregables manualmente; aprobación previa sin definir. | Fase 4 (afecta si `purchase_order_items` admite filas sin `purchase_run_line_id`) |
| D4 | **Numeración y PDF de OC** (§15.4): formato del consecutivo; ¿requiere IVA/flete/vencimiento/condiciones de pago (presentes en `COT-MED-0073.pdf`, ausentes en el PDF actual)?; ¿una OC por punto o consolidada por proveedor? | Sin recomendación provisional — requiere aprobación de diseño de PDF (plan approval obligatorio, runbook §4). | Fase 4 |
| D5 | **Usuarios iniciales** (§15.5): lista y roles; ¿todos los `buyer` ven todos los proveedores/órdenes o hay restricción por persona/equipo? | Sin restricción por defecto. | **Fase 1**, no Fase 3 — si hay restricción, cambia casi todas las políticas RLS de lectura (ver §7). Cerrar esto antes de escribir migraciones de RLS. |
| D6 | **Vigencia de archivos TBC** (§15.6): ¿cuántos días de antigüedad admite una importación para usarse en una corrida? ¿se puede elegir entre varias importaciones históricas? | Sin recomendación provisional. | Fase 3 |

Preguntas adicionales detectadas por `data-architect`, sin sección en el plan pero conviene cerrar antes de Fase 4: ¿quién puede cancelar una OC emitida y con qué motivo obligatorio? ¿retención de `exports` (propuesta: purga a 7 días)? ¿moneda única COP? ¿umbral de delta que obliga a `reason` en un ajuste de cantidad? ¿se migran datos históricos o se arranca con la primera carga oficial?

Pendiente adicional detectado por `domain-auditor`, fuera de §15 pero con impacto en el modelo: sin redistribución, **Bodega Bqlla** y **Modo Feria** quedan sin efecto operativo real (Bodega Bqlla ya no reabastece nada; Modo Feria ya no cambia ningún cálculo porque el inventario no entra a la fórmula). Confirmar con negocio si igual se conservan como metadato de la importación de inventario o se retiran del modelo.

---

## 3. Formatos de origen (verificados contra archivos reales, no solo el PRD)

### 3.1 `SDOSXSUC.CSV`

`pd.read_csv(sep=";", encoding="latin1", dtype=str)`. 39 columnas: `Codpro, Nompro, Valuni, Nrotab, Codean, Codea2, us01..us30, Tunida, U100xx, U105xx`. Solo `us01`–`us09` están mapeadas a ubicación; `us10`–`us30` existen en el archivo real y hoy se descartan sin aviso — **decidir si eso es intencional**. `Codean` es texto exacto (9% de la muestra real tiene ceros iniciales — leerlo como número corrompe el catálogo). `Codea2` = comodín, formato `.NNNxxxx`.

Mapeo de inventario por ubicación (`us01..us09`), depende de Modo Feria:

| Columna | Normal | Modo Feria |
| --- | --- | --- |
| us01 | Av. 19 | Av. 19 |
| us02 | Bulevar | Bulevar |
| us03 | Calle 74 | Calle 74 |
| us04 | Bvista | Bvista |
| us05 | Oviedo | Feria |
| us06 | CEDI | Oviedo |
| us07 | Sin uso | CEDI |
| us08 | Full MercadoLibre | Full MercadoLibre |
| us09 | Bodega Bqlla | Bodega Bqlla |

Columna ausente ⇒ inventario 0, no error.

### 3.2 `INVEPTOS.XLS`

`.xls` legado (BIFF) leído con `xlrd`, sin `CODEPAGE` — hoy cae a `iso-8859-1` por fallback implícito; **fijar `encoding_override` explícito** en el motor nuevo. 39 columnas: `CODPRO, COMODI, RFCLIE, DETALL, VALUNI, VALCOS, TISUC1..N, SDSUC1..N, SDSUCX, SDOFIN, UNSUC1..N, UNSUCX, UNIVTA, VTSUC1..N, VTSUCX, TOTVTA, FDESDE, FHASTA, CODEAN`. El número de pares `TISUC#/UNSUC#` **varía entre exportaciones** (la muestra real solo trae 6, sin Full ML/Bodega Bqlla/Feria) — el parser debe seguir descubriendo columnas dinámicamente vía regex, nunca asumir un conteo fijo, y **reportar como incidencia** cualquier `TISUC#` fuera del catálogo de `locations` (hoy se descarta en silencio).

`VALCOS` = costo TBC (base de comparación de costos). `UNSUC#` = unidades vendidas por ubicación, único insumo de la fórmula nueva. Validación sugerida nueva: `Σ UNSUC# == UNIVTA`, si no, incidencia (hoy `UNSUCX` se ignora sin verificar que esté en cero).

**Riesgo de corrección más grave detectado:** el motor actual toma `FDESDE`/`FHASTA` solo de la primera fila y, si son ilegibles, cae en silencio a `period_days = 1` (multiplicaría la sugerencia hasta ×174 en datos reales). El plan §6.4 exige bloquear la importación ante fecha inválida — **implementar esto antes que el resto del parser, con su prueba primero**.

### 3.3 Lista de precios de proveedor

Dos variantes a soportar:
- **Plantilla normalizada**: `.xlsx` con encabezado en fila 1, columnas exactas `EAN-13`, `Nombre`, `Costo proveedor`.
- **Lista real tipo Spektra**: encabezado desplazado (verificado en fila 8 de 1-index / índice 7), con columnas reales como `ITEM, LINEA, CODIGO, EAN-13, DESCRIPCION DEL ARTICULO, P.V.P UNITARIO SIN I.V.A 2026, PVP CON DESCUENTO JUGANDO Y EDUCANDO ANTES DE IVA, UNIDAD DE EMPAQUE, UNDS X CAJA MASTER`. Varios encabezados traen espacios finales — `.strip()` de nombres de columna es obligatorio. La detección de columna "costo"/"nombre" del motor actual está **hardcodeada al formato de un proveedor (Spektra)**; en el motor nuevo debe volverse un **mapeo de columnas configurable por proveedor**, persistido en BD, no una heurística de texto.

### 3.4 Reglas transversales exactas (a portar literalmente)

- **EAN válido:** no vacío, sin espacios al inicio/fin (no se hace `strip` — un EAN con espacio es inválido, no se limpia), solo dígitos, **cualquier longitud** (no se exige 13). Nunca convertir a número.
- **Comodín:** regex `^\.(\d{3})` sobre `Codea2`/`COMODI` — exige empezar con punto y al menos 3 dígitos (el regex no ancla el final: `.7451LAS` → `745`, documentar este comportamiento). Comodín ingresado por el usuario: `\d{3}` exacto.
- **Días de período:** `FHASTA - FDESDE + 1`, inclusivo, piso 1 — pero ahora **bloqueante** si las fechas no parsean o están invertidas (cambio deliberado vs. el motor viejo).
- **Duplicados:** unificar el criterio en las tres fuentes — un EAN duplicado excluye **todas** las copias del cruce automático (hoy SDOSXSUC solo se queda con la primera; INVEPTOS y proveedor descartan todas — adoptar este segundo comportamiento en todos lados).
- **Números es-CO:** `$`, separador de miles `.`, decimal `,`. **Corrección aplicada en `engine/validation.py` (Fase 1):** el motor viejo solo trataba el punto como separador de miles cuando el texto también traía coma; un valor como `"45.900"` (sin coma) se leía como `45.9` — mil veces menor, y así se comparaba contra el costo proveedor. La regla nueva trata el punto como miles cuando el texto calza `^\d{1,3}(\.\d{3})+$`; un decimal legítimo (`1.5`, `1234.56`) se respeta.

---

## 4. Propietarios de carpetas por fase

(Idéntico a `GUIA_AGENT_TEAMS_CLAUDE_CODE.md` §5; se repite aquí para referencia rápida durante la ejecución.)

| Fase | Agente | Propiedad |
| --- | --- | --- |
| 1 | `web-foundation` | `app/`, `components/`, UI de `lib/` |
| 1 | `db-auth` | `supabase/migrations/`, `supabase/seed.sql` |
| 1 | `engine-core` | `engine/`, `tests/python/`, fixtures sintéticos |
| 2 | `price-importer` | `engine/readers.py`, `engine/validation.py`, pruebas proveedor |
| 2 | `tbc-importer` | `engine/tbc_readers.py`, pruebas TBC |
| 2 | `imports-ui` | `app/imports/**` |
| 3 | `recommendation-engineer` | `engine/recommendation.py` y pruebas |
| 3 | `purchase-ui` | `app/purchase-runs/**` |
| 3 | `audit-reviewer` | pruebas integración/seguridad |
| 4 | `order-domain` | `engine/orders.py`, PDFs y pruebas |
| 4 | `orders-ui` | `app/orders/**` |
| 4 | `dashboard-catalog` | `app/dashboard/**`, `app/cost-changes/**`, `app/catalog/**` |

El **lead** es dueño exclusivo, en todas las fases, de: `package.json`, `package-lock.json`, `README.md`, `vercel.json`, configuración global, rutas API de integración transversal y migraciones que cruzan dominios.

---

## 5. Motor de dominio (`engine/`)

### 5.1 Eliminar (no dejar como código inactivo)

Redistribución interna completa (CEDI/Bodega Bqlla/tiendas) y su priorización de receptores/fuentes; excedentes; resta de inventario contra la sugerencia; mínimos por quiebre y el flujo de "revisión manual / posible quiebre"; la rama especial "ventas 0 + stock > 0 → necesidad 0" (se colapsa: **todo** ventas = 0 → 0); Modo Feria como interruptor de cálculo (si se conserva, es metadato de importación, no parámetro de corrida — pendiente D-adicional); transferencias; el concepto y campo "objetivo de inventario"; el Excel multihoja como mecanismo de edición (fórmulas cruzadas, hoja oculta `_Datos OC`); el marcador literal `"NUEVO"` en celdas.

### 5.2 Conservar y portar a `engine/`

Lectura CSV Latin-1 `;` con `dtype=str`; lectura `.xls` legado vía `xlrd` (fijando encoding explícito); búsqueda de encabezado desplazado (filas 0–19); detección de columnas por alias (evolucionar a mapeo configurable por proveedor); validación de columnas requeridas con error explícito; validación EAN; detección de EAN duplicado (regla unificada); extracción y validación de comodín; parseo de fecha TBC en español (`dd-Mmm-aa`, año 2 dígitos → +2000); cálculo de días de período (ahora bloqueante); mapeo dinámico `TISUC#` → ubicación; mapeo `us01..us09` → ubicación (solo inventario de referencia); parseo numérico es-CO; clasificación de productos nuevos / descontinuados / sin costo TBC; comparación de costos TBC vs. proveedor sin tolerancia; registro estructurado de incidencias (fuente/tipo/SKU/EAN/producto/detalle); bloqueo si el comodín no existe en SDOSXSUC, advertencia si no existe en INVEPTOS; suma provisional de ventas de Full ML al CEDI (sujeta a D1).

### 5.3 Casos borde obligatorios para pruebas (resumen; detalle completo en el informe de `domain-auditor`, sección C)

Ventas = 0 con y sin stock → siempre 0; el stock nunca resta de la sugerencia (prueba de no-regresión explícita, parametrizada sobre varios valores de stock); redondeo hacia arriba estricto; período de 1 día (resultado explosivo, documentar); fecha inválida o invertida → importación bloqueada, nunca `period_days = 1` silencioso; EAN con cero inicial se conserva íntegro; EAN inválido/duplicado excluido del cruce; comodín inválido/inexistente en SDOSXSUC bloquea, inexistente en INVEPTOS solo advierte; producto nuevo sin historia TBC → sugerencia 0, agregable manualmente; Full ML parametrizado por D1; Feria ignorada; Bodega Bqlla sin efecto en el cálculo; código `TISUC#` desconocido genera incidencia (no descarte silencioso); días objetivo por ubicación independientes, con fotografía guardada por corrida; reproducibilidad exacta con mismas fuentes y parámetros.

### 5.4 Pruebas unitarias mínimas a escribir antes de portar código

Las dos pruebas actuales (`test_procurement_engine.py`) dependen de archivos comerciales locales y **no se migran** (plan §16.7). Toda fixture nueva se construye en memoria (`BytesIO` + `pandas`) con EAN sintéticos, nunca con datos reales del repo.

- `tests/python/test_readers.py`: preservación de ceros iniciales en EAN, manejo de Latin-1, columnas `us`/`TISUC#` dinámicas y faltantes, detección de encabezado desplazado y alias de columna, mensajes de error con columnas faltantes completas.
- `tests/python/test_validation.py`: validez de EAN (formatos límite), duplicados, extracción/validez de comodín, parseo de fecha español y período inclusivo, bloqueo ante fecha inválida/invertida, parseo numérico es-CO.
- `tests/python/test_recommendation.py`: fórmula con ventas positivas y redondeo; ventas cero con/sin stock; **`test_stock_no_altera_la_sugerencia`** parametrizada; **`test_no_existen_campos_de_redistribucion`** (prueba estructural anti-regresión); días objetivo por ubicación; Full ML parametrizada (`@pytest.mark.pending_decision`, ligada a D1); Feria/Bodega Bqlla sin efecto; reproducibilidad; comparación de costos sin tolerancia.

Comando de referencia una vez exista `engine/`: `python -m pytest tests/python -v`.

---

## 6. Esquema de datos (`supabase/migrations/`)

### 6.1 Convención

Archivos `NNNN_nombre_snake_case.sql`, numeración estrictamente creciente, **nunca se edita una migración ya aplicada** (se corrige con una nueva). Cada migración que crea una tabla incluye en el mismo archivo: tabla + índices + constraints + `enable row level security` + sus políticas + triggers. Las 9 filas de `locations` se insertan de forma idempotente (`on conflict (code) do nothing`) dentro de `0003_locations.sql`, no solo en `seed.sql` — `seed.sql` no corre en producción y sin el catálogo de ubicaciones no hay importación posible. `supabase/seed.sql` (no es una migración) reafirma `locations` para bases locales limpias y agrega datos sintéticos de desarrollo (proveedores/productos ficticios) — nunca datos comerciales reales ni filas en `auth.users`.

Convenciones de tipo transversales: PK `uuid default gen_random_uuid()`; dinero `numeric(14,2) check (>= 0)`; cantidades `integer check (>= 0)`; timestamps de evento `timestamptz default now()`; períodos de negocio en `date` (no `timestamptz`, para que un cambio de zona horaria no mueva un período); `created_by`/`updated_by uuid references profiles(id)`; **`ean` siempre `text` con `check (ean ~ '^[0-9]+$')`, nunca numérico**.

### 6.2 Orden de migraciones propuesto

| # | Archivo | Contenido | Fase |
| --- | --- | --- | --- |
| 0001 | `0001_extensions_and_enums.sql` | `pgcrypto`; enums de estado; función `set_updated_at()` | 1 |
| 0002 | `0002_profiles.sql` | `profiles`, trigger de alta desde `auth.users`, helpers `current_user_role()`/`is_admin()`/`can_write()` | 1 |
| 0003 | `0003_locations.sql` | `locations` | 1 |
| 0004 | `0004_suppliers_products.sql` | `suppliers`, `products`, `supplier_products` | 1 |
| 0005 | `0005_files.sql` | `files` | 1 |
| 0006 | `0006_import_jobs.sql` | `import_jobs`, `import_issues` | 2 |
| 0007 | `0007_price_lists.sql` | `price_lists`, `price_list_items` + trigger de inmutabilidad | 2 |
| 0008 | `0008_sales.sql` | `sales_imports`, `sales_lines` | 2 |
| 0009 | `0009_inventory.sql` | `inventory_snapshots`, `inventory_lines` | 2 |
| 0010 | `0010_purchase_runs.sql` | `purchase_runs`, `purchase_run_target_days`, `purchase_run_lines`, `purchase_line_adjustments` + triggers de concurrencia/auditoría | 3 |
| 0011 | `0011_purchase_orders.sql` | `purchase_orders`, `purchase_order_items`, numeración | 4 |
| 0012 | `0012_audit_events.sql` | `audit_events` (append-only) | 4 |
| 0013 | `0013_views.sql` | `latest_supplier_prices`, `cost_changes`, `purchase_run_summary`, `import_issues_view` (`security_invoker = true`) | 4 |
| 0014 | `0014_storage_buckets.sql` | 3 buckets privados + políticas sobre `storage.objects` | 1 (buckets) / 4 (PDF) |

### 6.3 Tablas — columnas y constraints esenciales

- **`profiles`**: `id` = `auth.users.id`; `full_name text not null`; `role user_role default 'viewer'` (`admin`/`buyer`/`viewer`); `active boolean default true`.
- **`locations`**: `code text unique`, `name text unique` (Av. 19, Bulevar, Calle 74, Bvista, Oviedo, CEDI, Feria, Full MercadoLibre, Bodega Bqlla), `tisuc_code char(5) unique` (10000/10010/10500/10510/10600/10800/20010/20020/20030), `type location_type`, `is_purchase_target boolean` (true solo en las 6 operativas), `active`, `display_order smallint unique`. **Nunca se borran filas**, solo `active = false`.
- **`suppliers`**: `name`, `tbc_code char(3) unique check (~ '^[0-9]{3}$')`, `active`, contacto opcional, `nit`.
- **`products`**: `tbc_sku text unique` (nullable), `ean text unique` (nullable, con check de dígitos), `name`, `current_pvp numeric(14,2)`, `active`. Un EAN inválido nunca crea fila aquí.
- **`supplier_products`**: `supplier_id fk`, `product_id fk null`, `ean not null`, `supplier_name`, `status` (`matched`/`new`/`unmatched`/`discontinued`). **`unique (supplier_id, ean)`**.
- **`price_lists`**: `supplier_id`, `source_file_id fk files`, `version integer`, `effective_date date`, `status` (`draft`/`active`/`superseded`/`archived`), `supersedes_id fk price_lists`, `imported_at`, `import_job_id fk`. `unique (supplier_id, version)` + índice único parcial `(supplier_id) where status='active'`. **Inmutable una vez no-draft** (trigger).
- **`price_list_items`**: `price_list_id fk cascade`, `supplier_product_id fk null`, `ean not null`, `supplier_cost numeric(14,2) check(>=0)`, `source_row_number`, `raw jsonb`. `unique (price_list_id, ean)`.
- **`files`**: `bucket`, `object_path`, `original_name`, `mime_type`, `size_bytes bigint check(>0)`, `sha256 char(64) not null`, `uploaded_by fk`. `unique (bucket, object_path)`; índice **no único** sobre `sha256` (ver §8).
- **`import_jobs`**: `type` (`sdos_inventory`/`inveptos_sales`/`supplier_price_list`), `supplier_id` nullable, `file_id fk`, `status` (`pending`/`processing`/`completed`/`failed`), `period_start/period_end date`, `period_days integer generated always as (period_end - period_start + 1) stored check(>0)`, `rows_total/rows_valid/rows_rejected`, `error_message`, `started_at/finished_at`, `created_by`.
- **`import_issues`**: `import_job_id fk cascade`, `file_id fk`, `severity`, `code` (`ean_invalido`, `ean_duplicado`, `costo_invalido`, `comodin_invalido`, `fecha_invalida`, `tisuc_desconocido`), `source`, `row_number`, `ean`, `sku`, `product_name`, `detail`.
- **`sales_imports`**: `import_job_id fk unique`, `supplier_id` nullable, `period_start/period_end`, `period_days` generado, `status` (`active`/`superseded`), `created_by`. Índice único parcial `(supplier_id, period_start, period_end) where status='active'`.
- **`sales_lines`**: `sales_import_id fk cascade`, `ean not null`, `location_id fk`, `product_id null`, `units_sold integer check(>=0)`, `tbc_cost numeric(14,2)`, `source_row_number`. `unique (sales_import_id, ean, location_id)`.
- **`inventory_snapshots`**: `import_job_id fk unique`, `snapshot_date date`, `fair_mode boolean default false`, `status`.
- **`inventory_lines`**: `snapshot_id fk cascade`, `ean`, `tbc_sku`, `location_id fk`, `on_hand integer check(>=0)`, `pvp numeric(14,2)`, `supplier_tbc_code char(3)`. `unique (snapshot_id, ean, location_id)`.
- **`purchase_runs`**: `supplier_id fk restrict`, `sales_import_id fk restrict`, `price_list_id fk restrict`, `inventory_snapshot_id fk null restrict`, `period_start/period_end/period_days`, `status` (`draft`/`calculated`/`locked`/`cancelled`), `engine_version`, `params_hash` (reproducibilidad), `created_by`, `calculated_at`.
- **`purchase_run_target_days`**: `purchase_run_id fk cascade`, `location_id fk`, `target_days smallint check(>0)`. `unique (run_id, location_id)` — fotografía de días objetivo usados.
- **`purchase_run_lines`**: `purchase_run_id fk cascade`, `product_id null`, `ean not null`, `location_id fk`, `sales_units`, `period_days`, `daily_sales numeric(14,4)`, `suggested_quantity integer not null` (**inmutable por trigger**), `final_quantity integer not null check(>=0)` (default = sugerida), `stock_reference integer null`, `unit_cost`, `note`, `status`, `row_version integer default 1`, `updated_at`, `updated_by`. `unique (purchase_run_id, ean, location_id)` — `ean` es la llave real porque `product_id` puede ser nulo.
- **`purchase_line_adjustments`**: `purchase_run_line_id fk cascade`, `previous_quantity`, `new_quantity`, `reason`, `adjusted_by fk not null`, `created_at`. **Append-only, ni admin puede editar/borrar.**
- **`purchase_orders`**: `supplier_id fk restrict`, `location_id fk restrict`, `purchase_run_id fk null set null`, `order_number text unique`, `revision smallint default 1`, `supersedes_order_id fk`, `status` (`draft`/`issued`/`cancelled`), `issued_at/issued_by`, `cancelled_at/cancelled_by/cancel_reason`, `notes`, `pdf_file_id fk files`, `currency char(3) default 'COP'`, `total_units`, `subtotal`; columnas `tax_amount`/`freight_amount`/`total` **pendientes de D4**.
- **`purchase_order_items`**: `purchase_order_id fk cascade`, `purchase_run_line_id fk null set null`, `tbc_sku`, `ean not null`, `product_name not null`, `unit_cost numeric(14,2) check(>=0)`, `quantity integer check(>0)`, `line_total generated always as (unit_cost*quantity) stored`. `unique (purchase_order_id, ean)`. **Es snapshot**: copia textos, no resuelve por FK al mostrar.
- **`audit_events`**: `actor_id fk`, `entity_table`, `entity_id`, `action`, `payload jsonb`, `created_at`. Sin update/delete para nadie.

### 6.4 Vistas de lectura

`latest_supplier_prices`, `cost_changes`, `purchase_run_summary`, `import_issues_view` — todas con `security_invoker = true` para heredar RLS de las tablas base. Empezar como consultas de servidor; convertir a vista SQL solo cuando su forma se estabilice (plan §5).

### 6.5 Mapeo del flujo Excel/PDF actual → esquema nuevo

| Hoy | Destino |
| --- | --- |
| `SKU`/`EAN`/`Producto` de la fila de orden | `purchase_order_items.tbc_sku`/`ean`/`product_name` |
| Costo unitario (hoja oculta `_Datos OC`) | `purchase_order_items.unit_cost` (la BD es la fuente, no una hoja oculta) |
| Una columna por punto con cantidad final | Una fila de `purchase_run_lines` por `location_id` → `purchase_order_items` de la orden de ese punto |
| Marcador `"NUEVO"` | `supplier_products.status='new'` + `suggested_quantity = 0` |
| `base_number` + sufijo por punto | `purchase_orders.order_number` (formato oficial pendiente D4) |
| `AnalysisResult.inventory_objective`/`transfers`/`stockout_minimums` | **No se migran** |

---

## 7. RLS — políticas por tabla y rol

Base deny-by-default en toda tabla (`enable row level security` sin política ⇒ sin acceso); ninguna política `to public`/`to anon`, siempre `to authenticated`; helpers `current_user_role()`/`is_admin()`/`can_write()` como `security definer` para evitar recursión sobre `profiles` (nombre corregido: `current_role` es palabra reservada en Postgres — su uso sin comillas se resuelve al keyword nativo, no a una función propia). No usar `force row level security` en `profiles`: rompería el bypass de RLS del que dependen estos helpers `security definer` para no recursar.

| Tabla | viewer | buyer | admin |
| --- | --- | --- | --- |
| `profiles` | select propio | select propio | select/update/insert todos |
| `locations`, `suppliers`, `products`, `supplier_products` | select | select | select + insert/update (nunca delete físico) |
| `files` | select | select + insert (`uploaded_by = auth.uid()`) | select + insert |
| `import_jobs` / `import_issues` | select | select (+ insert en `import_jobs`) | select + insert; update solo servidor |
| `price_lists` / `price_list_items` | select | select; escritura solo si la lista padre está `draft` | ídem |
| `sales_*`, `inventory_*` | select | select | select — **escritura exclusiva de `service_role`** |
| `purchase_runs` | select | select + insert + update mientras `status in ('draft','calculated')` | ídem + cancelar/eliminar |
| `purchase_run_lines` | select | select + `update` restringido a columnas (`final_quantity`, `note`, `row_version`, `updated_at`, `updated_by`) vía `grant update (...)`, solo si la corrida no está `locked`/`cancelled` | ídem |
| `purchase_line_adjustments` | select | select + insert (`check adjusted_by = auth.uid()`), sin update/delete | ídem |
| `purchase_orders` / `purchase_order_items` | select | select + insert/update solo en `draft` | ídem + `cancelled` |
| `audit_events` | — | — | select; insert solo triggers/`service_role` |

**D5 (usuarios) es la decisión de mayor impacto sobre esta tabla:** si hay restricción por proveedor, se agrega `user_suppliers(user_id, supplier_id)` y casi todas las políticas de lectura arriba ganan `exists (select 1 from user_suppliers …) or is_admin()`. Cerrar D5 **antes de Fase 1**, no antes de Fase 3 — reescribir políticas después de implementadas es más costoso.

---

## 8. Storage

| Bucket | Contenido | Ruta | Escribe | Lee |
| --- | --- | --- | --- | --- |
| `source-files` | CSV/XLS/XLSX originales sin modificar | `{yyyy}/{mm}/{uploader_id}/{file_uuid}.{ext}` | buyer/admin | servidor; usuario solo por URL firmada |
| `purchase-order-pdfs` | PDF de OC emitidas y revisiones | `{supplier_id}/{purchase_order_id}/{order_number}-r{revision}.pdf` | **solo `service_role`** | URL firmada tras verificar acceso a la orden |
| `exports` | descargas puntuales | `{user_id}/{yyyymmdd}/{uuid}.xlsx` | servidor a nombre del usuario | propietario + admin |

URLs firmadas de vida corta (60–120 s para PDFs/`source-files`, 300 s para `exports`), generadas siempre en servidor, nunca persistidas. `sha256` se calcula **en servidor** tras la subida (no se confía en el cliente); se usa para avisar "este archivo ya se cargó" pero **no** como `unique` duro — el mismo archivo puede reprocesarse tras un `failed`, o servir a proveedores distintos.

---

## 9. Riesgos de datos e historial a respetar

1. **Inmutabilidad de `price_lists` emitidas**: trigger que aborta `update/delete` si `status <> 'draft'`; nueva versión = nueva fila con `supersedes_id`. El costo de una OC emitida se lee siempre del snapshot en `purchase_order_items`, nunca de `price_list_items`.
2. **No sobrescribir importaciones usadas**: `sales_imports`/`inventory_snapshots` nunca se actualizan in-place; archivo nuevo ⇒ cabecera nueva `active`, la anterior pasa a `superseded`. `purchase_runs` guarda los ids exactos de las fuentes + `params_hash` para reproducibilidad exacta.
3. **Fallos parciales en `import_jobs`**: inserción de líneas + paso a `completed` en una única transacción; cualquier excepción hace rollback y marca `failed` con `error_message` legible, conservando el archivo. Ningún consumidor lee cabeceras que no estén `completed`/`active`.
4. **Concurrencia en `purchase_run_lines`**: edición vía RPC `security definer` (`update_final_quantity`) que compara `row_version` — 0 filas afectadas ⇒ conflicto explícito, nunca last-write-wins silencioso. El mismo RPC inserta el `purchase_line_adjustments` e incrementa `row_version`, en la misma transacción.
5. **Trazabilidad de ajustes**: trigger `after update of final_quantity` inserta el ajuste con `auth.uid()`, imposible de saltar desde el navegador; tabla append-only.
6. **EAN como texto exacto** en todas las capas (Postgres `text`, TypeScript `string`) — nunca pasar por `numeric` en ningún punto del pipeline.

---

## 10. Referencia visual OMS y UI

### 10.1 Tokens de diseño (valores reales medidos en el OMS, con corrección de contraste)

| Rol | Hex OMS | Nota AA |
| --- | --- | --- |
| Fondo app | `#F3F4F6` | — |
| Superficie/card/sidebar | `#FFFFFF` | — |
| Texto principal | `#020618` | 18–20:1, sobrado |
| Texto atenuado | `#65738E` (OMS) → **usar `#4F5B76`** | El original da 4.34:1 sobre `#F3F4F6`, falla AA por poco |
| Azul primario (acento/foco/activo) | `#2B7FFF` | Solo como relleno decorativo — como texto/botón sólido da 3.6–3.76:1, **no cumple AA**; usar como `--ring` y fondo de estado activo, no como color de texto |
| Azul de acción/texto/botón sólido | **`#1447E6`** (o `#155DFC`) | Sustituye a `#2B7FFF` donde haya texto: 6.83:1 / 5.25:1 |
| Borde/input | `#E3E8F1` | — |
| Hover de nav | `#DBEAFE` | — |
| Destructivo | `#E7000B` (OMS) → **usar `#C10007`** sobre fondos claros | El original da 4.33:1, falla por poco |
| Radio base | `0.625rem` = 10px, escala derivada (`sm`=6px … `4xl`=16px) | — |
| Tipografía | Plus Jakarta Sans, vía `next/font/google`, pesos 400/500/600/700 | No depender de fuente instalada localmente |

Implementación propuesta: `app/globals.css` único con `@import "tailwindcss"`, bloque `@theme inline` mapeando `--color-*`/`--radius-*` a nombres semánticos estándar de shadcn (`background, foreground, card, primary, secondary, muted, accent, destructive, border, input, ring, sidebar-*`). `components.json`: style `new-york`, `rsc: true`, `cssVariables: true`, iconos `lucide`.

### 10.2 Mapa de rutas `app/`

| Ruta | Foco | Datos |
| --- | --- | --- |
| `/dashboard` | KPIs (corridas recientes, órdenes por estado, cambios de costo, importaciones con incidencia) | `purchase_run_summary`, `purchase_orders`, `cost_changes`, `import_jobs`/`import_issues` |
| `/suppliers` | CRUD proveedor + versiones de lista de precios | `suppliers`, `price_lists`, `supplier_products` |
| `/imports` | Carga a Storage, estado de `import_jobs`, período detectado, incidencias | `files`, `import_jobs`, `import_issues`, `sales_imports`, `inventory_snapshots`, `price_lists` |
| `/purchase-runs` | Crear corrida (proveedor, fuentes, días objetivo por ubicación) | `suppliers`, `sales_imports`, `price_lists`, `locations`, `purchase_runs` |
| `/purchase-runs/[id]` | **Vista central**: tabla virtualizada producto × ubicación, filtros pegajosos, cantidad final editable inline, motivo de ajuste, creación de borradores de orden | `purchase_run_lines`, `purchase_line_adjustments`, `latest_supplier_prices`, `inventory_lines` (referencia) |
| `/orders` | Borradores/emitidas/canceladas, emisión con confirmación, PDF por URL firmada | `purchase_orders`, `purchase_order_items`, `audit_events` |
| `/cost-changes` | Comparación costo proveedor vs. TBC, sin tolerancia | vista `cost_changes` |
| `/catalog` | Productos nuevos / descontinuados / problemas de EAN-archivo | `products`, `supplier_products`, `import_issues` |
| `/settings` | Solo `admin`: ubicaciones, días objetivo por defecto, usuarios/roles | `locations`, `profiles` |

Componentes transversales sugeridos en `components/`: `PageHeader`, `KpiCard`, `DataTable` (filtros pegajosos + orden + virtualización), `EditableQuantityCell`, `StatusBadge`, `FileDropzone`, `IssueList`, `EmptyState`, `ConfirmDialog`.

### 10.3 Layout / sidebar

El sidebar del OMS es **fijo, sin comportamiento móvil** (240px siempre visible) — el drawer/`Sheet` en móvil que exige el plan **se diseña nuevo**, no se deriva del OMS. Estructura propuesta: `<aside>` de 240px con superficie blanca y borde derecho — cabecera con logo (~36px, radio 8px) + nombre de la app; navegación con 9 items (icono Lucide 16px + label), estado activo con fondo `primary` + texto `primary-foreground` + `aria-current="page"` (no solo color); pie con indicador de conexión, usuario/rol y logout. Bajo `md` (768px): sidebar oculto, barra superior con botón que abre `Sheet` con el mismo árbol de navegación (componente `SidebarNav` compartido para no duplicar).

Primitives shadcn/ui sugeridas: `Button`/`Link` para nav, `Separator`, `Sheet` para el drawer móvil, `Avatar`+`DropdownMenu` para perfil, `Card`/`Skeleton` para KPIs, `Table` + TanStack Table (+ TanStack Virtual en `/purchase-runs/[id]`), `Input`/`Select`/`Popover`+`Command`/`Checkbox`/`Tabs`/`Badge` para filtros, `Form` (react-hook-form + zod) para formularios, `AlertDialog` para confirmaciones destructivas/emisión, `Sonner` para toasts, `Tooltip` (nunca como único portador de información).

### 10.4 Checklist de accesibilidad (obligatorio en cada PR de UI)

Contraste AA con la paleta corregida de §10.1; foco visible (`focus-visible` + ring, nunca `outline: none` sin reemplazo) en toda celda editable/fila seleccionable/trigger; estados (`pending/processing/completed/failed`, `draft/issued/cancelled`, cambios de costo) siempre con texto/icono además de color; tablas con `scope="col"`, `aria-sort`, edición por teclado (Enter/Escape/Tab) y cambios anunciados en región `aria-live`; checkboxes reales con etiqueta descriptiva para selección múltiple; formularios con `<label>` asociado (nunca placeholder como label), errores junto al campo con `aria-describedby`/`aria-invalid` y foco al primer inválido; errores de importación con causa y acción concreta, no códigos crudos; `AlertDialog` con consecuencias explícitas antes de emitir/cancelar una orden; zoom 200% sin scroll horizontal del body (solo contenedores de tabla desplazan); `<html lang="es">`.

---

## 11. Contratos de API (borrador para Fases 2–4)

Rutas de servidor Next.js (Route Handlers) o función Python, siempre autenticadas, nunca exponiendo `service_role` al navegador. Cuerpo/respuesta exactos se definen al implementar cada fase; este es el contrato de superficie a respetar para no romper dependencias entre compañeros.

| Método y ruta | Fase | Propósito | Notas |
| --- | --- | --- | --- |
| `POST /api/imports` | 2 | Solicitar URL firmada de subida + crear `files`/`import_jobs` en `pending` | body: `type`, `supplier_id?`, `filename`, `sha256` |
| `POST /api/imports/:id/process` | 2 | Disparar el parseo server-side (o lo dispara un trigger/queue) | Transaccional; termina en `completed` o `failed`, nunca deja datos parciales vigentes |
| `GET /api/imports/:id` | 2 | Estado, período detectado, conteos, incidencias | — |
| `POST /api/purchase-runs` | 3 | Crear corrida (proveedor, `sales_import_id`, `price_list_id`, `inventory_snapshot_id?`, días objetivo por ubicación) | Motor Python calcula `purchase_run_lines` en la misma operación o async con `status=calculated` al terminar |
| `GET /api/purchase-runs/:id/lines` | 3 | Listado filtrable/paginado de líneas | — |
| `POST /api/purchase-runs/:id/lines/:lineId/adjust` (RPC `update_final_quantity`) | 3 | Ajustar cantidad final con control de concurrencia | body: `new_quantity`, `expected_row_version`, `reason?`; 409 si la versión no coincide |
| `POST /api/purchase-orders` | 4 | Crear borrador(es) por ubicación desde líneas seleccionadas | Agrupación por defecto: proveedor + ubicación destino (sujeto a D4) |
| `PATCH /api/purchase-orders/:id` | 4 | Editar borrador (no emitido) | Solo `status='draft'` |
| `POST /api/purchase-orders/:id/issue` | 4 | Emitir: numeración, snapshot de líneas, generación de PDF, `audit_events` | Solo `service_role`; bloqueado hasta que compras valide el formato (runbook Fase 4) |
| `POST /api/purchase-orders/:id/cancel` | 4 | Cancelar orden emitida | Requiere motivo; pendiente de definir quién puede hacerlo (§2) |
| `GET /api/purchase-orders/:id/pdf` | 4 | URL firmada de corta duración al PDF | — |

---

## 12. Comandos de prueba

Estado actual del repo (antes de Fase 1): solo existe el motor Python viejo. Los comandos siguientes son el objetivo a partir de que cada pieza se inicialice; cada PR/fase debe ejecutarlos y reportar el resultado al lead (runbook §4, regla 7).

- **Python (motor):** `python -m pytest tests/python -v` (una vez exista `engine/` y `tests/python/`, sustituyendo a `python -m pytest test_procurement_engine.py`).
- **TypeScript/Next.js:** `npm run lint`, `npm run typecheck` (o `tsc --noEmit`), `npm test` — a definir por `web-foundation` en Fase 1 junto con `package.json`.
- **Migraciones:** validar contra una base efímera/de integración antes de aplicar en desarrollo; el lead controla el orden de aplicación real.
- **CI:** cada PR crea preview de Vercel; el pipeline corre lint + typecheck + pruebas Python/TypeScript + validación de migraciones (plan §13).

---

## 13. Próximo paso

Con este contrato publicado, la Fase 0 quedó cerrada. El usuario decidió abrir Fase 1 sin cerrar D5 todavía; se implementó con su default documentado (sin restricción por proveedor) y queda aislada en `src/lib/auth/roles.ts` (UI) y sin tabla `user_suppliers` (RLS) para que cerrarla más tarde sea localizado.

## 14. Estado de Fase 1 (fundación) — completada por el equipo

`web-foundation`, `db-auth` y `engine-core` entregaron y el lead verificó de forma independiente (`npm run lint`, `npm run typecheck`, `npm test`, `npm run build`, `python -m pytest tests/python`, más un smoke test con `next start` real). Resumen:

- **Next.js scaffold** (lead): inicializado, Tailwind v4 + App Router + TypeScript.
- **`web-foundation`**: shadcn/ui instalado (CLI v3 usa el paquete unificado `radix-ui` en vez de `@radix-ui/react-*` sueltos), clientes Supabase browser/server, `src/proxy.ts` (renombrado desde `middleware.ts` por deprecación en Next 16.3.1), layout `(app)`/`(auth)`, sidebar de 8 items + `Sheet` móvil, 9 rutas vacías, pantalla "app no configurada" sin env vars, pantalla `AccountInactive` para `profiles.active = false` (barrera de UI, no de datos), tema con los tokens corregidos por contraste de §10.1. 17 pruebas Vitest.
- **`db-auth`**: `supabase/migrations/0001..0005` + `supabase/seed.sql`. Corrigió dos erratas del contrato antes de escribir código: el helper se llama `current_user_role()` (no `current_role()`, que es palabra reservada en Postgres) y las 9 `locations` se insertan de forma idempotente dentro de `0003_locations.sql` (no solo en `seed.sql`, que no corre en producción). Validado con 49 pruebas de comportamiento contra un contenedor Postgres **efímero y descartado** (no el proyecto Supabase del usuario).
- **`engine-core`**: `engine/readers.py` y `engine/validation.py`, 154 pruebas pytest con fixtures 100% sintéticas. Corrigió un bug real del motor viejo en el parseo numérico es-CO (`to_number`): un precio como `"45.900"` sin coma se leía como `45.9` (mil veces menor); ahora el punto solo se trata como separador de miles cuando el texto calza el patrón de agrupación `^\d{1,3}(\.\d{3})+$`.

### Pendiente para que el criterio de salida de Fase 1 quede *empíricamente* comprobado (no solo por revisión estática)

Nadie ha iniciado sesión todavía contra un backend real — es trabajo humano, no delegable (runbook §9):

1. Crear el proyecto Supabase de desarrollo (`compras-dev`) y aplicar `supabase/migrations/0001..0005` en orden.
2. Copiar `.env.example` a `.env.local` y completar `NEXT_PUBLIC_SUPABASE_URL`/`NEXT_PUBLIC_SUPABASE_ANON_KEY` del proyecto (nunca pegar esos valores en el chat).
3. Registrar un usuario en la app y promoverlo a `admin` con el `UPDATE` documentado al final de `supabase/seed.sql`.
4. Confirmar que ese usuario ve sidebar completo (incluida Configuración) y que un usuario sin promover ve el sidebar sin Configuración — es el criterio de salida real del plan §12 Fase 0/runbook Fase 1.
5. Opcional: correr `supabase/seed.sql` para tener proveedores/productos ficticios de prueba en `/catalog` cuando exista esa UI (Fase 2).

### Riesgos abiertos que quedan para cuando exista esa instancia real

- El trigger `on_auth_user_created` sobre `auth.users` se creó y probó como superusuario en el contenedor efímero; en Supabase hosted corre como `postgres`, que debería tener permiso, pero es el punto con más probabilidad de fallar si el proyecto tiene alguna restricción particular.
- Las políticas RLS asumen que el rol `authenticated` tiene `GRANT` por defecto sobre las tablas nuevas de `public` (comportamiento estándar de Supabase, confirmado en la imagen oficial de Docker).
- `src/types/profile.ts` es un tipo TypeScript escrito a mano; reemplazar por `supabase gen types` en cuanto exista el proyecto — hoy una columna renombrada rompe en runtime, no en compilación.
- `0014_storage_buckets.sql` (los 3 buckets privados) no se implementó todavía — no estaba en el alcance de `db-auth` para Fase 1; queda para cuando `imports-ui`/`order-domain` lo necesiten (Fase 2/4).
- CI aún no existe: decidir si `xlwt` (dependencia de solo-pruebas de `engine-core`) se instala en el pipeline, o si las 6 pruebas del lector `.xls` quedan como `skipped` ahí.
