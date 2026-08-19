import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Catálogo",
};

export default function Page() {
  return (
    <PageHeader
      title="Catálogo"
      description="Productos nuevos, descontinuados o no encontrados y problemas de EAN. Sin contenido todavía: llega en la Fase 4."
    />
  );
}
