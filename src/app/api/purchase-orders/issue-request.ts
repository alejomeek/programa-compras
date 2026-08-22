export function issueOrderRequestInit(
  body: { orderId: string; issuedBy: string },
  env: { internalApiSecret: string | undefined; automationBypassSecret?: string | undefined },
): RequestInit | null {
  if (!env.internalApiSecret) return null;

  const headers: Record<string, string> = {
    "content-type": "application/json",
    "x-internal-secret": env.internalApiSecret,
  };
  if (env.automationBypassSecret) {
    headers["x-vercel-protection-bypass"] = env.automationBypassSecret;
  }
  return { method: "POST", headers, body: JSON.stringify(body) };
}
