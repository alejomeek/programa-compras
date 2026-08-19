import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Importaciones",
};

export default function Page() {
  return (
    <PageHeader
      title="Importaciones"
      description="Cargar SDOSXSUC, INVEPTOS o una lista de proveedor y seguir su procesamiento e incidencias. Sin contenido todavía: llega en la Fase 2."
    />
  );
}
