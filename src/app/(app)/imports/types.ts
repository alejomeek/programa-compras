/**
 * Formas de datos que consume la pantalla `/imports`.
 *
 * Son DTO en camelCase acordados con el lead, NO las columnas crudas de
 * `import_jobs`/`import_issues`: el Server Component resuelve el join de
 * proveedor y renombra antes de pasar los datos. Los componentes de esta
 * pantalla son presentacionales y no saben de donde salen.
 *
 * `ean`, `sku` y `productName` viajan siempre como `string`: un EAN nunca pasa
 * por `number` en ninguna capa (contrato §9.6), o se pierden los ceros
 * iniciales del 9% del catalogo real.
 */

import type { ImportType } from "./import-types";
import type { ImportStatus } from "./job-status";

export type SupplierOption = {
  id: string;
  name: string;
};

export type ImportIssueRow = {
  id: string;
  /** `error` bloquea la importacion; `warning`/`info` solo informan. */
  severity: string;
  /** Codigo del enum de `import_issues.code` (contrato §6.3). */
  code: string;
  /** Archivo/fuente que origino la incidencia (`INVEPTOS.XLS`, etc.). */
  source: string | null;
  rowNumber: number | null;
  ean: string | null;
  sku: string | null;
  productName: string | null;
  detail: string | null;
};

export type ImportJobRow = {
  id: string;
  type: ImportType;
  status: ImportStatus;
  supplierName: string | null;
  /** Fecha ISO `YYYY-MM-DD`, sin hora: es un periodo de negocio, no un instante. */
  periodStart: string | null;
  periodEnd: string | null;
  rowsTotal: number | null;
  rowsValid: number | null;
  rowsRejected: number | null;
  errorMessage: string | null;
  /** ISO datetime. */
  createdAt: string;
  finishedAt: string | null;
  /**
   * Incidencias del trabajo, si el servidor ya las trajo. `undefined` significa
   * "no cargadas todavia", distinto de `[]` que significa "sin incidencias".
   */
  issues?: ImportIssueRow[];
};
