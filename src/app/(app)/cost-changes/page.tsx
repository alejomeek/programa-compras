import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Cambios de costo",
};

export default function Page() {
  return (
    <PageHeader
      title="Cambios de costo"
      description="Comparación del costo del proveedor contra el último costo TBC, sin tolerancia. Sin contenido todavía: llega en la Fase 4."
    />
  );
}
