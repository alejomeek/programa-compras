"use client";

import { useEffect, useRef, useState } from "react";
import { PackageSearch } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
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
  "Seleccionar",
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
  selectedLineIds: ReadonlySet<string>;
  onLineSelectionChange: (lineId: string, selected: boolean) => void;
  onLinesSelectionChange: (lineIds: readonly string[], selected: boolean) => void;
  onLineAdjusted: (updated: PurchaseRunLineRow) => void;
};

export function PurchaseRunLinesTable({
  runId,
  lines,
  isLoading = false,
  adjustable,
  selectedLineIds,
  onLineSelectionChange,
  onLinesSelectionChange,
  onLineAdjusted,
}: PurchaseRunLinesTableProps) {
  const selectableLineIds = lines
    .filter((line) => line.finalQuantity > 0 && line.unitCost !== null)
    .map((line) => line.id);
  const allVisibleSelected =
    selectableLineIds.length > 0 && selectableLineIds.every((lineId) => selectedLineIds.has(lineId));
  const someVisibleSelected =
    !allVisibleSelected && selectableLineIds.some((lineId) => selectedLineIds.has(lineId));
  const selectAllRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (selectAllRef.current) selectAllRef.current.indeterminate = someVisibleSelected;
  }, [someVisibleSelected]);

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
          <TableHead scope="col">
            <label className="flex items-center gap-2">
              <input
                ref={selectAllRef}
                type="checkbox"
                className="size-4 accent-primary"
                checked={allVisibleSelected}
                disabled={!adjustable || selectableLineIds.length === 0}
                onChange={(event) => onLinesSelectionChange(selectableLineIds, event.target.checked)}
                aria-label="Seleccionar todas las líneas elegibles visibles"
              />
              <span>Seleccionar</span>
            </label>
          </TableHead>
          {COLUMNS.slice(1).map((column) => (
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
            selected={selectedLineIds.has(line.id)}
            onSelectionChange={onLineSelectionChange}
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
  selected,
  onSelectionChange,
  onLineAdjusted,
}: {
  runId: string;
  line: PurchaseRunLineRow;
  adjustable: boolean;
  selected: boolean;
  onSelectionChange: (lineId: string, selected: boolean) => void;
  onLineAdjusted: (updated: PurchaseRunLineRow) => void;
}) {
  const [quantity, setQuantity] = useState(String(line.finalQuantity));
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
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo guardar el ajuste.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <TableRow>
      <TableCell>
        <input
          type="checkbox"
          className="size-4 accent-primary"
          checked={selected}
          disabled={!adjustable || line.finalQuantity <= 0 || line.unitCost === null}
          onChange={(event) => onSelectionChange(line.id, event.target.checked)}
          aria-label={`Seleccionar ${line.productName ?? line.ean} para crear orden`}
        />
      </TableCell>
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
        {line.tbcCatalogStatus === "not_found" ? (
          <StatusBadge label="No existe en TBC" tone="warning" className="mt-1" />
        ) : null}
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
              <Button type="button" size="xs" onClick={onSave} disabled={saving}>
                {saving ? "Guardando…" : "Guardar"}
              </Button>
            ) : null}
          </div>
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
