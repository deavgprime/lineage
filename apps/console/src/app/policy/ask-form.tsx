"use client";

import { useActionState } from "react";

import { askQuestion, type AskState } from "./actions";

export function AskForm({ packs }: { packs: string[] }) {
  const [state, action, pending] = useActionState<AskState, FormData>(askQuestion, {});
  return (
    <form action={action} className="panel ask">
      <label>
        Question
        <textarea name="question" rows={3} required minLength={3} maxLength={1000} placeholder="When does enhanced due diligence apply?" />
      </label>
      <div className="row">
        <label>
          Pack
          <select name="pack" defaultValue={packs[0]}>
            {packs.map((p) => (
              <option key={p} value={p}>
                {p.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
        <button className="primary" type="submit" disabled={pending}>
          {pending ? "Searching the policy" : "Ask"}
        </button>
      </div>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  );
}
