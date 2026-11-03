"use client";

import { useActionState, useState } from "react";

import { signOff, type SignOffState } from "./actions";

type Props = {
  caseId: string;
  basis: string;
  minimum?: string | null;
  alerts: string[];
  stage: "first" | "second";
};

const RANK: Record<string, number> = { low: 1, medium: 2, high: 3 };

export function SignOffForm({ caseId, basis, minimum, alerts, stage }: Props) {
  const [state, action, pending] = useActionState<SignOffState, FormData>(signOff.bind(null, caseId), {});
  const [rating, setRating] = useState(basis);
  const changed = rating !== basis;
  return (
    <form action={action} className="panel sign-off">
      <h2>{stage === "first" ? "Sign off" : "Second sign-off (MLRO)"}</h2>
      {alerts.length > 0 && stage === "first" && (
        <fieldset>
          <legend>Clear each alert</legend>
          {alerts.map((a) => (
            <label key={a}>
              <span className="mono">{a}</span>
              <textarea name={`alert:${a}`} required rows={2} placeholder="Why this is or is not the same party" />
            </label>
          ))}
        </fieldset>
      )}
      <label>
        Rating
        <select name="rating" value={rating} onChange={(e) => setRating(e.target.value)}>
          <option value="low">Low</option>
          <option value="medium">Medium</option>
          <option value="high">High</option>
        </select>
      </label>
      <label>
        {changed ? `Reason for changing the rating from ${basis}` : "Note (optional)"}
        <textarea name="reason" rows={3} required={changed} maxLength={4000} />
      </label>
      {stage === "first" &&
        (rating === "high" || basis === "high" || minimum === "high" || (RANK[rating] ?? 0) < (RANK[basis] ?? 0)) && (
          <p className="muted">
            This file goes to a different MLRO for a second sign-off before it is final, because it was drafted or
            rated high, or its rating is being lowered.
          </p>
        )}
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "Signing" : changed ? "Override and sign off" : "Sign off"}
      </button>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  );
}
