import { describe, expect, it } from "vitest";

import { purchaseOrdersZipRequestInit } from "./zip-request";

describe("purchaseOrdersZipRequestInit", () => {
  it("no construye una petición sin el secreto interno", () => {
    expect(purchaseOrdersZipRequestInit({ orderIds: ["o-1"] }, { internalApiSecret: undefined })).toBeNull();
  });

  it("envía únicamente la selección al endpoint privado", () => {
    const init = purchaseOrdersZipRequestInit(
      { orderIds: ["o-1", "o-2"] },
      { internalApiSecret: "secret", automationBypassSecret: "bypass" },
    );
    expect(init?.method).toBe("POST");
    expect(init?.headers).toMatchObject({
      "content-type": "application/json",
      "x-internal-secret": "secret",
      "x-vercel-protection-bypass": "bypass",
    });
    expect(init?.body).toBe('{"orderIds":["o-1","o-2"]}');
  });
});
