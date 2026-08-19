import { describe, expect, it } from "vitest";

import {
  IMPORT_TYPES,
  IMPORT_TYPE_DEFINITIONS,
  acceptAttribute,
  importTypeDefinition,
  importTypeLabel,
  isImportType,
} from "./import-types";

describe("IMPORT_TYPES", () => {
  it("son exactamente los tres valores del enum de import_jobs.type (§6.3)", () => {
    expect([...IMPORT_TYPES].sort()).toEqual([
      "inveptos_sales",
      "sdos_inventory",
      "supplier_price_list",
    ]);
  });

  it("hay una definicion por tipo, sin duplicados", () => {
    expect(IMPORT_TYPE_DEFINITIONS).toHaveLength(IMPORT_TYPES.length);
    const values = IMPORT_TYPE_DEFINITIONS.map((item) => item.value);
    expect(new Set(values).size).toBe(values.length);
  });

  it("solo la lista de precios exige proveedor", () => {
    const conProveedor = IMPORT_TYPE_DEFINITIONS.filter((item) => item.requiresSupplier);
    expect(conProveedor.map((item) => item.value)).toEqual(["supplier_price_list"]);
  });

  it("cada tipo declara sus extensiones en minuscula y con punto", () => {
    for (const definition of IMPORT_TYPE_DEFINITIONS) {
      expect(definition.extensions.length).toBeGreaterThan(0);
      for (const extension of definition.extensions) {
        expect(extension).toMatch(/^\.[a-z0-9]+$/);
      }
    }
  });

  it("respeta los formatos reales del contrato §3.1-3.3", () => {
    expect(importTypeDefinition("sdos_inventory").extensions).toEqual([".csv"]);
    expect(importTypeDefinition("inveptos_sales").extensions).toEqual([".xls"]);
    expect(importTypeDefinition("supplier_price_list").extensions).toEqual([".xlsx", ".xls"]);
  });
});

describe("isImportType", () => {
  it("acepta los del enum y rechaza cualquier otro", () => {
    expect(isImportType("inveptos_sales")).toBe(true);
    expect(isImportType("ventas")).toBe(false);
    expect(isImportType("")).toBe(false);
  });
});

describe("importTypeLabel", () => {
  it("devuelve la etiqueta legible del tipo", () => {
    expect(importTypeLabel("sdos_inventory")).toBe("Inventario TBC (SDOSXSUC)");
  });

  it("nunca muestra el valor crudo de un tipo desconocido", () => {
    const label = importTypeLabel("otra_cosa");
    expect(label).toBe("Tipo no reconocido");
    expect(label).not.toContain("otra_cosa");
  });
});

describe("acceptAttribute", () => {
  it("lista las extensiones separadas por coma para el input file", () => {
    expect(acceptAttribute("supplier_price_list")).toBe(".xlsx,.xls");
  });
});
