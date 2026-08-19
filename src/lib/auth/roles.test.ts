import { describe, expect, it } from "vitest";

import {
  DEFAULT_ROLE,
  canWrite,
  isAdmin,
  isRole,
  normalizeRole,
  roleLabel,
} from "@/lib/auth/roles";
import { ROLES } from "@/types/profile";

describe("isRole", () => {
  it("acepta los tres roles del contrato §6.3", () => {
    for (const role of ROLES) {
      expect(isRole(role)).toBe(true);
    }
  });

  it("rechaza valores que no son roles", () => {
    for (const value of ["ADMIN", "administrador", "", null, undefined, 0, {}]) {
      expect(isRole(value)).toBe(false);
    }
  });
});

describe("normalizeRole", () => {
  it("conserva un rol valido", () => {
    expect(normalizeRole("admin")).toBe("admin");
    expect(normalizeRole("buyer")).toBe("buyer");
    expect(normalizeRole("viewer")).toBe("viewer");
  });

  it("degrada al rol de MENOR privilegio ante un valor desconocido", () => {
    // Regla de seguridad: un dato corrupto o una columna renombrada jamas debe
    // ascender a nadie a admin.
    for (const value of [null, undefined, "superadmin", "ADMIN", 42]) {
      expect(normalizeRole(value)).toBe("viewer");
    }
    expect(DEFAULT_ROLE).toBe("viewer");
  });
});

describe("isAdmin", () => {
  it("solo es cierto para admin", () => {
    expect(isAdmin("admin")).toBe(true);
    expect(isAdmin("buyer")).toBe(false);
    expect(isAdmin("viewer")).toBe(false);
  });
});

describe("canWrite", () => {
  it("permite escribir a admin y buyer, nunca a viewer", () => {
    expect(canWrite("admin")).toBe(true);
    expect(canWrite("buyer")).toBe(true);
    expect(canWrite("viewer")).toBe(false);
  });
});

describe("roleLabel", () => {
  it("devuelve una etiqueta en espanol para cada rol", () => {
    expect(roleLabel("admin")).toBe("Administrador");
    expect(roleLabel("buyer")).toBe("Comprador");
    expect(roleLabel("viewer")).toBe("Consulta");
  });
});
