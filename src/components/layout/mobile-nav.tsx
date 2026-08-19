"use client";

import { useState } from "react";
import { Menu } from "lucide-react";

import { AppLogo } from "@/components/layout/app-logo";
import { SidebarFooter } from "@/components/layout/sidebar-footer";
import { SidebarNav } from "@/components/layout/sidebar-nav";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import type { NavLinkItem } from "@/lib/nav";
import type { SessionUser } from "@/types/profile";

/**
 * Navegacion en pantallas menores a `md` (768px): el sidebar fijo se oculta y
 * su mismo arbol se abre en un `Sheet` (contrato §10.3).
 *
 * Incluye tambien el pie con usuario y logout: si solo estuviera en el sidebar
 * de escritorio, en movil no habria forma de cerrar sesion.
 *
 * El drawer se cierra al navegar; de lo contrario tapa la pagina recien
 * cargada y obliga a un gesto extra.
 */
export function MobileNav({ items, user }: { items: NavLinkItem[]; user: SessionUser }) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon" className="md:hidden">
          <Menu aria-hidden="true" className="size-5" />
          <span className="sr-only">Abrir menú de navegación</span>
        </Button>
      </SheetTrigger>
      <SheetContent side="left" className="flex w-[280px] flex-col bg-sidebar p-0">
        <SheetHeader className="border-b border-sidebar-border">
          <SheetTitle asChild>
            <AppLogo />
          </SheetTitle>
          <SheetDescription className="sr-only">
            Navegación principal del Programa de Compras
          </SheetDescription>
        </SheetHeader>
        <SidebarNav
          items={items}
          onNavigate={() => setOpen(false)}
          className="flex-1 overflow-y-auto px-3 py-2"
        />
        <div className="border-t border-sidebar-border p-3">
          <SidebarFooter user={user} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
