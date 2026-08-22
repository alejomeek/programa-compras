import { describe, expect, it } from "vitest";

import { productNamesByEan } from "@/lib/purchase-runs/product-names";

describe("productNamesByEan", () => {
  it("toma el nombre original de la lista de precios", () => {
    const names = productNamesByEan([
      { ean: "7700000000011", raw: { Nombre: "  Rompecabezas  " } },
    ]);

    expect(names.get("7700000000011")).toBe("Rompecabezas");
  });

  it("omite filas sin nombre utilizable", () => {
    const names = productNamesByEan([
      { ean: "7700000000011", raw: { Nombre: "" } },
      { ean: "7700000000012", raw: null },
      { ean: "7700000000013", raw: { nombre: "clave distinta" } },
    ]);

    expect(names.size).toBe(0);
  });
});
