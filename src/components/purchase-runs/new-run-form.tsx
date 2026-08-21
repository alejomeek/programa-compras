"use client";

import { useId, useRef, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SupplierOption } from "@/app/(app)/imports/types";
import { formatBusinessDate, formatPeriod } from "@/app/(app)/purchase-runs/run-status";
import type { NewRunOptions } from "@/app/(app)/purchase-runs/types";
import type { CreateRunInput } from "./purchase-runs-view";

/** Valor de opción "sin inventario de referencia" (contrato: opcional). */
const NO_INVENTORY = "__none__";

export type NewRunFormProps = {
  suppliers: readonly SupplierOption[];
  onCreateRun?: (input: CreateRunInput) => Promise<void>;
};

type Phase = "idle" | "loading-options" | "submitting" | "error";

export function NewRunForm({ suppliers, onCreateRun }: NewRunFormProps) {
  const supplierFieldId = useId();
  const salesImportFieldId = useId();
  const priceListFieldId = useId();
  const inventoryFieldId = useId();

  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [options, setOptions] = useState<NewRunOptions | null>(null);
  const [salesImportId, setSalesImportId] = useState<string | null>(null);
  const [priceListId, setPriceListId] = useState<string | null>(null);
  const [inventorySnapshotId, setInventorySnapshotId] = useState<string | null>(null);
  const [targetDaysByCode, setTargetDaysByCode] = useState<Record<string, number>>({});
  const [phase, setPhase] = useState<Phase>("idle");
  const [error, setError] = useState<string | null>(null);

  const bloqueado = !hasSuppliers(suppliers) || phase === "submitting";

  // Guarda cuál fue la ÚLTIMA selección de proveedor pedida. Si el usuario
  // cambia de proveedor dos veces rápido, la petición de la primera puede
  // resolver DESPUÉS que la de la segunda (orden de red, no de clics) y
  // pisar sus opciones — mostrando una lista de precios de otro proveedor
  // bajo el nombre del proveedor que sí quedó seleccionado. Cualquier
  // respuesta que no sea la del proveedor vigente se descarta.
  const latestSupplierRequestRef = useRef<string | null>(null);

  async function onSupplierChange(next: string) {
    latestSupplierRequestRef.current = next;
    setSupplierId(next);
    setOptions(null);
    setSalesImportId(null);
    setPriceListId(null);
    setInventorySnapshotId(null);
    setTargetDaysByCode({});
    setError(null);
    setPhase("loading-options");

    try {
      const response = await fetch(`/api/purchase-runs/new-run-options?supplierId=${next}`);
      const body = await response.json().catch(() => ({}) as { error?: string });
      if (latestSupplierRequestRef.current !== next) return; // ya no es la selección vigente
      if (!response.ok) {
        throw new Error((body as { error?: string }).error ?? "No se pudieron cargar las fuentes.");
      }
      const loaded = body as NewRunOptions;
      setOptions(loaded);
      setTargetDaysByCode(
        Object.fromEntries(
          loaded.operativeLocations.map((loc) => [loc.code, loaded.defaultTargetDays]),
        ),
      );
      setPhase("idle");
    } catch (cause) {
      if (latestSupplierRequestRef.current !== next) return;
      setError(cause instanceof Error ? cause.message : "No se pudieron cargar las fuentes.");
      setPhase("error");
    }
  }

  const puedeCrear = Boolean(supplierId && salesImportId && priceListId && options);

  async function onSubmit() {
    if (!supplierId || !salesImportId || !priceListId || !onCreateRun) return;

    setPhase("submitting");
    setError(null);
    try {
      await onCreateRun({
        supplierId,
        salesImportId,
        priceListId,
        inventorySnapshotId: inventorySnapshotId === NO_INVENTORY ? null : inventorySnapshotId,
        targetDays: targetDaysByCode,
      });
      // En éxito, la página navega al detalle (ver purchase-runs-page-client.tsx):
      // no hace falta resetear el formulario aquí.
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo crear la corrida.");
      setPhase("error");
    }
  }

  return (
    <div className="space-y-6">
      <div className="max-w-sm space-y-2">
        <Label htmlFor={supplierFieldId}>Proveedor</Label>
        <Select
          value={supplierId ?? undefined}
          onValueChange={onSupplierChange}
          disabled={bloqueado}
        >
          <SelectTrigger id={supplierFieldId} className="w-full">
            <SelectValue placeholder="Elige un proveedor" />
          </SelectTrigger>
          <SelectContent>
            {suppliers.map((supplier) => (
              <SelectItem key={supplier.id} value={supplier.id}>
                {supplier.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {phase === "loading-options" ? (
        <p className="text-sm text-muted-foreground">Cargando fuentes disponibles…</p>
      ) : null}

      {options ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <div className="space-y-2">
              <Label htmlFor={salesImportFieldId}>Importación de ventas</Label>
              <Select value={salesImportId ?? undefined} onValueChange={setSalesImportId}>
                <SelectTrigger id={salesImportFieldId} className="w-full">
                  <SelectValue placeholder="Elige un período" />
                </SelectTrigger>
                <SelectContent>
                  {options.salesImports.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {formatPeriod(item.periodStart, item.periodEnd)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {options.salesImports.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No hay importaciones de ventas vigentes.
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor={priceListFieldId}>Lista de precios</Label>
              <Select value={priceListId ?? undefined} onValueChange={setPriceListId}>
                <SelectTrigger id={priceListFieldId} className="w-full">
                  <SelectValue placeholder="Elige una lista" />
                </SelectTrigger>
                <SelectContent>
                  {options.priceLists.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      v{item.version} · vigente desde {formatBusinessDate(item.effectiveDate)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {options.priceLists.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  Este proveedor no tiene una lista de precios vigente.
                </p>
              ) : null}
            </div>

            <div className="space-y-2">
              <Label htmlFor={inventoryFieldId}>Inventario de referencia (opcional)</Label>
              <Select
                value={inventorySnapshotId ?? undefined}
                onValueChange={setInventorySnapshotId}
              >
                <SelectTrigger id={inventoryFieldId} className="w-full">
                  <SelectValue placeholder="Sin inventario de referencia" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NO_INVENTORY}>Sin inventario de referencia</SelectItem>
                  {options.inventorySnapshots.map((item) => (
                    <SelectItem key={item.id} value={item.id}>
                      {formatBusinessDate(item.snapshotDate)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <fieldset className="space-y-3">
            <legend className="text-sm font-medium text-foreground">
              Días objetivo por ubicación
            </legend>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              {options.operativeLocations.map((location) => {
                const fieldId = `${inventoryFieldId}-${location.code}`;
                return (
                  <div key={location.code} className="space-y-1">
                    <Label htmlFor={fieldId} className="text-xs">
                      {location.name}
                    </Label>
                    <Input
                      id={fieldId}
                      type="number"
                      min={1}
                      value={targetDaysByCode[location.code] ?? options.defaultTargetDays}
                      onChange={(event) =>
                        setTargetDaysByCode((previous) => ({
                          ...previous,
                          [location.code]: Number(event.target.value) || 1,
                        }))
                      }
                    />
                  </div>
                );
              })}
            </div>
          </fieldset>
        </div>
      ) : null}

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>No se pudo crear la corrida</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="button" onClick={onSubmit} disabled={!puedeCrear || phase === "submitting"}>
        {phase === "submitting" ? "Calculando…" : "Calcular corrida"}
      </Button>
    </div>
  );
}

function hasSuppliers(suppliers: readonly SupplierOption[]): boolean {
  return suppliers.length > 0;
}
