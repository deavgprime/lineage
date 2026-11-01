// Refresh a little early, so a token never expires between the check and the API call.
export const REFRESH_MARGIN_SECONDS = 30;

export function needsRefresh(expiresAt: number | undefined, now: number = Date.now()): boolean {
  if (expiresAt === undefined) return true;
  return now / 1000 >= expiresAt - REFRESH_MARGIN_SECONDS;
}

// Only paths on this site are allowed after sign-in, so the redirect cannot be used to send a
// user somewhere else.
export function safeReturnTo(value: string | null | undefined): string {
  if (!value || !value.startsWith("/") || value.startsWith("//") || value.includes("\\")) {
    return "/";
  }
  return value;
}
