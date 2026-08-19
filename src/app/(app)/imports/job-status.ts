/**
 * Estado y cifras de un trabajo de importacion, en texto legible.
 *
 * El estado SIEMPRE se describe con etiqueta + icono, nunca solo con color
 * (checklist de accesibilidad §10.4). Este modulo devuelve el *nombre* del
 * icono; quien renderiza decide el componente Lucide, para que la logica
 * siga siendo pura y probable en Node.
 *
 * Las fechas de periodo (`period_start`/`period_end`) son `date` de negocio:
 * se formatean partiendo la cadena `YYYY-MM-DD`, nunca con `new Date(iso)`,
 * porque interpretar una fecha sin hora como UTC la corre un dia en Bogota
 * (contrato §6.1: los periodos van en `date` justamente para que un cambio de
 * zona horaria no mueva un periodo).
 */

export const IMPORT_STATUSES = ["pending", "processing", "completed", "failed"] as const;

export type ImportStatus = (typeof IMPORT_STATUSES)[number];

/** Tono visual. El color acompana al texto; nunca lo sustituye. */
export type StatusTone = "neutral" | "info" | "success" | "danger";

/** Nombre logico del icono; el componente lo mapea a un icono de Lucide. */
export type StatusIconName = "clock" | "loader" | "check" | "alert" | "question";

export type StatusDescription = {
  status: string;
  label: string;
  tone: StatusTone;
  icon: StatusIconName;
  /** Que significa el estado, en una frase, para el panel de detalle. */
  description: string;
};

const STATUS_DESCRIPTIONS: Record<ImportStatus, StatusDescription> = {
  pending: {
    status: "pending",
    label: "En cola",
    tone: "neutral",
    icon: "clock",
    description: "El archivo se subió y espera turno de procesamiento.",
  },
  processing: {
    status: "processing",
    label: "Procesando",
    tone: "info",
    icon: "loader",
    description: "El motor está leyendo el archivo y validando sus filas.",
  },
  completed: {
    status: "completed",
    label: "Completada",
    tone: "success",
    icon: "check",
    description: "El archivo se procesó por completo y ya puede usarse en una corrida.",
  },
  failed: {
    status: "failed",
    label: "Fallida",
    tone: "danger",
    icon: "alert",
    description:
      "El archivo no se pudo procesar y no dejó datos a medias. Corrige lo indicado y vuelve a cargarlo.",
  },
};

export function isImportStatus(value: string): value is ImportStatus {
  return (IMPORT_STATUSES as readonly string[]).includes(value);
}

/**
 * Descripcion de un estado. Un valor fuera del enum (por ejemplo, si la BD
 * gana un estado nuevo antes que la UI) no rompe la pantalla: cae en una
 * descripcion neutra y legible en vez de mostrar el valor crudo.
 */
export function describeStatus(status: string): StatusDescription {
  if (isImportStatus(status)) {
    return STATUS_DESCRIPTIONS[status];
  }
  return {
    status,
    label: "Estado desconocido",
    tone: "neutral",
    icon: "question",
    description:
      "Esta versión de la aplicación no reconoce el estado de este trabajo. Actualiza la página o avisa al equipo técnico.",
  };
}

/** `true` mientras el trabajo sigue vivo (util para invitar a actualizar). */
export function isInProgress(status: string): boolean {
  return status === "pending" || status === "processing";
}

/** Fecha `YYYY-MM-DD` a `dd/mm/aaaa`. Devuelve `null` si no parsea. */
export function formatBusinessDate(date: string | null | undefined): string | null {
  if (!date) {
    return null;
  }
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date.trim());
  if (!match) {
    return null;
  }
  const [, year, month, day] = match;
  return `${day}/${month}/${year}`;
}

/**
 * Dias del periodo, inclusivo (`fin - inicio + 1`), igual que el motor
 * (contrato §3.4). `null` si falta una fecha, no parsea o el periodo esta
 * invertido — la UI no inventa un periodo de 1 dia, que es exactamente el
 * fallback silencioso que el contrato §3.2 manda eliminar.
 */
export function periodDays(start: string | null, end: string | null): number | null {
  if (!start || !end) {
    return null;
  }
  const startMs = toUtcMs(start);
  const endMs = toUtcMs(end);
  if (startMs === null || endMs === null || endMs < startMs) {
    return null;
  }
  return Math.round((endMs - startMs) / 86_400_000) + 1;
}

function toUtcMs(date: string): number | null {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(date.trim());
  if (!match) {
    return null;
  }
  const [, year, month, day] = match;
  return Date.UTC(Number(year), Number(month) - 1, Number(day));
}

/** Periodo detectado en una linea: `01/06/2026 – 30/06/2026 · 30 días`. */
export function formatPeriod(start: string | null, end: string | null): string {
  const from = formatBusinessDate(start);
  const to = formatBusinessDate(end);

  if (!from || !to) {
    return "Sin período detectado";
  }

  const days = periodDays(start, end);
  if (days === null) {
    return `${from} – ${to} · período inválido`;
  }
  return `${from} – ${to} · ${days} ${days === 1 ? "día" : "días"}`;
}

const DATE_TIME_FORMAT = new Intl.DateTimeFormat("es-CO", {
  timeZone: "America/Bogota",
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});

/**
 * Instante ISO a `dd/mm/aaaa, hh:mm` en hora de Bogota. Se fija la zona a
 * proposito: el negocio es colombiano y asi el texto no cambia segun el reloj
 * del equipo que abra la pagina (ni entre servidor y navegador).
 */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) {
    return "—";
  }
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) {
    return "—";
  }
  return DATE_TIME_FORMAT.format(parsed);
}

/** Conteo de filas. `null` (aun sin procesar) se muestra como raya, no como 0. */
export function formatCount(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) {
    return "—";
  }
  return new Intl.NumberFormat("es-CO").format(value);
}
