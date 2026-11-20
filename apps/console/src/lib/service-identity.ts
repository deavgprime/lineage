// When the API is behind Cloud Run's access control, the console proves who it is with a Google ID
// token from the metadata server, sent in X-Serverless-Authorization so the user's own token keeps
// the Authorization header. Off unless LINEAGE_API_AUDIENCE is set.
const METADATA =
  "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity";
// Google ID tokens last an hour; fetch a new one well before that.
const REUSE_MS = 45 * 60 * 1000;

let cached: { token: string; at: number } | undefined;

export async function serviceHeaders(
  audience: string | undefined,
  now: number = Date.now(),
  fetcher: typeof fetch = fetch,
): Promise<Record<string, string>> {
  if (!audience) return {};
  if (!cached || now - cached.at > REUSE_MS) {
    const response = await fetcher(`${METADATA}?audience=${encodeURIComponent(audience)}`, {
      headers: { "Metadata-Flavor": "Google" },
    });
    if (!response.ok) throw new Error(`metadata server refused an ID token: ${response.status}`);
    cached = { token: await response.text(), at: now };
  }
  return { "X-Serverless-Authorization": `Bearer ${cached.token}` };
}

export function resetForTests() {
  cached = undefined;
}
