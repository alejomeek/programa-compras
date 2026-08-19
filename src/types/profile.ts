/**
 * Tipos de `profiles` escritos a mano.
 *
 * TEMPORAL: refleja docs/IMPLEMENTATION_CONTRACT.md §6.3. Cuando `db-auth`
 * aplique la migracion `0002_profiles.sql` y existan tipos generados desde el
 * esquema real (`supabase gen types`), este archivo se reemplaza por ellos.
 * Cualquier divergencia de nombres de columna con la migracion rompe
 * `getSessionUser()` — es un acoplamiento conocido y declarado.
 */

/** Roles del contrato §6.3. El default de la columna en BD es `viewer`. */
export const ROLES = ["admin", "buyer", "viewer"] as const;

export type Role = (typeof ROLES)[number];

export type Profile = {
  /** Igual a `auth.users.id`. */
  id: string;
  full_name: string;
  role: Role;
  active: boolean;
};

/** Usuario autenticado tal como lo consume la UI. */
export type SessionUser = {
  id: string;
  email: string | null;
  profile: Profile;
};
