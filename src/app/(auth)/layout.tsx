import type { ReactNode } from "react";

/** Layout de las pantallas sin sesion: sin sidebar, contenido centrado. */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-svh items-center justify-center bg-background px-4 py-10">
      {children}
    </div>
  );
}
