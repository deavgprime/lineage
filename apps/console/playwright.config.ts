import { defineConfig, devices } from "@playwright/test";

// Runs against the compose stack with the API drafting from fixtures:
//   docker compose -f compose.yaml -f compose.e2e.yaml up -d --build --wait api keycloak
// and the console built and started on port 3000.
export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: 0,
  forbidOnly: !!process.env.CI,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://localhost:3000",
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
