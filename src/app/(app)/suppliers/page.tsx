import type { Metadata } from "next";

import { SuppliersPageClient } from "./suppliers-page-client";
import { PageHeader } from "@/components/page-header";
import { getSessionUser } from "@/lib/auth/session";
import { isAdmin } from "@/lib/auth/roles";
import { createClient } from "@/lib/supabase/server";
import type { SupplierRow } from "./types";

export const metadata: Metadata = {
  title: "Proveedores",
};

export const dynamic = "force-dynamic";

/**
 * `/suppliers` — alcance MÍNIMO (hallazgo post Fase 3): crear + listar
 * proveedores, nada de edición ni versiones de lista de precios (eso sigue
 * fuera de alcance — ningún agente lo tuvo asignado en el plan original,
 * contrato §4). Sin esto, `/purchase-runs` no tenía ningún proveedor para
 * ofrecer en su selector: crear una lista de precios en `/imports` ya
 * necesita un `supplier_id` que antes solo se podía insertar a mano por SQL.
 *
 * Solo `admin` crea (RLS `suppliers_insert_admin`); cualquiera con sesión
 * activa lista, igual que el resto del catálogo.
 */
export default async function Page() {
  const [user, supabase] = await Promise.all([getSessionUser(), createClient()]);

  const { data, error } = await supabase
    .from("suppliers")
    .select("id, name, tbc_code, nit, active, created_at")
    .order("name");

  const suppliers: SupplierRow[] = (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    tbcCode: row.tbc_code,
    nit: row.nit,
    active: row.active,
    createdAt: row.created_at,
  }));

  return (
    <div className="space-y-8">
      <PageHeader
        title="Proveedores"
        description="Catálogo de proveedores: comodín TBC y NIT. Crear una lista de precios en Importaciones o una corrida en Compras sugeridas necesita elegir uno de aquí."
      />
      <SuppliersPageClient
        suppliers={suppliers}
        loadErrorMessage={error ? error.message : null}
        canCreate={isAdmin(user?.profile.role ?? "viewer")}
      />
    </div>
  );
}
