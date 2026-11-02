// Rewrites requests for the public Keycloak origin to an internal one. Returns undefined when no
// internal address is set, so the default fetch is used.
export function backchannel(
  issuer: string,
  internal: string | undefined,
): ((url: string, init: RequestInit) => Promise<Response>) | undefined {
  if (!internal) return undefined;
  // The rewrite happens after openid-client's HTTPS check, so it must not undo it: plain HTTP is
  // allowed internally only when the issuer itself is a developer's localhost.
  if (new URL(internal).protocol !== "https:" && !issuer.startsWith("http://localhost")) {
    throw new Error("OIDC_BACKCHANNEL_URL must use https unless the issuer is localhost");
  }
  const from = new URL(issuer).origin;
  const to = new URL(internal).origin;
  return (url, init) => fetch(url.startsWith(from) ? to + url.slice(from.length) : url, init);
}
