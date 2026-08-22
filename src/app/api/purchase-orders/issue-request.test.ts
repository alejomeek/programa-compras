import { describe, expect, it } from "vitest";

import { issueOrderRequestInit } from "./issue-request";

describe("issueOrderRequestInit", () => {
  it("no crea una petición sin secreto interno", () => {
    expect(issueOrderRequestInit({ orderId: "o-1", issuedBy: "u-1" }, { internalApiSecret: undefined })).toBeNull();
  });

  it("protege la llamada interna y conserva el actor", () => {
    const request = issueOrderRequestInit(
      { orderId: "o-1", issuedBy: "u-1" },
      { internalApiSecret: "secret", automationBypassSecret: "bypass" },
    );

    expect(request).toMatchObject({ method: "POST", body: '{"orderId":"o-1","issuedBy":"u-1"}' });
    expect(request?.headers).toMatchObject({
      "x-internal-secret": "secret",
      "x-vercel-protection-bypass": "bypass",
    });
  });
});
