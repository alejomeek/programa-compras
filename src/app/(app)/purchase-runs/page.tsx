import type { Metadata } from "next";

import { PurchaseRunsPageClient } from "./purchase-runs-page-client";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseRunRow } from "./types";

export const metadata: Metadata = {
  title: "Compras sugeridas",
};

export const dynamic = "force-dynamic";

/**
 * `/purchase-runs` — crear una corrida y ver el historial (contrato §10.2).
 *
 * Mismo patrón que `/imports`: consulta `purchase_runs` (proveedor ya
 * resuelto por join) y `suppliers` directo con el cliente de servidor — RLS
 * decide qué ve cada rol. Las fuentes disponibles para crear una corrida
 * (`salesImports`/`inventorySnapshots`/`priceLists`) se piden bajo demanda a
 * `GET /api/purchase-runs/new-run-options?supplierId=` recién cuando se elige
 * proveedor, no aquí (dependen del proveedor elegido, que no existe todavía).
 */
export default async function Page() {
  const supabase = await createClient();

  const [{ data: runsData, error: runsError }, { data: suppliersData }] = await Promise.all([
    supabase
      .from("purchase_runs")
      .select(
        "id, status, period_start, period_end, engine_version, created_at, calculated_at, suppliers(name)",
      )
      .order("created_at", { ascending: false })
      .limit(50),
    supabase.from("suppliers").select("id, name").eq("active", true).order("name"),
  ]);

  const runs: PurchaseRunRow[] = (runsData ?? []).map((row) => ({
    id: row.id,
    status: row.status,
    supplierName: embeddedOne<{ name: string }>(row.suppliers)?.name ?? null,
    periodStart: row.period_start,
    periodEnd: row.period_end,
    engineVersion: row.engine_version,
    createdAt: row.created_at,
    calculatedAt: row.calculated_at,
  }));

  return (
    <div className="space-y-8">
      <PageHeader
        title="Compras sugeridas"
        description="Crea una corrida eligiendo proveedor y fuentes, y ajusta sus sugerencias."
      />
      <PurchaseRunsPageClient
        runs={runs}
        suppliers={suppliersData ?? []}
        loadErrorMessage={runsError ? runsError.message : null}
      />
    </div>
  );
}
