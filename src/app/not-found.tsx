import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="text-sm font-medium text-muted-foreground">Error 404</p>
      <h1 className="text-2xl font-semibold tracking-tight">Esta página no existe</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        Puede que el enlace esté mal escrito, que la página se haya movido o que tu usuario no tenga
        acceso a esta sección.
      </p>
      <Button asChild>
        <Link href="/dashboard">Volver al inicio</Link>
      </Button>
    </div>
  );
}
