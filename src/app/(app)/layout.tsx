import type { ReactNode } from "react";
import { redirect } from "next/navigation";

import { AccountInactive } from "@/components/layout/account-inactive";
import { AppShell } from "@/components/layout/app-shell";
import { NotConfigured } from "@/components/layout/not-configured";
import { getSessionUser } from "@/lib/auth/session";
import { isSupabaseConfigured } from "@/lib/env";

/**
 * Layout del segmento protegido.
 *
 * Es AQUI donde se decide el acceso, no en `proxy.ts`: el proxy solo refresca
 * el token. Esta comprobacion corre en servidor, en cada peticion, y usa
 * `auth.getUser()` (valida contra Supabase) en lugar de `getSession()`.
 *
 * `force-dynamic` evita que Next intente prerenderizar estas rutas durante
 * `next build`, cuando todavia no hay variables de entorno ni cookies.
 */
export const dynamic = "force-dynamic";

export default async function AppLayout({ children }: { children: ReactNode }) {
  // Sin configuracion no se deja pasar a nadie: se explica el problema en vez
  // de reventar con un error generico o de fingir una sesion.
  if (!isSupabaseConfigured()) {
    return <NotConfigured />;
  }

  const user = await getSessionUser();

  if (!user) {
    redirect("/login");
  }

  // Segun el contrato §6.3 las personas no se borran, se desactivan. Un perfil
  // inactivo conserva sesion valida, asi que hay que frenarlo explicitamente.
  if (!user.profile.active) {
    return <AccountInactive fullName={user.profile.full_name} />;
  }

  return <AppShell user={user}>{children}</AppShell>;
}
