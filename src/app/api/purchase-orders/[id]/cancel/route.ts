import { NextResponse, type NextRequest } from "next/server";

import { requireActiveUser } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireActiveUser();
  if ("response" in auth) return auth.response;
  const { id } = await params;
  let body: { reason?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }
  if (typeof body.reason !== "string" || !body.reason.trim()) {
    return NextResponse.json({ error: "Indica el motivo de cancelación." }, { status: 400 });
  }

  const supabase = await createClient();
  const { error } = await supabase.rpc("cancel_purchase_order", {
    p_order_id: id,
    p_reason: body.reason,
  });
  if (error) return NextResponse.json({ error: error.message }, { status: 422 });
  return NextResponse.json({ ok: true });
}
