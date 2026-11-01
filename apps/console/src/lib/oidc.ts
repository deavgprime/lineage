import "server-only";

import * as client from "openid-client";

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
  config ??= client.discovery(
    new URL(env("OIDC_ISSUER")),
    env("OIDC_CLIENT_ID"),
    undefined,
    client.None(),
    // Keycloak runs over plain HTTP only on a developer's machine.
    env("OIDC_ISSUER").startsWith("http://localhost")
      ? { execute: [client.allowInsecureRequests] }
      : undefined,
  );
  return config;
}

export { client };
