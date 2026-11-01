import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { age, normaliseCompanyNumber, statusLabel } from "./format.ts";

describe("normaliseCompanyNumber", () => {
  it("pads digits and keeps lettered prefixes", () => {
    assert.equal(normaliseCompanyNumber(" 519500 "), "00519500");
    assert.equal(normaliseCompanyNumber("sc613281"), "SC613281");
  });
  it("refuses anything else", () => {
    for (const value of ["", "123456789", "ABC12345", "12-34", "'; DROP"]) {
      assert.equal(normaliseCompanyNumber(value), null);
    }
  });
});

describe("age and status", () => {
  it("uses the largest whole unit", () => {
    const now = Date.parse("2026-11-02T12:00:00Z");
    assert.equal(age("2026-11-02T11:55:00Z", now), "5 min");
    assert.equal(age("2026-11-02T09:00:00Z", now), "3 h");
    assert.equal(age("2026-10-28T12:00:00Z", now), "5 d");
  });
  it("labels each status in plain words", () => {
    assert.equal(statusLabel("awaiting_mlro"), "Waiting for MLRO");
  });
});
