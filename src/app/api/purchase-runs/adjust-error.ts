/**
 * Traduce el error de Postgres del RPC `update_final_quantity`
 * (`supabase/migrations/0014_purchase_runs.sql`) a un status HTTP y un
 * mensaje legible. Se matchea por `error.code` (el SQLSTATE que `errcode`
 * fija en el RPC), no por texto del mensaje — más robusto ante cambios de
 * redacción. Separado de `route.ts` para poder probarlo sin mockear
 * Supabase (mismo criterio que `processing-request.ts`/`calculate-request.ts`).
 */
export type PostgrestLikeError = {
  code?: string | null;
  message: string;
};

export type MappedAdjustError = {
  status: number;
  error: string;
  /** `true` solo para el conflicto de versión: la ruta relee la línea para
   * devolver el valor vigente en vez de solo el mensaje. */
  isVersionConflict: boolean;
};

export function mapAdjustError(error: PostgrestLikeError): MappedAdjustError {
  switch (error.code) {
    case "40001": // serialization_failure -> ROW_VERSION_CONFLICT
      return {
        status: 409,
        error: "La cantidad cambió desde que se cargó esta línea. Recárgala e inténtalo de nuevo.",
        isVersionConflict: true,
      };
    case "P0002": // no_data_found -> LINE_NOT_FOUND
      return { status: 404, error: "La línea no existe.", isVersionConflict: false };
    case "55000": // object_not_in_prerequisite_state -> corrida locked/cancelled
      return {
        status: 409,
        error: "La corrida está bloqueada o cancelada y no admite ajustes.",
        isVersionConflict: false,
      };
    case "42501": // insufficient_privilege -> can_write() falso
      return {
        status: 403,
        error: "Tu rol no tiene permiso para ajustar cantidades.",
        isVersionConflict: false,
      };
    case "23514": // check_violation -> cantidad negativa
      return {
        status: 400,
        error: "La cantidad final no puede ser negativa.",
        isVersionConflict: false,
      };
    default:
      return { status: 500, error: error.message, isVersionConflict: false };
  }
}
