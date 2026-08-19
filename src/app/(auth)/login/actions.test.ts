import { describe, expect, it } from "vitest";

import * as actions from "@/app/(auth)/login/actions";

describe("modulo 'use server' de login", () => {
  it("solo exporta funciones async en tiempo de ejecucion", () => {
    // Next.js rechaza en build cualquier export runtime que no sea una
    // funcion async en un archivo "use server" (los tipos no cuentan: se
    // borran en compilacion). Regresion: INITIAL_LOGIN_STATE se exportaba
    // aqui como objeto plano y rompia el build.
    const runtimeExports = Object.entries(actions);
    expect(runtimeExports.length).toBeGreaterThan(0);

    for (const [name, value] of runtimeExports) {
      expect(typeof value, `export "${name}" debe ser una funcion`).toBe("function");
      expect(
        value.constructor?.name,
        `export "${name}" debe ser una funcion async`,
      ).toBe("AsyncFunction");
    }
  });

  it("expone signIn", () => {
    expect(actions.signIn).toBeInstanceOf(Function);
  });
});
