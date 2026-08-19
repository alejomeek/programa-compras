import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { isAdmin } from "@/lib/auth/roles";
import { getSessionUser } from "@/lib/auth/session";

export const metadata: Metadata = {
  title: "Configuración",
};

/**
 * Configuracion: ubicaciones, dias objetivo por defecto y usuarios/roles.
 * Solo `admin` (contrato §10.2).
 *
 * El rol se REVALIDA aqui, en servidor, aunque `AppShell` ya haya ocultado el
 * enlace del menu: ocultar no es proteger, y esta ruta se puede escribir a mano
 * en la barra de direcciones. Se responde 404 y no 403 para no confirmarle a un
 * usuario sin permiso que la seccion existe.
 */
export const dynamic = "force-dynamic";

export default async function SettingsPage() {
  const user = await getSessionUser();

  if (!user || !isAdmin(user.profile.role)) {
    notFound();
  }

  return (
    <PageHeader
      title="Configuración"
      description="Ubicaciones, días objetivo predeterminados y administración de usuarios. Sin contenido todavía: llega en fases posteriores."
    />
  );
}
