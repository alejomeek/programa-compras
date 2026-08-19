"use client";

import { AlertTriangle, CheckCircle2, CircleX, Info } from "lucide-react";

import { StatusBadge, type StatusTone } from "@/components/status-badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  groupIssuesByCode,
  summarizeIssues,
  type IssueSeverity,
} from "@/app/(app)/imports/issues";
import type { ImportIssueRow } from "@/app/(app)/imports/types";

/**
 * Incidencias de una importacion, agrupadas por codigo.
 *
 * Cada grupo encabeza con el problema en español y la accion concreta para
 * resolverlo (§10.4: "causa y acción concreta, no códigos crudos"); el
 * `detail` que manda el motor aparece por fila, como evidencia.
 *
 * El resumen de arriba es navegable: enlaza a cada grupo por ancla, que es lo
 * que pide el checklist para poder saltar a las filas problematicas.
 */
export type IssueListProps = {
  issues: readonly ImportIssueRow[];
};

const SEVERITY_TONE: Record<IssueSeverity, StatusTone> = {
  error: "danger",
  warning: "warning",
  info: "info",
};

const SEVERITY_LABEL: Record<IssueSeverity, string> = {
  error: "Error",
  warning: "Aviso",
  info: "Nota",
};

function SeverityIcon({ severity }: { severity: IssueSeverity }) {
  if (severity === "error") {
    return <CircleX aria-hidden="true" className="size-3.5" />;
  }
  if (severity === "warning") {
    return <AlertTriangle aria-hidden="true" className="size-3.5" />;
  }
  return <Info aria-hidden="true" className="size-3.5" />;
}

export function IssueList({ issues }: IssueListProps) {
  if (issues.length === 0) {
    return (
      <p className="flex items-center gap-2 text-sm text-foreground">
        <CheckCircle2 aria-hidden="true" className="size-4 text-emerald-700" />
        Sin incidencias: todas las filas del archivo se procesaron.
      </p>
    );
  }

  const grupos = groupIssuesByCode(issues);

  return (
    <div className="space-y-6">
      <nav aria-label="Resumen de incidencias" className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm font-medium text-foreground">{summarizeIssues(issues)}</p>
        <ul className="mt-2 space-y-1">
          {grupos.map((grupo) => (
            <li key={grupo.code} className="text-sm">
              <a
                href={`#${grupo.anchorId}`}
                className="rounded-sm text-primary underline underline-offset-4 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
              >
                {grupo.title}
              </a>{" "}
              <span className="text-muted-foreground">
                — {grupo.count} {grupo.count === 1 ? "fila" : "filas"} ·{" "}
                {SEVERITY_LABEL[grupo.severity]}
              </span>
            </li>
          ))}
        </ul>
      </nav>

      {grupos.map((grupo) => {
        const encabezadoId = `${grupo.anchorId}-titulo`;

        return (
          <section
            key={grupo.code}
            id={grupo.anchorId}
            aria-labelledby={encabezadoId}
            className="scroll-mt-4 space-y-3 rounded-lg border border-border bg-card p-4"
          >
            <div className="flex flex-wrap items-center gap-3">
              <h3 id={encabezadoId} className="text-sm font-semibold text-foreground">
                {grupo.title}
              </h3>
              <StatusBadge
                label={`${SEVERITY_LABEL[grupo.severity]} · ${grupo.count} ${
                  grupo.count === 1 ? "fila" : "filas"
                }`}
                tone={SEVERITY_TONE[grupo.severity]}
                icon={<SeverityIcon severity={grupo.severity} />}
              />
            </div>

            <p className="max-w-3xl text-sm text-muted-foreground">{grupo.action}</p>

            <Table>
              <caption className="sr-only">Filas afectadas por: {grupo.title}</caption>
              <TableHeader>
                <TableRow>
                  <TableHead scope="col">Fila</TableHead>
                  <TableHead scope="col">EAN</TableHead>
                  <TableHead scope="col">SKU</TableHead>
                  <TableHead scope="col">Producto</TableHead>
                  <TableHead scope="col">Detalle</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {grupo.issues.map((issue) => (
                  <TableRow key={issue.id}>
                    <TableCell className="whitespace-nowrap tabular-nums">
                      {issue.rowNumber ?? "—"}
                    </TableCell>
                    {/* El EAN es texto exacto: nunca se formatea como numero. */}
                    <TableCell className="font-mono text-xs">{issue.ean ?? "—"}</TableCell>
                    <TableCell className="font-mono text-xs">{issue.sku ?? "—"}</TableCell>
                    <TableCell>{issue.productName ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {issue.detail ?? "—"}
                      {issue.source ? (
                        <span className="block text-xs">Origen: {issue.source}</span>
                      ) : null}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </section>
        );
      })}
    </div>
  );
}
