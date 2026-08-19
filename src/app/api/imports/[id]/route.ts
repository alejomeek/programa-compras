import { NextResponse } from "next/server";

import type { ImportIssueRow, ImportJobRow } from "@/app/(app)/imports/types";
import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";

export const dynamic = "force-dynamic";

/**
 * Un trabajo con sus incidencias, para el panel de detalle/actualizar de
 * `/imports`. `issues` siempre viene como arreglo (incluso vacío): a
 * diferencia de `GET /api/imports` (lista, sin incidencias por costo de
 * traerlas todas), aquí sí se resolvieron.
 */
export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const { id } = await params;
  const supabase = await createClient();

  const { data: job, error: jobError } = await supabase
    .from("import_jobs")
    .select(
      "id, type, status, supplier_id, period_start, period_end, rows_total, rows_valid, rows_rejected, error_message, created_at, finished_at, suppliers(name)",
    )
    .eq("id", id)
    .maybeSingle();

  if (jobError) {
    return NextResponse.json({ error: jobError.message }, { status: 500 });
  }
  if (!job) {
    return NextResponse.json({ error: "Importación no encontrada." }, { status: 404 });
  }

  const { data: issuesData, error: issuesError } = await supabase
    .from("import_issues")
    .select("id, severity, code, source, row_number, ean, sku, product_name, detail")
    .eq("import_job_id", id)
    .order("row_number", { ascending: true, nullsFirst: true });

  if (issuesError) {
    return NextResponse.json({ error: issuesError.message }, { status: 500 });
  }

  const issues: ImportIssueRow[] = (issuesData ?? []).map((row) => ({
    id: row.id,
    severity: row.severity,
    code: row.code,
    source: row.source,
    rowNumber: row.row_number,
    ean: row.ean,
    sku: row.sku,
    productName: row.product_name,
    detail: row.detail,
  }));

  const result: ImportJobRow = {
    id: job.id,
    type: job.type,
    status: job.status,
    supplierName: embeddedOne<{ name: string }>(job.suppliers)?.name ?? null,
    periodStart: job.period_start,
    periodEnd: job.period_end,
    rowsTotal: job.rows_total,
    rowsValid: job.rows_valid,
    rowsRejected: job.rows_rejected,
    errorMessage: job.error_message,
    createdAt: job.created_at,
    finishedAt: job.finished_at,
    issues,
  };

  return NextResponse.json({ job: result });
}
