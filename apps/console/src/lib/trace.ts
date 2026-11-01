// One line of plain description for each kind of audit row.
type Payload = Record<string, unknown>;

export function describe(action: string, payload: Payload): string {
  switch (action) {
    case "case_opened":
      return `Case opened for ${String(payload.company_number)} in the ${String(payload.jurisdiction).toUpperCase()} pack`;
    case "plan":
      return `Plan: ${(payload.steps as string[] | undefined)?.join(", ") ?? "fixed by the pack"}`;
    case "tool_call": {
      const tool = String(payload.tool);
      if (tool === "screening") return `Screening: ${String(payload.hits)} candidate(s)`;
      if (tool === "lei") return `LEI lookup: ${String(payload.found)} record(s)`;
      return `Tool call: ${tool}`;
    }
    case "model_call":
      return `Model call, attempt ${String(payload.attempt)}`;
    case "draft":
      return Number(payload.citation_failures) === 0
        ? `Draft checked: every claim cited (${String(payload.attempts)} attempt(s))`
        : `Draft checked: ${String(payload.citation_failures)} citation failure(s)`;
    case "sign_off":
      return `${payload.stage === "second" ? "Second sign-off" : "Sign-off"}: rated ${String(payload.rating)}${
        payload.changed_from ? `, changed from ${String(payload.changed_from)}` : ""
      }, status ${String(payload.status)}`;
    case "redaction":
      return `Redaction: ${String(payload.people)} name(s) and ${String(payload.identifiers)} identifier(s) found and replaced`;
    case "analyst_request":
      return "Analyst request received";
    case "failed":
      return `Run failed: ${String(payload.error)}`;
    default:
      return action;
  }
}

export type Chain = { ok: boolean; firstBroken?: number };

export function chainStatus(rows: { seq: number; verified: boolean }[]): Chain {
  const broken = rows.find((r) => !r.verified);
  return broken ? { ok: false, firstBroken: broken.seq } : { ok: true };
}
