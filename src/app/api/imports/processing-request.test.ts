import { describe, expect, it } from "vitest";

import { processingRequestInit } from "./processing-request";

describe("processingRequestInit", () => {
  it("null si INTERNAL_API_SECRET no está configurado: nunca se llama sin secreto", () => {
    expect(
      processingRequestInit("job-1", {
        internalApiSecret: undefined,
        automationBypassSecret: "algo",
      }),
    ).toBeNull();
  });

  it("manda x-internal-secret y el jobId en el body, sin bypass si no hay esa variable", () => {
    const init = processingRequestInit("job-1", { internalApiSecret: "secreto-interno" });

    expect(init).not.toBeNull();
    expect(init?.method).toBe("POST");
    expect(init?.headers).toEqual({
      "content-type": "application/json",
      "x-internal-secret": "secreto-interno",
    });
    expect(init?.body).toBe(JSON.stringify({ jobId: "job-1" }));
  });

  it(
    "agrega x-vercel-protection-bypass cuando VERCEL_AUTOMATION_BYPASS_SECRET existe " +
      "(regresión: en Preview, sin este header, la Protección de Despliegue de Vercel " +
      "devuelve 401 antes de que este repo vea la petición — INTERNAL_API_SECRET no basta)",
    () => {
      const init = processingRequestInit("job-2", {
        internalApiSecret: "secreto-interno",
        automationBypassSecret: "bypass-de-vercel",
      });

      expect(init?.headers).toEqual({
        "content-type": "application/json",
        "x-internal-secret": "secreto-interno",
        "x-vercel-protection-bypass": "bypass-de-vercel",
      });
    },
  );

  it("no agrega el header de bypass si la variable viene vacía", () => {
    const init = processingRequestInit("job-3", {
      internalApiSecret: "secreto-interno",
      automationBypassSecret: "",
    });

    expect(init?.headers).toEqual({
      "content-type": "application/json",
      "x-internal-secret": "secreto-interno",
    });
  });
});
