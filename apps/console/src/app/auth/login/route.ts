import { NextResponse, type NextRequest } from "next/server";

import { client, oidc, appUrl } from "@/lib/oidc";
import { session } from "@/lib/session";
import { safeReturnTo } from "@/lib/tokens";

// Start the authorization code flow with PKCE.
export async function GET(request: NextRequest) {
  const s = await session();
  s.verifier = client.randomPKCECodeVerifier();
  s.state = client.randomState();
  s.returnTo = safeReturnTo(request.nextUrl.searchParams.get("returnTo"));
  await s.save();
  const url = client.buildAuthorizationUrl(await oidc(), {
    redirect_uri: `${appUrl()}/auth/callback`,
    scope: "openid",
    code_challenge: await client.calculatePKCECodeChallenge(s.verifier),
    code_challenge_method: "S256",
    state: s.state,
  });
  return NextResponse.redirect(url);
}
