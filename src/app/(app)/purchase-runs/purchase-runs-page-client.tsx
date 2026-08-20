"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import {
  PurchaseRunsView,
  type CreateRunInput,
  type PurchaseRunsViewProps,
} from "@/components/purchase-runs/purchase-runs-view";
import type { PurchaseRunRow } from "./types";

type Props = Omit<PurchaseRunsViewProps, "onCreateRun">;

/**
 * Envuelve `PurchaseRunsView` con la creación real de una corrida. Client
 * Component solo porque `onCreateRun` es una función (mismo límite que
 * `ImportsPageClient` documenta para `onUpload`). Pedir las fuentes
 * disponibles para un proveedor (`GET .../new-run-options`) no necesita este
 * envoltorio: `NewRunForm` lo hace con `fetch` directo, sin cruzar el límite
 * Server→Client.
 *
 * A diferencia de `/imports`, al crear con éxito se navega directo al
 * detalle (`router.push`): el cálculo ya terminó (la ruta responde solo
 * cuando el motor Python termina), así que lo natural es revisar/ajustar
 * líneas, no quedarse viendo la lista.
 */
export function PurchaseRunsPageClient({ runs: initialRuns, ...props }: Props) {
  const router = useRouter();
  const [runs, setRuns] = useState<readonly PurchaseRunRow[]>(initialRuns);
  const [syncedFrom, setSyncedFrom] = useState(initialRuns);

  if (initialRuns !== syncedFrom) {
    setSyncedFrom(initialRuns);
    setRuns(initialRuns);
  }

  const onCreateRun = async (input: CreateRunInput): Promise<void> => {
    const response = await fetch("/api/purchase-runs", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        supplierId: input.supplierId,
        salesImportId: input.salesImportId,
        priceListId: input.priceListId,
        inventorySnapshotId: input.inventorySnapshotId,
        targetDays: input.targetDays,
      }),
    });
    const body = await response.json().catch(() => ({}) as { error?: string; purchaseRunId?: string });
    if (!response.ok) {
      throw new Error(body.error ?? "No se pudo crear la corrida.");
    }
    router.push(`/purchase-runs/${body.purchaseRunId}`);
  };

  return <PurchaseRunsView {...props} runs={runs} onCreateRun={onCreateRun} />;
}
