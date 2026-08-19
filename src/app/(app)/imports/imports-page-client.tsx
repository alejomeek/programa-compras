"use client";

import { useState } from "react";

import { ImportsView, type ImportsViewProps } from "@/components/imports/imports-view";
import type { UploadHandler, UploadOutcome } from "@/components/imports/file-dropzone";
import { createClient } from "@/lib/supabase/client";
import { processingWarning } from "./processing-warning";
import type { ImportJobRow } from "./types";

type Props = Omit<ImportsViewProps, "onUpload" | "uploadDisabledReason" | "onSelectJob">;

/**
 * Envuelve `ImportsView` con la subida real (contrato §8/§11).
 *
 * Es Client Component SOLO porque `onUpload` es una función: no puede cruzar
 * de Server a Client Component (mismo límite que ya documentó `nav.ts` en
 * Fase 1 para los íconos). Todo lo demás — datos, tipos, validación — sigue
 * viniendo de `page.tsx` como props planas.
 *
 * Flujo real, en 3 llamadas:
 *  1. `POST /api/imports/upload-url` — pide una URL de subida firmada al
 *     bucket privado `source-files`. No crea nada en la base todavía.
 *  2. `supabase.storage.from(bucket).uploadToSignedUrl(...)` — sube el
 *     archivo con el token, usando el propio cliente del navegador (el mismo
 *     que ya usa toda la app, sin credenciales nuevas).
 *  3. `POST /api/imports` — el servidor descarga lo recién subido, calcula
 *     `sha256`/`size_bytes` (nunca confía en el cliente), crea `files` +
 *     `import_jobs`, y dispara el procesamiento.
 *
 * `onProgress` no se llama durante el paso 2: el SDK de Supabase sube con
 * `fetch`, que no expone progreso incremental. La barra queda indeterminada
 * en ese tramo — es preferible a inventar un porcentaje.
 *
 * También trae las incidencias BAJO DEMANDA: `jobs` llega desde `page.tsx`
 * sin `issues` (traerlas para las 50 filas de la lista sería una consulta
 * por fila que nadie va a mirar); al seleccionar un job se pide
 * `GET /api/imports/:id` una sola vez y se fusiona en el estado local.
 */
export function ImportsPageClient({ jobs: initialJobs, ...props }: Props) {
  const [jobs, setJobs] = useState<readonly ImportJobRow[]>(initialJobs);
  const [syncedFrom, setSyncedFrom] = useState(initialJobs);

  // `router.refresh()` (botón "Actualizar") vuelve a ejecutar `page.tsx` y nos
  // llega como una nueva prop `initialJobs`, no como un remount: `useState`
  // por sí solo no la recogería. Se ajusta DURANTE el render (patrón
  // recomendado por React para "resetear estado cuando cambia una prop"), no
  // en un efecto, para no pagar una vuelta de render extra. Se descartan las
  // incidencias ya cargadas a propósito: son del job tal como estaba antes.
  if (initialJobs !== syncedFrom) {
    setSyncedFrom(initialJobs);
    setJobs(initialJobs);
  }

  const onSelectJob = async (jobId: string) => {
    const current = jobs.find((job) => job.id === jobId);
    if (!current || current.issues !== undefined) return; // ya se pidieron

    try {
      const response = await fetch(`/api/imports/${jobId}`);
      if (!response.ok) return;
      const { job } = (await response.json()) as { job: ImportJobRow };
      setJobs((previous) => previous.map((item) => (item.id === jobId ? job : item)));
    } catch {
      // Sin conexión momentánea: el panel se queda en "no cargadas todavía"
      // y el usuario puede reintentar seleccionando el job de nuevo.
    }
  };

  const onUpload: UploadHandler = async ({ file, type, supplierId }, { onProgress }) => {
    const urlResponse = await fetch("/api/imports/upload-url", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ type, supplierId: supplierId ?? undefined, filename: file.name }),
    });
    if (!urlResponse.ok) {
      const body = await urlResponse.json().catch(() => ({}) as { error?: string });
      throw new Error(body.error ?? "No se pudo preparar la subida.");
    }
    const { bucket, objectPath, token } = (await urlResponse.json()) as {
      bucket: string;
      objectPath: string;
      token: string;
    };

    const supabase = createClient();
    const { error: uploadError } = await supabase.storage
      .from(bucket)
      .uploadToSignedUrl(objectPath, token, file);
    if (uploadError) {
      throw new Error(`No se pudo subir el archivo: ${uploadError.message}`);
    }

    const confirmResponse = await fetch("/api/imports", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        objectPath,
        type,
        supplierId: supplierId ?? undefined,
        originalName: file.name,
        mimeType: file.type || undefined,
      }),
    });
    if (!confirmResponse.ok) {
      const body = await confirmResponse.json().catch(() => ({}) as { error?: string });
      throw new Error(body.error ?? "No se pudo crear la importación.");
    }
    const confirmBody = (await confirmResponse.json()) as {
      processingTriggered: boolean;
      processingError: string | null;
    };

    onProgress(100);

    const warning = processingWarning(confirmBody);
    return warning ? ({ warning } satisfies UploadOutcome) : undefined;
  };

  return <ImportsView {...props} jobs={jobs} onUpload={onUpload} onSelectJob={onSelectJob} />;
}
