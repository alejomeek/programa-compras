import { NextResponse, type NextRequest } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { issueOrderRequestInit } from "@/app/api/purchase-orders/issue-request";

export const dynamic = "force-dynamic";

export async function POST(request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { id } = await params;
  const init = issueOrderRequestInit(
    { orderId: id, issuedBy: auth.user.id },
    {
      internalApiSecret: process.env.INTERNAL_API_SECRET,
      automationBypassSecret: process.env.VERCEL_AUTOMATION_BYPASS_SECRET,
    },
  );
  if (!init) {
    return NextResponse.json({ error: "INTERNAL_API_SECRET no está configurado." }, { status: 500 });
  }
  try {
    const response = await fetch(new URL("/api/purchase_orders_issue", request.nextUrl.origin), init);
    const body = await response.json().catch(() => ({}) as { error?: string });
    if (!response.ok) return NextResponse.json({ error: body.error ?? "No se pudo emitir la orden." }, { status: response.status });
    return NextResponse.json(body, { status: 201 });
  } catch (error) {
    return NextResponse.json({ error: `No se pudo contactar la emisión: ${(error as Error).message}.` }, { status: 502 });
  }
}
