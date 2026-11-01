"use client";

import { useActionState, useState } from "react";

import { signOff, type SignOffState } from "./actions";

type Props = {
  caseId: string;
  basis: string;
  alerts: string[];
  stage: "first" | "second";
};

export function SignOffForm({ caseId, basis, alerts, stage }: Props) {
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
      {stage === "first" && rating === "high" && (
        <p className="muted">A high rating goes to an MLRO for a second sign-off before the file is final.</p>
      )}
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "Signing" : changed ? "Override and sign off" : "Sign off"}
      </button>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  );
}
