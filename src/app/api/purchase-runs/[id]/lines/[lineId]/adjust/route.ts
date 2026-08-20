import { NextResponse } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { mapAdjustError } from "@/app/api/purchase-runs/adjust-error";

export const dynamic = "force-dynamic";

type AdjustRequest = {
  newQuantity?: number;
  expectedRowVersion?: number;
  reason?: string | null;
};

/**
 * Única vía de escritura de `purchase_run_lines.final_quantity` (contrato §9):
 * llama al RPC `update_final_quantity` (`supabase/migrations/0014_purchase_
 * runs.sql`), que compara `row_version` con concurrencia optimista — nunca
 * last-write-wins silencioso. El error de Postgres se traduce con
 * `mapAdjustError` (probado aparte, sin mockear Supabase).
 */
export async function POST(
  request: Request,
  { params }: { params: Promise<{ id: string; lineId: string }> },
) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const { lineId } = await params;

  let body: AdjustRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }

  const { newQuantity, expectedRowVersion, reason } = body;
  if (typeof newQuantity !== "number" || typeof expectedRowVersion !== "number") {
    return NextResponse.json(
      { error: "Faltan newQuantity o expectedRowVersion." },
      { status: 400 },
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("update_final_quantity", {
    p_line_id: lineId,
    p_new_quantity: newQuantity,
    p_expected_row_version: expectedRowVersion,
    p_reason: reason ?? null,
  });

  if (error) {
    const mapped = mapAdjustError(error);
    if (!mapped.isVersionConflict) {
      return NextResponse.json({ error: mapped.error }, { status: mapped.status });
    }
    // Conflicto de versión: se relee la línea para devolver el valor vigente,
    // así el cliente puede mostrar "esto es lo que hay ahora" sin otra ida y
    // vuelta manual.
    const { data: current } = await supabase
      .from("purchase_run_lines")
      .select("final_quantity, row_version, updated_at")
      .eq("id", lineId)
      .maybeSingle();
    return NextResponse.json(
      {
        error: mapped.error,
        current: current
          ? {
              finalQuantity: current.final_quantity,
              rowVersion: current.row_version,
              updatedAt: current.updated_at,
            }
          : null,
      },
      { status: mapped.status },
    );
  }

  return NextResponse.json({
    line: {
      id: data.id,
      finalQuantity: data.final_quantity,
      rowVersion: data.row_version,
      updatedAt: data.updated_at,
      note: data.note,
    },
  });
}
