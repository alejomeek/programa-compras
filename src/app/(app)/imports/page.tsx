import type { Metadata } from "next";

import { ImportsPageClient } from "./imports-page-client";
import { PageHeader } from "@/components/page-header";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";
import type { ImportJobRow, SupplierOption } from "./types";

export const metadata: Metadata = {
  title: "Importaciones",
};

export const dynamic = "force-dynamic";

/**
 * `/imports` — carga de archivos de origen y seguimiento de `import_jobs`
 * (contrato §10.2).
 *
 * Consulta `import_jobs` (con el nombre de proveedor ya resuelto por join) y
 * `suppliers` directamente con el cliente de servidor — RLS decide qué ve
 * cada rol, esta página no filtra nada por su cuenta. Las incidencias NO se
 * traen aquí (costaría una consulta por fila mostrada); el detalle las pide
 * bajo demanda a `GET /api/imports/:id` cuando el usuario selecciona un job
 * — ver `ImportSummary`/`imports-view.tsx`, que ya esperan `issues`
 * `undefined` como "no cargadas todavía".
 *
 * La subida (`onUpload`) es una función, así que no puede cruzar de este
 * Server Component a `ImportsView` (Client Component): se conecta en
 * `imports-page-client.tsx`, igual que el ícono de `nav.ts` en Fase 1.
 */
export default async function Page() {
  const supabase = await createClient();

  const [{ data: jobsData, error: jobsError }, { data: suppliersData }] = await Promise.all([
    supabase
      .from("import_jobs")
      .select(
        "id, type, status, period_start, period_end, rows_total, rows_valid, rows_rejected, error_message, created_at, finished_at, suppliers(name)",
      )
      .order("created_at", { ascending: false })
      .limit(50),
    supabase.from("suppliers").select("id, name").eq("active", true).order("name"),
  ]);

  const jobs: ImportJobRow[] = (jobsData ?? []).map((row) => ({
    id: row.id,
    type: row.type,
    status: row.status,
    supplierName: embeddedOne<{ name: string }>(row.suppliers)?.name ?? null,
    periodStart: row.period_start,
    periodEnd: row.period_end,
    rowsTotal: row.rows_total,
    rowsValid: row.rows_valid,
    rowsRejected: row.rows_rejected,
    errorMessage: row.error_message,
    createdAt: row.created_at,
    finishedAt: row.finished_at,
  }));

  const suppliers: SupplierOption[] = suppliersData ?? [];

  return (
    <>
      <PageHeader
        title="Importaciones"
        description="Carga los archivos de TBC y las listas de precios de proveedor, y sigue su procesamiento, el período detectado y sus incidencias."
      />

      <ImportsPageClient
        jobs={jobs}
        suppliers={suppliers}
        loadErrorMessage={jobsError ? jobsError.message : null}
      />
    </>
  );
}
