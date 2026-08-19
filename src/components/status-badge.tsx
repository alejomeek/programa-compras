import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

/**
 * Insignia de estado generica (contrato §10.2: `StatusBadge` transversal).
 *
 * Reglas del checklist §10.4 que este componente hace cumplir:
 *  - El estado SIEMPRE lleva texto; el color y el icono acompanan, no sustituyen.
 *  - El icono llega como `ReactNode` ya renderizado (`<Check />`), no como
 *    referencia al componente: asi un Server Component puede construirlo y
 *    pasarlo a un Client Component sin romper la serializacion (es el bug real
 *    que aparecio en la Fase 1, documentado en `src/lib/nav.ts`).
 *
 * No sabe nada de importaciones: lo reusan las demas pantallas (corridas,
 * ordenes, cambios de costo) con sus propios tonos.
 */
export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";

const TONE_CLASSES: Record<StatusTone, string> = {
  neutral: "border-border bg-secondary text-secondary-foreground",
  info: "border-primary/30 bg-accent text-primary",
  success: "border-emerald-300 bg-emerald-50 text-emerald-900",
  warning: "border-amber-300 bg-amber-50 text-amber-900",
  danger: "border-destructive/30 bg-destructive/10 text-destructive",
};

export type StatusBadgeProps = {
  /** Texto visible. Obligatorio: nunca hay estado solo-color. */
  label: string;
  tone?: StatusTone;
  /** Icono ya resuelto a elemento. Se marca `aria-hidden` por quien lo crea. */
  icon?: ReactNode;
  className?: string;
};

export function StatusBadge({ label, tone = "neutral", icon, className }: StatusBadgeProps) {
  return (
    <Badge variant="outline" className={cn("gap-1.5 px-2 py-1", TONE_CLASSES[tone], className)}>
      {icon}
      <span>{label}</span>
    </Badge>
  );
}
