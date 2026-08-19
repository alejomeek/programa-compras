import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Plus_Jakarta_Sans } from "next/font/google";

import "./globals.css";

/**
 * Plus Jakarta Sans se carga con `next/font/google` (contrato §10.1): se
 * autoaloja en el build, asi que no depende de que la fuente este instalada en
 * el equipo de quien usa la app ni de una peticion a un CDN externo.
 */
const plusJakartaSans = Plus_Jakarta_Sans({
  variable: "--font-plus-jakarta-sans",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Programa de Compras",
    template: "%s · Programa de Compras",
  },
  description: "Programa de Compras — Jugando y Educando",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // `lang="es"` es obligatorio por el checklist de accesibilidad (§10.4).
  return (
    <html lang="es" className={`${plusJakartaSans.variable} h-full`}>
      <body className="min-h-svh">{children}</body>
    </html>
  );
}
