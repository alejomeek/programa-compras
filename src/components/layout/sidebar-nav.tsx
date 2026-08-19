"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { isNavItemActive, type NavItem } from "@/lib/nav";
import { cn } from "@/lib/utils";

type SidebarNavProps = {
  items: NavItem[];
  /** Se invoca al navegar; lo usa el drawer movil para cerrarse. */
  onNavigate?: () => void;
  className?: string;
};

/**
 * Arbol de navegacion compartido por el sidebar de escritorio y el `Sheet`
 * movil (contrato §10.3: un solo componente, no dos copias).
 *
 * El estado activo no depende solo del color: ademas del fondo primario lleva
 * `aria-current="page"`, que es lo que anuncian los lectores de pantalla
 * (checklist de accesibilidad §10.4).
 */
export function SidebarNav({ items, onNavigate, className }: SidebarNavProps) {
  const pathname = usePathname();

  return (
    <nav aria-label="Navegación principal" className={cn("flex flex-col gap-1", className)}>
      {items.map((item) => {
        const active = isNavItemActive(item.href, pathname);
        const Icon = item.icon;

        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar",
              active
                ? "bg-sidebar-primary text-sidebar-primary-foreground"
                : "text-muted-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            )}
          >
            <Icon aria-hidden="true" className="size-4 shrink-0" />
            <span className="truncate">{item.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}
