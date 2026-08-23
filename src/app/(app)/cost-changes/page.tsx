import type { Metadata } from "next";

import { CostChangesView, type CostChangeRow } from "@/components/cost-changes/cost-changes-view";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Cambios de costo",
};

export const dynamic = "force-dynamic";

type CostChangeDbRow = {
  supplier_name: string;
  price_list_version: number;
  effective_date: string;
  ean: string;
  product_name: string;
  supplier_cost: string | number;
  tbc_cost: string | number;
  difference: string | number;
  tbc_period_end: string;
};

export default async function Page() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("cost_changes")
    .select("supplier_name, price_list_version, effective_date, ean, product_name, supplier_cost, tbc_cost, difference, tbc_period_end")
    .order("supplier_name")
    .order("ean")
    .limit(500);
  const changes: CostChangeRow[] = ((data ?? []) as CostChangeDbRow[]).map((row) => ({
    supplierName: row.supplier_name,
    priceListVersion: row.price_list_version,
    effectiveDate: row.effective_date,
    ean: row.ean,
    productName: row.product_name,
    supplierCost: String(row.supplier_cost),
    tbcCost: String(row.tbc_cost),
    difference: String(row.difference),
    tbcPeriodEnd: row.tbc_period_end,
  }));

  return (
    <div className="space-y-8">
      <PageHeader
        title="Cambios de costo"
        description="Comparación exacta del costo de la lista vigente del proveedor contra el último costo TBC disponible."
      />
      {error ? <p className="text-sm text-destructive">No se pudieron cargar los cambios: {error.message}</p> : <CostChangesView changes={changes} />}
    </div>
  );
}
