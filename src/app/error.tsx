"use client";

import { useEffect } from "react";

import { Button } from "@/components/ui/button";

/**
 * Pantalla de error global. Muestra una causa y una accion concreta, nunca un
 * codigo crudo (checklist de accesibilidad §10.4).
 */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 text-center">
      <h1 className="text-2xl font-semibold tracking-tight">Algo salió mal</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        No se pudo cargar esta página. Vuelve a intentarlo; si el problema sigue, avisa a la persona
        que administra el sistema.
      </p>
      <Button onClick={reset}>Reintentar</Button>
    </div>
  );
}
