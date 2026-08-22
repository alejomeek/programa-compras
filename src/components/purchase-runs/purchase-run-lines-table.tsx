"use client";

import { useState } from "react";
import { PackageSearch } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { describeLineStatus } from "@/app/(app)/purchase-runs/run-status";
import type { PurchaseRunLineRow } from "@/app/(app)/purchase-runs/types";
import { cn } from "@/lib/utils";

const COLUMNS = [
  "Producto / EAN",
  "Ubicación",
  "Ventas",
  "Sugerida",
  "Stock (ref.)",
  "Costo",
  "Estado",
  "Cantidad final",
] as const;

export type PurchaseRunLinesTableProps = {
  runId: string;
  lines: readonly PurchaseRunLineRow[];
  isLoading?: boolean;
  adjustable: boolean;
  onLineAdjusted: (updated: PurchaseRunLineRow) => void;
};

export function PurchaseRunLinesTable({
  runId,
  lines,
  isLoading = false,
  adjustable,
  onLineAdjusted,
}: PurchaseRunLinesTableProps) {
  if (isLoading) {
    return (
      <div className="space-y-2" aria-busy="true" aria-live="polite">
        <span className="sr-only">Cargando líneas…</span>
        {[0, 1, 2, 3].map((row) => (
          <Skeleton key={row} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (lines.length === 0) {
    return (
      <EmptyState
        icon={<PackageSearch aria-hidden="true" className="size-6" />}
        title="Sin líneas para estos filtros"
        description="Prueba a quitar algún filtro o busca por otro EAN."
      />
    );
  }

  return (
    <Table>
      <caption className="sr-only">
        Líneas de la corrida: ventas, sugerencia, referencia de stock y cantidad final por
        producto y ubicación.
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
        {lines.map((line) => (
          <LineRow
            key={line.id}
            runId={runId}
            line={line}
            adjustable={adjustable}
            onLineAdjusted={onLineAdjusted}
          />
        ))}
      </TableBody>
    </Table>
  );
}

function LineRow({
  runId,
  line,
  adjustable,
  onLineAdjusted,
}: {
  runId: string;
  line: PurchaseRunLineRow;
  adjustable: boolean;
  onLineAdjusted: (updated: PurchaseRunLineRow) => void;
}) {
  const [quantity, setQuantity] = useState(String(line.finalQuantity));
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isDirty = Number(quantity) !== line.finalQuantity && quantity.trim() !== "";

  async function onSave() {
    const newQuantity = Number(quantity);
    if (!Number.isFinite(newQuantity) || newQuantity < 0) {
      setError("La cantidad debe ser un número mayor o igual a 0.");
      return;
    }

    setSaving(true);
    setError(null);
    try {
      const response = await fetch(`/api/purchase-runs/${runId}/lines/${line.id}/adjust`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          newQuantity,
          expectedRowVersion: line.rowVersion,
          reason: reason.trim() || undefined,
        }),
      });
      const body = await response.json().catch(() => ({}) as Record<string, unknown>);
      if (!response.ok) {
        const current = (body as { current?: { finalQuantity: number; rowVersion: number } }).current;
        if (current) {
          // Conflicto de versión: se acepta el valor vigente del servidor en
          // vez de sobrescribirlo en silencio — el contrato §9 lo exige.
          onLineAdjusted({ ...line, finalQuantity: current.finalQuantity, rowVersion: current.rowVersion });
          setQuantity(String(current.finalQuantity));
        }
        throw new Error((body as { error?: string }).error ?? "No se pudo guardar el ajuste.");
      }
      const updated = (body as { line: { id: string; finalQuantity: number; rowVersion: number; updatedAt: string; note: string | null } }).line;
      onLineAdjusted({
        ...line,
        finalQuantity: updated.finalQuantity,
        rowVersion: updated.rowVersion,
        updatedAt: updated.updatedAt,
        note: updated.note,
      });
      setQuantity(String(updated.finalQuantity));
      setReason("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar el ajuste.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <TableRow>
      <TableCell>
        {line.productName ? (
          <span className="font-medium text-foreground">{line.productName}</span>
        ) : null}
        <span
          className={cn(
            "block text-xs",
            line.productName ? "text-muted-foreground" : "font-medium text-foreground",
          )}
        >
          {line.ean}
        </span>
      </TableCell>
      <TableCell className="whitespace-nowrap">{line.locationName}</TableCell>
      <TableCell className="whitespace-nowrap">{line.salesUnits}</TableCell>
      <TableCell className="whitespace-nowrap font-medium text-foreground">
        {line.suggestedQuantity}
      </TableCell>
      <TableCell className="whitespace-nowrap text-muted-foreground">
        {line.stockReference ?? "—"}
      </TableCell>
      <TableCell className="whitespace-nowrap">
        {line.unitCost ?? "—"}
      </TableCell>
      <TableCell>
        <span className={cn("text-xs", line.status === "no_price" && "text-destructive")}>
          {describeLineStatus(line.status)}
        </span>
      </TableCell>
      <TableCell>
        <div className="flex min-w-48 flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <Input
              type="number"
              min={0}
              value={quantity}
              disabled={!adjustable || saving}
              onChange={(event) => setQuantity(event.target.value)}
              className="h-8 w-24"
              aria-label={`Cantidad final para ${line.ean} en ${line.locationName}`}
            />
            {isDirty ? (
              <Input
                value={reason}
                disabled={saving}
                onChange={(event) => setReason(event.target.value)}
                placeholder="Motivo (opcional)"
                className="h-8"
                aria-label={`Motivo del ajuste de ${line.ean} en ${line.locationName}`}
              />
            ) : null}
          </div>
          {isDirty ? (
            <Button type="button" size="xs" onClick={onSave} disabled={saving}>
              {saving ? "Guardando…" : "Guardar"}
            </Button>
          ) : null}
          {error ? (
            <Alert variant="destructive" className="px-2 py-1.5">
              <AlertTitle className="text-xs">No se guardó</AlertTitle>
              <AlertDescription className="text-xs">{error}</AlertDescription>
            </Alert>
          ) : null}
        </div>
      </TableCell>
    </TableRow>
  );
}
