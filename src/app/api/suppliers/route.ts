import { NextResponse, type NextRequest } from "next/server";

import { isAdmin } from "@/lib/auth/roles";
import { requireWriter } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import type { SupplierRow } from "@/app/(app)/suppliers/types";

export const dynamic = "force-dynamic";

type CreateSupplierRequest = {
  name?: string;
  tbcCode?: string;
  nit?: string | null;
};

/**
 * CRUD mínimo de proveedores (hallazgo post Fase 3, ver `types.ts`): crear +
 * listar. Solo `admin` crea (RLS `suppliers_insert_admin`, contrato §7,
 * mismo espejo temprano que `requireWriter()` ya documenta); cualquier
 * usuario autenticado activo lista.
 */
export async function GET() {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("suppliers")
    .select("id, name, tbc_code, nit, active, created_at")
    .order("name");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  const suppliers: SupplierRow[] = (data ?? []).map((row) => ({
    id: row.id,
    name: row.name,
    tbcCode: row.tbc_code,
    nit: row.nit,
    active: row.active,
    createdAt: row.created_at,
  }));

  return NextResponse.json({ suppliers });
}

export async function POST(request: NextRequest) {
  const auth = await requireWriter();
  if ("response" in auth) return auth.response;
  const { user } = auth;

  if (!isAdmin(user.profile.role)) {
    return NextResponse.json(
      { error: "Solo un administrador puede crear proveedores." },
      { status: 403 },
    );
  }

  let body: CreateSupplierRequest;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Cuerpo de la petición inválido." }, { status: 400 });
  }

  const name = body.name?.trim();
  const tbcCode = body.tbcCode?.trim();
  const nit = body.nit?.trim() || null;

  if (!name || !tbcCode) {
    return NextResponse.json({ error: "Faltan name o tbcCode." }, { status: 400 });
  }
  if (!/^\d{3}$/.test(tbcCode)) {
    return NextResponse.json(
      { error: "El comodín TBC debe ser exactamente 3 dígitos." },
      { status: 400 },
    );
  }

  const supabase = await createClient();
  const { data, error } = await supabase
    .from("suppliers")
    .insert({ name, tbc_code: tbcCode, nit, created_by: user.id })
    .select("id, name, tbc_code, nit, active, created_at")
    .single();

  if (error) {
    // 23505 = unique_violation (name o tbc_code repetido, ambos unique en 0004).
    const status = error.code === "23505" ? 409 : 500;
    return NextResponse.json({ error: error.message }, { status });
  }

  const supplier: SupplierRow = {
    id: data.id,
    name: data.name,
    tbcCode: data.tbc_code,
    nit: data.nit,
    active: data.active,
    createdAt: data.created_at,
  };

  return NextResponse.json({ supplier }, { status: 201 });
}
