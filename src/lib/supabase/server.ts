import { cookies } from "next/headers";
import { createServerClient } from "@supabase/ssr";

import { getSupabaseEnv } from "@/lib/env";

/**
 * Cliente de Supabase para el SERVIDOR (Server Components, Server Actions,
 * Route Handlers). Propaga la sesion del usuario via cookies.
 *
 * Nunca usa `service_role`: las operaciones de proceso que si la requieren
 * (parseo de importaciones, calculo de corridas, emision de ordenes) viven en
 * rutas de servidor de fases posteriores con su propio cliente privilegiado.
 */
export async function createClient() {
  const { url, publishableKey } = getSupabaseEnv();
  const cookieStore = await cookies();

  return createServerClient(url, publishableKey, {
    cookies: {
      getAll() {
        return cookieStore.getAll();
      },
      setAll(cookiesToSet) {
        try {
          for (const { name, value, options } of cookiesToSet) {
            cookieStore.set(name, value, options);
          }
        } catch {
          // Invocado desde un Server Component: ahi no se pueden escribir
          // cookies. Es inofensivo porque `middleware.ts` ya refresco la
          // sesion en esta misma peticion.
        }
      },
    },
  });
}
