"use server";

import { revalidatePath } from "next/cache";

import { api } from "@/lib/api";

export type SignOffState = { error?: string; done?: boolean };

const RATINGS = ["low", "medium", "high"] as const;
type Rating = (typeof RATINGS)[number];

export async function signOff(caseId: string, _: SignOffState, form: FormData): Promise<SignOffState> {
  const rating = String(form.get("rating") ?? "") as Rating;
  if (!RATINGS.includes(rating)) return { error: "Choose a rating." };
  const reason = String(form.get("reason") ?? "").trim();
  const alertNotes: Record<string, string> = {};
  for (const [key, value] of form.entries()) {
    if (key.startsWith("alert:")) alertNotes[key.slice("alert:".length)] = String(value).trim();
  }
  const { response, error } = await (await api(`/cases/${caseId}`)).POST("/cases/{case_id}/sign-off", {
    params: { path: { case_id: caseId } },
    body: { rating, reason: reason || null, alert_notes: alertNotes },
  });
  if (!response.ok) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return { error: typeof detail === "string" ? detail : "The file was not signed off." };
  }
  revalidatePath(`/cases/${caseId}`);
  return { done: true };
}

export async function retryCase(caseId: string): Promise<void> {
  await (await api(`/cases/${caseId}`)).POST("/cases/{case_id}/retry", {
    params: { path: { case_id: caseId } },
  });
  revalidatePath(`/cases/${caseId}`);
}
