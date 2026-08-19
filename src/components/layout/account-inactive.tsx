import { UserX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

/**
 * Pantalla para un usuario cuyo perfil esta desactivado (`profiles.active = false`).
 *
 * Se muestra en vez de redirigir a `/login`: la sesion de Supabase sigue siendo
 * valida, asi que `/login` lo devolveria al area protegida y se formaria un
 * bucle de redirecciones. La unica salida ofrecida es cerrar sesion.
 *
 * Nota: esto es una barrera de INTERFAZ. Segun el contrato §6.3 las personas se
 * desactivan en vez de borrarse; si ademas debe cortarse su lectura de datos,
 * eso corresponde a las politicas RLS de `db-auth`, no a esta pantalla.
 */
export function AccountInactive({ fullName }: { fullName: string }) {
  return (
    <div className="flex min-h-svh items-center justify-center px-4 py-10">
      <Card className="w-full max-w-lg">
        <CardHeader className="flex-row items-start gap-3 space-y-0">
          <UserX aria-hidden="true" className="mt-0.5 size-5 shrink-0 text-destructive" />
          <CardTitle className="text-lg">Tu acceso está desactivado</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 text-sm text-muted-foreground">
          <p>
            La cuenta de <span className="font-medium text-foreground">{fullName}</span> existe, pero
            está marcada como inactiva, así que no puede entrar al Programa de Compras.
          </p>
          <p>
            Si crees que es un error, pide a quien administra el sistema que vuelva a activarla desde
            Configuración.
          </p>
          <form action="/auth/signout" method="post">
            <Button type="submit" variant="outline">
              Cerrar sesión
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
