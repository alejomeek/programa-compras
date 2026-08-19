"use client";

import { useId, useRef, useState, type DragEvent } from "react";
import { FileUp, Upload, X } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import {
  acceptAttribute,
  importTypeDefinition,
  type ImportType,
} from "@/app/(app)/imports/import-types";
import { formatBytes, validateImportFile } from "@/app/(app)/imports/file-validation";
import { cn } from "@/lib/utils";

/**
 * Zona de carga de archivo: arrastrar y soltar + selector clasico.
 *
 * Validaciones en cliente ANTES de pedir la URL firmada (extension segun el
 * tipo y tamano maximo, `file-validation.ts`). No sustituyen a las del
 * servidor: solo evitan gastar una subida completa y dan el mensaje en el
 * momento, junto al campo.
 *
 * Accesibilidad (§10.4):
 *  - `<input type="file">` real con `<label>` asociado; el area punteada es
 *    decoracion, el control accesible es el input.
 *  - Errores junto al campo, con `role="alert"`, `aria-invalid` y
 *    `aria-describedby`.
 *  - Progreso en una region `aria-live="polite"` con texto, ademas de la barra.
 *
 * La subida real llega por la prop `onUpload`, que el lead conecta a
 * `POST /api/imports` → `PUT` a Storage → `POST /api/imports/:id/process`
 * (contrato §8 y §11). Sin esa prop el componente queda deshabilitado y lo
 * dice: no simula una carga contra un backend inexistente.
 */
export type UploadInput = {
  file: File;
  type: ImportType;
  supplierId: string | null;
};

export type UploadHandler = (
  input: UploadInput,
  helpers: {
    /** Porcentaje 0–100. Si el handler no lo llama, la barra queda indeterminada. */
    onProgress: (percent: number) => void;
  },
) => Promise<void>;

export type FileDropzoneProps = {
  type: ImportType;
  supplierId: string | null;
  onUpload?: UploadHandler;
  /** Motivo por el que la carga esta bloqueada (falta proveedor, sin backend…). */
  disabledReason?: string | null;
  /** Se llama al terminar una carga con exito, para refrescar la lista. */
  onUploaded?: () => void;
};

type Phase = "idle" | "uploading" | "done" | "error";

export function FileDropzone({
  type,
  supplierId,
  onUpload,
  disabledReason,
  onUploaded,
}: FileDropzoneProps) {
  const inputId = useId();
  const errorId = `${inputId}-error`;
  const hintId = `${inputId}-hint`;
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [percent, setPercent] = useState<number | null>(null);
  const [dragging, setDragging] = useState(false);

  const definition = importTypeDefinition(type);
  const bloqueado = Boolean(disabledReason) || !onUpload;
  const subiendo = phase === "uploading";

  function seleccionar(candidate: File | undefined) {
    setPhase("idle");
    setPercent(null);

    if (!candidate) {
      setFile(null);
      setError(null);
      return;
    }

    const resultado = validateImportFile(
      { name: candidate.name, size: candidate.size },
      type,
    );

    if (!resultado.ok) {
      setFile(null);
      setError(resultado.message);
      return;
    }

    setFile(candidate);
    setError(null);
  }

  function limpiar() {
    setFile(null);
    setError(null);
    setPhase("idle");
    setPercent(null);
    if (inputRef.current) {
      inputRef.current.value = "";
    }
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (bloqueado || subiendo) {
      return;
    }
    const dropped = event.dataTransfer.files?.[0];
    seleccionar(dropped);
    // Refleja el archivo soltado en el `<input>` para que ambos digan lo mismo.
    if (dropped && inputRef.current) {
      try {
        inputRef.current.files = event.dataTransfer.files;
      } catch {
        // Algunos navegadores no permiten asignar `files`; el estado ya quedo bien.
      }
    }
  }

  async function subir() {
    if (!file || !onUpload) {
      return;
    }

    setPhase("uploading");
    setPercent(null);
    setError(null);

    try {
      await onUpload(
        { file, type, supplierId },
        { onProgress: (value) => setPercent(clampPercent(value)) },
      );
      setPhase("done");
      setPercent(100);
      onUploaded?.();
    } catch (cause) {
      setPhase("error");
      setPercent(null);
      setError(
        cause instanceof Error && cause.message
          ? cause.message
          : "No se pudo subir el archivo. Revisa tu conexión e inténtalo de nuevo.",
      );
    }
  }

  const mensajeEstado = estadoTextual({ phase, percent, fileName: file?.name ?? null });

  return (
    <div className="space-y-3">
      <Label htmlFor={inputId}>Archivo de {definition.sourceName}</Label>

      <div
        onDragOver={(event) => {
          event.preventDefault();
          if (!bloqueado && !subiendo) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "rounded-lg border-2 border-dashed bg-card p-6 transition-colors",
          dragging ? "border-primary bg-accent/50" : "border-border",
          bloqueado && "opacity-70",
        )}
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <FileUp aria-hidden="true" className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            Arrastra aquí el archivo o elígelo desde tu equipo.
          </p>

          <input
            ref={inputRef}
            id={inputId}
            type="file"
            accept={acceptAttribute(type)}
            disabled={bloqueado || subiendo}
            onChange={(event) => seleccionar(event.target.files?.[0])}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy(error ? errorId : null, hintId)}
            className={cn(
              "block w-full max-w-md cursor-pointer rounded-md border border-input bg-background text-sm text-foreground",
              "file:mr-3 file:cursor-pointer file:rounded-l-md file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-medium file:text-secondary-foreground",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
              "disabled:cursor-not-allowed disabled:opacity-60",
              error && "border-destructive",
            )}
          />

          <p id={hintId} className="text-xs text-muted-foreground">
            Se aceptan archivos {definition.extensions.join(" o ")} de hasta 25 MB. El archivo se
            guarda sin modificar y queda como respaldo de la importación.
          </p>
        </div>
      </div>

      {error ? (
        <p id={errorId} role="alert" className="text-sm font-medium text-destructive">
          {error}
        </p>
      ) : null}

      {file ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-border bg-card px-3 py-2">
          <p className="text-sm text-foreground">
            <span className="font-medium">{file.name}</span>{" "}
            <span className="text-muted-foreground">({formatBytes(file.size)})</span>
          </p>
          <Button type="button" variant="ghost" size="sm" onClick={limpiar} disabled={subiendo}>
            <X aria-hidden="true" />
            Quitar archivo
          </Button>
        </div>
      ) : null}

      {disabledReason ? (
        <Alert>
          <AlertTitle>Carga no disponible todavía</AlertTitle>
          <AlertDescription>{disabledReason}</AlertDescription>
        </Alert>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" onClick={subir} disabled={!file || bloqueado || subiendo}>
          <Upload aria-hidden="true" />
          {subiendo ? "Subiendo…" : "Subir e importar"}
        </Button>
      </div>

      {/* Region viva: anuncia validacion, progreso y resultado sin mover el foco. */}
      <div aria-live="polite" className="space-y-2">
        <p className="text-sm text-muted-foreground">{mensajeEstado}</p>
        {phase === "uploading" || phase === "done" ? (
          <Progress
            value={percent ?? 0}
            aria-label="Progreso de la carga"
            aria-valuetext={
              percent === null ? "Subiendo, progreso desconocido" : `${percent}% completado`
            }
          />
        ) : null}
      </div>
    </div>
  );
}

function clampPercent(value: number): number {
  if (!Number.isFinite(value)) return 0;
  return Math.min(100, Math.max(0, Math.round(value)));
}

function describedBy(...ids: (string | null | undefined)[]): string | undefined {
  const list = ids.filter((id): id is string => Boolean(id));
  return list.length > 0 ? list.join(" ") : undefined;
}

function estadoTextual({
  phase,
  percent,
  fileName,
}: {
  phase: Phase;
  percent: number | null;
  fileName: string | null;
}): string {
  switch (phase) {
    case "uploading":
      return percent === null
        ? `Subiendo ${fileName ?? "el archivo"}…`
        : `Subiendo ${fileName ?? "el archivo"}: ${percent}% completado.`;
    case "done":
      return "Archivo subido. La importación quedó en cola: su estado aparece en la tabla de abajo.";
    case "error":
      return "La carga no se completó.";
    default:
      return fileName
        ? `Archivo listo para subir: ${fileName}.`
        : "Ningún archivo seleccionado todavía.";
  }
}
