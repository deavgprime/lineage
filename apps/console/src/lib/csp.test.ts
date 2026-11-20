import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { contentSecurityPolicy } from "./csp.ts";

describe("contentSecurityPolicy", () => {
  it("allows scripts only by nonce, never inline", () => {
    const policy = contentSecurityPolicy("abc123");
    const scripts = policy.split("; ").find((d) => d.startsWith("script-src")) ?? "";
    assert.equal(scripts, "script-src 'self' 'nonce-abc123' 'strict-dynamic'");
    assert.ok(!scripts.includes("unsafe-inline"));
    assert.ok(policy.includes("object-src 'none'"));
  });
});
