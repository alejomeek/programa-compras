import { describe, expect, it } from "vitest";

import { processingWarning } from "./processing-warning";

describe("processingWarning", () => {
  it("no hay aviso cuando el procesamiento sí se disparó", () => {
    expect(processingWarning({ processingTriggered: true })).toBeNull();
    expect(
      processingWarning({ processingTriggered: true, processingError: "no debería importar" }),
    ).toBeNull();
  });

  it("usa el mensaje del servidor cuando el procesamiento no se disparó", () => {
    expect(
      processingWarning({
        processingTriggered: false,
        processingError: "INTERNAL_API_SECRET no está configurado.",
      }),
    ).toBe("INTERNAL_API_SECRET no está configurado.");
  });

  it("cae en un mensaje genérico si el servidor no mandó detalle", () => {
    const mensaje = processingWarning({ processingTriggered: false, processingError: null });
    expect(mensaje).toContain("no se pudo iniciar");
  });

  it("también cae en el mensaje genérico si processingError no viene en la respuesta", () => {
    const mensaje = processingWarning({ processingTriggered: false });
    expect(mensaje).toContain("no se pudo iniciar");
  });
});
