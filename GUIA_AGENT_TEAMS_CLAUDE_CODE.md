# Runbook: implementación con Claude Code Agent Teams

> Guía de ejecución de punta a punta para implementar el Programa de Compras Web.

## Objetivo y fuentes de verdad

El objetivo es completar la aplicación descrita en `PLAN_MIGRACION_COMPRAS_WEB.md`: Next.js + Supabase + Python, desplegada en Vercel y con la referencia visual del OMS. El lead debe leer al inicio:

1. Este runbook y `PLAN_MIGRACION_COMPRAS_WEB.md`.
2. `agent-teams.md` para la operación de Claude Code.
3. `PRD_MVP_SOFTWARE_COMPRAS.md` y `procurement_engine.py` para formatos TBC heredados.
4. La referencia OMS: `/Users/alejomeek/Documents/oms-jugando-educando/src/index.css`, `src/components/layout/AppLayout.tsx` y `src/components/layout/Sidebar.tsx`.

Del OMS se reutilizan los principios visuales, no su código ni secretos: Plus Jakarta Sans, tokens azul/gris claros, panel lateral fijo, navegación activa y superficies limpias.

## 1. Bloqueador previo: actualizar Claude Code

En este equipo Agent Teams ya está activado y tmux está instalado/configurado. Sin embargo, Claude Code instalado es `2.1.45`, mientras `agent-teams.md` documenta el flujo moderno desde `2.1.178`.

**No crear un equipo antes de actualizar.** En Terminal ejecutar:

```bash
claude update
claude --version
claude doctor
tmux -V
```

Si la actualización no instala la versión estable, seguir la instrucción de `claude doctor` o ejecutar `claude install latest`. El resultado debe ser una versión actual/compatible, sin errores de doctor y tmux disponible.

Verificar la configuración sin mostrar ni compartir todo `~/.claude/settings.json`:

```bash
python3 - <<'PY'
import json
from pathlib import Path
settings = json.loads((Path.home() / '.claude' / 'settings.json').read_text())
print('agent teams:', settings.get('env', {}).get('CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'))
print('teammate mode:', settings.get('teammateMode'))
PY
```

Debe informar `agent teams: 1` y `teammate mode: tmux`. Si no lo hace, añadir estas claves al JSON de configuración:

```json
{
  "env": { "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1" },
  "teammateMode": "tmux"
}
```

## 2. Preparación humana antes de delegar

### 2.1 Checkpoint de Git

La carpeta tiene cambios locales. No iniciar compañeros escribiendo en un árbol sucio sin decidir qué pertenece al checkpoint.

```bash
cd /Users/alejomeek/Documents/programa-compras
git status --short
git diff --check
```

Revisar los cambios y hacer un commit de documentación/estado actual, o preservarlos en una rama de respaldo. No usar `git reset --hard`. Después crear la rama de trabajo:

```bash
git switch -c feature/compras-web
```

### 2.2 Servicios externos

Una persona autorizada debe crear los proyectos `compras-dev` y `compras-prod` en Supabase, conectar Vercel al repositorio e iniciar sesión si se usarán CLIs:

```bash
supabase login
vercel login
```

Crear localmente `.env.local` a partir de `.env.example` cuando este exista. Secretos permitidos solo en entorno local/Vercel:

```text
NEXT_PUBLIC_SUPABASE_URL=
NEXT_PUBLIC_SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
SUPABASE_DB_URL=
```

Nunca pegar valores de esas variables en un prompt, un chat, un commit, un archivo de documentación ni una tarea de agente.

### 2.3 Decisiones que no se pueden inventar

Antes de liberar la Fase 3, el usuario debe confirmar:

- Si Full Mercado Libre sigue sumando ventas al CEDI.
- Si los días objetivo son globales por ubicación y editables por corrida (propuesta recomendada).
- Consecutivo oficial, IVA, flete, vencimiento y condiciones de pago de la orden.
- Usuarios iniciales y asignación de roles `admin`, `buyer`, `viewer`.
- Vigencia aceptable de archivos TBC para una corrida.

## 3. Abrir el lead en tmux

Usar modo interactivo: `claude -p` no crea equipos.

```bash
cd /Users/alejomeek/Documents/programa-compras
tmux new-session -s compras-web
claude
```

Para retomar la terminal más tarde:

```bash
tmux attach -t compras-web
```

Pegar este prompt en la sesión lead:

```text
Actúa como team lead de Agent Teams para implementar el programa de compras web.
Lee GUIA_AGENT_TEAMS_CLAUDE_CODE.md, PLAN_MIGRACION_COMPRAS_WEB.md,
agent-teams.md, PRD_MVP_SOFTWARE_COMPRAS.md y procurement_engine.py. Consulta
el OMS de /Users/alejomeek/Documents/oms-jugando-educando solo como referencia
visual; no copies su código ni secretos.

Trabaja en la rama feature/compras-web. No descartes cambios existentes ni expongas
secretos. Usa la lista de tareas compartida y dependencias claras. El lead es el
único propietario de package.json, package-lock.json, README.md, vercel.json,
configuración global, integración de rutas API y migraciones transversales.

Comienza con tres compañeros llamados domain-auditor, data-architect y ui-architect.
Requiere plan approval antes de modificar; en esta fase solo investigan y mandan
resultados al lead. Espera sus resultados y publica docs/IMPLEMENTATION_CONTRACT.md
antes de implementar código.
```

En tmux, cada compañero tendrá panel propio. `Ctrl+T` abre la lista de tareas. Para dirigir a uno, entrar a su panel y escribirle una instrucción. Para consultar estado global, pedir al lead: `Muestra tareas, dependencias y propietarios de archivos.`

## 4. Reglas que se repiten en cada fase

Pegar al lead este bloque antes de crear compañeros de implementación:

```text
Reglas para todos los compañeros:
1. Lee el plan y docs/IMPLEMENTATION_CONTRACT.md antes de editar.
2. Reclama una tarea concreta y declara los archivos bajo tu propiedad.
3. No modifiques archivos propiedad de otro compañero ni del lead.
4. No uses git reset, checkout destructivo ni borres cambios ajenos.
5. No uses datos comerciales ni secretos en Git, prompts, fixtures o pruebas.
6. Escribe pruebas junto con cada cambio de dominio.
7. Antes de terminar, ejecuta las verificaciones relevantes y comunica comandos y resultados.
8. Envía al lead archivos cambiados, riesgos, dependencias y resultado antes de marcar completada la tarea.
```

Normas de coordinación:

- Máximo tres compañeros activos por fase.
- Plan approval obligatorio para esquema, RLS, autenticación, despliegue y PDF.
- El lead espera los resultados antes de editar la misma zona.
- Al finalizar cada fase: integración, pruebas completas, commit atómico, actualización del contrato y apagado ordenado de compañeros.
- No editar `~/.claude/teams/*` ni los buzones/tareas de Claude manualmente.

## 5. Equipo y puerta de salida por fase

### Fase 0 — Descubrimiento sin escritura

| Agente | Entregable |
| --- | --- |
| `domain-auditor` | Formatos TBC, reglas que se conservan/eliminan y casos borde de fórmula. |
| `data-architect` | Esquema, RLS, Storage, historial y riesgos de datos. |
| `ui-architect` | Rutas, flujo de usuario y tokens/patrones OMS aplicables. |

El lead crea `docs/IMPLEMENTATION_CONTRACT.md`: contratos API, tablas, propietarios de carpetas, convenciones de migración, comandos de prueba y decisiones bloqueadas. Luego pide que los compañeros se apaguen.

**Salida:** contrato revisado y decisiones de negocio registradas.

### Fase 1 — Fundación

| Agente | Archivos de propiedad | Entregable |
| --- | --- | --- |
| `web-foundation` | `app/`, `components/`, UI de `lib/` | Next.js protegido, layout/sidebar OMS, estados base. |
| `db-auth` | `supabase/migrations/`, `supabase/seed.sql` | Auth, profiles, roles, proveedores, ubicaciones, RLS y buckets privados. |
| `engine-core` | `engine/`, `tests/python/`, fixtures sintéticos | Lectores/validadores puros sin Streamlit ni redistribución. |

El lead crea el proyecto Next, controla dependencias y configura CI. No permite que más de un agente toque `package.json` o migraciones que se conecten entre dominios.

**Salida:** login, RLS comprobada, layout y motor importable con pruebas.

### Fase 2 — Catálogo e importaciones

| Agente | Archivos de propiedad | Entregable |
| --- | --- | --- |
| `price-importer` | `engine/readers.py`, `engine/validation.py` y pruebas proveedor | Plantilla/lista Spektra, EAN, costos e incidencias. |
| `tbc-importer` | `engine/tbc_readers.py` y pruebas TBC | SDOSXSUC, INVEPTOS, fechas y ubicaciones. |
| `imports-ui` | `app/imports/**`, componentes asociados | Carga a Storage, estado de trabajo, período e incidencias. |

El lead posee las rutas API, operaciones transaccionales y migraciones adicionales.

**Salida:** se importan las tres fuentes; fallas no dejan datos vigentes parciales.

### Fase 3 — Compras sugeridas

| Agente | Archivos de propiedad | Entregable |
| --- | --- | --- |
| `recommendation-engineer` | `engine/recommendation.py` y sus pruebas | `ceil(ventas/días × días objetivo)`, cero ventas = cero, sin uso de stock. |
| `purchase-ui` | `app/purchase-runs/**` | Crear corrida, tabla/filtros, stock de referencia y cantidad final editable. |
| `audit-reviewer` | pruebas integración/seguridad | Auditoría de ajustes, concurrencia y permisos. |

El lead integra API y migraciones de `purchase_runs`, líneas y ajustes. Debe rechazar cualquier reintroducción de mínimos de quiebre, excedentes, objetivos por stock o transferencias.

**Salida:** resultados reproducibles y cambiar stock no altera sugerencia.

### Fase 4 — Órdenes y dashboard

| Agente | Archivos de propiedad | Entregable |
| --- | --- | --- |
| `order-domain` | `engine/orders.py`, PDFs y pruebas | Borrador, emisión, snapshot inmutable y PDF privado. |
| `orders-ui` | `app/orders/**` | Órdenes por ubicación, revisión, emisión y descarga. |
| `dashboard-catalog` | `app/dashboard/**`, `app/cost-changes/**`, `app/catalog/**` | KPIs, cambios de costo, nuevos e incidencias. |

El lead es dueño de schema/API de órdenes. No se emite una orden hasta que compras valide su formato.

**Salida:** orden emitida recuperable con mismas líneas/costos/cantidades y PDF autorizado.

### Fase 5 — QA, seguridad y producción

| Agente | Entregable |
| --- | --- |
| `security-qa` | Revisión RLS, Auth, Storage, secretos y cargas. |
| `performance-qa` | Pruebas de archivos/tablas grandes y decisión Vercel/worker basada en evidencia. |
| `acceptance-qa` | Flujo comprador, checklist UAT y manual de uso. |

Los revisores informan; el lead corrige, integra, genera release y prepara el despliegue.

**Salida:** pruebas verdes, UAT aprobada, migraciones aplicadas y producción autorizada.

## 6. Prompt reutilizable para cada fase

```text
Inicia la Fase <NOMBRE>. Lee GUIA_AGENT_TEAMS_CLAUDE_CODE.md,
PLAN_MIGRACION_COMPRAS_WEB.md y docs/IMPLEMENTATION_CONTRACT.md.

Aplica todas las reglas de coordinación del runbook. Crea tareas con dependencias
y activa estos compañeros: <NOMBRES>. Requiere plan approval antes de editar.
Asigna propietarios exclusivos de archivos. El lead mantiene package.json,
package-lock.json, README.md, vercel.json, configuración global, rutas API de
integración y migraciones transversales.

No expongas secretos ni datos comerciales. Cada compañero debe enviar archivos
modificados, pruebas ejecutadas, resultados, riesgos y bloqueos. Espera sus
informes, integra, ejecuta la suite completa, realiza un commit atómico al cumplir
la puerta de salida y actualiza el contrato y plan.
```

Si un agente se detiene antes de acabar: `Revisa el transcript de <nombre>, resuelve el bloqueo y hazlo continuar; si no puede, reemplázalo.` Si el lead intenta avanzar sin dependencias: `No avances ni integres hasta validar las tareas dependientes.`

## 7. Desarrollo, previews y producción

El lead debe crear `.env.example`, sin valores, y usar localmente:

```bash
cp .env.example .env.local
npm install
npm run dev
```

Cada PR/fase debe ejecutar lint, tipo, pruebas TypeScript/Python y validación de migraciones. Vercel crea un preview; este usa datos sintéticos o Supabase de desarrollo, nunca secretos ni datos de producción.

En producción una persona autorizada:

1. Revisa y aprueba migraciones; se aplican en orden.
2. Configura las variables en Vercel, sin agregarlas a Git.
3. Prueba login, importación, corrida, ajuste, emisión, PDF y auditoría con una cuenta de prueba.
4. Revisa logs, backups, RLS y accesos a Storage.

Vercel es la primera plataforma de despliegue. El motor Python pasa a Railway/Render/Fly.io solo si hay evidencia de timeout, bundle demasiado grande o necesidad de cola persistente; el frontend y Supabase permanecen igual.

## 8. Aceptación humana final

Antes de reemplazar Streamlit, validar con archivos reales:

- [ ] Lista proveedor, SDOSXSUC e INVEPTOS se importan y sus incidencias son rastreables.
- [ ] Ventas `0` dan sugerencia `0`, sin importar stock.
- [ ] Cambiar stock de referencia no altera la recomendación.
- [ ] Una muestra manual coincide con `ceil((ventas/días) × días objetivo)`.
- [ ] Ajustes de comprador quedan auditados.
- [ ] Las órdenes por ubicación y PDF cumplen el formato comercial aprobado.
- [ ] Un viewer no puede editar ni emitir, y archivos/PDF no son públicos.
- [ ] Producción Vercel, backups Supabase y monitoreo están activos.

## 9. Trabajo que seguirá siendo humano

Claude Code y los equipos pueden completar código, migraciones, interfaz, pruebas, CI, previews y documentación. Una persona debe conservar control sobre: autenticación/facturación de Supabase y Vercel, secretos, decisiones de negocio pendientes, aprobación de PDF, migraciones productivas, despliegue final y validación con archivos reales.
