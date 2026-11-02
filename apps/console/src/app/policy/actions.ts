"use server";

import { redirect } from "next/navigation";

import { api } from "@/lib/api";

export type AskState = { error?: string };

export async function askQuestion(_: AskState, form: FormData): Promise<AskState> {
  const question = String(form.get("question") ?? "").trim();
  const pack = String(form.get("pack") ?? "");
  if (question.length < 3) return { error: "Write a question." };
  if (pack !== "uk" && pack !== "uae") return { error: "Choose a pack." };
  const { data, response } = await (await api("/policy")).POST("/policy/questions", {
    body: { question, pack },
  });
  if (!data) {
    return { error: response.status === 403 ? "You cannot ask in that pack." : "The question was not answered." };
  }
  redirect(`/policy?q=${data.id}`);
}
