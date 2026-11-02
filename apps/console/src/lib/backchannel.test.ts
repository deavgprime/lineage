import assert from "node:assert/strict";
import { describe, it, mock } from "node:test";

import { backchannel } from "./backchannel.ts";

describe("backchannel", () => {
  it("is off without an internal address", () => {
    assert.equal(backchannel("http://localhost:8080/realms/lineage", undefined), undefined);
  });
  it("sends public Keycloak URLs to the internal address and leaves others alone", async () => {
    const seen: string[] = [];
    mock.method(globalThis, "fetch", async (url: string) => {
      seen.push(url);
      return new Response("{}");
    });
    const f = backchannel("http://localhost:8080/realms/lineage", "http://keycloak:8080");
    await f?.("http://localhost:8080/realms/lineage/.well-known/openid-configuration", {});
    await f?.("http://other.example/x", {});
    assert.deepEqual(seen, [
      "http://keycloak:8080/realms/lineage/.well-known/openid-configuration",
      "http://other.example/x",
    ]);
  });
});
