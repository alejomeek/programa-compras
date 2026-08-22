import Link from "next/link";

import { EmptyState } from "@/components/empty-state";
import { OrderStatus, formatCop, formatOrderDate } from "@/components/purchase-orders/orders-view";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { PurchaseOrderRow } from "@/app/(app)/orders/types";

export type DashboardOverviewProps = {
  draftCount: number;
  pendingUnits: number;
  pendingValue: number;
  issuedCount: number;
  recentOrders: readonly PurchaseOrderRow[];
};

export function DashboardOverview({
  draftCount,
  pendingUnits,
  pendingValue,
  issuedCount,
  recentOrders,
}: DashboardOverviewProps) {
  return (
    <div className="space-y-8">
      <section aria-label="Resumen de órdenes" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Borradores por emitir" value={String(draftCount)} detail="Pendientes de revisión" />
        <MetricCard label="Unidades por emitir" value={String(pendingUnits)} detail="En borradores actuales" />
        <MetricCard label="Valor pendiente" value={formatCop(String(pendingValue))} detail="En borradores actuales" />
        <MetricCard label="Órdenes emitidas" value={String(issuedCount)} detail="Histórico activo" />
      </section>

      <section aria-labelledby="ordenes-recientes" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 id="ordenes-recientes" className="text-lg font-semibold text-foreground">Órdenes recientes</h2>
            <p className="text-sm text-muted-foreground">Las últimas órdenes creadas, incluidas las pendientes de emisión.</p>
          </div>
          <Link className="text-sm font-medium text-primary hover:underline" href="/orders">Ver todas las órdenes</Link>
        </div>

        {recentOrders.length === 0 ? (
          <EmptyState title="Aún no hay órdenes" description="Crea borradores desde una compra sugerida para verlos aquí." />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Orden</TableHead>
                    <TableHead>Creada</TableHead>
                    <TableHead>Proveedor</TableHead>
                    <TableHead>Destino</TableHead>
                    <TableHead>Estado</TableHead>
                    <TableHead>Total</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {recentOrders.map((order) => (
                    <TableRow key={order.id}>
                      <TableCell>
                        <Link className="font-medium text-primary hover:underline" href={`/orders/${order.id}`}>
                          {order.orderNumber ?? "Borrador"}
                        </Link>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">{formatOrderDate(order.createdAt)}</TableCell>
                      <TableCell>{order.supplierName}</TableCell>
                      <TableCell>{order.locationName}</TableCell>
                      <TableCell><OrderStatus status={order.status} /></TableCell>
                      <TableCell>{formatCop(order.subtotal)}</TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </section>
    </div>
  );
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <Card>
      <CardHeader className="gap-1">
        <p className="text-sm text-muted-foreground">{label}</p>
        <CardTitle className="text-2xl tabular-nums">{value}</CardTitle>
      </CardHeader>
      <CardContent className="text-sm text-muted-foreground">{detail}</CardContent>
    </Card>
  );
}
