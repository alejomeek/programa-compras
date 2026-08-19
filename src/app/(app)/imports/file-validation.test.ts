import { describe, expect, it } from "vitest";

import {
  MAX_IMPORT_FILE_BYTES,
  fileExtension,
  formatBytes,
  validateImportFile,
} from "./file-validation";

const UN_MEGA = 1024 * 1024;

describe("fileExtension", () => {
  it("devuelve la extension en minuscula y con punto", () => {
    expect(fileExtension("INVEPTOS.XLS")).toBe(".xls");
    expect(fileExtension("lista.XlSx")).toBe(".xlsx");
  });

  it("toma solo la ultima extension de un nombre compuesto", () => {
    expect(fileExtension("SDOSXSUC.2026.06.csv")).toBe(".csv");
  });

  it("devuelve vacio cuando no hay extension real", () => {
    expect(fileExtension("SDOSXSUC")).toBe("");
    expect(fileExtension(".gitignore")).toBe("");
    expect(fileExtension("archivo.")).toBe("");
  });
});

describe("formatBytes", () => {
  it("usa coma decimal (es-CO) y la unidad mas cercana", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2 * UN_MEGA)).toBe("2 MB");
    expect(formatBytes(2.5 * UN_MEGA)).toBe("2,5 MB");
    expect(formatBytes(MAX_IMPORT_FILE_BYTES)).toBe("25 MB");
  });

  it("no produce textos raros con valores no validos", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(-1)).toBe("0 B");
    expect(formatBytes(Number.NaN)).toBe("0 B");
  });
});

describe("validateImportFile", () => {
  it("acepta el archivo correcto de cada tipo", () => {
    expect(validateImportFile({ name: "SDOSXSUC.CSV", size: 2_800_000 }, "sdos_inventory")).toEqual({
      ok: true,
    });
    expect(validateImportFile({ name: "INVEPTOS.XLS", size: 31_151 }, "inveptos_sales")).toEqual({
      ok: true,
    });
    expect(
      validateImportFile({ name: "lista proveedor.xlsx", size: 65_536 }, "supplier_price_list"),
    ).toEqual({ ok: true });
    // La lista real de un proveedor puede venir como .xls legado.
    expect(
      validateImportFile({ name: "lista proveedor.xls", size: 65_536 }, "supplier_price_list"),
    ).toEqual({ ok: true });
  });

  it("no distingue mayusculas de minusculas en la extension", () => {
    expect(validateImportFile({ name: "sdosxsuc.csv", size: 10 }, "sdos_inventory").ok).toBe(true);
    expect(validateImportFile({ name: "SDOSXSUC.CsV", size: 10 }, "sdos_inventory").ok).toBe(true);
  });

  it("rechaza la extension que corresponde a OTRO tipo de importacion", () => {
    const resultado = validateImportFile(
      { name: "INVEPTOS.XLS", size: 31_151 },
      "sdos_inventory",
    );
    expect(resultado.ok).toBe(false);
    if (resultado.ok) return;
    expect(resultado.message).toContain("INVEPTOS.XLS");
    expect(resultado.message).toContain(".csv");
  });

  it("explica que extension se esperaba cuando el archivo no tiene ninguna", () => {
    const resultado = validateImportFile({ name: "INVEPTOS", size: 100 }, "inveptos_sales");
    expect(resultado.ok).toBe(false);
    if (resultado.ok) return;
    expect(resultado.message).toContain("extensión");
    expect(resultado.message).toContain(".xls");
  });

  it("nombra las dos extensiones posibles de la lista de proveedor", () => {
    const resultado = validateImportFile({ name: "lista.pdf", size: 100 }, "supplier_price_list");
    expect(resultado.ok).toBe(false);
    if (resultado.ok) return;
    expect(resultado.message).toContain(".xlsx");
    expect(resultado.message).toContain(".xls");
  });

  it("rechaza un archivo vacio", () => {
    const resultado = validateImportFile({ name: "SDOSXSUC.CSV", size: 0 }, "sdos_inventory");
    expect(resultado.ok).toBe(false);
    if (resultado.ok) return;
    expect(resultado.message).toContain("vacío");
  });

  it("rechaza un archivo por encima del maximo, diciendo cuanto pesa y cuanto se admite", () => {
    const resultado = validateImportFile(
      { name: "SDOSXSUC.CSV", size: MAX_IMPORT_FILE_BYTES + 1 },
      "sdos_inventory",
    );
    expect(resultado.ok).toBe(false);
    if (resultado.ok) return;
    expect(resultado.message).toContain("25 MB");
  });

  it("acepta exactamente el maximo (el limite no es estricto por debajo)", () => {
    expect(
      validateImportFile({ name: "SDOSXSUC.CSV", size: MAX_IMPORT_FILE_BYTES }, "sdos_inventory")
        .ok,
    ).toBe(true);
  });

  it("permite ajustar el maximo por parametro", () => {
    const resultado = validateImportFile({ name: "SDOSXSUC.CSV", size: 2_000 }, "sdos_inventory", {
      maxBytes: 1_000,
    });
    expect(resultado.ok).toBe(false);
  });

  it("rechaza un nombre vacio", () => {
    expect(validateImportFile({ name: "   ", size: 100 }, "sdos_inventory").ok).toBe(false);
  });

  it("siempre da un mensaje accionable, no un codigo", () => {
    const casos = [
      validateImportFile({ name: "x.pdf", size: 10 }, "sdos_inventory"),
      validateImportFile({ name: "x", size: 10 }, "inveptos_sales"),
      validateImportFile({ name: "x.csv", size: 0 }, "sdos_inventory"),
    ];
    for (const caso of casos) {
      expect(caso.ok).toBe(false);
      if (caso.ok) continue;
      expect(caso.message.length).toBeGreaterThan(30);
      expect(caso.message).toMatch(/[a-záéíóúñ]/i);
    }
  });
});
