import "server-only";

import { createClient } from "@/lib/supabase/server";
import { normalizeRole } from "@/lib/auth/roles";
import type { SessionUser } from "@/types/profile";

/**
 * Devuelve el usuario autenticado con su perfil, o `null` si no hay sesion.
 *
 * Se usa SIEMPRE `auth.getUser()`, nunca `auth.getSession()`: `getSession()`
 * se limita a leer la cookie y por tanto no sirve para autorizar en servidor.
 *
 * Este modulo es `server-only`: importarlo desde un Client Component es un
 * error de compilacion, no un fallo silencioso en produccion.
 */
export async function getSessionUser(): Promise<SessionUser | null> {
  const supabase = await createClient();

  const {
    data: { user },
    error: userError,
  } = await supabase.auth.getUser();

  if (userError || !user) {
    return null;
  }

  const { data: profile, error: profileError } = await supabase
    .from("profiles")
    .select("id, full_name, role, active")
    .eq("id", user.id)
    .maybeSingle();

  if (profileError) {
    // La migracion `0002_profiles.sql` es propiedad de `db-auth` y puede no
    // estar aplicada todavia. En ese caso la UI sigue siendo utilizable con el
    // rol de menor privilegio en vez de dejar al usuario ante una pantalla
    // rota. No se inventan permisos: RLS sigue decidiendo cada consulta.
    console.warn(
      "[auth] No se pudo leer 'profiles' (¿migracion 0002 sin aplicar?). " +
        `Se degrada al rol de menor privilegio. Detalle: ${profileError.message}`,
    );
  }

  return {
    id: user.id,
    email: user.email ?? null,
    profile: {
      id: user.id,
      full_name: profile?.full_name ?? user.email ?? "Usuario",
      role: normalizeRole(profile?.role),
      active: profile?.active ?? true,
    },
  };
}
