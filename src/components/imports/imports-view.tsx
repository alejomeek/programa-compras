"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { RefreshCw } from "lucide-react";

import { FileDropzone, type UploadHandler } from "@/components/imports/file-dropzone";
import { ImportJobsTable } from "@/components/imports/import-jobs-table";
import { ImportSummary } from "@/components/imports/import-summary";
import { ImportTypeSelector } from "@/components/imports/import-type-selector";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { importTypeDefinition, type ImportType } from "@/app/(app)/imports/import-types";
import type { ImportJobRow, SupplierOption } from "@/app/(app)/imports/types";

/**
 * Vista completa de `/imports`: selector de tipo, zona de carga, historial de
 * trabajos y panel de detalle.
 *
 * Solo maneja estado de INTERFAZ (tipo elegido, proveedor, fila seleccionada).
 * Los datos entran por props desde el Server Component y la subida entra por
 * `onUpload`; sin ella la carga queda deshabilitada con su explicacion, en vez
 * de fingir un backend.
 *
 * Sin polling ni realtime (decision del lead para la Fase 2): el boton
 * "Actualizar" pide de nuevo los datos del servidor con `router.refresh()`.
 */
export type ImportsViewProps = {
  jobs: readonly ImportJobRow[];
  suppliers: readonly SupplierOption[];
  isLoading?: boolean;
  /** Error al obtener el historial, ya redactado para una persona. */
  loadErrorMessage?: string | null;
  /** Motivo por el que la carga no esta disponible (integracion pendiente). */
  uploadDisabledReason?: string | null;
  onUpload?: UploadHandler;
  defaultType?: ImportType;
  /**
   * Se llama al seleccionar un job en la tabla, además de marcarlo como
   * seleccionado internamente. Lo usa `imports-page-client.tsx` para pedir
   * `GET /api/imports/:id` bajo demanda y traer sus incidencias — no vienen
   * en `jobs` (costaría una consulta por fila mostrada en la lista).
   */
  onSelectJob?: (jobId: string) => void;
};

export function ImportsView({
  jobs,
  suppliers,
  isLoading = false,
  loadErrorMessage,
  uploadDisabledReason,
  onUpload,
  defaultType = "inveptos_sales",
  onSelectJob,
}: ImportsViewProps) {
  const router = useRouter();
  const [refrescando, startRefresh] = useTransition();

  const [type, setType] = useState<ImportType>(defaultType);
  const [supplierId, setSupplierId] = useState<string | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);

  const requiereProveedor = importTypeDefinition(type).requiresSupplier;
  const faltaProveedor = requiereProveedor && supplierId === null;

  const selectedJob = jobs.find((job) => job.id === selectedJobId) ?? null;

  const motivoBloqueo =
    uploadDisabledReason ??
    (faltaProveedor
      ? "Elige el proveedor al que pertenece la lista de precios antes de subir el archivo."
      : null);

  return (
    <div className="space-y-8">
      <Card>
        <CardHeader>
          <CardTitle>Nueva importación</CardTitle>
          <p className="text-sm text-muted-foreground">
            Elige qué archivo vas a cargar; la validación de formato ocurre antes de subirlo.
          </p>
        </CardHeader>

        <CardContent className="space-y-6">
          <ImportTypeSelector
            value={type}
            onChange={(next) => {
              setType(next);
              if (!importTypeDefinition(next).requiresSupplier) {
                setSupplierId(null);
              }
            }}
            suppliers={suppliers}
            supplierId={supplierId}
            onSupplierChange={setSupplierId}
          />

          <FileDropzone
            type={type}
            supplierId={supplierId}
            onUpload={onUpload}
            disabledReason={motivoBloqueo}
            onUploaded={() => startRefresh(() => router.refresh())}
          />
        </CardContent>
      </Card>

      <section aria-labelledby="historial-importaciones" className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="historial-importaciones" className="text-lg font-semibold text-foreground">
            Importaciones recientes
          </h2>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => startRefresh(() => router.refresh())}
            disabled={refrescando}
          >
            <RefreshCw aria-hidden="true" className={refrescando ? "motion-safe:animate-spin" : ""} />
            {refrescando ? "Actualizando…" : "Actualizar"}
          </Button>
        </div>

        <ImportJobsTable
          jobs={jobs}
          isLoading={isLoading}
          errorMessage={loadErrorMessage}
          selectedJobId={selectedJobId}
          onSelectJob={(jobId) => {
            setSelectedJobId(jobId);
            onSelectJob?.(jobId);
          }}
        />
      </section>

      {selectedJob ? (
        <section aria-labelledby="detalle-importacion" className="space-y-4">
          <h2 id="detalle-importacion" className="text-lg font-semibold text-foreground">
            Detalle de la importación
          </h2>
          <ImportSummary job={selectedJob} />
        </section>
      ) : null}
    </div>
  );
}
