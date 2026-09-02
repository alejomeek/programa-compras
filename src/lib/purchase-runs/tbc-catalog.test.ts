import { describe, expect, it } from "vitest";

import { tbcCatalogStatusForEan } from "@/lib/purchase-runs/tbc-catalog";

describe("tbcCatalogStatusForEan", () => {
  it("identifica un EAN incluido en el último SDOSXSUC activo", () => {
    expect(tbcCatalogStatusForEan("7700000000011", new Set(["7700000000011"]))).toBe("found");
  });

  it("marca como no encontrado únicamente si el catálogo está disponible", () => {
    expect(tbcCatalogStatusForEan("7700000000011", new Set(["7700000000099"]))).toBe("not_found");
  });

  it("no produce un falso negativo si no hay fotografía activa", () => {
    expect(tbcCatalogStatusForEan("7700000000011", null)).toBe("unavailable");
  });
});
