"use client";

import { useCallback, useEffect, useState } from "react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { OrderStatus, formatCop } from "@/components/purchase-orders/orders-view";
import type { PurchaseOrderDetail } from "@/app/(app)/orders/types";

export function PurchaseOrderDetailView({ orderId, canWrite }: { orderId: string; canWrite: boolean }) {
  const [order, setOrder] = useState<PurchaseOrderDetail | null>(null);
  const [notes, setNotes] = useState("");
  const [cancelReason, setCancelReason] = useState("");
  const [manualItem, setManualItem] = useState({ ean: "", productName: "", tbcSku: "", unitCost: "", quantity: "1" });
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/purchase-orders/${orderId}`);
      const body = await response.json().catch(() => ({})) as { error?: string; order?: PurchaseOrderDetail };
      if (!response.ok || !body.order) throw new Error(body.error ?? "No se pudo cargar la orden.");
      setOrder(body.order);
      setNotes(body.order.notes);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo cargar la orden.");
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    const timer = window.setTimeout(() => { void load(); }, 0);
    return () => window.clearTimeout(timer);
  }, [load]);

  async function saveNotes() {
    setWorking(true); setError(null);
    try {
      const response = await fetch(`/api/purchase-orders/${orderId}`, { method: "PATCH", headers: { "content-type": "application/json" }, body: JSON.stringify({ notes }) });
      const body = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "No se pudieron guardar las notas.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudieron guardar las notas.");
    } finally { setWorking(false); }
  }

  async function issue() {
    setWorking(true); setError(null);
    try {
      const response = await fetch(`/api/purchase-orders/${orderId}/issue`, { method: "POST" });
      const body = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "No se pudo emitir la orden.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo emitir la orden.");
    } finally { setWorking(false); }
  }

  async function addManualItem() {
    setWorking(true); setError(null);
    try {
      const response = await fetch(`/api/purchase-orders/${orderId}/items`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ ...manualItem, unitCost: Number(manualItem.unitCost), quantity: Number(manualItem.quantity) }),
      });
      const body = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "No se pudo agregar el producto.");
      setManualItem({ ean: "", productName: "", tbcSku: "", unitCost: "", quantity: "1" });
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo agregar el producto.");
    } finally { setWorking(false); }
  }

  async function deleteItem(itemId: string) {
    setWorking(true); setError(null);
    try {
      const response = await fetch(`/api/purchase-orders/${orderId}/items/${itemId}`, { method: "DELETE" });
      const body = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "No se pudo quitar el producto.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo quitar el producto.");
    } finally { setWorking(false); }
  }

  async function cancel() {
    setWorking(true); setError(null);
    try {
      const response = await fetch(`/api/purchase-orders/${orderId}/cancel`, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify({ reason: cancelReason }) });
      const body = await response.json().catch(() => ({})) as { error?: string };
      if (!response.ok) throw new Error(body.error ?? "No se pudo cancelar la orden.");
      await load();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo cancelar la orden.");
    } finally { setWorking(false); }
  }

  if (loading) return <p className="text-sm text-muted-foreground">Cargando orden…</p>;
  if (!order) return <Alert variant="destructive"><AlertTitle>No se pudo cargar la orden</AlertTitle><AlertDescription>{error}</AlertDescription></Alert>;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-3">
            <span>{order.orderNumber ?? "Borrador de orden"}</span><OrderStatus status={order.status} />
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Dato label="Proveedor" value={order.supplierName} />
            <Dato label="Destino" value={order.locationName} />
            <Dato label="Unidades" value={String(order.totalUnits)} />
            <Dato label="Total" value={formatCop(order.subtotal)} />
          </dl>
          {order.status === "draft" ? (
            <div className="space-y-5">
              <div className="space-y-2">
                <label htmlFor="order-notes" className="text-sm font-medium">Notas</label>
                <textarea id="order-notes" className="min-h-20 w-full rounded-md border border-input bg-transparent px-3 py-2 text-sm" value={notes} disabled={!canWrite || working} onChange={(event) => setNotes(event.target.value)} />
                {canWrite ? <div className="flex flex-wrap gap-2"><Button type="button" variant="outline" disabled={working} onClick={() => void saveNotes()}>Guardar notas</Button><Button type="button" disabled={working || order.items.length === 0} onClick={() => void issue()}>{working ? "Emitiendo…" : "Emitir y generar PDF"}</Button></div> : null}
              </div>
              {canWrite ? <div className="space-y-2 border-t pt-5"><p className="text-sm font-medium">Agregar producto manual</p><div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-5"><Input placeholder="EAN" value={manualItem.ean} onChange={(event) => setManualItem({ ...manualItem, ean: event.target.value })} /><Input placeholder="Producto" value={manualItem.productName} onChange={(event) => setManualItem({ ...manualItem, productName: event.target.value })} /><Input placeholder="SKU (opcional)" value={manualItem.tbcSku} onChange={(event) => setManualItem({ ...manualItem, tbcSku: event.target.value })} /><Input type="number" min="0" placeholder="Costo" value={manualItem.unitCost} onChange={(event) => setManualItem({ ...manualItem, unitCost: event.target.value })} /><Input type="number" min="1" placeholder="Cantidad" value={manualItem.quantity} onChange={(event) => setManualItem({ ...manualItem, quantity: event.target.value })} /></div><Button type="button" variant="outline" disabled={working} onClick={() => void addManualItem()}>Agregar producto</Button></div> : null}
            </div>
          ) : null}
          {order.status === "issued" ? <div className="flex flex-wrap gap-2"><Button asChild type="button" variant="outline"><a href={`/api/purchase-orders/${order.id}/pdf`}>Descargar PDF</a></Button><Input value={cancelReason} onChange={(event) => setCancelReason(event.target.value)} placeholder="Motivo de cancelación" aria-label="Motivo de cancelación" disabled={working} /><Button type="button" variant="destructive" disabled={working || !cancelReason.trim()} onClick={() => void cancel()}>{working ? "Cancelando…" : "Cancelar orden"}</Button></div> : null}
          {order.status === "cancelled" ? <Alert><AlertTitle>Orden cancelada</AlertTitle><AlertDescription>{order.cancelReason}</AlertDescription></Alert> : null}
        </CardContent>
      </Card>
      {error ? <Alert variant="destructive"><AlertTitle>Acción no completada</AlertTitle><AlertDescription>{error}</AlertDescription></Alert> : null}
      <Card><CardContent className="p-0"><Table><TableHeader><TableRow><TableHead>Producto</TableHead><TableHead>EAN</TableHead><TableHead>Cantidad</TableHead><TableHead>Costo</TableHead><TableHead>Total</TableHead>{order.status === "draft" && canWrite ? <TableHead><span className="sr-only">Acciones</span></TableHead> : null}</TableRow></TableHeader><TableBody>{order.items.map((item) => <TableRow key={item.id}><TableCell className="font-medium">{item.productName}</TableCell><TableCell className="text-muted-foreground">{item.ean}</TableCell><TableCell>{item.quantity}</TableCell><TableCell>{formatCop(item.unitCost)}</TableCell><TableCell>{formatCop(item.lineTotal)}</TableCell>{order.status === "draft" && canWrite ? <TableCell><Button type="button" size="xs" variant="ghost" disabled={working} onClick={() => void deleteItem(item.id)}>Quitar</Button></TableCell> : null}</TableRow>)}</TableBody></Table></CardContent></Card>
    </div>
  );
}

function Dato({ label, value }: { label: string; value: string }) {
  return <div><dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">{label}</dt><dd className="mt-1 text-sm text-foreground">{value}</dd></div>;
}
