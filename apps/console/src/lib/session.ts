import "server-only";

import { getIronSession, type SessionOptions } from "iron-session";
import { cookies } from "next/headers";

// Tokens live only in this encrypted, httpOnly cookie. Browser scripts never see them.
export type Session = {
  accessToken?: string;
  refreshToken?: string;
  idToken?: string;
  expiresAt?: number;
  // Held between the redirect to Keycloak and the callback.
  verifier?: string;
  state?: string;
  returnTo?: string;
};

export function sessionOptions(): SessionOptions {
  const password = process.env.SESSION_SECRET ?? "";
  if (password.length < 32) {
    throw new Error("SESSION_SECRET must be at least 32 characters");
  }
  return {
    password,
    cookieName: "lineage_session",
    cookieOptions: {
      httpOnly: true,
      secure: process.env.NODE_ENV === "production",
      sameSite: "lax",
      path: "/",
    },
    ttl: 60 * 60 * 8,
  };
}

export async function session() {
  return getIronSession<Session>(await cookies(), sessionOptions());
}
