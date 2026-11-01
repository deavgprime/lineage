"use client";

import { useActionState } from "react";

import { openCase, type OpenState } from "./actions";

export function OpenCase({ packs }: { packs: string[] }) {
  const [state, action, pending] = useActionState<OpenState, FormData>(openCase, {});
  return (
    <form action={action} className="panel open-case">
      <label>
        Company number
        <input name="company_number" required maxLength={10} placeholder="00519500" />
      </label>
      <label>
        Pack
        <select name="jurisdiction" defaultValue={packs[0]}>
          {packs.map((p) => (
            <option key={p} value={p}>
              {p.toUpperCase()}
            </option>
          ))}
        </select>
      </label>
      <button className="primary" type="submit" disabled={pending}>
        {pending ? "Opening" : "Open case"}
      </button>
      {state.error && <p className="error">{state.error}</p>}
    </form>
  );
}
