import { NextResponse, type NextRequest } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function DELETE(
  _request: NextRequest,
  { params }: { params: Promise<{ id: string; itemId: string }> },
) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { id, itemId } = await params;
  const supabase = await createClient();

  const { data: item, error: itemError } = await supabase
    .from("purchase_order_items")
    .select("id")
    .eq("id", itemId)
    .eq("purchase_order_id", id)
    .maybeSingle();
  if (itemError) return NextResponse.json({ error: itemError.message }, { status: 500 });
  if (!item) return NextResponse.json({ error: "La línea no pertenece a esta orden." }, { status: 404 });

  const { error } = await supabase.rpc("delete_purchase_order_item", { p_item_id: itemId });
  if (error) return NextResponse.json({ error: error.message }, { status: 422 });
  return NextResponse.json({ ok: true });
}
