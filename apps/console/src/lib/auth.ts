import "server-only";

import { redirect } from "next/navigation";

import { client, oidc } from "./oidc";
import { session } from "./session";
import { needsRefresh } from "./tokens";

// A valid access token for the signed-in user, refreshed when close to expiry. Sends the user to
// sign in when there is none.
export async function accessToken(returnTo = "/"): Promise<string> {
  const s = await session();
  if (s.accessToken && !needsRefresh(s.expiresAt)) return s.accessToken;
  if (s.refreshToken) {
    try {
      const tokens = await client.refreshTokenGrant(await oidc(), s.refreshToken);
      s.accessToken = tokens.access_token;
      s.refreshToken = tokens.refresh_token ?? s.refreshToken;
      s.expiresAt = Math.floor(Date.now() / 1000) + (tokens.expires_in ?? 60);
      await s.save();
      return tokens.access_token;
    } catch {
      s.destroy();
    }
  }
  redirect(`/auth/login?returnTo=${encodeURIComponent(returnTo)}`);
}
