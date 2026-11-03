import { expect, test, type Page } from "@playwright/test";

const pause = (page: Page, ms = 1500) => page.waitForTimeout(ms);

async function signIn(page: Page, user: string) {
  await page.goto("/");
  await pause(page);
  await page.getByRole("textbox", { name: "Username or email" }).pressSequentially(user, { delay: 40 });
  await page.getByRole("textbox", { name: "Password", exact: true }).fill(`${user}-local-test`);
  await page.getByRole("button", { name: "Sign In", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Cases" })).toBeVisible();
  await pause(page);
}

async function signOut(page: Page) {
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.context().clearCookies();
}

async function openCase(page: Page, number: string) {
  await page.getByLabel("Company number").pressSequentially(number, { delay: 60 });
  await page.getByRole("button", { name: "Open case" }).click();
  await expect(page).toHaveURL(/\/cases\/[0-9a-f-]{36}$/);
  await expect(async () => {
    await page.reload();
    await expect(page.getByRole("heading", { name: "Summary" })).toBeVisible({ timeout: 1000 });
  }).toPass({ timeout: 30_000 });
  await pause(page, 2500);
}

test("Lineage walkthrough", async ({ page }) => {
  // An analyst opens a case and reviews the cited draft.
  await signIn(page, "analyst-uk-1");
  const suffix = String(Date.now() % 100000).padStart(5, "0");
  await openCase(page, `005${suffix}`);
  await page.getByRole("link", { name: "source" }).nth(1).click();
  await expect(page.locator("mark")).toBeVisible();
  await pause(page, 3000);

  // Clearing the alert is required; then sign off.
  await page.locator('textarea[name^="alert:"]').pressSequentially("Different entity: only the word Holdings is shared.", { delay: 20 });
  await pause(page);
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.getByText(/First: analyst-uk-1/)).toBeVisible();
  await pause(page, 2500);

  // Every step is in a hash-chained audit trail.
  await page.getByRole("link", { name: "Trace" }).click();
  await expect(page.getByText(/audit rows verify against the hash chain/)).toBeVisible();
  await pause(page, 3500);

  // A high-rated file waits for an MLRO.
  await page.goto("/");
  await openCase(page, `990${suffix}`);
  const high = page.url();
  await page.locator('textarea[name^="alert:"]').pressSequentially("Different entity.", { delay: 20 });
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.getByText("Waiting for a second sign-off by a different MLRO.")).toBeVisible();
  await pause(page, 2500);
  await signOut(page);

  // A different MLRO gives the second sign-off.
  await signIn(page, "mlro-uk-1");
  await page.goto(high);
  await pause(page);
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.getByText(/Second: mlro-uk-1/)).toBeVisible();
  await pause(page, 2500);

  // A policy question, answered only from the bank's policy, with its source.
  await page.getByRole("link", { name: "Policy questions" }).click();
  await page.getByLabel("Question").pressSequentially("Who signs off a file rated high risk?", { delay: 30 });
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page).toHaveURL(/\/policy\?q=/);
  await page.getByRole("link", { name: "source" }).first().click();
  await expect(page.locator("mark")).toBeVisible();
  await pause(page, 3500);
});
