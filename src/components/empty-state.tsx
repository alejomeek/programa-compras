import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Estado vacio generico (contrato §10.2: `EmptyState` transversal).
 *
 * Un estado vacio explica por que no hay nada y que hacer a continuacion; no
 * es una tabla en blanco. El icono llega ya resuelto a elemento por la misma
 * razon que en `StatusBadge`.
 */
export type EmptyStateProps = {
  icon?: ReactNode;
  title: string;
  description?: string;
  /** Accion sugerida (boton o enlace). Opcional. */
  action?: ReactNode;
  className?: string;
};

export function EmptyState({ icon, title, description, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-lg border border-dashed border-border bg-card px-6 py-10 text-center",
        className,
      )}
    >
      {icon ? <div className="text-muted-foreground">{icon}</div> : null}
      <div className="space-y-1">
        <p className="text-sm font-semibold text-foreground">{title}</p>
        {description ? (
          <p className="mx-auto max-w-md text-sm text-muted-foreground">{description}</p>
        ) : null}
      </div>
      {action}
    </div>
  );
}
