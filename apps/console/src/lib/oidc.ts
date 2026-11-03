import "server-only";

import * as client from "openid-client";

import { backchannel } from "./backchannel";

let config: Promise<client.Configuration> | undefined;

function env(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is not set`);
  return value;
}

export function appUrl(): string {
  return env("APP_URL");
}

export function oidc(): Promise<client.Configuration> {
  const issuer = env("OIDC_ISSUER");
  // Server-to-server calls can reach Keycloak on another address, such as a container name,
  // while tokens keep the issuer the browser uses.
  const fetch = backchannel(issuer, process.env.OIDC_BACKCHANNEL_URL);
  const options = {
    // Keycloak runs over plain HTTP only on a developer's machine.
    ...(issuer.startsWith("http://localhost") ? { execute: [client.allowInsecureRequests] } : {}),
    ...(fetch ? { [client.customFetch]: fetch as client.CustomFetch } : {}),
  };
  config ??= client.discovery(new URL(issuer), env("OIDC_CLIENT_ID"), undefined, client.None(), options);
  return config;
}

export { client };
