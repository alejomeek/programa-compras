"use client";

import { useState } from "react";

import {
  SuppliersView,
  type CreateSupplierInput,
} from "@/components/suppliers/suppliers-view";
import type { SupplierRow } from "./types";

type Props = {
  suppliers: readonly SupplierRow[];
  loadErrorMessage?: string | null;
  canCreate: boolean;
};

/**
 * Envuelve `SuppliersView` con la creación real. Client Component solo
 * porque `onCreateSupplier` es una función (mismo límite documentado en
 * `ImportsPageClient`/`PurchaseRunsPageClient`).
 */
export function SuppliersPageClient({ suppliers: initialSuppliers, loadErrorMessage, canCreate }: Props) {
  const [suppliers, setSuppliers] = useState<readonly SupplierRow[]>(initialSuppliers);
  const [syncedFrom, setSyncedFrom] = useState(initialSuppliers);

  if (initialSuppliers !== syncedFrom) {
    setSyncedFrom(initialSuppliers);
    setSuppliers(initialSuppliers);
  }

  const onCreateSupplier = async (input: CreateSupplierInput): Promise<void> => {
    const response = await fetch("/api/suppliers", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(input),
    });
    const body = await response.json().catch(() => ({}) as { error?: string; supplier?: SupplierRow });
    if (!response.ok) {
      throw new Error(body.error ?? "No se pudo crear el proveedor.");
    }
    if (body.supplier) {
      setSuppliers((previous) => [...previous, body.supplier as SupplierRow].sort((a, b) => a.name.localeCompare(b.name)));
    }
  };

  return (
    <SuppliersView
      suppliers={suppliers}
      loadErrorMessage={loadErrorMessage}
      canCreate={canCreate}
      onCreateSupplier={onCreateSupplier}
    />
  );
}
