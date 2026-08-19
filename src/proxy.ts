import type { NextRequest } from "next/server";

import { updateSession } from "@/lib/supabase/middleware";

export default async function proxy(request: NextRequest) {
  return updateSession(request);
}

export const config = {
  matcher: [
    /*
     * Todas las rutas salvo los estaticos y los assets de imagen. No se
     * excluye ninguna ruta de la app: el refresco de sesion debe ocurrir
     * tambien en `/login` para que un usuario ya autenticado sea redirigido.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp|ico)$).*)",
  ],
};
