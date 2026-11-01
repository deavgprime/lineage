import assert from "node:assert/strict";
import { describe, it } from "node:test";

import { locate } from "./quote.ts";

describe("locate", () => {
  const record = "Company TESCO STORES LIMITED, number 00519500.\nControlled by UK company TESCO HOLDINGS LIMITED (00445790).";
  it("splits the record around the quote, ignoring case and spacing", () => {
    assert.deepEqual(locate(record, "controlled  by uk company"), [
      "Company TESCO STORES LIMITED, number 00519500.\n",
      "Controlled by UK company",
      " TESCO HOLDINGS LIMITED (00445790).",
    ]);
  });
  it("treats special characters literally", () => {
    assert.equal(locate(record, "(00445790)")?.[1], "(00445790)");
  });
  it("returns null for an absent or empty quote", () => {
    assert.equal(locate(record, "not in the record"), null);
    assert.equal(locate(record, "   "), null);
  });
});
