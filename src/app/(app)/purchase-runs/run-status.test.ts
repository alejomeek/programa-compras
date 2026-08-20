import { describe, expect, it } from "vitest";

import {
  PURCHASE_RUN_STATUSES,
  describeLineStatus,
  describeRunStatus,
  isAdjustable,
  isPurchaseRunStatus,
} from "./run-status";

describe("describeRunStatus", () => {
  it("cubre los 4 estados del contrato §6.3", () => {
    expect([...PURCHASE_RUN_STATUSES]).toEqual(["draft", "calculated", "locked", "cancelled"]);
    for (const status of PURCHASE_RUN_STATUSES) {
      const descripcion = describeRunStatus(status);
      expect(descripcion.label.length).toBeGreaterThan(0);
      expect(descripcion.description.length).toBeGreaterThan(0);
    }
  });

  it("cada estado tiene etiqueta e ícono propios: el color nunca es el único portador (§10.4)", () => {
    const etiquetas = PURCHASE_RUN_STATUSES.map((status) => describeRunStatus(status).label);
    const iconos = PURCHASE_RUN_STATUSES.map((status) => describeRunStatus(status).icon);
    expect(new Set(etiquetas).size).toBe(PURCHASE_RUN_STATUSES.length);
    expect(new Set(iconos).size).toBe(PURCHASE_RUN_STATUSES.length);
  });

  it("un estado desconocido cae en una descripción neutra, no rompe la pantalla", () => {
    const descripcion = describeRunStatus("archivada-por-error");
    expect(descripcion.tone).toBe("neutral");
    expect(descripcion.icon).toBe("question");
  });
});

describe("isPurchaseRunStatus", () => {
  it("reconoce los 4 estados válidos y rechaza cualquier otro texto", () => {
    for (const status of PURCHASE_RUN_STATUSES) {
      expect(isPurchaseRunStatus(status)).toBe(true);
    }
    expect(isPurchaseRunStatus("pending")).toBe(false);
  });
});

describe("isAdjustable", () => {
  it("draft y calculated admiten ajustes; locked y cancelled no", () => {
    expect(isAdjustable("draft")).toBe(true);
    expect(isAdjustable("calculated")).toBe(true);
    expect(isAdjustable("locked")).toBe(false);
    expect(isAdjustable("cancelled")).toBe(false);
  });
});

describe("describeLineStatus", () => {
  it("ok y no_price tienen etiquetas distintas", () => {
    expect(describeLineStatus("ok")).toBe("OK");
    expect(describeLineStatus("no_price")).not.toBe(describeLineStatus("ok"));
  });

  it("un estado desconocido no rompe, cae en 'Desconocido'", () => {
    expect(describeLineStatus("algo-nuevo")).toBe("Desconocido");
  });
});
