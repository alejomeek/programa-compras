import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Compras sugeridas",
};

export default function Page() {
  return (
    <PageHeader
      title="Compras sugeridas"
      description="Crear una corrida eligiendo proveedor y fuentes, y consultar sus sugerencias. Sin contenido todavía: llega en la Fase 3."
    />
  );
}
