import { NextResponse } from "next/server";

import { appUrl, client, oidc } from "@/lib/oidc";
import { session } from "@/lib/session";

// Sign out here and at Keycloak. POST only, so a link on another site cannot sign a user out.
export async function POST() {
  const s = await session();
  s.destroy();
  const config = await oidc();
  // Keycloak accepts the client id in place of an ID token hint for the redirect back here.
  const url = client.buildEndSessionUrl(config, {
    post_logout_redirect_uri: `${appUrl()}/`,
    client_id: config.clientMetadata().client_id,
  });
  return NextResponse.redirect(url, 303);
}
