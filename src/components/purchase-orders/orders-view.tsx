import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { PurchaseOrderRow } from "@/app/(app)/orders/types";

export function OrdersView({ orders }: { orders: readonly PurchaseOrderRow[] }) {
  if (orders.length === 0) {
    return <EmptyState title="Aún no hay órdenes" description="Selecciona líneas con cantidad final positiva en una corrida para crear borradores por ubicación." />;
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Orden</TableHead>
              <TableHead>Proveedor</TableHead>
              <TableHead>Destino</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Unidades</TableHead>
              <TableHead>Total</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {orders.map((order) => (
              <TableRow key={order.id}>
                <TableCell>
                  <Link className="font-medium text-primary hover:underline" href={`/orders/${order.id}`}>
                    {order.orderNumber ?? "Borrador"}
                  </Link>
                </TableCell>
                <TableCell>{order.supplierName}</TableCell>
                <TableCell>{order.locationName}</TableCell>
                <TableCell><OrderStatus status={order.status} /></TableCell>
                <TableCell>{order.totalUnits}</TableCell>
                <TableCell>{formatCop(order.subtotal)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export function OrderStatus({ status }: { status: PurchaseOrderRow["status"] }) {
  const label = status === "draft" ? "Borrador" : status === "issued" ? "Emitida" : "Cancelada";
  const tone = status === "issued" ? "text-emerald-700" : status === "cancelled" ? "text-destructive" : "text-amber-700";
  return <span className={`text-sm font-medium ${tone}`}>{label}</span>;
}

export function formatCop(value: string) {
  const amount = Number(value);
  return Number.isFinite(amount) ? `$ ${amount.toLocaleString("es-CO", { maximumFractionDigits: 0 })}` : "—";
}
