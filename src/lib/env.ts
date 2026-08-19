/**
 * Configuracion de entorno de la aplicacion.
 *
 * Reglas (docs/IMPLEMENTATION_CONTRACT.md §8 y runbook del equipo):
 *  - NUNCA se hardcodean ni se inventan valores: si falta una variable, la app
 *    falla con un mensaje explicito en vez de degradarse a un backend falso.
 *  - La lectura es PEREZOSA (dentro de la funcion, no en el top-level del
 *    modulo) para que `next build` pueda compilar en un entorno sin variables
 *    todavia configuradas. El fallo ocurre en tiempo de ejecucion, cuando de
 *    verdad se necesita hablar con Supabase.
 *  - Solo se exponen al navegador la URL y la publishable key (`NEXT_PUBLIC_*`).
 *    La `service_role`/`secret` jamas se lee aqui ni llega al cliente.
 */

/** Error de configuracion: distingue "la app no esta configurada" de "las credenciales del usuario son incorrectas". */
export class MissingEnvError extends Error {
  readonly variable: string;

  constructor(variable: string) {
    super(
      `Falta la variable de entorno ${variable}. ` +
        `Copia .env.example a .env.local y completa los valores del proyecto de Supabase.`,
    );
    this.name = "MissingEnvError";
    this.variable = variable;
  }
}

function requireEnv(name: string, value: string | undefined): string {
  // Se comprueba tambien la cadena vacia: una variable declarada sin valor es
  // tan inutilizable como una ausente, y falla mas tarde y peor.
  if (value === undefined || value.trim() === "") {
    throw new MissingEnvError(name);
  }
  return value;
}

export type SupabaseEnv = {
  url: string;
  publishableKey: string;
};

/**
 * Devuelve la configuracion publica de Supabase o lanza `MissingEnvError`.
 *
 * Se referencian `process.env.NEXT_PUBLIC_*` de forma literal a proposito:
 * Next.js sustituye estas expresiones en tiempo de compilacion para el bundle
 * del navegador y no puede hacerlo con acceso dinamico (`process.env[name]`).
 *
 * `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` es la clave publica del modelo nuevo
 * de API keys de Supabase (reemplaza a la `anon key`/`NEXT_PUBLIC_SUPABASE_ANON_KEY`
 * del modelo anterior). No se admite el nombre viejo: si el proyecto sigue en
 * el modelo anterior, renombra la variable en Supabase o en `.env.local`.
 */
export function getSupabaseEnv(): SupabaseEnv {
  return {
    url: requireEnv("NEXT_PUBLIC_SUPABASE_URL", process.env.NEXT_PUBLIC_SUPABASE_URL),
    publishableKey: requireEnv(
      "NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY",
      process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY,
    ),
  };
}

/** true si la app tiene configuracion de Supabase utilizable. No valida que las credenciales sirvan. */
export function isSupabaseConfigured(): boolean {
  try {
    getSupabaseEnv();
    return true;
  } catch {
    return false;
  }
}

/**
 * Nombres de las variables que faltan (nunca sus valores).
 * Sirve para mostrar un diagnostico util sin filtrar credenciales.
 */
export function missingSupabaseEnvVars(): string[] {
  const missing: string[] = [];
  if (!process.env.NEXT_PUBLIC_SUPABASE_URL?.trim()) {
    missing.push("NEXT_PUBLIC_SUPABASE_URL");
  }
  if (!process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY?.trim()) {
    missing.push("NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY");
  }
  return missing;
}
