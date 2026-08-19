"use client";

import { useState } from "react";
import Image from "next/image";

import { cn } from "@/lib/utils";

/** Nombre de la aplicacion, en un solo sitio para no desincronizar titulo y marca. */
export const APP_NAME = "Programa de Compras";
const APP_OWNER = "Jugando y Educando";

/**
 * Marca de la aplicacion: logo de 36px con radio 8px + nombre (contrato §10.3).
 *
 * Si la imagen no carga, cae a una marca tipografica con las iniciales para que
 * la cabecera del sidebar nunca quede vacia.
 */
export function AppLogo({ className }: { className?: string }) {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <div className={cn("flex items-center gap-3", className)}>
      {imageFailed ? (
        <span
          aria-hidden="true"
          className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-primary text-sm font-bold text-primary-foreground"
        >
          JE
        </span>
      ) : (
        <Image
          src="/logo.png"
          alt={APP_OWNER}
          width={36}
          height={36}
          priority
          className="size-9 shrink-0 rounded-lg object-contain"
          onError={() => setImageFailed(true)}
        />
      )}
      <span className="flex min-w-0 flex-col leading-tight">
        <span className="truncate text-sm font-semibold text-foreground">{APP_NAME}</span>
        <span className="truncate text-xs text-muted-foreground">{APP_OWNER}</span>
      </span>
    </div>
  );
}
