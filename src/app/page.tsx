import { redirect } from "next/navigation";

/**
 * La raiz no tiene contenido propio: envia a `/dashboard`, que ya vive en el
 * segmento protegido y redirige a `/login` si no hay sesion.
 */
export default function RootPage() {
  redirect("/dashboard");
}
