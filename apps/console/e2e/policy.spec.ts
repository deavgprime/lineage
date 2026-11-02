import { expect, test } from "@playwright/test";

import { signIn } from "./helpers";

test("an analyst asks a policy question and opens its source", async ({ page }) => {
  await signIn(page, "analyst-uk-1");
  await page.getByRole("link", { name: "Policy questions" }).click();
  await page.getByLabel("Question").fill("How long are due diligence records kept?");
  await page.getByRole("button", { name: "Ask" }).click();
  await expect(page).toHaveURL(/\/policy\?q=[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "How long are due diligence records kept?" })).toBeVisible();

  await page.getByRole("link", { name: "source" }).first().click();
  await expect(page.locator("mark")).toBeVisible();
  await expect(page.locator("aside h2")).toContainText(/\d/);
  await expect(page.getByRole("link", { name: "How long are due diligence records kept?" }).first()).toBeVisible();
});

test("a UAE analyst asks in the UAE pack only", async ({ page }) => {
  await signIn(page, "analyst-uae-1");
  await page.goto("/policy");
  await expect(page.getByLabel("Pack").locator("option")).toHaveText(["UAE"]);
});
