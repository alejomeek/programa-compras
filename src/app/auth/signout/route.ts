import { NextResponse, type NextRequest } from "next/server";

import { MissingEnvError } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

/**
 * Cierre de sesion.
 *
 * Solo POST: un endpoint GET puede dispararse con el prefetch del router de
 * Next y desconectar al usuario sin que lo haya pedido.
 */
export async function POST(request: NextRequest) {
  try {
    const supabase = await createClient();
    await supabase.auth.signOut();
  } catch (error) {
    // Si no hay configuracion tampoco hay sesion que cerrar: se redirige a
    // /login igual, que es el estado final deseado.
    if (!(error instanceof MissingEnvError)) {
      throw error;
    }
  }

  return NextResponse.redirect(new URL("/login", request.url), { status: 303 });
}
