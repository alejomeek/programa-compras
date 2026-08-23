import { ROLES, type Role } from "@/types/profile";

/**
 * Reglas de rol en el CLIENTE.
 *
 * ADVERTENCIA IMPORTANTE: estas funciones solo sirven para OCULTAR opciones de
 * la interfaz. No son un control de seguridad. La autoridad real es RLS en
 * Postgres (docs/IMPLEMENTATION_CONTRACT.md §7), que replica esta misma logica
 * con los helpers `current_role()` / `is_admin()` / `can_write()`. Ocultar un
 * enlace nunca sustituye a una politica.
 *
 * DECISION ABIERTA D5 (contrato §2 y §7): sigue sin definirse si un `buyer`
 * puede ver todos los proveedores/ordenes o si hay restriccion por persona o
 * equipo. Mientras tanto se implementa SIN restriccion y con `viewer` como rol
 * por defecto. Este modulo es el unico punto de la UI que codifica ese
 * supuesto: si D5 se cierra con restriccion (tabla `user_suppliers`), el
 * cambio en la interfaz debe quedar contenido aqui.
 */

/** Rol por defecto mientras D5 siga abierta. Coincide con el default de la columna en BD. */
export const DEFAULT_ROLE: Role = "viewer";

/** Type guard: convierte un valor desconocido de BD en un `Role` valido. */
export function isRole(value: unknown): value is Role {
  return typeof value === "string" && (ROLES as readonly string[]).includes(value);
}

/**
 * Normaliza un rol proveniente de la base de datos.
 * Un valor desconocido degrada al rol MENOS privilegiado, nunca al mayor.
 */
export function normalizeRole(value: unknown): Role {
  return isRole(value) ? value : DEFAULT_ROLE;
}

/** Administración de operaciones restringidas, como la creación de proveedores. */
export function isAdmin(role: Role): boolean {
  return role === "admin";
}

/** Puede escribir datos operativos (corridas, ajustes, ordenes). Espejo de `can_write()` en SQL. */
export function canWrite(role: Role): boolean {
  return role === "admin" || role === "buyer";
}

/** Etiqueta en espanol para mostrar el rol en la interfaz. */
export function roleLabel(role: Role): string {
  switch (role) {
    case "admin":
      return "Administrador";
    case "buyer":
      return "Comprador";
    case "viewer":
      return "Consulta";
  }
}
