import { describe, expect, it } from "vitest";

import { formatCop, formatOrderDate } from "./purchase-order-format";

describe("purchase-order-format", () => {
  it("formatea importes COP sin depender de un componente cliente", () => {
    expect(formatCop("45600")).toBe("$ 45.600");
  });

  it("formatea la fecha de la orden en la zona operativa", () => {
    expect(formatOrderDate("2026-08-24T05:00:00.000Z")).toMatch(/24.*2026/);
  });
});
