"use client";

import { IssueList } from "@/components/imports/issue-list";
import { StatusIcon } from "@/components/imports/status-icon";
import { StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { importTypeLabel } from "@/app/(app)/imports/import-types";
import {
  describeStatus,
  formatCount,
  formatDateTime,
  formatPeriod,
} from "@/app/(app)/imports/job-status";
import type { ImportJobRow } from "@/app/(app)/imports/types";

/**
 * Panel de detalle de una importacion: estado, periodo detectado, conteos y
 * sus incidencias agrupadas (contrato §10.2).
 *
 * Los conteos se muestran tal como llegan: `null` significa "todavia sin
 * procesar" y se pinta como raya, no como 0 — un 0 inventado en "filas
 * rechazadas" leeria como "todo salio bien".
 */
export type ImportSummaryProps = {
  job: ImportJobRow;
};

export function ImportSummary({ job }: ImportSummaryProps) {
  const estado = describeStatus(job.status);
  const incidenciasId = `incidencias-de-${job.id}`;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex flex-wrap items-center gap-3">
          <span>{importTypeLabel(job.type)}</span>
          <StatusBadge
            label={estado.label}
            tone={estado.tone}
            icon={<StatusIcon name={estado.icon} />}
          />
        </CardTitle>
        <p className="text-sm text-muted-foreground">{estado.description}</p>
      </CardHeader>

      <CardContent className="space-y-6">
        <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <Dato termino="Proveedor" valor={job.supplierName ?? "No aplica"} />
          <Dato termino="Período detectado" valor={formatPeriod(job.periodStart, job.periodEnd)} />
          <Dato termino="Filas leídas" valor={formatCount(job.rowsTotal)} />
          <Dato termino="Filas válidas" valor={formatCount(job.rowsValid)} />
          <Dato termino="Filas rechazadas" valor={formatCount(job.rowsRejected)} />
          <Dato
            termino="Cargada / finalizada"
            valor={`${formatDateTime(job.createdAt)} · ${formatDateTime(job.finishedAt)}`}
          />
        </dl>

        {job.status === "failed" ? (
          <Alert variant="destructive">
            <AlertTitle>La importación falló y no dejó datos a medias</AlertTitle>
            <AlertDescription>
              {job.errorMessage ??
                "El servidor no reportó una causa. Vuelve a intentarlo y, si se repite, avísale al equipo técnico indicando el archivo cargado."}
            </AlertDescription>
          </Alert>
        ) : null}

        {job.status === "completed" && (job.rowsRejected ?? 0) === 0 && (job.issues?.length ?? 0) === 0 ? (
          <Alert>
            <AlertTitle>Importación completa, sin incidencias</AlertTitle>
            <AlertDescription>
              Ya puede usarse como fuente de una corrida de compra.
            </AlertDescription>
          </Alert>
        ) : null}

        <section aria-labelledby={incidenciasId} className="space-y-3">
          <h2 id={incidenciasId} className="text-sm font-semibold text-foreground">
            Incidencias
          </h2>

          {job.issues === undefined ? (
            <p className="text-sm text-muted-foreground">
              Las incidencias de esta importación aún no se han consultado.
            </p>
          ) : (
            <IssueList issues={job.issues} />
          )}
        </section>
      </CardContent>
    </Card>
  );
}

function Dato({ termino, valor }: { termino: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {termino}
      </dt>
      <dd className="mt-1 text-sm text-foreground">{valor}</dd>
    </div>
  );
}
