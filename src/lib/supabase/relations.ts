/**
 * Sin tipos generados desde el esquema real (pendiente, ver `types/profile.ts`),
 * el cliente de Supabase infiere una relación embebida uno-a-uno (`fk(...)`
 * en un `select`) como si pudiera ser un arreglo. En tiempo de ejecución
 * PostgREST siempre devuelve un objeto único para una FK many-to-one — esto
 * solo normaliza el tipo para que TypeScript no lo rechace.
 */
export function embeddedOne<T>(value: T | T[] | null | undefined): T | null {
  if (Array.isArray(value)) {
    return value[0] ?? null;
  }
  return value ?? null;
}
