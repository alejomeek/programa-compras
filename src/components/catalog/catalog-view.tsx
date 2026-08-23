import { CircleAlert, CircleCheck, CirclePlus } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { formatCop } from "@/components/purchase-orders/orders-view";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export type CatalogStatus = "matched" | "new" | "not_available";

export type CatalogItemRow = {
  supplierName: string;
  priceListVersion: number | null;
  ean: string;
  productName: string;
  supplierCost: string | null;
  tbcSku: string | null;
  status: CatalogStatus;
};

export type CatalogIssueRow = {
  id: string;
  severity: string;
  code: string;
  ean: string | null;
  productName: string | null;
  detail: string;
};

const STATUS_COPY: Record<CatalogStatus, { label: string; className: string; icon: typeof CircleCheck }> = {
  matched: { label: "En lista y TBC", className: "text-emerald-700", icon: CircleCheck },
  new: { label: "Nuevo en lista", className: "text-amber-700", icon: CirclePlus },
  not_available: { label: "No disponible en lista", className: "text-destructive", icon: CircleAlert },
};

export function CatalogView({ items, issues }: { items: readonly CatalogItemRow[]; issues: readonly CatalogIssueRow[] }) {
  return (
    <div className="space-y-8">
      <section aria-labelledby="catalogo-vigente" className="space-y-4">
        <div>
          <h2 id="catalogo-vigente" className="text-lg font-semibold text-foreground">Catálogo vigente</h2>
          <p className="text-sm text-muted-foreground">El inventario TBC solo sirve para clasificar. Un EAN ausente de la lista vigente no está disponible para comprar.</p>
        </div>
        {items.length === 0 ? (
          <EmptyState title="Sin listas vigentes" description="Carga una lista de precios activa para ver los productos disponibles por proveedor." />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <caption className="sr-only">Catálogo de productos por proveedor y disponibilidad en lista vigente</caption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Proveedor</TableHead>
                    <TableHead>Producto / EAN</TableHead>
                    <TableHead>SKU TBC</TableHead>
                    <TableHead>Costo proveedor</TableHead>
                    <TableHead>Estado</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((item) => {
                    const copy = STATUS_COPY[item.status];
                    const Icon = copy.icon;
                    return (
                      <TableRow key={`${item.supplierName}-${item.ean}-${item.status}`}>
                        <TableCell>{item.supplierName}</TableCell>
                        <TableCell>
                          <span className="block font-medium text-foreground">{item.productName}</span>
                          <span className="block text-xs text-muted-foreground">{item.ean}</span>
                        </TableCell>
                        <TableCell className="text-muted-foreground">{item.tbcSku ?? "—"}</TableCell>
                        <TableCell>{item.supplierCost === null ? "—" : formatCop(item.supplierCost)}</TableCell>
                        <TableCell>
                          <span className={`inline-flex items-center gap-1 text-sm font-medium ${copy.className}`}>
                            <Icon aria-hidden="true" className="size-3.5" />
                            {copy.label}
                          </span>
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        )}
      </section>

      <section aria-labelledby="incidencias-catalogo" className="space-y-4">
        <div>
          <h2 id="incidencias-catalogo" className="text-lg font-semibold text-foreground">Problemas detectados en archivos</h2>
          <p className="text-sm text-muted-foreground">Últimas 50 incidencias de EAN, costo, comodín o estructura que requieren revisar el archivo de origen.</p>
        </div>
        {issues.length === 0 ? (
          <EmptyState title="Sin incidencias registradas" description="Las próximas importaciones con problemas aparecerán aquí." />
        ) : (
          <Card>
            <CardContent className="p-0">
              <Table>
                <caption className="sr-only">Incidencias recientes de archivos</caption>
                <TableHeader>
                  <TableRow>
                    <TableHead>Severidad</TableHead>
                    <TableHead>Producto / EAN</TableHead>
                    <TableHead>Problema</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {issues.map((issue) => (
                    <TableRow key={issue.id}>
                      <TableCell>{issue.severity === "error" ? "Error" : issue.severity === "warning" ? "Aviso" : "Nota"}</TableCell>
                      <TableCell>
                        <span className="block font-medium text-foreground">{issue.productName ?? "—"}</span>
                        <span className="block text-xs text-muted-foreground">{issue.ean ?? "—"}</span>
                      </TableCell>
                      <TableCell className="text-muted-foreground">{issue.detail}</TableCell>
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
