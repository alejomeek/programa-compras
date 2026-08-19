"use server";

import { revalidatePath } from "next/cache";
import { redirect } from "next/navigation";

import { MissingEnvError } from "@/lib/env";
import { createClient } from "@/lib/supabase/server";

import type { LoginState } from "./login-state";

// Re-exportado solo como tipo: un modulo "use server" unicamente puede
// exportar funciones async en tiempo de ejecucion (Next.js lo rechaza en
// build). El estado inicial (un objeto, no una funcion) vive en
// ./login-state, sin la directiva "use server".
export type { LoginState };

/**
 * Inicia sesion contra Supabase Auth.
 *
 * Se distinguen dos fallos que el usuario no puede confundir:
 *  - la aplicacion no esta configurada (faltan variables de entorno);
 *  - las credenciales no sirven.
 * En el segundo caso el mensaje es deliberadamente generico: decir "ese correo
 * no existe" permite enumerar cuentas.
 */
export async function signIn(_prevState: LoginState, formData: FormData): Promise<LoginState> {
  const email = String(formData.get("email") ?? "").trim();
  const password = String(formData.get("password") ?? "");

  if (!email || !password) {
    return { error: "Escribe tu correo y tu contraseña." };
  }

  let supabase;
  try {
    supabase = await createClient();
  } catch (error) {
    if (error instanceof MissingEnvError) {
      return {
        error:
          "La aplicación no está configurada: falta la conexión con Supabase. " +
          "Avisa a la persona que administra el sistema.",
      };
    }
    throw error;
  }

  const { error } = await supabase.auth.signInWithPassword({ email, password });

  if (error) {
    return { error: "Correo o contraseña incorrectos." };
  }

  // El shell de la app se renderiza en servidor a partir de la sesion, asi que
  // hay que invalidar su cache antes de navegar.
  revalidatePath("/", "layout");
  redirect("/dashboard");
}
