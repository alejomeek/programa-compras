import { NextResponse } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseRunDetail, TargetDayRow } from "@/app/(app)/purchase-runs/types";

export const dynamic = "force-dynamic";

/**
 * Cabecera de una corrida + sus días objetivo por ubicación (fotografía,
 * `purchase_run_target_days`), para el resumen de `/purchase-runs/[id]`.
 * Las líneas se piden aparte y paginadas — ver `[id]/lines/route.ts`.
 */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

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
    return NextResponse.json({ error: runError.message }, { status: 500 });
  }
  if (!run) {
    return NextResponse.json({ error: "Corrida no encontrada." }, { status: 404 });
  }

  const { data: targetDaysData, error: targetDaysError } = await supabase
    .from("purchase_run_target_days")
    .select("target_days, locations(code, name)")
    .eq("purchase_run_id", id);

  if (targetDaysError) {
    return NextResponse.json({ error: targetDaysError.message }, { status: 500 });
  }

  const targetDays: TargetDayRow[] = (targetDaysData ?? []).map((row) => {
    const location = embeddedOne<{ code: string; name: string }>(row.locations);
    return {
      locationCode: location?.code ?? "",
      locationName: location?.name ?? "",
      targetDays: row.target_days,
    };
  });

  const result: PurchaseRunDetail = {
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

  return NextResponse.json({ run: result });
}
