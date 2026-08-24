import { NextResponse, type NextRequest } from "next/server";

import { requireActiveUser } from "@/lib/api/auth";
import { purchaseOrdersZipRequestInit } from "@/app/api/purchase-orders/zip-request";

export const dynamic = "force-dynamic";

const MAX_ORDERS_PER_ZIP = 50;

export async function POST(request: NextRequest) {
  const auth = await requireActiveUser();
  if ("response" in auth) return auth.response;

  let body: { orderIds?: unknown };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }
  if (
    !Array.isArray(body.orderIds)
    || body.orderIds.length === 0
    || body.orderIds.length > MAX_ORDERS_PER_ZIP
    || !body.orderIds.every((id) => typeof id === "string")
  ) {
    return NextResponse.json(
      { error: `Selecciona entre 1 y ${MAX_ORDERS_PER_ZIP} órdenes emitidas.` },
      { status: 400 },
    );
  }

  const init = purchaseOrdersZipRequestInit(
    { orderIds: body.orderIds },
    {
      internalApiSecret: process.env.INTERNAL_API_SECRET,
      automationBypassSecret: process.env.VERCEL_AUTOMATION_BYPASS_SECRET,
    },
  );
  if (!init) {
    return NextResponse.json({ error: "INTERNAL_API_SECRET no está configurado." }, { status: 500 });
  }

  try {
    const response = await fetch(new URL("/api/purchase_orders_zip", request.nextUrl.origin), init);
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { error?: string };
      return NextResponse.json({ error: body.error ?? "No se pudo preparar el archivo ZIP." }, { status: response.status });
    }
    if (!response.body) {
      return NextResponse.json({ error: "La generación del ZIP no devolvió contenido." }, { status: 502 });
    }
    return new NextResponse(response.body, {
      headers: {
        "content-type": "application/zip",
        "content-disposition": 'attachment; filename="ordenes-de-compra.zip"',
        "cache-control": "no-store",
      },
    });
  } catch (error) {
    return NextResponse.json(
      { error: `No se pudo contactar la generación del ZIP: ${(error as Error).message}.` },
      { status: 502 },
    );
  }
}
