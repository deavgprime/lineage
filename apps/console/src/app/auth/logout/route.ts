import { NextResponse } from "next/server";

import { appUrl, client, oidc } from "@/lib/oidc";
import { session } from "@/lib/session";

// Sign out here and at Keycloak. POST only, so a link on another site cannot sign a user out.
export async function POST() {
  const s = await session();
  const idToken = s.idToken;
  s.destroy();
  const url = client.buildEndSessionUrl(await oidc(), {
    post_logout_redirect_uri: `${appUrl()}/`,
    ...(idToken ? { id_token_hint: idToken } : {}),
  });
  return NextResponse.redirect(url, 303);
}
