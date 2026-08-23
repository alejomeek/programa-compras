import { describe, expect, it } from "vitest";

import { NAV_ITEMS, isNavItemActive, navItemsForRole } from "@/lib/nav";

describe("NAV_ITEMS", () => {
  it("tiene las 7 entradas de menú activas", () => {
    expect(NAV_ITEMS).toHaveLength(7);
    expect(NAV_ITEMS.map((item) => item.href)).toEqual([
      "/dashboard",
      "/suppliers",
      "/imports",
      "/purchase-runs",
      "/orders",
      "/cost-changes",
      "/settings",
    ]);
  });

  it("no repite rutas ni etiquetas", () => {
    expect(new Set(NAV_ITEMS.map((i) => i.href)).size).toBe(NAV_ITEMS.length);
    expect(new Set(NAV_ITEMS.map((i) => i.label)).size).toBe(NAV_ITEMS.length);
  });

  it("marca como adminOnly unicamente Configuracion", () => {
    const adminOnly = NAV_ITEMS.filter((item) => item.adminOnly);
    expect(adminOnly.map((item) => item.href)).toEqual(["/settings"]);
  });
});

describe("navItemsForRole", () => {
  it("admin ve las 7 entradas", () => {
    expect(navItemsForRole("admin")).toHaveLength(7);
  });

  it("buyer y viewer no ven Configuracion", () => {
    for (const role of ["buyer", "viewer"] as const) {
      const hrefs = navItemsForRole(role).map((item) => item.href);
      expect(hrefs).toHaveLength(6);
      expect(hrefs).not.toContain("/settings");
    }
  });

  it("solo filtra: conserva el orden del menu", () => {
    const hrefs = navItemsForRole("viewer").map((item) => item.href);
    expect(hrefs).toEqual([
      "/dashboard",
      "/suppliers",
      "/imports",
      "/purchase-runs",
      "/orders",
      "/cost-changes",
    ]);
  });
});

describe("isNavItemActive", () => {
  it("marca la entrada de la ruta exacta", () => {
    expect(isNavItemActive("/suppliers", "/suppliers")).toBe(true);
    expect(isNavItemActive("/suppliers", "/orders")).toBe(false);
  });

  it("mantiene activa la entrada padre en una subruta", () => {
    // /purchase-runs/[id] no esta en el menu: debe iluminar "Compras sugeridas".
    expect(isNavItemActive("/purchase-runs", "/purchase-runs/abc-123")).toBe(true);
  });

  it("exige coincidencia exacta en Inicio", () => {
    expect(isNavItemActive("/dashboard", "/dashboard")).toBe(true);
    expect(isNavItemActive("/dashboard", "/dashboard/algo")).toBe(false);
  });

  it("respeta el limite de segmento y no activa por prefijo de texto", () => {
    expect(isNavItemActive("/orders", "/orders-archive")).toBe(false);
    expect(isNavItemActive("/cost-changes", "/cost-changes-history")).toBe(false);
  });
});
