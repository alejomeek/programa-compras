import { ArrowDown, ArrowUp, Equal } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { formatCop } from "@/lib/purchase-order-format";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

export type CostChangeRow = {
  supplierName: string;
  priceListVersion: number;
  effectiveDate: string;
  ean: string;
  productName: string;
  supplierCost: string;
  tbcCost: string;
  difference: string;
  tbcPeriodEnd: string;
};

export function CostChangesView({ changes }: { changes: readonly CostChangeRow[] }) {
  if (changes.length === 0) {
    return (
      <EmptyState
        title="Sin diferencias de costo"
        description="Las listas de precios vigentes coinciden exactamente con el último costo TBC disponible, o aún no hay costo TBC para comparar."
      />
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <caption className="sr-only">Diferencias entre lista de proveedor vigente y último costo TBC</caption>
          <TableHeader>
            <TableRow>
              <TableHead>Proveedor</TableHead>
              <TableHead>Producto / EAN</TableHead>
              <TableHead>Costo proveedor</TableHead>
              <TableHead>Costo TBC</TableHead>
              <TableHead>Diferencia</TableHead>
              <TableHead>Fuentes</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {changes.map((change) => {
              const direction = Number(change.difference);
              return (
                <TableRow key={`${change.supplierName}-${change.priceListVersion}-${change.ean}`}>
                  <TableCell>{change.supplierName}</TableCell>
                  <TableCell>
                    <span className="block font-medium text-foreground">{change.productName}</span>
                    <span className="block text-xs text-muted-foreground">{change.ean}</span>
                  </TableCell>
                  <TableCell>{formatCop(change.supplierCost)}</TableCell>
                  <TableCell>{formatCop(change.tbcCost)}</TableCell>
                  <TableCell>
                    <span className={direction > 0 ? "inline-flex items-center gap-1 text-destructive" : "inline-flex items-center gap-1 text-emerald-700"}>
                      {direction > 0 ? <ArrowUp aria-hidden="true" className="size-3.5" /> : direction < 0 ? <ArrowDown aria-hidden="true" className="size-3.5" /> : <Equal aria-hidden="true" className="size-3.5" />}
                      {formatCop(String(Math.abs(direction)))}
                    </span>
                  </TableCell>
                  <TableCell className="text-xs text-muted-foreground">
                    <span className="block">Lista v{change.priceListVersion} · {change.effectiveDate}</span>
                    <span className="block">TBC · período hasta {change.tbcPeriodEnd}</span>
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
