/**
 * Construye la petición interna `POST /api/purchase_runs_calculate`, mismo
 * criterio que `src/app/api/imports/processing-request.ts`: separado de
 * `route.ts` para poder probarlo sin mockear Next.js/Supabase, y agrega el
 * header `x-vercel-protection-bypass` cuando `VERCEL_AUTOMATION_BYPASS_SECRET`
 * existe (hallazgo de Fase 2, ver docs/IMPLEMENTATION_CONTRACT.md §15) — sin
 * esa variable (como en Producción, donde no hace falta) el header no se
 * agrega.
 */
export type CalculateRunBody = {
  supplierId: string;
  salesImportId: string;
  priceListId: string;
  inventorySnapshotId?: string | null;
  targetDays: Record<string, number>;
  createdBy: string;
};

export function calculateRequestInit(
  body: CalculateRunBody,
  env: {
    internalApiSecret: string | undefined;
    automationBypassSecret?: string | undefined;
  },
): RequestInit | null {
  if (!env.internalApiSecret) {
    return null;
  }
  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-internal-secret": env.internalApiSecret,
  };
  if (env.automationBypassSecret) {
    headers["x-vercel-protection-bypass"] = env.automationBypassSecret;
  }
  return {
    method: "POST",
    headers,
    body: JSON.stringify(body),
  };
}
