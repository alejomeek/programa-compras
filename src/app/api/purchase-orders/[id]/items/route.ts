import { NextResponse, type NextRequest } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { id } = await params;
  let body: { ean?: unknown; productName?: unknown; tbcSku?: unknown; unitCost?: unknown; quantity?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }
  const unitCost = Number(body.unitCost);
  const quantity = Number(body.quantity);
  const tbcSku = typeof body.tbcSku === "string" ? body.tbcSku : "";
  if (
    typeof body.ean !== "string" || !/^\d+$/.test(body.ean) ||
    typeof body.productName !== "string" || !body.productName.trim() ||
    !Number.isFinite(unitCost) || unitCost < 0 || !Number.isInteger(quantity) || quantity <= 0 ||
    (body.tbcSku !== undefined && typeof body.tbcSku !== "string")
  ) {
    return NextResponse.json({ error: "Completa EAN, producto, cantidad positiva y costo no negativo." }, { status: 400 });
  }

  const supabase = await createClient();
  const { error } = await supabase.rpc("add_manual_purchase_order_item", {
    p_order_id: id,
    p_ean: body.ean,
    p_product_name: body.productName.trim(),
    p_tbc_sku: tbcSku,
    p_unit_cost: unitCost,
    p_quantity: quantity,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 422 });
  return NextResponse.json({ ok: true }, { status: 201 });
}
