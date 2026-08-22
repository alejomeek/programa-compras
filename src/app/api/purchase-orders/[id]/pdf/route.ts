import { NextResponse, type NextRequest } from "next/server";

import { requireActiveUser } from "@/lib/api/auth";
import { createClient } from "@/lib/supabase/server";
import { createAdminClient } from "@/lib/supabase/admin";

export const dynamic = "force-dynamic";

export async function GET(_request: NextRequest, { params }: { params: Promise<{ id: string }> }) {
  const auth = await requireActiveUser();
  if ("response" in auth) return auth.response;
  const { id } = await params;
  const supabase = await createClient();
  const { data: order, error } = await supabase
    .from("purchase_orders")
    .select("pdf_file_id")
    .eq("id", id)
    .maybeSingle();
  if (error) return NextResponse.json({ error: error.message }, { status: 500 });
  if (!order?.pdf_file_id) return NextResponse.json({ error: "La orden aún no tiene PDF." }, { status: 404 });

  const { data: file, error: fileError } = await supabase
    .from("files")
    .select("bucket, object_path")
    .eq("id", order.pdf_file_id)
    .maybeSingle();
  if (fileError || !file || file.bucket !== "purchase-order-pdfs") {
    return NextResponse.json({ error: "No se encontró el archivo PDF de la orden." }, { status: 404 });
  }
  const admin = createAdminClient();
  if (!admin) return NextResponse.json({ error: "La descarga de PDFs no está configurada." }, { status: 500 });
  const { data: signed, error: signedError } = await admin.storage
    .from("purchase-order-pdfs")
    .createSignedUrl(file.object_path, 120);
  if (signedError || !signed?.signedUrl) {
    return NextResponse.json({ error: signedError?.message ?? "No se pudo firmar el PDF." }, { status: 500 });
  }
  return NextResponse.redirect(signed.signedUrl);
}
