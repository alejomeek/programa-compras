import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { OrdersView } from "@/components/purchase-orders/orders-view";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseOrderRow } from "./types";

export const metadata: Metadata = {
  title: "Órdenes de compra",
};

export const dynamic = "force-dynamic";

export default async function Page() {
  const supabase = await createClient();
  const { data, error } = await supabase
    .from("purchase_orders")
    .select("id, order_number, status, total_units, subtotal, created_at, issued_at, cancelled_at, suppliers(name), locations(code, name)")
    .order("created_at", { ascending: false })
    .limit(50);
  const orders: PurchaseOrderRow[] = (data ?? []).map((order) => {
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
        title="Órdenes de compra"
        description="Borradores por destino, órdenes emitidas y sus documentos PDF auditables."
      />
      {error ? <p className="text-sm text-destructive">No se pudieron cargar las órdenes: {error.message}</p> : <OrdersView orders={orders} />}
    </div>
  );
}
