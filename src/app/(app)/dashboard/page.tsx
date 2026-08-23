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
  const { data: recentRows, error } = await supabase
    .from("purchase_orders")
    .select("id, order_number, status, total_units, subtotal, created_at, issued_at, cancelled_at, suppliers(name), locations(code, name)")
    .order("created_at", { ascending: false })
    .limit(8);

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

  return (
    <div className="space-y-8">
      <PageHeader
        title="Inicio"
        description="Órdenes de compra creadas recientemente."
      />
      {error ? (
        <p className="text-sm text-destructive">No se pudo cargar el resumen: {error.message}</p>
      ) : (
        <DashboardOverview recentOrders={recentOrders} />
      )}
    </div>
  );
}
