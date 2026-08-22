import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { PurchaseRunDetailView } from "@/components/purchase-runs/purchase-run-detail";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import { productNamesByEan } from "@/lib/purchase-runs/product-names";
import type {
  PurchaseRunDetail,
  PurchaseRunLineRow,
  TargetDayRow,
} from "@/app/(app)/purchase-runs/types";

export const metadata: Metadata = {
  title: "Detalle de la corrida",
};

export const dynamic = "force-dynamic";

const LINES_PAGE_SIZE = 100;

/**
 * Vista central de una corrida (contrato §10.2): resumen + tabla producto x
 * ubicación con cantidad final editable. No aparece en el menú; se llega
 * desde `/purchase-runs`.
 *
 * Trae la cabecera + la primera página de líneas directo con el cliente de
 * servidor (mismo criterio que `/imports`: RLS decide qué ve cada rol). Las
 * páginas siguientes, los filtros y los ajustes de cantidad los pide
 * `PurchaseRunDetailView` (Client Component) a `GET/POST /api/purchase-runs/
 * [id]/...` — no hace falta duplicar esa lógica aquí.
 */
export default async function PurchaseRunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const supabase = await createClient();

  const { data: run, error: runError } = await supabase
    .from("purchase_runs")
    .select(
      "id, status, supplier_id, sales_import_id, price_list_id, inventory_snapshot_id, period_start, period_end, engine_version, params_hash, created_at, calculated_at, suppliers(name)",
    )
    .eq("id", id)
    .maybeSingle();

  if (runError) {
    return (
      <PageHeader
        title="Detalle de la corrida"
        description={`No se pudo cargar la corrida: ${runError.message}`}
      />
    );
  }
  if (!run) {
    notFound();
  }

  const [{ data: targetDaysData }, { data: linesData, count }] = await Promise.all([
    supabase
      .from("purchase_run_target_days")
      .select("target_days, locations(code, name)")
      .eq("purchase_run_id", id),
    supabase
      .from("purchase_run_lines")
      .select(
        "id, ean, sales_units, period_days, daily_sales, suggested_quantity, final_quantity, stock_reference, unit_cost, status, note, row_version, updated_at, products(name), locations(code, name)",
        { count: "exact" },
      )
      .eq("purchase_run_id", id)
      .order("ean", { ascending: true })
      .range(0, LINES_PAGE_SIZE - 1),
  ]);

  const targetDays: TargetDayRow[] = (targetDaysData ?? []).map((row) => {
    const location = embeddedOne<{ code: string; name: string }>(row.locations);
    return {
      locationCode: location?.code ?? "",
      locationName: location?.name ?? "",
      targetDays: row.target_days,
    };
  });

  // La relación opcional con `products` no se llena para todos los EAN. La
  // lista de precios de esta corrida sí conserva el nombre provisto por el
  // proveedor, incluso para corridas históricas.
  const lineEans = [...new Set((linesData ?? []).map((row) => row.ean))];
  const { data: priceListItems } = lineEans.length
    ? await supabase
        .from("price_list_items")
        .select("ean, raw")
        .eq("price_list_id", run.price_list_id)
        .in("ean", lineEans)
    : { data: [] };
  const priceListNames = productNamesByEan(priceListItems ?? []);

  const detail: PurchaseRunDetail = {
    id: run.id,
    status: run.status,
    supplierId: run.supplier_id,
    supplierName: embeddedOne<{ name: string }>(run.suppliers)?.name ?? null,
    salesImportId: run.sales_import_id,
    priceListId: run.price_list_id,
    inventorySnapshotId: run.inventory_snapshot_id,
    periodStart: run.period_start,
    periodEnd: run.period_end,
    engineVersion: run.engine_version,
    paramsHash: run.params_hash,
    createdAt: run.created_at,
    calculatedAt: run.calculated_at,
    targetDays,
  };

  const lines: PurchaseRunLineRow[] = (linesData ?? []).map((row) => {
    const location = embeddedOne<{ code: string; name: string }>(row.locations);
    return {
      id: row.id,
      ean: row.ean,
      productName:
        priceListNames.get(row.ean) ?? embeddedOne<{ name: string }>(row.products)?.name ?? null,
      locationCode: location?.code ?? "",
      locationName: location?.name ?? "",
      salesUnits: row.sales_units,
      periodDays: row.period_days,
      dailySales: row.daily_sales,
      suggestedQuantity: row.suggested_quantity,
      finalQuantity: row.final_quantity,
      stockReference: row.stock_reference,
      unitCost: row.unit_cost,
      status: row.status,
      note: row.note,
      rowVersion: row.row_version,
      updatedAt: row.updated_at,
    };
  });

  return (
    <div className="space-y-8">
      <PageHeader
        title="Detalle de la corrida"
        description={`Proveedor ${detail.supplierName ?? "—"}. Tabla por producto y ubicación: ventas, días objetivo, compra sugerida y cantidad final.`}
      />
      <PurchaseRunDetailView run={detail} initialLines={lines} initialTotal={count ?? 0} />
    </div>
  );
}
