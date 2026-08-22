import { NextResponse, type NextRequest } from "next/server";

import { requireActiveUser, requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseOrderDetail, PurchaseOrderItemRow } from "@/app/(app)/orders/types";

export const dynamic = "force-dynamic";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireActiveUser();
  if ("response" in auth) return auth.response;
  const { id } = await params;
  const supabase = await createClient();
  const [{ data: order, error }, { data: items }] = await Promise.all([
    supabase
      .from("purchase_orders")
      .select("id, supplier_id, location_id, purchase_run_id, order_number, status, notes, total_units, subtotal, pdf_file_id, created_at, issued_at, cancelled_at, cancelled_by, cancel_reason, suppliers(name), locations(code, name)")
      .eq("id", id)
      .maybeSingle(),
    supabase
      .from("purchase_order_items")
      .select("id, ean, product_name, tbc_sku, unit_cost, quantity, line_total")
      .eq("purchase_order_id", id)
      .order("created_at", { ascending: true }),
  ]);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!order) return NextResponse.json({ error: "Orden no encontrada." }, { status: 404 });

  const supplier = embeddedOne<{ name: string }>(order.suppliers);
  const location = embeddedOne<{ code: string; name: string }>(order.locations);
  const detail: PurchaseOrderDetail = {
    id: order.id,
    supplierId: order.supplier_id,
    supplierName: supplier?.name ?? "Proveedor",
    locationId: order.location_id,
    locationCode: location?.code ?? "",
    locationName: location?.name ?? "Ubicación",
    purchaseRunId: order.purchase_run_id,
    orderNumber: order.order_number,
    status: order.status,
    notes: order.notes,
    totalUnits: order.total_units,
    subtotal: String(order.subtotal),
    pdfFileId: order.pdf_file_id,
    createdAt: order.created_at,
    issuedAt: order.issued_at,
    cancelledAt: order.cancelled_at,
    cancelledBy: order.cancelled_by,
    cancelReason: order.cancel_reason,
    items: (items ?? []).map((item): PurchaseOrderItemRow => ({
      id: item.id,
      ean: item.ean,
      productName: item.product_name,
      tbcSku: item.tbc_sku,
      unitCost: String(item.unit_cost),
      quantity: item.quantity,
      lineTotal: String(item.line_total),
    })),
  };
  return NextResponse.json({ order: detail });
}

export async function PATCH(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { id } = await params;
  let body: { notes?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }
  if (typeof body.notes !== "string") {
    return NextResponse.json({ error: "Notas debe ser texto." }, { status: 400 });
  }

  const supabase = await createClient();
  const { error } = await supabase.rpc("update_purchase_order_draft", {
    p_order_id: id,
    p_notes: body.notes,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 422 });
  return NextResponse.json({ ok: true });
}
