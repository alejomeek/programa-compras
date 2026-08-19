import type { Metadata } from "next";

import { LoginForm } from "@/app/(auth)/login/login-form";
import { AppLogo } from "@/components/layout/app-logo";
import { NotConfigured } from "@/components/layout/not-configured";
import { Card, CardContent, CardDescription, CardHeader } from "@/components/ui/card";
import { getSessionUser } from "@/lib/auth/session";
import { isSupabaseConfigured } from "@/lib/env";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Entrar",
};

/**
 * Pantalla de acceso.
 *
 * Es dinamica porque consulta la sesion: si el usuario ya entro, no tiene
 * sentido mostrarle el formulario.
 */
export const dynamic = "force-dynamic";

export default async function LoginPage() {
  // Sin configuracion no hay sesion que comprobar ni forma de entrar: se dice
  // por adelantado en vez de dejar que el usuario falle al enviar el formulario.
  if (!isSupabaseConfigured()) {
    return <NotConfigured />;
  }

  const user = await getSessionUser();
  if (user) {
    redirect("/dashboard");
  }

  return (
    <Card className="w-full max-w-sm">
      <CardHeader className="space-y-4">
        <AppLogo />
        <div className="space-y-1">
          <h1 className="text-xl font-semibold tracking-tight">Entrar</h1>
          <CardDescription>Usa el correo con el que te dieron acceso.</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <LoginForm />
      </CardContent>
    </Card>
  );
}
