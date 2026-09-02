/**
 * Presencia de un EAN en el catálogo operativo de TBC. `SDOSXSUC` es la
 * fuente acordada para ese catálogo: contiene también productos sin stock.
 *
 * `unavailable` evita afirmar que un producto no existe cuando todavía no
 * hay una fotografía activa de SDOSXSUC (o no pudo consultarse).
 */
export type TbcCatalogStatus = "found" | "not_found" | "unavailable";

export function tbcCatalogStatusForEan(
  ean: string,
  catalogEans: ReadonlySet<string> | null,
): TbcCatalogStatus {
  if (catalogEans === null) return "unavailable";
  return catalogEans.has(ean) ? "found" : "not_found";
}
