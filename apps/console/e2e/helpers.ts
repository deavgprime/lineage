import { expect, type Page } from "@playwright/test";

// Every run opens new cases, so numbers are unique to the run.
export function companyNumber(prefix: "00" | "99"): string {
  return prefix + String(Date.now() % 1_000_000).padStart(6, "0");
}

export async function signIn(page: Page, username: string) {
  await page.goto("/");
  await page.getByRole("textbox", { name: "Username or email" }).fill(username);
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(`${username}-local-test`);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
}

export async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.context().clearCookies();
}

export async function openCase(page: Page, number: string) {
  await page.getByLabel("Company number").fill(number);
  await page.getByRole("button", { name: "Open case" }).click();
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}$/);
  // The agent drafts in the background; reload until the file is ready.
  await expect(async () => {
    await page.reload();
    await expect(page.getByRole("heading", { name: "Summary" })).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 30_000 });
  return page.url();
}
