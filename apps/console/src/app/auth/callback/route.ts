import { NextResponse, type NextRequest } from "next/server";

import { appUrl, client, oidc } from "@/lib/oidc";
import { session } from "@/lib/session";

export async function GET(request: NextRequest) {
  const s = await session();
  const { verifier, state, returnTo = "/" } = s;
  if (!verifier || !state) {
    return NextResponse.redirect(`${appUrl()}/auth/login`);
  }
  const current = new URL(request.nextUrl.pathname + request.nextUrl.search, appUrl());
  const tokens = await client.authorizationCodeGrant(await oidc(), current, {
    pkceCodeVerifier: verifier,
    expectedState: state,
  });
  s.accessToken = tokens.access_token;
  s.refreshToken = tokens.refresh_token;
  s.idToken = tokens.id_token;
  s.expiresAt = Math.floor(Date.now() / 1000) + (tokens.expires_in ?? 60);
  delete s.verifier;
  delete s.state;
  delete s.returnTo;
  await s.save();
  return NextResponse.redirect(`${appUrl()}${returnTo}`);
}
