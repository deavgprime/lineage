// Rewrites requests for the public Keycloak origin to an internal one. Returns undefined when no
// internal address is set, so the default fetch is used.
export function backchannel(
  issuer: string,
  internal: string | undefined,
): ((url: string, init: RequestInit) => Promise<Response>) | undefined {
  if (!internal) return undefined;
  const from = new URL(issuer).origin;
  const to = new URL(internal).origin;
  return (url, init) => fetch(url.startsWith(from) ? to + url.slice(from.length) : url, init);
}
