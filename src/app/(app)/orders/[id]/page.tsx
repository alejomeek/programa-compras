import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { PageHeader } from "@/components/page-header";
import { PurchaseOrderDetailView } from "@/components/purchase-orders/purchase-order-detail";
import { canWrite } from "@/lib/auth/roles";
import { getSessionUser } from "@/lib/auth/session";

export const metadata: Metadata = { title: "Detalle de orden" };
export const dynamic = "force-dynamic";

export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!id) notFound();
  const user = await getSessionUser();
  return <div className="space-y-8"><PageHeader title="Detalle de orden" description="Revisa el snapshot, emite la orden o consulta su PDF." /><PurchaseOrderDetailView orderId={id} canWrite={Boolean(user && canWrite(user.profile.role))} /></div>;
}
