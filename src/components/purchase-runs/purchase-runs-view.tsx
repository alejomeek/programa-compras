"use client";

import { useRouter } from "next/navigation";
import { useTransition } from "react";
import { RefreshCw } from "lucide-react";

import { NewRunForm } from "@/components/purchase-runs/new-run-form";
import { PurchaseRunsTable } from "@/components/purchase-runs/purchase-runs-table";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { SupplierOption } from "@/app/(app)/imports/types";
import type { PurchaseRunRow } from "@/app/(app)/purchase-runs/types";

export type CreateRunInput = {
  supplierId: string;
  salesImportId: string;
  priceListId: string;
  inventorySnapshotId: string | null;
  targetDays: Record<string, number>;
};

/**
 * Vista completa de `/purchase-runs`: formulario de creación + historial.
 * Mismo criterio que `ImportsView`: sin polling ni realtime, el botón
 * "Actualizar" pide de nuevo los datos del servidor con `router.refresh()`.
 */
export type PurchaseRunsViewProps = {
  runs: readonly PurchaseRunRow[];
  suppliers: readonly SupplierOption[];
  isLoading?: boolean;
  loadErrorMessage?: string | null;
  onCreateRun?: (input: CreateRunInput) => Promise<void>;
};

export function PurchaseRunsView({
  runs,
  suppliers,
  isLoading = false,
  loadErrorMessage,
  onCreateRun,
}: PurchaseRunsViewProps) {
  const router = useRouter();
  const [refrescando, startRefresh] = useTransition();

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>Nueva corrida</CardTitle>
          <p className="text-sm text-muted-foreground">
            Elige el proveedor y las fuentes ya importadas; el motor calcula la sugerencia al
            instante.
          </p>
        </CardHeader>
        <CardContent>
          <NewRunForm suppliers={suppliers} onCreateRun={onCreateRun} />
        </CardContent>
      </Card>

      <section aria-labelledby="historial-corridas" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="historial-corridas" className="text-lg font-semibold text-foreground">
            Corridas recientes
          </h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => startRefresh(() => router.refresh())}
            disabled={refrescando}
          >
            <RefreshCw aria-hidden="true" className={refrescando ? "motion-safe:animate-spin" : ""} />
            {refrescando ? "Actualizando…" : "Actualizar"}
          </Button>
        </div>

        <PurchaseRunsTable runs={runs} isLoading={isLoading} errorMessage={loadErrorMessage} />
      </section>
    </div>
  );
}
