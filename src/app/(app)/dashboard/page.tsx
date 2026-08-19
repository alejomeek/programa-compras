import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Inicio",
};

export default function Page() {
  return (
    <PageHeader
      title="Inicio"
      description="Corridas recientes, órdenes por estado, cambios de costo e importaciones que requieren atención. Sin contenido todavía: llega en fases posteriores."
    />
  );
}
