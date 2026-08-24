import Form from "next/form";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import type { PurchaseOrderStatus } from "@/app/(app)/orders/types";

export type OrderFilterOption = {
  id: string;
  label: string;
};

type OrdersFiltersProps = {
  suppliers: readonly OrderFilterOption[];
  destinations: readonly OrderFilterOption[];
  selected: {
    createdFrom: string | null;
    createdTo: string | null;
    supplierId: string | null;
    locationId: string | null;
    status: PurchaseOrderStatus | null;
  };
};

const STATUSES: readonly { value: PurchaseOrderStatus; label: string }[] = [
  { value: "draft", label: "Borrador" },
  { value: "issued", label: "Emitida" },
  { value: "cancelled", label: "Cancelada" },
];

export function OrdersFilters({ suppliers, destinations, selected }: OrdersFiltersProps) {
  const hasFilters = Object.values(selected).some((value) => value !== null);

  return (
    <Form action="/orders" className="flex flex-wrap items-end gap-3">
      <fieldset className="flex flex-wrap gap-3">
        <legend className="mb-1.5 text-sm font-medium text-foreground">Fecha de creación</legend>
        <label className="grid gap-1.5 text-sm text-muted-foreground">
          Desde
          <input
            type="date"
            name="createdFrom"
            defaultValue={selected.createdFrom ?? ""}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </label>
        <label className="grid gap-1.5 text-sm text-muted-foreground">
          Hasta
          <input
            type="date"
            name="createdTo"
            defaultValue={selected.createdTo ?? ""}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
          />
        </label>
      </fieldset>
      <label className="grid gap-1.5 text-sm font-medium text-foreground">
        Proveedor
        <select
          name="supplier"
          defaultValue={selected.supplierId ?? ""}
          className="h-9 min-w-48 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <option value="">Todos los proveedores</option>
          {suppliers.map((supplier) => <option key={supplier.id} value={supplier.id}>{supplier.label}</option>)}
        </select>
      </label>
      <label className="grid gap-1.5 text-sm font-medium text-foreground">
        Destino
        <select
          name="location"
          defaultValue={selected.locationId ?? ""}
          className="h-9 min-w-40 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <option value="">Todos los destinos</option>
          {destinations.map((destination) => <option key={destination.id} value={destination.id}>{destination.label}</option>)}
        </select>
      </label>
      <label className="grid gap-1.5 text-sm font-medium text-foreground">
        Estado
        <select
          name="status"
          defaultValue={selected.status ?? ""}
          className="h-9 min-w-36 rounded-md border border-input bg-background px-3 text-sm shadow-xs outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50"
        >
          <option value="">Todos los estados</option>
          {STATUSES.map((status) => <option key={status.value} value={status.value}>{status.label}</option>)}
        </select>
      </label>
      <Button type="submit" variant="outline">Filtrar</Button>
      {hasFilters ? <Button asChild variant="ghost"><Link href="/orders">Limpiar</Link></Button> : null}
    </Form>
  );
}
