import type { Metadata } from "next";

import {
  CostChangesFilters,
  type CostChangeSourceOption,
  type CostChangeSupplierOption,
} from "@/components/cost-changes/cost-changes-filters";
import { CostChangesView, type CostChangeRow } from "@/components/cost-changes/cost-changes-view";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Cambios de costo",
};

export const dynamic = "force-dynamic";

type CostChangeDbRow = {
  supplier_id: string;
  supplier_name: string;
  price_list_version: number;
  effective_date: string;
  ean: string;
  product_name: string;
  supplier_cost: string | number;
  tbc_cost: string | number;
  difference: string | number;
  sales_import_id: string;
  tbc_period_end: string;
};

type SearchParams = Promise<{
  supplier?: string | string[];
  tbcSource?: string | string[];
}>;

function firstSearchParam(value: string | string[] | undefined) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export default async function Page({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const supplierId = firstSearchParam(params.supplier);
  const tbcSourceId = firstSearchParam(params.tbcSource);
  const supabase = await createClient();
  let changesQuery = supabase
    .from("cost_changes")
    .select("supplier_id, supplier_name, price_list_version, effective_date, ean, product_name, supplier_cost, tbc_cost, difference, sales_import_id, tbc_period_end")
    .order("supplier_name")
    .order("ean");
  if (supplierId) changesQuery = changesQuery.eq("supplier_id", supplierId);
  if (tbcSourceId) changesQuery = changesQuery.eq("sales_import_id", tbcSourceId);

  const [{ data, error }, { data: filterData, error: filterError }] = await Promise.all([
    changesQuery.limit(500),
    supabase
      .from("cost_changes")
      .select("supplier_id, supplier_name, sales_import_id, tbc_period_end")
      .order("supplier_name")
      .order("tbc_period_end", { ascending: false })
      .limit(1000),
  ]);
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
  const supplierOptions = new Map<string, CostChangeSupplierOption>();
  const sourceOptions = new Map<string, CostChangeSourceOption>();
  for (const row of (filterData ?? []) as Pick<CostChangeDbRow, "supplier_id" | "supplier_name" | "sales_import_id" | "tbc_period_end">[]) {
    supplierOptions.set(row.supplier_id, { id: row.supplier_id, name: row.supplier_name });
    sourceOptions.set(row.sales_import_id, { id: row.sales_import_id, label: `TBC · período hasta ${row.tbc_period_end}` });
  }
  const filtersError = error ?? filterError;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Cambios de costo"
        description="Comparación exacta del costo de la lista vigente del proveedor contra el último costo TBC disponible."
      />
      {filtersError ? (
        <p className="text-sm text-destructive">No se pudieron cargar los cambios: {filtersError.message}</p>
      ) : (
        <>
          <CostChangesFilters
            suppliers={[...supplierOptions.values()]}
            tbcSources={[...sourceOptions.values()]}
            selectedSupplierId={supplierId}
            selectedTbcSourceId={tbcSourceId}
          />
          <CostChangesView changes={changes} />
        </>
      )}
    </div>
  );
}
