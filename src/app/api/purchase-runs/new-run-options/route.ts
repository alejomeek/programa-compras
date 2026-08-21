import { NextResponse, type NextRequest } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import type { NewRunOptions } from "@/app/(app)/purchase-runs/types";

export const dynamic = "force-dynamic";

/**
 * D6 (contrato §2, cerrado): sin límite de antigüedad — se listan todas las
 * fuentes `active` disponibles, más recientes primero, y el comprador elige.
 * "Active" (no "completed"): un `import_job` completado que luego quedó
 * `superseded` por una importación más nueva del mismo período/proveedor
 * es una versión vieja del mismo dato, no una fuente distinta que ofrecer.
 *
 * `DEFAULT_TARGET_DAYS = 45` debe coincidir con `engine.recommendation.
 * DEFAULT_TARGET_DAYS` — es solo el valor con el que el formulario prellena
 * los inputs; el motor aplica el mismo default igual si no llega nada.
 */
const DEFAULT_TARGET_DAYS = 45;

export async function GET(request: NextRequest) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const supplierId = request.nextUrl.searchParams.get("supplierId");
  if (!supplierId) {
    return NextResponse.json({ error: "Falta supplierId." }, { status: 400 });
  }

  const supabase = await createClient();
  const [salesImportsResult, inventorySnapshotsResult, priceListsResult, locationsResult] =
    await Promise.all([
      supabase
        .from("sales_imports")
        .select("id, period_start, period_end, created_at")
        .eq("status", "active")
        .order("created_at", { ascending: false }),
      supabase
        .from("inventory_snapshots")
        .select("id, snapshot_date, created_at")
        .eq("status", "active")
        .order("created_at", { ascending: false }),
      supabase
        .from("price_lists")
        .select("id, version, effective_date, created_at")
        .eq("supplier_id", supplierId)
        .eq("status", "active")
        .order("created_at", { ascending: false }),
      supabase
        .from("locations")
        .select("code, name")
        .eq("active", true)
        .eq("is_purchase_target", true)
        .order("display_order"),
    ]);

  const firstError =
    salesImportsResult.error ??
    inventorySnapshotsResult.error ??
    priceListsResult.error ??
    locationsResult.error;
  if (firstError) {
    return NextResponse.json({ error: firstError.message }, { status: 500 });
  }

  const options: NewRunOptions = {
    salesImports: (salesImportsResult.data ?? []).map((row) => ({
      id: row.id,
      periodStart: row.period_start,
      periodEnd: row.period_end,
      createdAt: row.created_at,
    })),
    inventorySnapshots: (inventorySnapshotsResult.data ?? []).map((row) => ({
      id: row.id,
      snapshotDate: row.snapshot_date,
      createdAt: row.created_at,
    })),
    priceLists: (priceListsResult.data ?? []).map((row) => ({
      id: row.id,
      version: row.version,
      effectiveDate: row.effective_date,
      createdAt: row.created_at,
    })),
    operativeLocations: (locationsResult.data ?? []).map((row) => ({
      code: row.code,
      name: row.name,
    })),
    defaultTargetDays: DEFAULT_TARGET_DAYS,
  };

  return NextResponse.json(options);
}
