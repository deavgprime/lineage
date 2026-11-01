import { expect, test } from "@playwright/test";

import { companyNumber, openCase, signIn, signOut } from "./helpers";

test("an analyst drafts, reviews and signs off a file", async ({ page }) => {
  await signIn(page, "analyst-uk-1");
  const number = companyNumber("00");
  await openCase(page, number);
  await expect(page.getByRole("heading", { level: 1 })).toHaveText(`FIXTURE COMPANY ${number} LIMITED`);

  // A claim's source opens its record with the quoted passage marked.
  await page.getByRole("link", { name: "source" }).first().click();
  await expect(page.locator("mark")).toHaveText(`Company FIXTURE COMPANY ${number} LIMITED`);

  // The weak alert must be cleared before sign-off.
  await expect(page.getByRole("heading", { name: "Alerts to clear" })).toBeVisible();
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.locator("textarea:invalid")).toHaveCount(1);
  await page.locator('textarea[name^="alert:"]').fill("Different entity: only the word Holdings is shared.");
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.getByText(/First: analyst-uk-1 \(analyst\)/)).toBeVisible();
  await expect(page.getByText("Signed off")).toBeVisible();

  // The trace shows every step, and the chain verifies.
  await page.getByRole("link", { name: "Trace" }).click();
  await expect(page.getByText(/audit rows verify against the hash chain/)).toBeVisible();
  await expect(page.getByText(/Sign-off: rated low, status final/)).toBeVisible();
});

test("another analyst cannot see the case", async ({ page }) => {
  await signIn(page, "analyst-uk-1");
  const number = companyNumber("00");
  const url = await openCase(page, number);
  await signOut(page);

  await signIn(page, "analyst-uk-2");
  await expect(page.getByText(`FIXTURE COMPANY ${number} LIMITED`)).toHaveCount(0);
  const response = await page.goto(url);
  expect(response?.status()).toBe(404);
});

test("a high-rated file needs a second sign-off by an MLRO", async ({ page }) => {
  await signIn(page, "analyst-uk-1");
  const url = await openCase(page, companyNumber("99"));
  await page.locator('textarea[name^="alert:"]').fill("Different entity.");
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.getByText("Waiting for a second sign-off by a different MLRO.")).toBeVisible();
  await signOut(page);

  await signIn(page, "mlro-uk-1");
  await page.goto(url);
  await expect(page.getByRole("heading", { name: "Second sign-off (MLRO)" })).toBeVisible();
  await page.getByRole("button", { name: "Sign off" }).click();
  await expect(page.getByText(/Second: mlro-uk-1 \(mlro\)/)).toBeVisible();
  await expect(page.getByText("Signed off")).toBeVisible();
});

test("changing the rating needs a reason", async ({ page }) => {
  await signIn(page, "analyst-uk-1");
  await openCase(page, companyNumber("00"));
  await page.locator('textarea[name^="alert:"]').fill("Different entity.");
  await page.getByLabel("Rating").selectOption("medium");
  await expect(page.getByRole("button", { name: "Override and sign off" })).toBeVisible();
  await page.getByLabel(/Reason for changing the rating/).fill("Cash-intensive sector.");
  await page.getByRole("button", { name: "Override and sign off" }).click();
  await expect(page.getByText(/Rated medium, changed from low/)).toBeVisible();
});

test("an auditor can read but not open or sign", async ({ page }) => {
  await signIn(page, "analyst-uk-1");
  const url = await openCase(page, companyNumber("00"));
  await signOut(page);

  await signIn(page, "auditor-1");
  await expect(page.getByRole("button", { name: "Open case" })).toHaveCount(0);
  await page.goto(url);
  await expect(page.getByRole("heading", { name: "Summary" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign off" })).toHaveCount(0);
});
