import type { Metadata } from "next";

import {
  CostChangesFilters,
  type CostChangePriceListOption,
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
  price_list_id: string;
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

type SupplierDbRow = {
  id: string;
  name: string;
};

type PriceListDbRow = {
  id: string;
  supplier_id: string;
  version: number;
  effective_date: string;
  suppliers: { name: string }[] | null;
};

type SearchParams = Promise<{
  supplier?: string | string[];
  priceList?: string | string[];
  tbcSource?: string | string[];
}>;

function firstSearchParam(value: string | string[] | undefined) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

export default async function Page({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const supplierId = firstSearchParam(params.supplier);
  const priceListId = firstSearchParam(params.priceList);
  const tbcSourceId = firstSearchParam(params.tbcSource);
  const supabase = await createClient();
  let changesQuery = supabase
    .from("cost_changes")
    .select("supplier_id, supplier_name, price_list_id, price_list_version, effective_date, ean, product_name, supplier_cost, tbc_cost, difference, sales_import_id, tbc_period_end")
    .order("supplier_name")
    .order("ean");
  if (supplierId) changesQuery = changesQuery.eq("supplier_id", supplierId);
  if (priceListId) changesQuery = changesQuery.eq("price_list_id", priceListId);
  if (tbcSourceId) changesQuery = changesQuery.eq("sales_import_id", tbcSourceId);

  const [
    { data, error },
    { data: sourceData, error: sourceError },
    { data: supplierData, error: supplierError },
    { data: priceListData, error: priceListError },
  ] = await Promise.all([
    changesQuery.limit(500),
    supabase
      .from("cost_changes")
      .select("sales_import_id, tbc_period_end")
      .order("tbc_period_end", { ascending: false })
      .limit(1000),
    supabase.from("suppliers").select("id, name").order("name"),
    supabase
      .from("price_lists")
      .select("id, supplier_id, version, effective_date, suppliers(name)")
      .eq("status", "active")
      .order("effective_date", { ascending: false })
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
  const supplierOptions: CostChangeSupplierOption[] = ((supplierData ?? []) as SupplierDbRow[])
    .map((supplier) => ({ id: supplier.id, name: supplier.name }));
  const priceListOptions = ((priceListData ?? []) as PriceListDbRow[])
    .filter((priceList) => !supplierId || priceList.supplier_id === supplierId)
    .map((priceList) => ({
      id: priceList.id,
      label: `${priceList.suppliers?.[0]?.name ?? "Proveedor"} · lista v${priceList.version} · vigente desde ${priceList.effective_date}`,
    } satisfies CostChangePriceListOption));
  const sourceOptions = new Map<string, CostChangeSourceOption>();
  for (const row of (sourceData ?? []) as Pick<CostChangeDbRow, "sales_import_id" | "tbc_period_end">[]) {
    sourceOptions.set(row.sales_import_id, { id: row.sales_import_id, label: `TBC · período hasta ${row.tbc_period_end}` });
  }
  const filtersError = error ?? sourceError ?? supplierError ?? priceListError;

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
            suppliers={supplierOptions}
            priceLists={priceListOptions}
            tbcSources={[...sourceOptions.values()]}
            selectedSupplierId={supplierId}
            selectedPriceListId={priceListId}
            selectedTbcSourceId={tbcSourceId}
          />
          <CostChangesView changes={changes} />
        </>
      )}
    </div>
  );
}
