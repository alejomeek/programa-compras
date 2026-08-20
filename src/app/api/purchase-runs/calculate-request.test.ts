import { describe, expect, it } from "vitest";

import { calculateRequestInit } from "./calculate-request";

const BODY = {
  supplierId: "sup-1",
  salesImportId: "sales-1",
  priceListId: "pl-1",
  inventorySnapshotId: null,
  targetDays: { CEDI: 30 },
  createdBy: "user-1",
};

describe("calculateRequestInit", () => {
  it("null si INTERNAL_API_SECRET no está configurado: nunca se llama sin secreto", () => {
    expect(
      calculateRequestInit(BODY, { internalApiSecret: undefined, automationBypassSecret: "algo" }),
    ).toBeNull();
  });

  it("manda x-internal-secret y el body serializado, sin bypass si no hay esa variable", () => {
    const init = calculateRequestInit(BODY, { internalApiSecret: "secreto-interno" });

    expect(init).not.toBeNull();
    expect(init?.method).toBe("POST");
    expect(init?.headers).toEqual({
      "content-type": "application/json",
      "x-internal-secret": "secreto-interno",
    });
    expect(init?.body).toBe(JSON.stringify(BODY));
  });

  it("agrega x-vercel-protection-bypass cuando VERCEL_AUTOMATION_BYPASS_SECRET existe", () => {
    const init = calculateRequestInit(BODY, {
      internalApiSecret: "secreto-interno",
      automationBypassSecret: "bypass-de-vercel",
    });

    expect(init?.headers).toEqual({
      "content-type": "application/json",
      "x-internal-secret": "secreto-interno",
      "x-vercel-protection-bypass": "bypass-de-vercel",
    });
  });

  it("no agrega el header de bypass si la variable viene vacía", () => {
    const init = calculateRequestInit(BODY, {
      internalApiSecret: "secreto-interno",
      automationBypassSecret: "",
    });

    expect(init?.headers).toEqual({
      "content-type": "application/json",
      "x-internal-secret": "secreto-interno",
    });
  });
});
