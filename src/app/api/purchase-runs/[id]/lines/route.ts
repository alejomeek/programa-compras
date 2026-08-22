import { NextResponse, type NextRequest } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import { productNamesByEan } from "@/lib/purchase-runs/product-names";
import type { PurchaseRunLineRow } from "@/app/(app)/purchase-runs/types";

export const dynamic = "force-dynamic";

const DEFAULT_PAGE_SIZE = 100;
const MAX_PAGE_SIZE = 500;

/**
 * Líneas de una corrida, paginadas y filtrables — una corrida real puede
 * tener cientos/miles de filas (producto x ubicación), a diferencia de
 * `import_issues` que `GET /api/imports/:id` trae completas.
 */
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> },
) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const { id } = await params;
  const searchParams = request.nextUrl.searchParams;
  const locationCode = searchParams.get("locationCode");
  const status = searchParams.get("status");
  const search = searchParams.get("search")?.trim();
  const page = Math.max(1, Number(searchParams.get("page") ?? "1") || 1);
  const pageSize = Math.min(
    MAX_PAGE_SIZE,
    Math.max(1, Number(searchParams.get("pageSize") ?? String(DEFAULT_PAGE_SIZE)) || DEFAULT_PAGE_SIZE),
  );

  const supabase = await createClient();
  let query = supabase
    .from("purchase_run_lines")
    .select(
      "id, ean, sales_units, period_days, daily_sales, suggested_quantity, final_quantity, stock_reference, unit_cost, status, note, row_version, updated_at, products(name), locations!inner(code, name)",
      { count: "exact" },
    )
    .eq("purchase_run_id", id);

  if (locationCode) {
    query = query.eq("locations.code", locationCode);
  }
  if (status) {
    query = query.eq("status", status);
  }
  if (search) {
    query = query.ilike("ean", `%${search}%`);
  }

  const from = (page - 1) * pageSize;
  const [{ data, error, count }, { data: run }] = await Promise.all([
    query.order("ean", { ascending: true }).range(from, from + pageSize - 1),
    supabase.from("purchase_runs").select("price_list_id").eq("id", id).maybeSingle(),
  ]);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const lineEans = [...new Set((data ?? []).map((row) => row.ean))];
  const { data: priceListItems } = run?.price_list_id && lineEans.length
    ? await supabase
        .from("price_list_items")
        .select("ean, raw")
        .eq("price_list_id", run.price_list_id)
        .in("ean", lineEans)
    : { data: [] };
  const priceListNames = productNamesByEan(priceListItems ?? []);

  const lines: PurchaseRunLineRow[] = (data ?? []).map((row) => {
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

  return NextResponse.json({ lines, total: count ?? 0, page, pageSize });
}
