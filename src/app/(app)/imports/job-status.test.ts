import { describe, expect, it } from "vitest";

import {
  IMPORT_STATUSES,
  describeStatus,
  formatBusinessDate,
  formatCount,
  formatDateTime,
  formatPeriod,
  isImportStatus,
  isInProgress,
  periodDays,
} from "./job-status";

describe("describeStatus", () => {
  it("cubre los cuatro estados del contrato §6.3", () => {
    expect([...IMPORT_STATUSES]).toEqual(["pending", "processing", "completed", "failed"]);
    for (const status of IMPORT_STATUSES) {
      const descripcion = describeStatus(status);
      expect(descripcion.label.length).toBeGreaterThan(0);
      expect(descripcion.description.length).toBeGreaterThan(0);
    }
  });

  it("cada estado tiene texto e icono propios: el color nunca es el unico portador (§10.4)", () => {
    const etiquetas = IMPORT_STATUSES.map((status) => describeStatus(status).label);
    const iconos = IMPORT_STATUSES.map((status) => describeStatus(status).icon);
    expect(new Set(etiquetas).size).toBe(IMPORT_STATUSES.length);
    expect(new Set(iconos).size).toBe(IMPORT_STATUSES.length);
  });

  it("no muestra el valor crudo de un estado que la UI no conoce", () => {
    const descripcion = describeStatus("cancelled");
    expect(descripcion.label).toBe("Estado desconocido");
    expect(descripcion.label).not.toContain("cancelled");
    expect(descripcion.icon).toBe("question");
    expect(descripcion.status).toBe("cancelled");
  });

  it("marca como fallido con tono destructivo solo a failed", () => {
    expect(describeStatus("failed").tone).toBe("danger");
    expect(describeStatus("completed").tone).toBe("success");
  });
});

describe("isImportStatus / isInProgress", () => {
  it("reconoce los estados del enum", () => {
    expect(isImportStatus("processing")).toBe(true);
    expect(isImportStatus("procesando")).toBe(false);
  });

  it("solo pending y processing siguen en curso", () => {
    expect(isInProgress("pending")).toBe(true);
    expect(isInProgress("processing")).toBe(true);
    expect(isInProgress("completed")).toBe(false);
    expect(isInProgress("failed")).toBe(false);
  });
});

describe("formatBusinessDate", () => {
  it("convierte YYYY-MM-DD a dd/mm/aaaa sin correr el dia por zona horaria", () => {
    expect(formatBusinessDate("2026-06-01")).toBe("01/06/2026");
    expect(formatBusinessDate("2026-01-01")).toBe("01/01/2026");
  });

  it("devuelve null si falta la fecha o no parsea", () => {
    expect(formatBusinessDate(null)).toBeNull();
    expect(formatBusinessDate("")).toBeNull();
    expect(formatBusinessDate("01/06/2026")).toBeNull();
    expect(formatBusinessDate("2026-06-01T00:00:00Z")).toBeNull();
  });
});

describe("periodDays", () => {
  it("cuenta el periodo inclusivo, como el motor (§3.4)", () => {
    expect(periodDays("2026-06-01", "2026-06-30")).toBe(30);
    expect(periodDays("2026-06-01", "2026-06-01")).toBe(1);
  });

  it("cruza fin de mes y ano bisiesto", () => {
    expect(periodDays("2026-12-28", "2027-01-03")).toBe(7);
    expect(periodDays("2028-02-01", "2028-02-29")).toBe(29);
  });

  it("devuelve null ante periodo invertido o fecha ilegible: no cae a 1 dia", () => {
    // El fallback silencioso a period_days = 1 es exactamente el bug que el
    // contrato §3.2 manda eliminar; la UI tampoco lo reintroduce.
    expect(periodDays("2026-06-30", "2026-06-01")).toBeNull();
    expect(periodDays("no-es-fecha", "2026-06-30")).toBeNull();
    expect(periodDays(null, "2026-06-30")).toBeNull();
    expect(periodDays("2026-06-01", null)).toBeNull();
  });
});

describe("formatPeriod", () => {
  it("muestra rango y dias en singular o plural", () => {
    expect(formatPeriod("2026-06-01", "2026-06-30")).toBe("01/06/2026 – 30/06/2026 · 30 días");
    expect(formatPeriod("2026-06-01", "2026-06-01")).toBe("01/06/2026 – 01/06/2026 · 1 día");
  });

  it("avisa cuando todavia no hay periodo detectado", () => {
    expect(formatPeriod(null, null)).toBe("Sin período detectado");
    expect(formatPeriod("2026-06-01", null)).toBe("Sin período detectado");
  });

  it("marca el periodo invertido como invalido en vez de mostrar un conteo", () => {
    expect(formatPeriod("2026-06-30", "2026-06-01")).toBe("30/06/2026 – 01/06/2026 · período inválido");
  });
});

describe("formatDateTime", () => {
  it("usa hora de Bogota, no la del equipo que abre la pagina", () => {
    expect(formatDateTime("2026-06-30T23:30:00Z")).toBe("30/06/2026, 18:30");
  });

  it("devuelve raya si no hay instante o no parsea", () => {
    expect(formatDateTime(null)).toBe("—");
    expect(formatDateTime("")).toBe("—");
    expect(formatDateTime("ayer")).toBe("—");
  });
});

describe("formatCount", () => {
  it("agrupa miles en formato es-CO", () => {
    expect(formatCount(1234)).toBe("1.234");
    expect(formatCount(0)).toBe("0");
  });

  it("distingue 'sin procesar' (null) de cero", () => {
    expect(formatCount(null)).toBe("—");
    expect(formatCount(undefined)).toBe("—");
    expect(formatCount(0)).toBe("0");
  });
});
