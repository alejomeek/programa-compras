import type { Metadata } from "next";

import { PageHeader } from "@/components/page-header";

export const metadata: Metadata = {
  title: "Órdenes de compra",
};

export default function Page() {
  return (
    <PageHeader
      title="Órdenes de compra"
      description="Borradores, órdenes emitidas y canceladas, con su PDF y su valor total. Sin contenido todavía: llega en la Fase 4."
    />
  );
}
