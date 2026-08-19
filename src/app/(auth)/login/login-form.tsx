"use client";

import { useActionState } from "react";
import { useFormStatus } from "react-dom";
import { AlertCircle } from "lucide-react";

import { signIn } from "@/app/(auth)/login/actions";
import { INITIAL_LOGIN_STATE } from "@/app/(auth)/login/login-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function SubmitButton() {
  const { pending } = useFormStatus();

  return (
    <Button type="submit" className="w-full" disabled={pending}>
      {pending ? "Entrando…" : "Entrar"}
    </Button>
  );
}

/**
 * Formulario de acceso.
 *
 * Accesibilidad (contrato §10.4): cada campo tiene `<label>` asociado real (el
 * placeholder no es una etiqueta), el error se anuncia en una region
 * `aria-live` y se enlaza a ambos campos con `aria-describedby` + `aria-invalid`.
 */
export function LoginForm() {
  const [state, formAction] = useActionState(signIn, INITIAL_LOGIN_STATE);
  const hasError = state.error !== null;
  const errorId = "login-error";

  return (
    <form action={formAction} className="space-y-4" noValidate>
      <div className="space-y-2">
        <Label htmlFor="email">Correo electrónico</Label>
        <Input
          id="email"
          name="email"
          type="email"
          autoComplete="username"
          required
          aria-invalid={hasError || undefined}
          aria-describedby={hasError ? errorId : undefined}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="password">Contraseña</Label>
        <Input
          id="password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          aria-invalid={hasError || undefined}
          aria-describedby={hasError ? errorId : undefined}
        />
      </div>

      <div aria-live="polite" role="status">
        {hasError ? (
          <p
            id={errorId}
            className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive"
          >
            <AlertCircle aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
            <span>{state.error}</span>
          </p>
        ) : null}
      </div>

      <SubmitButton />
    </form>
  );
}
