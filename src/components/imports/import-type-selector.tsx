"use client";

import { useId } from "react";

import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  IMPORT_TYPE_DEFINITIONS,
  importTypeDefinition,
  type ImportType,
} from "@/app/(app)/imports/import-types";
import type { SupplierOption } from "@/app/(app)/imports/types";
import { cn } from "@/lib/utils";

/**
 * Selector de tipo de importacion y, cuando aplica, de proveedor.
 *
 * Accesibilidad (§10.4):
 *  - Los tres tipos son radios NATIVOS dentro de un `<fieldset>` con `<legend>`:
 *    se recorren con flechas y el lector anuncia "1 de 3" sin ARIA a mano.
 *  - Cada radio tiene `<label>` real y su descripcion enlazada con
 *    `aria-describedby` (la descripcion no es el label).
 *  - El error del proveedor va junto al campo, con `aria-invalid` y
 *    `aria-describedby`, nunca como toast suelto.
 *
 * Componente presentacional: no decide nada, avisa hacia arriba.
 */
export type ImportTypeSelectorProps = {
  value: ImportType;
  onChange: (type: ImportType) => void;
  suppliers: readonly SupplierOption[];
  supplierId: string | null;
  onSupplierChange: (supplierId: string | null) => void;
  /** Error de proveedor a mostrar junto al campo. */
  supplierError?: string | null;
  disabled?: boolean;
};

export function ImportTypeSelector({
  value,
  onChange,
  suppliers,
  supplierId,
  onSupplierChange,
  supplierError,
  disabled = false,
}: ImportTypeSelectorProps) {
  const groupName = useId();
  const supplierFieldId = useId();
  const supplierErrorId = `${supplierFieldId}-error`;
  const supplierHintId = `${supplierFieldId}-hint`;

  const requiresSupplier = importTypeDefinition(value).requiresSupplier;
  const sinProveedores = suppliers.length === 0;

  return (
    <div className="space-y-5">
      <fieldset className="space-y-3" disabled={disabled}>
        <legend className="text-sm font-medium text-foreground">Tipo de importación</legend>

        <div className="grid gap-3 md:grid-cols-3">
          {IMPORT_TYPE_DEFINITIONS.map((definition) => {
            const inputId = `${groupName}-${definition.value}`;
            const descriptionId = `${inputId}-descripcion`;
            const checked = definition.value === value;

            return (
              <div
                key={definition.value}
                className={cn(
                  "relative rounded-lg border bg-card p-4 transition-colors",
                  checked ? "border-primary ring-1 ring-primary" : "border-border hover:bg-accent/40",
                  disabled && "opacity-60",
                )}
              >
                <div className="flex items-start gap-3">
                  <input
                    type="radio"
                    id={inputId}
                    name={groupName}
                    value={definition.value}
                    checked={checked}
                    onChange={() => onChange(definition.value)}
                    aria-describedby={descriptionId}
                    className="mt-1 size-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                  />
                  <div className="space-y-1">
                    <Label htmlFor={inputId} className="block cursor-pointer text-sm font-semibold">
                      {definition.label}
                    </Label>
                    <p id={descriptionId} className="text-xs leading-relaxed text-muted-foreground">
                      <span className="font-medium text-foreground">{definition.sourceName}</span>{" "}
                      · {definition.description} Formato aceptado:{" "}
                      {definition.extensions.join(" o ")}.
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </fieldset>

      {requiresSupplier ? (
        <div className="max-w-sm space-y-2">
          <Label htmlFor={supplierFieldId}>
            Proveedor de la lista <span aria-hidden="true">*</span>
            <span className="sr-only">(obligatorio)</span>
          </Label>

          <Select
            value={supplierId ?? undefined}
            onValueChange={(next) => onSupplierChange(next)}
            disabled={disabled || sinProveedores}
          >
            <SelectTrigger
              id={supplierFieldId}
              className="w-full"
              aria-invalid={supplierError ? true : undefined}
              aria-describedby={
                [supplierError ? supplierErrorId : null, sinProveedores ? supplierHintId : null]
                  .filter(Boolean)
                  .join(" ") || undefined
              }
            >
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

          {sinProveedores ? (
            <p id={supplierHintId} className="text-xs text-muted-foreground">
              Todavía no hay proveedores cargados. Créalos en Proveedores antes de subir una lista
              de precios.
            </p>
          ) : null}

          {supplierError ? (
            <p id={supplierErrorId} role="alert" className="text-sm font-medium text-destructive">
              {supplierError}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
