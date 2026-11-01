import assert from "node:assert/strict";
import { describe as group, it } from "node:test";

import { chainStatus, describe } from "./trace.ts";

group("describe", () => {
  it("summarises each step in plain words", () => {
    assert.equal(describe("tool_call", { tool: "screening", hits: 2 }), "Screening: 2 candidate(s)");
    assert.equal(describe("model_call", { attempt: 1 }), "Model call, attempt 1");
    assert.equal(
      describe("sign_off", { stage: "second", rating: "high", changed_from: null, status: "final" }),
      "Second sign-off: rated high, status final",
    );
  });
});

group("chainStatus", () => {
  it("reports the first row that fails", () => {
    assert.deepEqual(chainStatus([{ seq: 1, verified: true }]), { ok: true });
    assert.deepEqual(
      chainStatus([
        { seq: 1, verified: true },
        { seq: 5, verified: false },
        { seq: 9, verified: false },
      ]),
      { ok: false, firstBroken: 5 },
    );
  });
});
