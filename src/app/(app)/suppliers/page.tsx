import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Proveedores",
};

export default function Page() {
  return (
    <PageHeader
      title="Proveedores"
      description="Crear y editar proveedores y consultar las versiones de su lista de precios. Sin contenido todavía: llega en la Fase 2."
    />
  );
}
