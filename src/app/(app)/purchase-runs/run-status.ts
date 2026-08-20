/**
 * Estado de una corrida y de una línea, en texto legible — mismo criterio que
 * `src/app/(app)/imports/job-status.ts`: estado SIEMPRE con etiqueta + ícono,
 * nunca solo color (checklist §10.4); funciones puras, 100% probables en Node.
 *
 * El formateo de fechas/números es genérico (no específico de importaciones),
 * así que se reusa de `job-status.ts` en vez de duplicarlo.
 */

export {
  formatBusinessDate,
  formatCount,
  formatDateTime,
  formatPeriod,
  periodDays,
} from "@/app/(app)/imports/job-status";
import type { StatusIconName, StatusTone } from "@/app/(app)/imports/job-status";

export const PURCHASE_RUN_STATUSES = ["draft", "calculated", "locked", "cancelled"] as const;
export type PurchaseRunStatus = (typeof PURCHASE_RUN_STATUSES)[number];

export const PURCHASE_RUN_LINE_STATUSES = ["ok", "no_price"] as const;
export type PurchaseRunLineStatus = (typeof PURCHASE_RUN_LINE_STATUSES)[number];

export type StatusDescription = {
  status: string;
  label: string;
  tone: StatusTone;
  icon: StatusIconName;
  description: string;
};

const RUN_STATUS_DESCRIPTIONS: Record<PurchaseRunStatus, StatusDescription> = {
  draft: {
    status: "draft",
    label: "Borrador",
    tone: "neutral",
    icon: "clock",
    description: "La corrida se está calculando.",
  },
  calculated: {
    status: "calculated",
    label: "Calculada",
    tone: "success",
    icon: "check",
    description: "La corrida terminó de calcular sus líneas. Las cantidades finales se pueden ajustar.",
  },
  locked: {
    status: "locked",
    label: "Bloqueada",
    tone: "info",
    icon: "loader",
    description: "Un admin bloqueó la corrida: sus líneas ya no se pueden ajustar.",
  },
  cancelled: {
    status: "cancelled",
    label: "Cancelada",
    tone: "danger",
    icon: "alert",
    description: "La corrida se canceló y no se usa para generar órdenes.",
  },
};

export function isPurchaseRunStatus(value: string): value is PurchaseRunStatus {
  return (PURCHASE_RUN_STATUSES as readonly string[]).includes(value);
}

/** Igual que `describeStatus` de imports: un valor fuera del enum cae en una
 * descripción neutra en vez de romper la pantalla. */
export function describeRunStatus(status: string): StatusDescription {
  if (isPurchaseRunStatus(status)) {
    return RUN_STATUS_DESCRIPTIONS[status];
  }
  return {
    status,
    label: "Estado desconocido",
    tone: "neutral",
    icon: "question",
    description:
      "Esta versión de la aplicación no reconoce el estado de esta corrida. Actualiza la página o avisa al equipo técnico.",
  };
}

/** `true` mientras la corrida admite ajustar cantidades (ni locked ni cancelled). */
export function isAdjustable(status: string): boolean {
  return status === "draft" || status === "calculated";
}

const LINE_STATUS_LABELS: Record<PurchaseRunLineStatus, string> = {
  ok: "OK",
  no_price: "Sin precio vigente",
};

/** Etiqueta corta para la columna de estado de una línea (no usa tono/ícono
 * completo como una corrida: es una marca dentro de una tabla densa). */
export function describeLineStatus(status: string): string {
  if (status === "ok" || status === "no_price") {
    return LINE_STATUS_LABELS[status];
  }
  return "Desconocido";
}
