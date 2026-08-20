import { NextResponse, type NextRequest } from "next/server";

import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import { calculateRequestInit } from "./calculate-request";
import type { PurchaseRunRow } from "@/app/(app)/purchase-runs/types";

export const dynamic = "force-dynamic";

type CreatePurchaseRunRequest = {
  supplierId?: string;
  salesImportId?: string;
  priceListId?: string;
  inventorySnapshotId?: string | null;
  targetDays?: Record<string, number>;
};

/**
 * Corridas recientes para la lista de `/purchase-runs`, más recientes primero.
 * Mismo patrón que `GET /api/imports`: el Server Component de la página
 * también puede consultar directo, esta ruta es para refrescos del cliente.
 */
export async function GET() {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("purchase_runs")
    .select(
      "id, status, period_start, period_end, engine_version, created_at, calculated_at, suppliers(name)",
    )
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const runs: PurchaseRunRow[] = (data ?? []).map((row) => ({
    id: row.id,
    status: row.status,
    supplierName: embeddedOne<{ name: string }>(row.suppliers)?.name ?? null,
    periodStart: row.period_start,
    periodEnd: row.period_end,
    engineVersion: row.engine_version,
    createdAt: row.created_at,
    calculatedAt: row.calculated_at,
  }));

  return NextResponse.json({ runs });
}

/**
 * Crea y calcula una corrida en un solo paso (contrato §11). A diferencia de
 * `POST /api/imports`, esta ruta ESPERA la respuesta de la función Python: no
 * existe un "quedó en cola sin calcular" válido — el comprador pidió
 * explícitamente un cálculo, no una carga async. Si la función Python no
 * responde, 502; si responde con un error de negocio (422) o de
 * infraestructura (500), se reenvía tal cual — es más útil que un 502 opaco.
 */
export async function POST(request: NextRequest) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { user } = auth;

  let body: CreatePurchaseRunRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }

  const { supplierId, salesImportId, priceListId, inventorySnapshotId, targetDays } = body;
  if (!supplierId || !salesImportId || !priceListId) {
    return NextResponse.json(
      { error: "Faltan supplierId, salesImportId o priceListId." },
      { status: 400 },
    );
  }

  const init = calculateRequestInit(
    {
      supplierId,
      salesImportId,
      priceListId,
      inventorySnapshotId: inventorySnapshotId ?? null,
      targetDays: targetDays ?? {},
      createdBy: user.id,
    },
    {
      internalApiSecret: process.env.INTERNAL_API_SECRET,
      automationBypassSecret: process.env.VERCEL_AUTOMATION_BYPASS_SECRET,
    },
  );
  if (!init) {
    return NextResponse.json(
      { error: "INTERNAL_API_SECRET no está configurado: el cálculo no está disponible." },
      { status: 500 },
    );
  }

  let response: Response;
  try {
    response = await fetch(
      new URL("/api/purchase_runs_calculate", request.nextUrl.origin),
      init,
    );
  } catch (error) {
    return NextResponse.json(
      { error: `No se pudo contactar el cálculo: ${(error as Error).message}.` },
      { status: 502 },
    );
  }

  const resultBody = await response.json().catch(() => ({}) as { error?: string });
  if (!response.ok) {
    return NextResponse.json(
      { error: resultBody.error ?? `El cálculo respondió ${response.status}.` },
      { status: response.status },
    );
  }

  return NextResponse.json(resultBody, { status: 201 });
}
