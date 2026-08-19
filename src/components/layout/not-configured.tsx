import { AlertTriangle } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { missingSupabaseEnvVars } from "@/lib/env";

/**
 * Pantalla mostrada cuando la aplicacion no tiene conexion configurada con
 * Supabase.
 *
 * Es deliberadamente honesta: no simula una sesion, no muestra datos de ejemplo
 * y no deja pasar a nadie. Enumera los NOMBRES de las variables que faltan
 * (jamas sus valores) para que quien administra el sistema sepa que corregir.
 */
export function NotConfigured() {
  const missing = missingSupabaseEnvVars();

  return (
    <div className="flex min-h-svh items-center justify-center px-4 py-10">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-start gap-3 space-y-0">
          <AlertTriangle aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-destructive" />
          <CardTitle className="text-lg">La aplicación no está configurada</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            No hay conexión con la base de datos, así que no se puede comprobar quién eres ni
            mostrar información. Nadie puede entrar hasta que se corrija.
          </p>
          {missing.length > 0 ? (
            <div className="space-y-2">
              <p className="font-medium text-foreground">Faltan estas variables de entorno:</p>
              <ul className="list-inside list-disc space-y-1 font-mono text-xs">
                {missing.map((name) => (
                  <li key={name}>{name}</li>
                ))}
              </ul>
            </div>
          ) : null}
          <p>
            Quien administra el sistema debe copiar <code className="font-mono">.env.example</code>{" "}
            a <code className="font-mono">.env.local</code> con los valores del proyecto de Supabase
            y volver a iniciar la aplicación.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
