import { createHash } from "node:crypto";

import { NextResponse, type NextRequest } from "next/server";

import { isImportType, importTypeDefinition } from "@/app/(app)/imports/import-types";
import type { ImportJobRow } from "@/app/(app)/imports/types";
import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { embeddedOne } from "@/lib/supabase/relations";

export const dynamic = "force-dynamic";

const SOURCE_BUCKET = "source-files";

type CreateImportRequest = {
  objectPath?: string;
  type?: string;
  supplierId?: string;
  originalName?: string;
  mimeType?: string;
};

/**
 * Paso 2 de 2 de la carga (contrato §8): el archivo YA está en Storage
 * (subido con el token de `POST /api/imports/upload-url`). Esta ruta:
 *
 * 1. Descarga el objeto con el cliente del propio usuario (la policy
 *    `source_files_select_owner` de `data-model` lo permite: acaba de
 *    subirlo bajo su propio uid).
 * 2. Calcula `sha256`/`size_bytes` EN SERVIDOR — nunca se confía en un valor
 *    que mande el cliente (contrato §8).
 * 3. Inserta `files` (con esos valores reales) y `import_jobs` en `pending`.
 * 4. Dispara el procesamiento (función Python) y responde con el resultado
 *    que ya se conoce en el momento de contestar — el pipeline es síncrono
 *    desde el punto de vista de esta petición, no hay cola ni polling.
 *
 * Si el paso 4 no está disponible (función de proceso no desplegada
 * todavía), la importación queda creada y en `pending`: no se inventa un
 * éxito que no ocurrió, y `processingTriggered: false` se lo dice al cliente.
 */
export async function POST(request: NextRequest) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { user } = auth;

  let body: CreateImportRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }

  const { objectPath, type, supplierId, originalName, mimeType } = body;

  if (!type || !isImportType(type)) {
    return NextResponse.json({ error: "type inválido." }, { status: 400 });
  }
  const definition = importTypeDefinition(type);
  if (definition.requiresSupplier && !supplierId) {
    return NextResponse.json(
      { error: `${definition.label} requiere un proveedor.` },
      { status: 400 },
    );
  }
  if (!objectPath || typeof objectPath !== "string") {
    return NextResponse.json(
      { error: "Falta objectPath (¿se completó la subida?)." },
      { status: 400 },
    );
  }
  // El tercer segmento de la ruta debe ser el propio uid: coincide con la
  // policy de Storage y evita que alguien intente confirmar el archivo de
  // otra persona pasando una ruta ajena.
  if (objectPath.split("/")[2] !== user.id) {
    return NextResponse.json(
      { error: "La ruta del archivo no corresponde a tu usuario." },
      { status: 403 },
    );
  }

  const supabase = await createClient();

  const { data: blob, error: downloadError } = await supabase.storage
    .from(SOURCE_BUCKET)
    .download(objectPath);
  if (downloadError || !blob) {
    return NextResponse.json(
      {
        error:
          `No se pudo leer el archivo recién subido: ${downloadError?.message ?? "desconocido"}. ` +
          "Vuelve a intentar la carga.",
      },
      { status: 502 },
    );
  }
  const bytes = Buffer.from(await blob.arrayBuffer());
  const sha256 = createHash("sha256").update(bytes).digest("hex");

  const { data: fileRow, error: fileError } = await supabase
    .from("files")
    .insert({
      bucket: SOURCE_BUCKET,
      object_path: objectPath,
      original_name: originalName?.trim() || objectPath.split("/").pop()!,
      mime_type: mimeType ?? null,
      size_bytes: bytes.length,
      sha256,
      uploaded_by: user.id,
    })
    .select("id")
    .single();
  if (fileError || !fileRow) {
    return NextResponse.json(
      { error: `No se pudo registrar el archivo: ${fileError?.message}.` },
      { status: 500 },
    );
  }

  const { data: jobRow, error: jobError } = await supabase
    .from("import_jobs")
    .insert({
      type,
      supplier_id: supplierId ?? null,
      file_id: fileRow.id,
      created_by: user.id,
    })
    .select(
      "id, type, status, supplier_id, period_start, period_end, rows_total, rows_valid, rows_rejected, error_message, created_at, finished_at",
    )
    .single();
  if (jobError || !jobRow) {
    return NextResponse.json(
      { error: `No se pudo crear la importación: ${jobError?.message}.` },
      { status: 500 },
    );
  }

  const processing = await triggerProcessing(request, jobRow.id);

  return NextResponse.json(
    {
      job: await toImportJobRow(supabase, jobRow),
      processingTriggered: processing.triggered,
      processingError: processing.triggered ? null : processing.message,
    },
    { status: 201 },
  );
}

/**
 * Trabajos existentes para la tabla de `/imports`, más recientes primero.
 * `supplierName` ya viene resuelto (join): los componentes nunca reciben un
 * id crudo para mostrar.
 */
export async function GET() {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("import_jobs")
    .select(
      "id, type, status, period_start, period_end, rows_total, rows_valid, rows_rejected, error_message, created_at, finished_at, suppliers(name)",
    )
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const jobs: ImportJobRow[] = (data ?? []).map((row) => ({
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

  return NextResponse.json({ jobs });
}

async function toImportJobRow(
  supabase: Awaited<ReturnType<typeof createClient>>,
  jobRow: {
    id: string;
    type: string;
    status: string;
    supplier_id: string | null;
    period_start: string | null;
    period_end: string | null;
    rows_total: number | null;
    rows_valid: number | null;
    rows_rejected: number | null;
    error_message: string | null;
    created_at: string;
    finished_at: string | null;
  },
): Promise<ImportJobRow> {
  let supplierName: string | null = null;
  if (jobRow.supplier_id) {
    const { data } = await supabase
      .from("suppliers")
      .select("name")
      .eq("id", jobRow.supplier_id)
      .maybeSingle();
    supplierName = data?.name ?? null;
  }
  return {
    id: jobRow.id,
    type: jobRow.type as ImportJobRow["type"],
    status: jobRow.status as ImportJobRow["status"],
    supplierName,
    periodStart: jobRow.period_start,
    periodEnd: jobRow.period_end,
    rowsTotal: jobRow.rows_total,
    rowsValid: jobRow.rows_valid,
    rowsRejected: jobRow.rows_rejected,
    errorMessage: jobRow.error_message,
    createdAt: jobRow.created_at,
    finishedAt: jobRow.finished_at,
  };
}

/**
 * Dispara `api/imports_process.py` (función Python en Vercel, contrato §11).
 *
 * NO forma parte de esta app Next.js: es una función serverless aparte que
 * Vercel expone en la misma URL base porque vive bajo `/api`. Se autentica
 * con un secreto compartido (`INTERNAL_API_SECRET`) para que no sea invocable
 * públicamente — nunca con `service_role` en un header, eso viaja solo entre
 * servidores, nunca al navegador.
 *
 * Si la función no responde (todavía no desplegada, `INTERNAL_API_SECRET` sin
 * configurar), la importación queda creada en `pending` y esta función
 * informa el fallo sin lanzar: crear el registro sí funcionó, y eso no debe
 * perderse por un problema de despliegue del otro componente.
 */
async function triggerProcessing(
  request: NextRequest,
  jobId: string,
): Promise<{ triggered: boolean; message?: string }> {
  const secret = process.env.INTERNAL_API_SECRET;
  if (!secret) {
    return {
      triggered: false,
      message:
        "INTERNAL_API_SECRET no está configurado: el procesamiento automático " +
        "todavía no está conectado. La importación quedó creada en estado pendiente.",
    };
  }
  try {
    const response = await fetch(new URL("/api/imports_process", request.nextUrl.origin), {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-internal-secret": secret,
      },
      body: JSON.stringify({ jobId }),
    });
    if (!response.ok) {
      return {
        triggered: false,
        message: `El procesamiento respondió ${response.status}. La importación quedó en pendiente.`,
      };
    }
    return { triggered: true };
  } catch (error) {
    return {
      triggered: false,
      message: `No se pudo contactar el procesamiento: ${(error as Error).message}.`,
    };
  }
}
