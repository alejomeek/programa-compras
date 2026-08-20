"use client";

import Link from "next/link";
import { ClipboardList } from "lucide-react";

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
import { describeRunStatus, formatDateTime, formatPeriod } from "@/app/(app)/purchase-runs/run-status";
import type { PurchaseRunRow } from "@/app/(app)/purchase-runs/types";

/**
 * Tabla de corridas (`purchase_runs`), mirror de `ImportJobsTable`: mismos
 * estados (error/carga/vacío) y misma regla de accesibilidad (§10.4, estado
 * siempre con texto + ícono). A diferencia de las importaciones, no hay panel
 * de detalle inline: cada fila enlaza a `/purchase-runs/[id]`, que YA es el
 * detalle (no hace falta duplicarlo aquí).
 */
export type PurchaseRunsTableProps = {
  runs: readonly PurchaseRunRow[];
  isLoading?: boolean;
  errorMessage?: string | null;
};

const COLUMNS = ["Proveedor", "Estado", "Período", "Motor", "Creada", "Detalle"] as const;

export function PurchaseRunsTable({ runs, isLoading = false, errorMessage }: PurchaseRunsTableProps) {
  if (errorMessage) {
    return (
      <Alert variant="destructive">
        <AlertTitle>No se pudo cargar el historial de corridas</AlertTitle>
        <AlertDescription>{errorMessage}</AlertDescription>
      </Alert>
    );
  }

  if (isLoading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-live="polite">
        <span className="sr-only">Cargando corridas…</span>
        {[0, 1, 2].map((row) => (
          <Skeleton key={row} className="h-12 w-full" />
        ))}
      </div>
    );
  }

  if (runs.length === 0) {
    return (
      <EmptyState
        icon={<ClipboardList aria-hidden="true" className="size-6" />}
        title="Todavía no hay corridas"
        description="Crea una corrida eligiendo proveedor y fuentes: aquí aparecerá con su estado y período."
      />
    );
  }

  return (
    <Table>
      <caption className="sr-only">
        Historial de corridas de compra sugerida con su estado y período.
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
        {runs.map((run) => {
          const estado = describeRunStatus(run.status);
          return (
            <TableRow key={run.id}>
              <TableCell className="font-medium text-foreground">
                {run.supplierName ?? "—"}
              </TableCell>
              <TableCell>
                <StatusBadge
                  label={estado.label}
                  tone={estado.tone}
                  icon={<StatusIcon name={estado.icon} />}
                />
              </TableCell>
              <TableCell className="whitespace-nowrap">
                {formatPeriod(run.periodStart, run.periodEnd)}
              </TableCell>
              <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                {run.engineVersion}
              </TableCell>
              <TableCell className="whitespace-nowrap">{formatDateTime(run.createdAt)}</TableCell>
              <TableCell>
                <Button type="button" variant="outline" size="sm" asChild>
                  <Link href={`/purchase-runs/${run.id}`}>
                    Ver detalle
                    <span className="sr-only"> de la corrida de {run.supplierName ?? "proveedor"}</span>
                  </Link>
                </Button>
              </TableCell>
            </TableRow>
          );
        })}
      </TableBody>
    </Table>
  );
}
