"use client";

import { useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";

import { PurchaseRunLinesTable } from "@/components/purchase-runs/purchase-run-lines-table";
import { StatusBadge } from "@/components/status-badge";
import { StatusIcon } from "@/components/imports/status-icon";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  describeRunStatus,
  formatDateTime,
  formatPeriod,
  isAdjustable,
} from "@/app/(app)/purchase-runs/run-status";
import type { PurchaseRunDetail, PurchaseRunLineRow } from "@/app/(app)/purchase-runs/types";

const PAGE_SIZE = 100;
const ALL_LOCATIONS = "__all__";
const ALL_STATUSES = "__all__";

export type PurchaseRunDetailViewProps = {
  run: PurchaseRunDetail;
  initialLines: readonly PurchaseRunLineRow[];
  initialTotal: number;
  canWrite: boolean;
};

/**
 * Resumen de la corrida + filtros + tabla de líneas paginada. Trae la
 * primera página del servidor (ver `[id]/page.tsx`); páginas siguientes y
 * cambios de filtro se piden a `GET /api/purchase-runs/[id]/lines` desde
 * acá, porque una corrida real puede tener cientos/miles de líneas — traer
 * todas de una no escala como sí lo hace la tabla de 50 filas de `/imports`.
 */
export function PurchaseRunDetailView({
  run,
  initialLines,
  initialTotal,
  canWrite,
}: PurchaseRunDetailViewProps) {
  const router = useRouter();
  const locationFieldId = useId();
  const statusFieldId = useId();
  const searchFieldId = useId();

  const [lines, setLines] = useState<readonly PurchaseRunLineRow[]>(initialLines);
  const [total, setTotal] = useState(initialTotal);
  const [page, setPage] = useState(1);
  const [locationCode, setLocationCode] = useState<string>(ALL_LOCATIONS);
  const [status, setStatus] = useState<string>(ALL_STATUSES);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selectedLineIds, setSelectedLineIds] = useState<ReadonlySet<string>>(new Set());
  const [creatingOrders, setCreatingOrders] = useState(false);
  const [createOrderError, setCreateOrderError] = useState<string | null>(null);

  const adjustable = isAdjustable(run.status) && canWrite;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  // Misma condición de carrera que ya se corrigió en NewRunForm: escribir en
  // "Buscar por EAN" dispara una petición por cada tecla, y una respuesta
  // vieja puede resolver DESPUÉS que una más nueva (orden de red, no de
  // tecleo) y pisar la tabla con resultados de una búsqueda intermedia.
  // Un token por llamada descarta cualquier respuesta que ya no sea la última pedida.
  const latestRequestRef = useRef(0);

  async function fetchLines(nextPage: number, filters: { locationCode: string; status: string; search: string }) {
    const requestId = ++latestRequestRef.current;
    setLoading(true);
    setLoadError(null);
    const query = new URLSearchParams({ page: String(nextPage), pageSize: String(PAGE_SIZE) });
    if (filters.locationCode !== ALL_LOCATIONS) query.set("locationCode", filters.locationCode);
    if (filters.status !== ALL_STATUSES) query.set("status", filters.status);
    if (filters.search.trim()) query.set("search", filters.search.trim());

    try {
      const response = await fetch(`/api/purchase-runs/${run.id}/lines?${query.toString()}`);
      const body = await response.json().catch(() => ({}) as { error?: string });
      if (latestRequestRef.current !== requestId) return; // ya no es la última petición
      if (!response.ok) {
        throw new Error((body as { error?: string }).error ?? "No se pudieron cargar las líneas.");
      }
      const loaded = body as { lines: PurchaseRunLineRow[]; total: number };
      setLines(loaded.lines);
      setTotal(loaded.total);
      setPage(nextPage);
    } catch (cause) {
      if (latestRequestRef.current !== requestId) return;
      setLoadError(cause instanceof Error ? cause.message : "No se pudieron cargar las líneas.");
    } finally {
      if (latestRequestRef.current === requestId) setLoading(false);
    }
  }

  function onFilterChange(next: { locationCode?: string; status?: string; search?: string }) {
    const filters = {
      locationCode: next.locationCode ?? locationCode,
      status: next.status ?? status,
      search: next.search ?? search,
    };
    if (next.locationCode !== undefined) setLocationCode(next.locationCode);
    if (next.status !== undefined) setStatus(next.status);
    if (next.search !== undefined) setSearch(next.search);
    void fetchLines(1, filters);
  }

  function onLineAdjusted(updated: PurchaseRunLineRow) {
    setLines((previous) => previous.map((line) => (line.id === updated.id ? updated : line)));
  }

  function onLineSelectionChange(lineId: string, selected: boolean) {
    setSelectedLineIds((previous) => {
      const next = new Set(previous);
      if (selected) next.add(lineId);
      else next.delete(lineId);
      return next;
    });
  }

  function onLinesSelectionChange(lineIds: readonly string[], selected: boolean) {
    setSelectedLineIds((previous) => {
      const next = new Set(previous);
      for (const lineId of lineIds) {
        if (selected) next.add(lineId);
        else next.delete(lineId);
      }
      return next;
    });
  }

  async function createOrders() {
    setCreatingOrders(true);
    setCreateOrderError(null);
    try {
      const response = await fetch("/api/purchase-orders", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ runLineIds: [...selectedLineIds] }),
      });
      const body = await response.json().catch(() => ({}) as { error?: string });
      if (!response.ok) throw new Error(body.error ?? "No se pudieron crear los borradores.");
      router.push("/orders");
    } catch (cause) {
      setCreateOrderError(cause instanceof Error ? cause.message : "No se pudieron crear los borradores.");
      setCreatingOrders(false);
    }
  }

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle className="flex flex-wrap items-center gap-3">
            <span>{run.supplierName ?? "Proveedor"}</span>
            <StatusBadge
              label={describeRunStatus(run.status).label}
              tone={describeRunStatus(run.status).tone}
              icon={<StatusIcon name={describeRunStatus(run.status).icon} />}
            />
          </CardTitle>
          <p className="text-sm text-muted-foreground">{describeRunStatus(run.status).description}</p>
        </CardHeader>
        <CardContent className="space-y-6">
          <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <Dato termino="Período" valor={formatPeriod(run.periodStart, run.periodEnd)} />
            <Dato termino="Motor" valor={run.engineVersion} />
            <Dato termino="Calculada" valor={formatDateTime(run.calculatedAt)} />
            <Dato termino="Creada" valor={formatDateTime(run.createdAt)} />
          </dl>

          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Días objetivo usados
            </p>
            <ul className="mt-2 flex flex-wrap gap-2">
              {run.targetDays.map((entry) => (
                <li
                  key={entry.locationCode}
                  className="rounded-md border border-border bg-card px-2 py-1 text-xs text-foreground"
                >
                  {entry.locationName}: {entry.targetDays} días
                </li>
              ))}
            </ul>
          </div>

          {!isAdjustable(run.status) ? (
            <Alert>
              <AlertTitle>Esta corrida no admite ajustes</AlertTitle>
              <AlertDescription>
                Está {describeRunStatus(run.status).label.toLowerCase()}: las cantidades finales
                quedaron fijas.
              </AlertDescription>
            </Alert>
          ) : null}
        </CardContent>
      </Card>

      <section aria-labelledby="lineas-corrida" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="lineas-corrida" className="text-lg font-semibold text-foreground">
            Líneas
          </h2>
          {canWrite ? (
            <Button
              type="button"
              disabled={!adjustable || selectedLineIds.size === 0 || creatingOrders}
              onClick={() => void createOrders()}
            >
              {creatingOrders ? "Creando borradores…" : `Crear órdenes (${selectedLineIds.size})`}
            </Button>
          ) : null}
        </div>

        <div className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-2">
            <Label htmlFor={locationFieldId}>Ubicación</Label>
            <Select
              value={locationCode}
              onValueChange={(next) => onFilterChange({ locationCode: next })}
            >
              <SelectTrigger id={locationFieldId} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_LOCATIONS}>Todas</SelectItem>
                {run.targetDays.map((entry) => (
                  <SelectItem key={entry.locationCode} value={entry.locationCode}>
                    {entry.locationName}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor={statusFieldId}>Estado de la línea</Label>
            <Select value={status} onValueChange={(next) => onFilterChange({ status: next })}>
              <SelectTrigger id={statusFieldId} className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL_STATUSES}>Todos</SelectItem>
                <SelectItem value="ok">OK</SelectItem>
                <SelectItem value="no_price">Sin precio vigente</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor={searchFieldId}>Buscar por EAN</Label>
            <Input
              id={searchFieldId}
              value={search}
              onChange={(event) => onFilterChange({ search: event.target.value })}
              placeholder="7700000000011"
            />
          </div>
        </div>

        {loadError ? (
          <Alert variant="destructive">
            <AlertTitle>No se pudieron cargar las líneas</AlertTitle>
            <AlertDescription>{loadError}</AlertDescription>
          </Alert>
        ) : null}
        {createOrderError ? (
          <Alert variant="destructive">
            <AlertTitle>No se pudieron crear los borradores</AlertTitle>
            <AlertDescription>{createOrderError}</AlertDescription>
          </Alert>
        ) : null}

        <PurchaseRunLinesTable
          runId={run.id}
          lines={lines}
          isLoading={loading}
          adjustable={adjustable}
          selectedLineIds={selectedLineIds}
          onLineSelectionChange={onLineSelectionChange}
          onLinesSelectionChange={onLinesSelectionChange}
          onLineAdjusted={onLineAdjusted}
        />

        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted-foreground">
            {total} {total === 1 ? "línea" : "líneas"} · página {page} de {totalPages}
          </p>
          <div className="flex gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page <= 1 || loading}
              onClick={() => fetchLines(page - 1, { locationCode, status, search })}
            >
              Anterior
            </Button>
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={page >= totalPages || loading}
              onClick={() => fetchLines(page + 1, { locationCode, status, search })}
            >
              Siguiente
            </Button>
          </div>
        </div>
      </section>
    </div>
  );
}

function Dato({ termino, valor }: { termino: string; valor: string }) {
  return (
    <div>
      <dt className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {termino}
      </dt>
      <dd className="mt-1 text-sm text-foreground">{valor}</dd>
    </div>
  );
}
