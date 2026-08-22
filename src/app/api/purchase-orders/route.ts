import { NextResponse, type NextRequest } from "next/server";

import { requireActiveUser, requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseOrderRow } from "@/app/(app)/orders/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const auth = await requireActiveUser();
  if ("response" in auth) return auth.response;

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("purchase_orders")
    .select("id, order_number, status, total_units, subtotal, created_at, issued_at, cancelled_at, suppliers(name), locations(code, name)")
    .order("created_at", { ascending: false })
    .limit(50);
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });

  return NextResponse.json({ orders: (data ?? []).map(toOrderRow) });
}

export async function POST(request: NextRequest) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  let body: { runLineIds?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }
  const runLineIds = body.runLineIds;
  if (!Array.isArray(runLineIds) || runLineIds.length === 0 || !runLineIds.every((id) => typeof id === "string")) {
    return NextResponse.json({ error: "Selecciona al menos una línea de la corrida." }, { status: 400 });
  }

  const supabase = await createClient();
  const { data, error } = await supabase.rpc("create_purchase_order_drafts", {
    p_line_ids: runLineIds,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 422 });

  return NextResponse.json(
    { orderIds: (data ?? []).map((row: { purchase_order_id: string }) => row.purchase_order_id) },
    { status: 201 },
  );
}

function toOrderRow(row: {
  id: string;
  order_number: string | null;
  status: string;
  total_units: number;
  subtotal: number | string;
  created_at: string;
  issued_at: string | null;
  cancelled_at: string | null;
  suppliers: { name: string } | { name: string }[] | null;
  locations: { code: string; name: string } | { code: string; name: string }[] | null;
}): PurchaseOrderRow {
  const supplier = embeddedOne<{ name: string }>(row.suppliers);
  const location = embeddedOne<{ code: string; name: string }>(row.locations);
  return {
    id: row.id,
    orderNumber: row.order_number,
    status: row.status as PurchaseOrderRow["status"],
    supplierName: supplier?.name ?? "Proveedor",
    locationCode: location?.code ?? "",
    locationName: location?.name ?? "Ubicación",
    totalUnits: row.total_units,
    subtotal: String(row.subtotal),
    createdAt: row.created_at,
    issuedAt: row.issued_at,
    cancelledAt: row.cancelled_at,
  };
}
