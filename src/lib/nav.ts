import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import {
  ArrowLeftRight,
  Building2,
  FileText,
  LayoutDashboard,
  ShoppingCart,
  Upload,
} from "lucide-react";


/**
 * Definicion unica de la navegacion principal.
 *
 * La comparte el sidebar de escritorio y el `Sheet` movil para que el arbol de
 * navegacion no se duplique (docs/IMPLEMENTATION_CONTRACT.md §10.3).
 *
 * Las rutas de detalle, como `/purchase-runs/[id]`, no aparecen en el menú.
 */
export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export const NAV_ITEMS: readonly NavItem[] = [
  { href: "/dashboard", label: "Inicio", icon: LayoutDashboard },
  { href: "/suppliers", label: "Proveedores", icon: Building2 },
  { href: "/imports", label: "Importaciones", icon: Upload },
  { href: "/purchase-runs", label: "Compras sugeridas", icon: ShoppingCart },
  { href: "/orders", label: "Órdenes de compra", icon: FileText },
  { href: "/cost-changes", label: "Cambios de costo", icon: ArrowLeftRight },
] as const;

/** Todas las entradas actuales están disponibles para cualquier usuario activo. */
export function navItemsForRole(): NavItem[] {
  return [...NAV_ITEMS];
}

/**
 * Forma serializable de una entrada de menu para cruzar el limite
 * servidor -> Client Component.
 *
 * `NavItem.icon` es una referencia a un componente (funcion), y React no
 * puede pasar funciones como prop de un Server Component a un Client
 * Component: solo acepta datos planos o elementos ya renderizados (JSX). Por
 * eso el icono se resuelve a un `ReactNode` (`<Icon />`) ANTES de cruzar ese
 * limite, en vez de mandar el tipo del componente y resolverlo del lado del
 * cliente.
 */
export type NavLinkItem = {
  href: string;
  label: string;
  icon: ReactNode;
};

/**
 * Decide si una entrada debe marcarse como activa para la ruta actual.
 *
 * `/dashboard` exige coincidencia exacta; el resto acepta subrutas para que
 * `/purchase-runs/abc` mantenga iluminado "Compras sugeridas". El limite se
 * comprueba con "/" para que `/orders-archive` no active `/orders`.
 */
export function isNavItemActive(itemHref: string, pathname: string): boolean {
  if (itemHref === "/dashboard") {
    return pathname === "/dashboard";
  }
  return pathname === itemHref || pathname.startsWith(`${itemHref}/`);
}
