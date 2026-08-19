import { createBrowserClient } from "@supabase/ssr";

import { getSupabaseEnv } from "@/lib/env";

/**
 * Cliente de Supabase para el NAVEGADOR (Client Components).
 *
 * Usa exclusivamente la anon key publica; toda autorizacion real la impone RLS
 * en Postgres (docs/IMPLEMENTATION_CONTRACT.md §7), nunca este cliente.
 *
 * Se crea bajo demanda, no en el top-level del modulo, para que un bundle
 * compilado sin variables de entorno no explote al importarse.
 */
export function createClient() {
  const { url, anonKey } = getSupabaseEnv();
  return createBrowserClient(url, anonKey);
}
