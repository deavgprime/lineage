import type { NextConfig } from "next";

// Pages are rendered on the server and talk to the API from there, so the browser only ever loads
// this origin. The Content-Security-Policy is set per request in src/proxy.ts, with a nonce.
const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  // Not "no-referrer": that makes browsers send Origin: null on form posts, and Next.js then refuses
  // server actions behind a proxy. "same-origin" still sends nothing to other sites.
  { key: "Referrer-Policy", value: "same-origin" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
];

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default config;
