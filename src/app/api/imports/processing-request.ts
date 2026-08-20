/**
 * Construye la petición interna `POST /api/imports_process` (contrato §11),
 * separado de `route.ts` para poder probarlo sin mockear Next.js/Supabase —
 * mismo criterio que `processing-warning.ts` en la pantalla `/imports`.
 *
 * HALLAZGO DE HOTFIX (post primer despliegue real, ver
 * docs/IMPLEMENTATION_CONTRACT.md §15): en Preview, esta petición recibía 401
 * SIEMPRE, incluso con `INTERNAL_API_SECRET` bien configurado en ambos lados.
 * `src/proxy.ts` quedó descartado (no redirige, no toca este header: revisado
 * y confirmado con curl directo). La causa real es una capa anterior a
 * cualquier código de este repo: la Protección de Despliegue de Vercel
 * ("Vercel Authentication" / SSO), que en Preview devuelve 401 — con un
 * cuerpo `{"error":{"message":"Protected deployment",...}}`, distinto del
 * `{"error":"No autorizado."}` que responde `api/imports_process.py` — para
 * CUALQUIER petición sin la cookie de sesión de Vercel, sin importar qué
 * headers propios mande la petición. Producción no tiene esa protección
 * activada (confirmado con el mismo curl), así que nunca la sufrió.
 *
 * La salida documentada por Vercel para llamadas servidor-a-servidor como
 * esta es "Protection Bypass for Automation": al activarlo en Project
 * Settings → Deployment Protection, Vercel provisiona automáticamente
 * `VERCEL_AUTOMATION_BYPASS_SECRET` en el entorno — no es un secreto que
 * este repo cree ni gestione. Si esa variable existe, se manda como header
 * `x-vercel-protection-bypass` (el nombre exacto que exige Vercel). Si no
 * existe (por ejemplo en Producción, donde no hace falta), el header
 * simplemente no se agrega: no rompe nada donde la protección no está
 * activada.
 */
export function processingRequestInit(
  jobId: string,
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
    body: JSON.stringify({ jobId }),
  };
}
