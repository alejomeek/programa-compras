import type { ReactNode } from "react";

import { AppLogo } from "@/components/layout/app-logo";
import { MobileNav } from "@/components/layout/mobile-nav";
import { SidebarFooter } from "@/components/layout/sidebar-footer";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { navItemsForRole, type NavLinkItem } from "@/lib/nav";
import type { SessionUser } from "@/types/profile";

/**
 * Estructura general de la aplicacion (contrato §10.3):
 *  - >= md: `<aside>` fijo de 240px, superficie blanca y borde derecho.
 *  - <  md: sidebar oculto y barra superior con boton que abre el `Sheet`.
 *
 * Las entradas de menu se calculan EN SERVIDOR a partir del rol del perfil,
 * asi que "Configuración" ni siquiera se envia al navegador para quien no es
 * admin. Aun asi, `/settings` revalida el rol por su cuenta: ocultar un enlace
 * no protege una ruta.
 */
export function AppShell({ user, children }: { user: SessionUser; children: ReactNode }) {
  // El icono se resuelve a elemento AQUI, en servidor: `SidebarNav`/`MobileNav`
  // son Client Components y no pueden recibir la referencia al componente del
  // icono como prop (no es serializable), solo el elemento ya renderizado.
  const items: NavLinkItem[] = navItemsForRole(user.profile.role).map((item) => ({
    href: item.href,
    label: item.label,
    icon: <item.icon aria-hidden="true" className="size-4 shrink-0" />,
  }));

  return (
    <div className="flex min-h-svh flex-col md:flex-row">
      <aside className="sticky top-0 hidden h-svh w-60 shrink-0 flex-col border-r border-sidebar-border bg-sidebar md:flex">
        <div className="border-b border-sidebar-border px-4 py-4">
          <AppLogo />
        </div>
        <SidebarNav items={items} className="flex-1 overflow-y-auto px-3 py-4" />
        <div className="border-t border-sidebar-border p-3">
          <SidebarFooter user={user} />
        </div>
      </aside>

      <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-sidebar-border bg-sidebar px-3 py-2 md:hidden">
        <MobileNav items={items} user={user} />
        <AppLogo />
      </header>

      <div className="flex min-w-0 flex-1 flex-col">
        <main id="contenido" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
          <div className="mx-auto flex w-full max-w-7xl flex-col gap-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
