/**
 * Incidencias de una importacion: agrupacion y redaccion.
 *
 * Regla del contrato §10.4: "errores de importación con causa y acción
 * concreta, no códigos crudos". Por eso cada codigo de `import_issues.code`
 * (§6.3) tiene aqui un titulo y una accion en español; el `detail` que manda
 * el motor se muestra por fila, como evidencia, no como el mensaje principal.
 *
 * Modulo de logica pura, sin React.
 */

import type { ImportIssueRow } from "./types";

export const ISSUE_CODES = [
  "ean_invalido",
  "ean_duplicado",
  "costo_invalido",
  "comodin_invalido",
  "fecha_invalida",
  "tisuc_desconocido",
] as const;

export type IssueCode = (typeof ISSUE_CODES)[number];

export type IssueSeverity = "error" | "warning" | "info";

export type IssueCopy = {
  /** Titulo del grupo, legible. Nunca el codigo crudo. */
  title: string;
  /** Que hacer para resolverlo, en imperativo. */
  action: string;
};

const ISSUE_COPY: Record<IssueCode, IssueCopy> = {
  ean_invalido: {
    title: "EAN inválido",
    action:
      "El código de barras está vacío, tiene espacios o trae caracteres que no son dígitos. Corrige esas filas en el archivo de origen y vuelve a cargarlo: esos productos quedan fuera del cruce.",
  },
  ean_duplicado: {
    title: "EAN duplicado",
    action:
      "El mismo EAN aparece en varias filas del archivo. Se excluyen todas sus copias del cruce automático, no solo las repetidas. Deja una sola fila por EAN y vuelve a cargarlo.",
  },
  costo_invalido: {
    title: "Costo ilegible",
    action:
      "El costo no se pudo leer como número. Revisa esas celdas: los miles van con punto y los decimales con coma (45.900 o 1.234,56); quita textos y símbolos sobrantes.",
  },
  comodin_invalido: {
    title: "Comodín inválido",
    action:
      "El comodín debe empezar con punto y traer al menos tres dígitos (por ejemplo .745). Corrígelo en el archivo de origen; sin comodín válido el producto no se asigna al proveedor.",
  },
  fecha_invalida: {
    title: "Período no legible",
    action:
      "No se pudieron leer FDESDE/FHASTA, o la fecha final es anterior a la inicial. La importación se bloquea a propósito: sin período válido la cantidad sugerida se calcularía sobre un solo día y saldría inflada. Corrige las fechas del archivo y vuelve a cargarlo.",
  },
  tisuc_desconocido: {
    title: "Punto de venta desconocido",
    action:
      "El archivo trae un código de ubicación (TISUC) que no está en el catálogo, así que sus unidades no se sumaron a ningún punto. Pide al responsable de los datos que valide la ubicación, o confirma que debe ignorarse.",
  },
};

export function isIssueCode(value: string): value is IssueCode {
  return (ISSUE_CODES as readonly string[]).includes(value);
}

/**
 * Titulo y accion de un codigo. Un codigo que la UI todavia no conoce cae en
 * un texto legible (el codigo humanizado) en vez de mostrarse crudo.
 */
export function issueCopy(code: string): IssueCopy {
  if (isIssueCode(code)) {
    return ISSUE_COPY[code];
  }
  return {
    title: humanizeCode(code),
    action:
      "Esta versión de la aplicación no conoce esta incidencia. Revisa el detalle de cada fila y, si se repite, avísale al equipo técnico indicando el archivo cargado.",
  };
}

/** `tisuc_desconocido` → `Tisuc desconocido`. Nunca deja el codigo tal cual. */
function humanizeCode(code: string): string {
  const clean = code.replace(/[_-]+/g, " ").trim();
  if (clean.length === 0) {
    return "Incidencia sin clasificar";
  }
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

const SEVERITY_ORDER: Record<IssueSeverity, number> = { error: 0, warning: 1, info: 2 };

export function normalizeSeverity(severity: string): IssueSeverity {
  const value = severity.trim().toLowerCase();
  if (value === "error" || value === "warning" || value === "info") {
    return value;
  }
  // Un valor desconocido se trata como error: es mas seguro sobre-avisar que
  // esconder una incidencia que podria estar bloqueando la importacion.
  return "error";
}

export type IssueGroup = {
  code: string;
  title: string;
  action: string;
  /** La mas grave del grupo. */
  severity: IssueSeverity;
  count: number;
  /** Id de ancla para el resumen navegable (§10.4). */
  anchorId: string;
  issues: ImportIssueRow[];
};

/**
 * Agrupa las incidencias por codigo. Orden: primero las mas graves, luego las
 * mas numerosas, y a igualdad por codigo (orden estable y reproducible).
 * Dentro de cada grupo se conserva el orden de fila del archivo.
 */
export function groupIssuesByCode(issues: readonly ImportIssueRow[]): IssueGroup[] {
  const groups = new Map<string, IssueGroup>();

  for (const issue of issues) {
    const severity = normalizeSeverity(issue.severity);
    const existing = groups.get(issue.code);

    if (existing) {
      existing.issues.push(issue);
      existing.count += 1;
      if (SEVERITY_ORDER[severity] < SEVERITY_ORDER[existing.severity]) {
        existing.severity = severity;
      }
      continue;
    }

    const copy = issueCopy(issue.code);
    groups.set(issue.code, {
      code: issue.code,
      title: copy.title,
      action: copy.action,
      severity,
      count: 1,
      anchorId: anchorIdForCode(issue.code),
      issues: [issue],
    });
  }

  for (const group of groups.values()) {
    group.issues.sort(byRowNumber);
  }

  return [...groups.values()].sort((a, b) => {
    const bySeverity = SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity];
    if (bySeverity !== 0) {
      return bySeverity;
    }
    if (a.count !== b.count) {
      return b.count - a.count;
    }
    return a.code.localeCompare(b.code, "es");
  });
}

/** Las filas sin numero van al final: no se inventa un 0 para ordenarlas. */
function byRowNumber(a: ImportIssueRow, b: ImportIssueRow): number {
  if (a.rowNumber === null && b.rowNumber === null) {
    return 0;
  }
  if (a.rowNumber === null) {
    return 1;
  }
  if (b.rowNumber === null) {
    return -1;
  }
  return a.rowNumber - b.rowNumber;
}

/** Ancla estable y valida como id de HTML para enlazar desde el resumen. */
export function anchorIdForCode(code: string): string {
  const slug = code
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return `incidencias-${slug === "" ? "sin-codigo" : slug}`;
}

/** Resumen en una frase para el encabezado del panel: "3 errores y 1 aviso". */
export function summarizeIssues(issues: readonly ImportIssueRow[]): string {
  if (issues.length === 0) {
    return "Sin incidencias.";
  }

  let errors = 0;
  let warnings = 0;
  let infos = 0;
  for (const issue of issues) {
    const severity = normalizeSeverity(issue.severity);
    if (severity === "error") errors += 1;
    else if (severity === "warning") warnings += 1;
    else infos += 1;
  }

  const parts: string[] = [];
  if (errors > 0) parts.push(`${errors} ${errors === 1 ? "error" : "errores"}`);
  if (warnings > 0) parts.push(`${warnings} ${warnings === 1 ? "aviso" : "avisos"}`);
  if (infos > 0) parts.push(`${infos} ${infos === 1 ? "nota" : "notas"}`);

  if (parts.length === 1) {
    return `${parts[0]}.`;
  }
  return `${parts.slice(0, -1).join(", ")} y ${parts[parts.length - 1]}.`;
}
