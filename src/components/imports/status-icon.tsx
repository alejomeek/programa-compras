import { AlertTriangle, CheckCircle2, CircleHelp, Clock, Loader2 } from "lucide-react";

import type { StatusIconName } from "@/app/(app)/imports/job-status";

/**
 * Traduce el nombre logico de icono que devuelve `describeStatus()` a un icono
 * de Lucide ya resuelto a elemento.
 *
 * La logica pura (`job-status.ts`) devuelve un nombre y no un componente para
 * poder probarse en Node; el mapeo a JSX vive aqui, en la capa de vista.
 */
export function StatusIcon({ name, className = "size-3.5" }: { name: StatusIconName; className?: string }) {
  const props = { className, "aria-hidden": true as const };

  switch (name) {
    case "clock":
      return <Clock {...props} />;
    case "loader":
      // `animate-spin` solo decora: el texto "Procesando" es quien informa.
      return <Loader2 {...props} className={`${className} motion-safe:animate-spin`} />;
    case "check":
      return <CheckCircle2 {...props} />;
    case "alert":
      return <AlertTriangle {...props} />;
    default:
      return <CircleHelp {...props} />;
  }
}
