import { expect, test } from "@playwright/test";

import { signIn } from "./helpers";

test("pages run with a nonce policy and no blocked scripts", async ({ page }) => {
  const violations: string[] = [];
  page.on("console", (message) => {
    if (/Content Security Policy|Refused to (execute|load)/i.test(message.text())) {
      violations.push(message.text());
    }
  });
  await signIn(page, "analyst-uk-1");
  const response = await page.goto("/policy");
  const policy = response?.headers()["content-security-policy"] ?? "";
  const scripts = policy.split("; ").find((d) => d.startsWith("script-src")) ?? "";
  expect(scripts).toMatch(/'nonce-[A-Za-z0-9+/=]+' 'strict-dynamic'/);
  expect(scripts).not.toContain("unsafe-inline");
  // Interactive parts still work, which needs the page's scripts to have run.
  await page.getByLabel("Question").fill("How long are records kept?");
  await expect(page.getByRole("button", { name: "Ask" })).toBeEnabled();
  expect(violations).toEqual([]);
});
