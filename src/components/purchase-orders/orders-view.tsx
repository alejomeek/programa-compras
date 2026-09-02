"use client";

import Link from "next/link";
import { useState } from "react";

import { EmptyState } from "@/components/empty-state";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatCop, formatOrderDate } from "@/lib/purchase-order-format";
import type { PurchaseOrderRow } from "@/app/(app)/orders/types";

export function OrdersView({ orders }: { orders: readonly PurchaseOrderRow[] }) {
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(new Set());
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  const selectedCount = selectedIds.size;

  function toggleOrder(orderId: string, selected: boolean) {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (selected) next.add(orderId);
      else next.delete(orderId);
      return next;
    });
  }

  async function downloadZip() {
    if (selectedCount === 0 || downloading) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      const response = await fetch("/api/purchase-orders/download-zip", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ orderIds: [...selectedIds] }),
      });
      if (!response.ok) {
        const body = await response.json().catch(() => ({})) as { error?: string };
        throw new Error(body.error ?? "No se pudo preparar el archivo ZIP.");
      }
      const blob = await response.blob();
      const downloadUrl = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = downloadUrl;
      link.download = "ordenes-de-compra.zip";
      document.body.append(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(downloadUrl);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "No se pudo preparar el archivo ZIP.");
    } finally {
      setDownloading(false);
    }
  }

  if (orders.length === 0) {
    return <EmptyState title="Aún no hay órdenes" description="Selecciona líneas con cantidad final positiva en una corrida para crear borradores por ubicación." />;
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-end gap-3">
        {downloadError ? <p role="alert" className="text-sm text-destructive">{downloadError}</p> : null}
        <Button type="button" disabled={selectedCount === 0 || downloading} onClick={() => void downloadZip()}>
          {downloading ? "Preparando ZIP…" : `Descargar ZIP (${selectedCount})`}
        </Button>
      </div>
      <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-9"><span className="sr-only">Seleccionar</span></TableHead>
              <TableHead>Orden</TableHead>
              <TableHead>Creada</TableHead>
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
                  {order.status === "issued" ? (
                    <input
                      type="checkbox"
                      checked={selectedIds.has(order.id)}
                      aria-label={`Seleccionar ${order.orderNumber ?? "orden emitida"}`}
                      onChange={(event) => toggleOrder(order.id, event.target.checked)}
                      className="size-3 rounded border-input align-middle accent-primary"
                    />
                  ) : null}
                </TableCell>
                <TableCell>
                  <Link className="font-medium text-primary hover:underline" href={`/orders/${order.id}`}>
                    {order.orderNumber ?? "Borrador"}
                  </Link>
                </TableCell>
                <TableCell className="whitespace-nowrap text-muted-foreground">
                  {formatOrderDate(order.createdAt)}
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
    </div>
  );
}

export function OrderStatus({ status }: { status: PurchaseOrderRow["status"] }) {
  const label = status === "draft" ? "Borrador" : status === "issued" ? "Emitida" : "Cancelada";
  const tone = status === "issued" ? "text-emerald-700" : status === "cancelled" ? "text-destructive" : "text-amber-700";
  return <span className={`text-sm font-medium ${tone}`}>{label}</span>;
}
