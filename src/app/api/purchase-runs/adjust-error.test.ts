import { describe, expect, it } from "vitest";

import { mapAdjustError } from "./adjust-error";

describe("mapAdjustError", () => {
  it("40001 (serialization_failure) -> 409, marcado como conflicto de versión", () => {
    const result = mapAdjustError({ code: "40001", message: "raw" });
    expect(result.status).toBe(409);
    expect(result.isVersionConflict).toBe(true);
  });

  it("P0002 (no_data_found) -> 404", () => {
    const result = mapAdjustError({ code: "P0002", message: "raw" });
    expect(result.status).toBe(404);
    expect(result.isVersionConflict).toBe(false);
  });

  it("55000 (object_not_in_prerequisite_state) -> 409, corrida bloqueada", () => {
    const result = mapAdjustError({ code: "55000", message: "raw" });
    expect(result.status).toBe(409);
    expect(result.isVersionConflict).toBe(false);
  });

  it("42501 (insufficient_privilege) -> 403", () => {
    const result = mapAdjustError({ code: "42501", message: "raw" });
    expect(result.status).toBe(403);
  });

  it("23514 (check_violation) -> 400", () => {
    const result = mapAdjustError({ code: "23514", message: "raw" });
    expect(result.status).toBe(400);
  });

  it("código desconocido -> 500 con el mensaje crudo", () => {
    const result = mapAdjustError({ code: "XX000", message: "algo inesperado" });
    expect(result.status).toBe(500);
    expect(result.error).toBe("algo inesperado");
  });

  it("sin código -> 500 con el mensaje crudo", () => {
    const result = mapAdjustError({ message: "sin code" });
    expect(result.status).toBe(500);
    expect(result.error).toBe("sin code");
  });
});
