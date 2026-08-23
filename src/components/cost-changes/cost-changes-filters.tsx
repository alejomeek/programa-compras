import Form from "next/form";
import Link from "next/link";

import { Button } from "@/components/ui/button";

export type CostChangeSupplierOption = {
  id: string;
  name: string;
};

export type CostChangeSourceOption = {
  id: string;
  label: string;
};

type CostChangesFiltersProps = {
  suppliers: readonly CostChangeSupplierOption[];
  tbcSources: readonly CostChangeSourceOption[];
  selectedSupplierId: string | null;
  selectedTbcSourceId: string | null;
};

/**
 * La lista de precios activa es única por proveedor. Por eso el segundo
 * filtro es la fuente que realmente puede variar entre EANs: la importación
 * TBC que aportó el último costo de comparación.
 */
export function CostChangesFilters({
  suppliers,
  tbcSources,
  selectedSupplierId,
  selectedTbcSourceId,
}: CostChangesFiltersProps) {
  const hasFilters = selectedSupplierId !== null || selectedTbcSourceId !== null;

  return (
    <Form action="/cost-changes" className="flex flex-wrap items-end gap-3">
      <label className="grid gap-1.5 text-sm font-medium text-foreground">
        Proveedor
        <select
          name="supplier"
          defaultValue={selectedSupplierId ?? ""}
          className="h-9 min-w-52 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <option value="">Todos los proveedores</option>
          {suppliers.map((supplier) => (
            <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
          ))}
        </select>
      </label>
      <label className="grid gap-1.5 text-sm font-medium text-foreground">
        Fuente TBC
        <select
          name="tbcSource"
          defaultValue={selectedTbcSourceId ?? ""}
          className="h-9 min-w-60 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <option value="">Todas las fuentes TBC</option>
          {tbcSources.map((source) => (
            <option key={source.id} value={source.id}>{source.label}</option>
          ))}
        </select>
      </label>
      <Button type="submit" variant="outline">Filtrar</Button>
      {hasFilters ? (
        <Button asChild variant="ghost">
          <Link href="/cost-changes">Limpiar</Link>
        </Button>
      ) : null}
    </Form>
  );
}
