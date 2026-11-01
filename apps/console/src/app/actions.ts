"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api";
import { normaliseCompanyNumber } from "@/lib/format";

export type OpenState = { error?: string };

export async function openCase(_: OpenState, form: FormData): Promise<OpenState> {
  const number = normaliseCompanyNumber(String(form.get("company_number") ?? ""));
  const pack = String(form.get("jurisdiction") ?? "");
  if (!number) return { error: "Enter an eight-character company number." };
  if (pack !== "uk" && pack !== "uae") return { error: "Choose a pack." };
  const { data, response } = await (await api()).POST("/cases", {
    body: { company_number: number, jurisdiction: pack },
  });
  if (!data) {
    return {
      error:
        response.status === 403 ? "You cannot open cases in that pack." : "The case was not opened.",
    };
  }
  redirect(`/cases/${data.id}`);
}
