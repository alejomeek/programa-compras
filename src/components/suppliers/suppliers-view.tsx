"use client";

import { useId, useState } from "react";
import { Building2 } from "lucide-react";

import { EmptyState } from "@/components/empty-state";
import { StatusBadge } from "@/components/status-badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SupplierRow } from "@/app/(app)/suppliers/types";

export type CreateSupplierInput = {
  name: string;
  tbcCode: string;
  nit?: string | null;
};

export type SuppliersViewProps = {
  suppliers: readonly SupplierRow[];
  loadErrorMessage?: string | null;
  canCreate: boolean;
  onCreateSupplier?: (input: CreateSupplierInput) => Promise<void>;
};

/**
 * Vista mínima de `/suppliers`: crear + listar (ver `types.ts`). Sin
 * edición ni versiones de lista de precios — eso sigue fuera de alcance.
 */
export function SuppliersView({ suppliers, loadErrorMessage, canCreate, onCreateSupplier }: SuppliersViewProps) {
  return (
    <div className="space-y-8">
      {canCreate ? (
        <Card>
          <CardHeader>
            <CardTitle>Nuevo proveedor</CardTitle>
            <p className="text-sm text-muted-foreground">
              El comodín TBC (3 dígitos) es el que ya trae SDOSXSUC/INVEPTOS para identificarlo.
            </p>
          </CardHeader>
          <CardContent>
            <CreateSupplierForm onCreateSupplier={onCreateSupplier} />
          </CardContent>
        </Card>
      ) : (
        <Alert>
          <AlertTitle>Solo un administrador puede crear proveedores</AlertTitle>
          <AlertDescription>Puedes consultar el catálogo debajo.</AlertDescription>
        </Alert>
      )}

      <section aria-labelledby="catalogo-proveedores" className="space-y-4">
        <h2 id="catalogo-proveedores" className="text-lg font-semibold text-foreground">
          Catálogo
        </h2>

        {loadErrorMessage ? (
          <Alert variant="destructive">
            <AlertTitle>No se pudo cargar el catálogo de proveedores</AlertTitle>
            <AlertDescription>{loadErrorMessage}</AlertDescription>
          </Alert>
        ) : suppliers.length === 0 ? (
          <EmptyState
            icon={<Building2 aria-hidden="true" className="size-6" />}
            title="Todavía no hay proveedores"
            description="Crea el primero arriba para poder subir sus listas de precios o calcular una corrida."
          />
        ) : (
          <Table>
            <caption className="sr-only">Catálogo de proveedores con su comodín TBC y NIT.</caption>
            <TableHeader>
              <TableRow>
                <TableHead scope="col">Nombre</TableHead>
                <TableHead scope="col">Comodín TBC</TableHead>
                <TableHead scope="col">NIT</TableHead>
                <TableHead scope="col">Estado</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {suppliers.map((supplier) => (
                <TableRow key={supplier.id}>
                  <TableCell className="font-medium text-foreground">{supplier.name}</TableCell>
                  <TableCell className="whitespace-nowrap font-mono text-xs">{supplier.tbcCode}</TableCell>
                  <TableCell className="whitespace-nowrap text-muted-foreground">
                    {supplier.nit ?? "—"}
                  </TableCell>
                  <TableCell>
                    <StatusBadge
                      label={supplier.active ? "Activo" : "Inactivo"}
                      tone={supplier.active ? "success" : "neutral"}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </section>
    </div>
  );
}

function CreateSupplierForm({
  onCreateSupplier,
}: {
  onCreateSupplier?: (input: CreateSupplierInput) => Promise<void>;
}) {
  const nameFieldId = useId();
  const tbcFieldId = useId();
  const nitFieldId = useId();

  const [name, setName] = useState("");
  const [tbcCode, setTbcCode] = useState("");
  const [nit, setNit] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const tbcValido = /^\d{3}$/.test(tbcCode);
  const puedeCrear = name.trim().length > 0 && tbcValido;

  async function onSubmit() {
    if (!puedeCrear || !onCreateSupplier) return;

    setSubmitting(true);
    setError(null);
    try {
      await onCreateSupplier({ name: name.trim(), tbcCode, nit: nit.trim() || null });
      setName("");
      setTbcCode("");
      setNit("");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "No se pudo crear el proveedor.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-2">
          <Label htmlFor={nameFieldId}>Nombre</Label>
          <Input id={nameFieldId} value={name} onChange={(event) => setName(event.target.value)} />
        </div>
        <div className="space-y-2">
          <Label htmlFor={tbcFieldId}>Comodín TBC (3 dígitos)</Label>
          <Input
            id={tbcFieldId}
            value={tbcCode}
            onChange={(event) => setTbcCode(event.target.value.replace(/[^0-9]/g, "").slice(0, 3))}
            aria-invalid={tbcCode.length > 0 && !tbcValido ? true : undefined}
            placeholder="801"
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor={nitFieldId}>NIT (opcional)</Label>
          <Input id={nitFieldId} value={nit} onChange={(event) => setNit(event.target.value)} />
        </div>
      </div>

      {error ? (
        <Alert variant="destructive">
          <AlertTitle>No se pudo crear el proveedor</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      ) : null}

      <Button type="button" onClick={onSubmit} disabled={!puedeCrear || submitting}>
        {submitting ? "Creando…" : "Crear proveedor"}
      </Button>
    </div>
  );
}
