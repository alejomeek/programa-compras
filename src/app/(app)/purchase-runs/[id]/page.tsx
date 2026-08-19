import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Detalle de la corrida",
};

/**
 * Vista central de una corrida (contrato §10.2): tabla producto x ubicacion con
 * cantidad final editable. No aparece en el menu; se llega desde
 * `/purchase-runs`. Sin contenido todavia: llega en la Fase 3.
 */
export default async function PurchaseRunDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <PageHeader
      title="Detalle de la corrida"
      description={`Corrida ${id}. Tabla por producto y punto con ventas, días objetivo, compra sugerida y cantidad final. Sin contenido todavía: llega en la Fase 3.`}
    />
  );
}
