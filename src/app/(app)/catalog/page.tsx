import type { Metadata } from "next";

import { CatalogView, type CatalogIssueRow, type CatalogItemRow, type CatalogStatus } from "@/components/catalog/catalog-view";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/server";

export const metadata: Metadata = {
  title: "Catálogo",
};

export const dynamic = "force-dynamic";

type CatalogItemDbRow = {
  supplier_name: string;
  price_list_version: number | null;
  ean: string;
  product_name: string;
  supplier_cost: string | number | null;
  tbc_sku: string | null;
  status: CatalogStatus;
};

type CatalogIssueDbRow = {
  id: string;
  severity: string;
  code: string;
  ean: string | null;
  product_name: string | null;
  detail: string;
};

export default async function Page() {
  const supabase = await createClient();
  const [{ data: catalogData, error: catalogError }, { data: issueData, error: issueError }] = await Promise.all([
    supabase
      .from("catalog_items")
      .select("supplier_name, price_list_version, ean, product_name, supplier_cost, tbc_sku, status")
      .order("supplier_name")
      .order("product_name")
      .limit(500),
    supabase
      .from("import_issues")
      .select("id, severity, code, ean, product_name, detail")
      .order("created_at", { ascending: false })
      .limit(50),
  ]);
  const items: CatalogItemRow[] = ((catalogData ?? []) as CatalogItemDbRow[]).map((row) => ({
    supplierName: row.supplier_name,
    priceListVersion: row.price_list_version,
    ean: row.ean,
    productName: row.product_name,
    supplierCost: row.supplier_cost === null ? null : String(row.supplier_cost),
    tbcSku: row.tbc_sku,
    status: row.status,
  }));
  const issues: CatalogIssueRow[] = ((issueData ?? []) as CatalogIssueDbRow[]).map((row) => ({
    id: row.id,
    severity: row.severity,
    code: row.code,
    ean: row.ean,
    productName: row.product_name,
    detail: row.detail,
  }));
  const error = catalogError ?? issueError;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Catálogo"
        description="Productos disponibles por proveedor, novedades de lista y problemas detectados durante las importaciones."
      />
      {error ? <p className="text-sm text-destructive">No se pudo cargar el catálogo: {error.message}</p> : <CatalogView items={items} issues={issues} />}
    </div>
  );
}
