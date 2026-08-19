import { NextResponse, type NextRequest } from "next/server";
import { createServerClient } from "@supabase/ssr";

import { getSupabaseEnv, MissingEnvError } from "@/lib/env";

/**
 * Refresca el token de Supabase y reescribe las cookies en la respuesta.
 *
 * OJO CON EL ALCANCE: este helper NO decide si una ruta es accesible. La
 * decision de autorizacion vive en `src/app/(app)/layout.tsx` (servidor) y,
 * para `/settings`, se revalida ademas en la propia pagina. El middleware solo
 * mantiene viva la sesion, que es justamente lo que Supabase recomienda.
 */
export async function updateSession(request: NextRequest) {
  const response = NextResponse.next({ request });

  let env;
  try {
    env = getSupabaseEnv();
  } catch (error) {
    if (error instanceof MissingEnvError) {
      // Sin configuracion no hay sesion que refrescar. Se deja pasar la
      // peticion para que el fallo aparezca donde se puede explicar (la
      // pagina), en vez de convertir todo el sitio en un 500 opaco.
      return response;
    }
    throw error;
  }

  const supabase = createServerClient(env.url, env.publishableKey, {
    cookies: {
      getAll() {
        return request.cookies.getAll();
      },
      setAll(cookiesToSet) {
        for (const { name, value } of cookiesToSet) {
          request.cookies.set(name, value);
        }
        for (const { name, value, options } of cookiesToSet) {
          response.cookies.set(name, value, options);
        }
      },
    },
  });

  // Llamada obligatoria: es la que dispara el refresco del token.
  // `getUser()` valida contra Supabase; `getSession()` solo lee la cookie y por
  // eso no se usa nunca en servidor.
  await supabase.auth.getUser();

  return response;
}
