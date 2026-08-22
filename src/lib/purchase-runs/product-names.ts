/**
 * La lista de precios conserva el nombre que entregó el proveedor en `raw`.
 * `purchase_run_lines.product_id` es opcional, por lo que no puede ser la
 * única fuente para mostrarlo en corridas reales o históricas.
 */
export function productNamesByEan(
  items: readonly { ean: string; raw: unknown }[],
): ReadonlyMap<string, string> {
  const names = new Map<string, string>();

  for (const item of items) {
    const name = productNameFromRaw(item.raw);
    if (name && !names.has(item.ean)) names.set(item.ean, name);
  }

  return names;
}

function productNameFromRaw(raw: unknown): string | null {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;

  const value = (raw as Record<string, unknown>).Nombre;
  if (typeof value !== "string") return null;

  const name = value.trim();
  return name || null;
}
