"use client";

import { Inbox } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { StatusIcon } from "@/components/imports/status-icon";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { importTypeLabel } from "@/app/(app)/imports/import-types";
import {
  describeStatus,
  formatCount,
  formatDateTime,
  formatPeriod,
} from "@/app/(app)/imports/job-status";
import type { ImportJobRow } from "@/app/(app)/imports/types";
import { cn } from "@/lib/utils";

/**
 * Tabla de trabajos de importacion (`import_jobs`).
 *
 * Presentacional: recibe las filas ya resueltas por props (el DTO camelCase
 * acordado con el lead) y no sabe de donde salen. Sin polling ni realtime en
 * la Fase 2: la lista se refresca con el boton "Actualizar" de la vista.
 *
 * Accesibilidad (§10.4): `scope="col"` en cada encabezado, estado con texto +
 * icono (nunca solo color), y el desplazamiento horizontal ocurre dentro del
 * contenedor de la tabla, no en el `body`.
 */
export type ImportJobsTableProps = {
  jobs: readonly ImportJobRow[];
  isLoading?: boolean;
  /** Mensaje de error de carga, ya redactado para una persona. */
  errorMessage?: string | null;
  selectedJobId?: string | null;
  onSelectJob?: (jobId: string) => void;
};

const COLUMNS = [
  "Importación",
  "Estado",
  "Período detectado",
  "Filas",
  "Cargada",
  "Detalle",
] as const;

export function ImportJobsTable({
  jobs,
  isLoading = false,
  errorMessage,
  selectedJobId,
  onSelectJob,
}: ImportJobsTableProps) {
  if (errorMessage) {
    return (
      <Alert variant="destructive">
        <AlertTitle>No se pudo cargar el historial de importaciones</AlertTitle>
        <AlertDescription>{errorMessage}</AlertDescription>
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-live="polite">
        <span className="sr-only">Cargando importaciones…</span>
        {[0, 1, 2].map((row) => (
          <Skeleton key={row} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <EmptyState
        icon={<Inbox aria-hidden="true" className="size-6" />}
        title="Todavía no hay importaciones"
        description="Cuando subas un archivo de ventas, de inventario o una lista de precios, aparecerá aquí con su estado, el período detectado y sus incidencias."
      />
    );
  }

  return (
    <Table>
      <caption className="sr-only">
        Historial de importaciones con su estado, período detectado y conteo de filas.
      </caption>
      <TableHeader>
        <TableRow>
          {COLUMNS.map((column) => (
            <TableHead key={column} scope="col">
              {column}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {jobs.map((job) => {
          const estado = describeStatus(job.status);
          const seleccionada = job.id === selectedJobId;

          return (
            <TableRow
              key={job.id}
              className={cn(seleccionada && "bg-accent/50")}
            >
              <TableCell>
                <span className="font-medium text-foreground">{importTypeLabel(job.type)}</span>
                {job.supplierName ? (
                  <span className="block text-xs text-muted-foreground">{job.supplierName}</span>
                ) : null}
              </TableCell>

              <TableCell>
                <StatusBadge
                  label={estado.label}
                  tone={estado.tone}
                  icon={<StatusIcon name={estado.icon} />}
                />
              </TableCell>

              <TableCell className="whitespace-nowrap">
                {formatPeriod(job.periodStart, job.periodEnd)}
              </TableCell>

              <TableCell>
                <span className="whitespace-nowrap">
                  {formatCount(job.rowsValid)} válidas de {formatCount(job.rowsTotal)}
                </span>
                <span
                  className={cn(
                    "block text-xs",
                    job.rowsRejected && job.rowsRejected > 0
                      ? "text-destructive"
                      : "text-muted-foreground",
                  )}
                >
                  {formatCount(job.rowsRejected)} rechazadas
                </span>
              </TableCell>

              <TableCell className="whitespace-nowrap">{formatDateTime(job.createdAt)}</TableCell>

              <TableCell>
                <Button
                  type="button"
                  variant={seleccionada ? "secondary" : "outline"}
                  size="sm"
                  onClick={() => onSelectJob?.(job.id)}
                  aria-pressed={seleccionada}
                >
                  {seleccionada ? "Viendo detalle" : "Ver detalle"}
                  <span className="sr-only">
                    {" "}
                    de la importación de {importTypeLabel(job.type)} del{" "}
                    {formatDateTime(job.createdAt)}
                  </span>
                </Button>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
