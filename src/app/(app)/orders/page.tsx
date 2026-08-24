import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";
import { OrdersFilters, type OrderFilterOption } from "@/components/purchase-orders/orders-filters";
import { OrdersView } from "@/components/purchase-orders/orders-view";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { PurchaseOrderRow } from "./types";

export const metadata: Metadata = {
  title: "Órdenes de compra",
};

export const dynamic = "force-dynamic";

type SearchParams = Promise<{
  createdFrom?: string | string[];
  createdTo?: string | string[];
  supplier?: string | string[];
  location?: string | string[];
  status?: string | string[];
}>;

const ORDER_STATUSES = new Set(["draft", "issued", "cancelled"]);

function dateParam(value: string | string[] | undefined) {
  return typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value) ? value : null;
}

function stringParam(value: string | string[] | undefined) {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function dayAfterBogota(date: string) {
  const result = new Date(`${date}T00:00:00-05:00`);
  result.setUTCDate(result.getUTCDate() + 1);
  return result.toISOString();
}

export default async function Page({ searchParams }: { searchParams: SearchParams }) {
  const params = await searchParams;
  const createdFrom = dateParam(params.createdFrom);
  const createdTo = dateParam(params.createdTo);
  const supplierId = stringParam(params.supplier);
  const locationId = stringParam(params.location);
  const statusParam = stringParam(params.status);
  const status = statusParam && ORDER_STATUSES.has(statusParam) ? statusParam as PurchaseOrderRow["status"] : null;
  const supabase = await createClient();
  let ordersQuery = supabase
    .from("purchase_orders")
    .select("id, order_number, status, total_units, subtotal, created_at, issued_at, cancelled_at, suppliers(name), locations(code, name)")
    .order("created_at", { ascending: false })
  if (createdFrom) ordersQuery = ordersQuery.gte("created_at", `${createdFrom}T00:00:00-05:00`);
  if (createdTo) ordersQuery = ordersQuery.lt("created_at", dayAfterBogota(createdTo));
  if (supplierId) ordersQuery = ordersQuery.eq("supplier_id", supplierId);
  if (locationId) ordersQuery = ordersQuery.eq("location_id", locationId);
  if (status) ordersQuery = ordersQuery.eq("status", status);

  const [
    { data, error },
    { data: supplierData, error: supplierError },
    { data: locationData, error: locationError },
  ] = await Promise.all([
    ordersQuery.limit(50),
    supabase.from("suppliers").select("id, name").order("name"),
    supabase.from("locations").select("id, code, name").order("display_order"),
  ]);
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

  const suppliers: OrderFilterOption[] = (supplierData ?? []).map((supplier) => ({ id: supplier.id, label: supplier.name }));
  const destinations: OrderFilterOption[] = (locationData ?? []).map((location) => ({ id: location.id, label: location.name || location.code }));
  const loadError = error ?? supplierError ?? locationError;

  return (
    <div className="space-y-8">
      <PageHeader
        title="Órdenes de compra"
        description="Borradores por destino, órdenes emitidas y sus documentos PDF auditables."
      />
      {loadError ? (
        <p className="text-sm text-destructive">No se pudieron cargar las órdenes: {loadError.message}</p>
      ) : (
        <>
          <OrdersFilters
            suppliers={suppliers}
            destinations={destinations}
            selected={{ createdFrom, createdTo, supplierId, locationId, status }}
          />
          <OrdersView key={orders.map((order) => `${order.id}:${order.status}`).join("|")} orders={orders} />
        </>
      )}
    </div>
  );
}
