import type { Metadata } from "next";

import { DashboardOverview } from "@/components/dashboard/dashboard-overview";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseOrderRow } from "@/app/(app)/orders/types";

export const metadata: Metadata = {
  title: "Inicio",
};

export const dynamic = "force-dynamic";

export default async function Page() {
  const supabase = await createClient();
  const [{ data: summaryRows, error: summaryError }, { data: recentRows, error: recentError }] = await Promise.all([
    supabase
      .from("purchase_orders")
      .select("status, total_units, subtotal"),
    supabase
      .from("purchase_orders")
      .select("id, order_number, status, total_units, subtotal, created_at, issued_at, cancelled_at, suppliers(name), locations(code, name)")
      .order("created_at", { ascending: false })
      .limit(8),
  ]);

  const summary = (summaryRows ?? []).reduce(
    (metrics, order) => {
      if (order.status === "draft") {
        metrics.draftCount += 1;
        metrics.pendingUnits += order.total_units;
        metrics.pendingValue += Number(order.subtotal);
      }
      if (order.status === "issued") metrics.issuedCount += 1;
      return metrics;
    },
    { draftCount: 0, pendingUnits: 0, pendingValue: 0, issuedCount: 0 },
  );

  const recentOrders: PurchaseOrderRow[] = (recentRows ?? []).map((order) => {
    const supplier = embeddedOne<{ name: string }>(order.suppliers);
    const location = embeddedOne<{ code: string; name: string }>(order.locations);
    return {
      id: order.id,
      orderNumber: order.order_number,
      status: order.status,
      supplierName: supplier?.name ?? "Proveedor",
      locationCode: location?.code ?? "",
      locationName: location?.name ?? "Ubicación",
      totalUnits: order.total_units,
      subtotal: String(order.subtotal),
      createdAt: order.created_at,
      issuedAt: order.issued_at,
      cancelledAt: order.cancelled_at,
    };
  });

  const error = summaryError ?? recentError;
  return (
    <div className="space-y-8">
      <PageHeader
        title="Inicio"
        description="Resumen de órdenes de compra y pendientes de emisión."
      />
      {error ? (
        <p className="text-sm text-destructive">No se pudo cargar el resumen: {error.message}</p>
      ) : (
        <DashboardOverview {...summary} recentOrders={recentOrders} />
      )}
    </div>
  );
}
