import { ChevronsUpDown, LogOut } from "lucide-react";

import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { roleLabel } from "@/lib/auth/roles";
import type { SessionUser } from "@/types/profile";

/** Iniciales para el avatar. Solo decorativo: el nombre siempre se muestra como texto. */
function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
}

/**
 * Pie del sidebar: usuario, rol y cierre de sesion (contrato §10.3).
 *
 * El logout va por POST a un Route Handler, nunca por GET: un enlace GET puede
 * dispararse solo con el prefetch del router y desconectar al usuario sin que
 * lo haya pedido.
 *
 * Todavia no se muestra "indicador de conexion": no hay backend real conectado
 * en esta fase y pintar un punto verde fijo seria informacion falsa.
 */
export function SidebarFooter({ user }: { user: SessionUser }) {
  const { full_name: fullName, role } = user.profile;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left transition-colors hover:bg-sidebar-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-sidebar">
        <Avatar className="size-8 shrink-0">
          <AvatarFallback className="bg-secondary text-xs font-semibold text-secondary-foreground">
            {initials(fullName)}
          </AvatarFallback>
        </Avatar>
        <span className="flex min-w-0 flex-1 flex-col leading-tight">
          <span className="truncate text-sm font-medium text-foreground">{fullName}</span>
          <span className="truncate text-xs text-muted-foreground">{roleLabel(role)}</span>
        </span>
        <ChevronsUpDown aria-hidden="true" className="size-4 shrink-0 text-muted-foreground" />
        <span className="sr-only">Abrir menú de la cuenta</span>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" side="top" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <span className="block truncate text-sm font-medium text-foreground">{fullName}</span>
          <span className="block truncate text-xs text-muted-foreground">
            {user.email ?? "Sin correo asociado"}
          </span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <form action="/auth/signout" method="post">
          <DropdownMenuItem asChild>
            <button type="submit" className="w-full cursor-pointer">
              <LogOut aria-hidden="true" className="size-4" />
              Cerrar sesión
            </button>
          </DropdownMenuItem>
        </form>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
