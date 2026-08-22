import "server-only";

import { NextResponse } from "next/server";

import { canWrite } from "@/lib/auth/roles";
import { getSessionUser } from "@/lib/auth/session";
import type { SessionUser } from "@/types/profile";

/**
 * Guardia de autorización para rutas de API que escriben datos operativos
 * (importaciones, corridas, órdenes). Espejo en TypeScript de las mismas tres
 * comprobaciones que ya hace RLS en Postgres — esto NO reemplaza a RLS, es
 * para devolver un error temprano y legible antes de tocar la base.
 */
export async function requireWriter(): Promise<
  { user: SessionUser } | { response: NextResponse }
> {
  const auth = await requireActiveUser();
  if ("response" in auth) return auth;
  const { user } = auth;
  if (!canWrite(user.profile.role)) {
    return {
      response: NextResponse.json(
        { error: "Tu rol no tiene permiso para esta acción." },
        { status: 403 },
      ),
    };
  }
  return { user };
}

/** Usuario autenticado y activo, sin exigir rol de escritura. */
export async function requireActiveUser(): Promise<
  { user: SessionUser } | { response: NextResponse }
> {
  const user = await getSessionUser();
  if (!user) {
    return {
      response: NextResponse.json({ error: "No autenticado." }, { status: 401 }),
    };
  }
  if (!user.profile.active) {
    return {
      response: NextResponse.json(
        { error: "Esta cuenta está desactivada." },
        { status: 403 },
      ),
    };
  }
  return { user };
}
