import { describe, expect, it } from "vitest";

import {
  ISSUE_CODES,
  anchorIdForCode,
  groupIssuesByCode,
  issueCopy,
  normalizeSeverity,
  summarizeIssues,
} from "./issues";
import type { ImportIssueRow } from "./types";

function issue(overrides: Partial<ImportIssueRow> & Pick<ImportIssueRow, "id" | "code">): ImportIssueRow {
  return {
    severity: "error",
    source: "INVEPTOS.XLS",
    rowNumber: null,
    ean: null,
    sku: null,
    productName: null,
    detail: null,
    ...overrides,
  };
}

describe("issueCopy", () => {
  it("cubre los seis codigos de import_issues.code (§6.3)", () => {
    expect([...ISSUE_CODES]).toHaveLength(6);
    for (const code of ISSUE_CODES) {
      const copy = issueCopy(code);
      expect(copy.title.length).toBeGreaterThan(0);
      // Titulo legible: nunca el codigo crudo con guiones bajos.
      expect(copy.title).not.toContain("_");
      // Accion concreta, no un enunciado del error (§10.4).
      expect(copy.action.length).toBeGreaterThan(40);
    }
  });

  it("explica el bloqueo por fecha invalida y por que se bloquea", () => {
    const copy = issueCopy("fecha_invalida");
    expect(copy.action).toContain("FDESDE");
    expect(copy.action.toLowerCase()).toContain("bloquea");
  });

  it("dice que un EAN duplicado excluye TODAS sus copias", () => {
    expect(issueCopy("ean_duplicado").action.toLowerCase()).toContain("todas");
  });

  it("humaniza un codigo que la UI todavia no conoce, sin dejarlo crudo", () => {
    const copy = issueCopy("columna_faltante");
    expect(copy.title).toBe("Columna faltante");
    expect(copy.title).not.toContain("_");
    expect(copy.action.length).toBeGreaterThan(40);
  });

  it("no revienta con un codigo vacio", () => {
    expect(issueCopy("").title).toBe("Incidencia sin clasificar");
  });
});

describe("normalizeSeverity", () => {
  it("acepta las tres severidades conocidas sin importar el formato", () => {
    expect(normalizeSeverity("error")).toBe("error");
    expect(normalizeSeverity(" WARNING ")).toBe("warning");
    expect(normalizeSeverity("Info")).toBe("info");
  });

  it("trata una severidad desconocida como error (sobre-avisar antes que esconder)", () => {
    expect(normalizeSeverity("critico")).toBe("error");
  });
});

describe("groupIssuesByCode", () => {
  const issues: ImportIssueRow[] = [
    issue({ id: "1", code: "ean_invalido", severity: "error", rowNumber: 12 }),
    issue({ id: "2", code: "tisuc_desconocido", severity: "warning", rowNumber: 3 }),
    issue({ id: "3", code: "ean_invalido", severity: "error", rowNumber: 5 }),
    issue({ id: "4", code: "tisuc_desconocido", severity: "warning", rowNumber: 40 }),
    issue({ id: "5", code: "tisuc_desconocido", severity: "warning", rowNumber: 41 }),
    issue({ id: "6", code: "costo_invalido", severity: "error", rowNumber: 9 }),
  ];

  it("agrupa por codigo y cuenta cada grupo", () => {
    const grupos = groupIssuesByCode(issues);
    expect(grupos.map((g) => g.code)).toEqual([
      "ean_invalido",
      "costo_invalido",
      "tisuc_desconocido",
    ]);
    expect(grupos.map((g) => g.count)).toEqual([2, 1, 3]);
  });

  it("ordena primero por gravedad y luego por volumen (los avisos van despues de los errores)", () => {
    const grupos = groupIssuesByCode(issues);
    expect(grupos[0].severity).toBe("error");
    expect(grupos[grupos.length - 1].severity).toBe("warning");
  });

  it("ordena las filas de cada grupo por numero de fila y deja al final las que no lo traen", () => {
    const grupos = groupIssuesByCode([
      issue({ id: "a", code: "ean_invalido", rowNumber: 30 }),
      issue({ id: "b", code: "ean_invalido", rowNumber: null }),
      issue({ id: "c", code: "ean_invalido", rowNumber: 4 }),
    ]);
    expect(grupos[0].issues.map((i) => i.id)).toEqual(["c", "a", "b"]);
  });

  it("un grupo mixto toma la severidad mas grave", () => {
    const grupos = groupIssuesByCode([
      issue({ id: "a", code: "ean_invalido", severity: "warning" }),
      issue({ id: "b", code: "ean_invalido", severity: "error" }),
    ]);
    expect(grupos[0].severity).toBe("error");
  });

  it("da a cada grupo titulo, accion y ancla para el resumen navegable", () => {
    const grupos = groupIssuesByCode(issues);
    for (const grupo of grupos) {
      expect(grupo.title).not.toContain("_");
      expect(grupo.action.length).toBeGreaterThan(40);
      expect(grupo.anchorId).toMatch(/^incidencias-[a-z0-9-]+$/);
    }
    expect(new Set(grupos.map((g) => g.anchorId)).size).toBe(grupos.length);
  });

  it("conserva el EAN como texto exacto, con sus ceros iniciales", () => {
    const grupos = groupIssuesByCode([
      issue({ id: "a", code: "ean_duplicado", ean: "0007894561230", rowNumber: 2 }),
    ]);
    expect(grupos[0].issues[0].ean).toBe("0007894561230");
  });

  it("devuelve lista vacia sin incidencias", () => {
    expect(groupIssuesByCode([])).toEqual([]);
  });
});

describe("anchorIdForCode", () => {
  it("produce un id valido y estable", () => {
    expect(anchorIdForCode("tisuc_desconocido")).toBe("incidencias-tisuc-desconocido");
    expect(anchorIdForCode("Comodín inválido")).toBe("incidencias-comodin-invalido");
    expect(anchorIdForCode("")).toBe("incidencias-sin-codigo");
  });
});

describe("summarizeIssues", () => {
  it("resume por severidad, en singular y plural", () => {
    expect(summarizeIssues([])).toBe("Sin incidencias.");
    expect(summarizeIssues([issue({ id: "a", code: "ean_invalido", severity: "error" })])).toBe(
      "1 error.",
    );
    expect(
      summarizeIssues([
        issue({ id: "a", code: "ean_invalido", severity: "error" }),
        issue({ id: "b", code: "ean_invalido", severity: "error" }),
        issue({ id: "c", code: "tisuc_desconocido", severity: "warning" }),
      ]),
    ).toBe("2 errores y 1 aviso.");
  });

  it("enumera las tres severidades cuando conviven", () => {
    expect(
      summarizeIssues([
        issue({ id: "a", code: "ean_invalido", severity: "error" }),
        issue({ id: "b", code: "tisuc_desconocido", severity: "warning" }),
        issue({ id: "c", code: "ean_duplicado", severity: "info" }),
      ]),
    ).toBe("1 error, 1 aviso y 1 nota.");
  });
});
