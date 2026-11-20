import assert from "node:assert/strict";
import { beforeEach, describe, it } from "node:test";

import { resetForTests, serviceHeaders } from "./service-identity.ts";

describe("serviceHeaders", () => {
  beforeEach(() => resetForTests());

  it("adds nothing when the API is not behind access control", async () => {
    assert.deepEqual(await serviceHeaders(undefined), {});
  });

  it("asks the metadata server for a token for the API and reuses it", async () => {
    const asked: string[] = [];
    const fetcher = (async (url: string, init: RequestInit) => {
      asked.push(url);
      assert.equal((init.headers as Record<string, string>)["Metadata-Flavor"], "Google");
      return new Response("id-token");
    }) as typeof fetch;
    const api = "https://lineage-api.example.run.app";
    const first = await serviceHeaders(api, 0, fetcher);
    await serviceHeaders(api, 60_000, fetcher);
    assert.deepEqual(first, { "X-Serverless-Authorization": "Bearer id-token" });
    assert.equal(asked.length, 1);
    assert.ok(asked[0]?.endsWith(`audience=${encodeURIComponent(api)}`));
    await serviceHeaders(api, 50 * 60 * 1000, fetcher);
    assert.equal(asked.length, 2);
  });
});
