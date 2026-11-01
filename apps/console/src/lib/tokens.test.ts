import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { needsRefresh, safeReturnTo } from "./tokens.ts";

describe("needsRefresh", () => {
  const now = 1_000_000_000_000;
  it("refreshes a missing or nearly expired token", () => {
    assert.equal(needsRefresh(undefined, now), true);
    assert.equal(needsRefresh(now / 1000 + 10, now), true);
  });
  it("keeps a token with time left", () => {
    assert.equal(needsRefresh(now / 1000 + 300, now), false);
  });
});

describe("safeReturnTo", () => {
  it("keeps paths on this site", () => {
    assert.equal(safeReturnTo("/cases/1"), "/cases/1");
  });
  it("refuses other sites and odd forms", () => {
    for (const value of ["https://evil.example", "//evil.example", "/\\evil", "", null]) {
      assert.equal(safeReturnTo(value), "/");
    }
  });
});
