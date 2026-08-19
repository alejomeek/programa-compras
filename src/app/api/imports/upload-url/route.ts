import { randomUUID } from "node:crypto";

import { NextResponse, type NextRequest } from "next/server";

import { isImportType, importTypeDefinition } from "@/app/(app)/imports/import-types";
import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";

export const dynamic = "force-dynamic";

const SOURCE_BUCKET = "source-files";

type UploadUrlRequest = {
  type?: string;
  supplierId?: string;
  filename?: string;
};

/**
 * Paso 1 de 2 de la carga (contrato §8): pide una URL de subida firmada al
 * bucket privado `source-files`, SIN crear todavía filas en `files`ni en
 * `import_jobs`.
 *
 * Por qué no se crea `files` aquí: `files.sha256`/`files.size_bytes` son
 * `not null` en el esquema (0005_files.sql) — no hay un valor real de
 * ninguno de los dos hasta que el archivo termina de subirse. Crear la fila
 * antes obligaría a inventar un hash provisional, justo lo que el contrato
 * prohíbe ("no se confía en el cliente"). La fila se crea en
 * `POST /api/imports`, después de que el archivo ya está en Storage.
 *
 * La ruta de objeto sigue la convención de la policy de `data-model`
 * (`0011_storage_buckets.sql`): `{yyyy}/{mm}/{uploader_id}/{uuid}.{ext}` — el
 * tercer segmento debe ser el uid de quien sube, o la policy de Storage
 * deniega el `insert`.
 */
export async function POST(request: NextRequest) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { user } = auth;

  let body: UploadUrlRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }

  const { type, supplierId, filename } = body;

  if (!type || !isImportType(type)) {
    return NextResponse.json(
      { error: "type debe ser uno de: sdos_inventory, inveptos_sales, supplier_price_list." },
      { status: 400 },
    );
  }
  const definition = importTypeDefinition(type);
  if (definition.requiresSupplier && !supplierId) {
    return NextResponse.json(
      { error: `${definition.label} requiere elegir un proveedor.` },
      { status: 400 },
    );
  }
  if (!filename || typeof filename !== "string" || !filename.trim()) {
    return NextResponse.json({ error: "Falta el nombre del archivo." }, { status: 400 });
  }

  const extension = filename.includes(".") ? filename.split(".").pop()!.toLowerCase() : "";
  if (!extension || !definition.extensions.includes(`.${extension}`)) {
    return NextResponse.json(
      {
        error:
          `${definition.label} espera un archivo con extensión ` +
          `${definition.extensions.join(" o ")}, no ".${extension}".`,
      },
      { status: 400 },
    );
  }

  const now = new Date();
  const yyyy = String(now.getFullYear());
  const mm = String(now.getMonth() + 1).padStart(2, "0");
  const objectPath = `${yyyy}/${mm}/${user.id}/${randomUUID()}.${extension}`;

  const supabase = await createClient();
  const { data, error } = await supabase.storage
    .from(SOURCE_BUCKET)
    .createSignedUploadUrl(objectPath);

  if (error || !data) {
    return NextResponse.json(
      { error: `No se pudo preparar la subida: ${error?.message ?? "error desconocido"}.` },
      { status: 502 },
    );
  }

  return NextResponse.json({
    bucket: SOURCE_BUCKET,
    objectPath,
    token: data.token,
  });
}
