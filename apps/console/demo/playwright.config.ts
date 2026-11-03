import { defineConfig, devices } from "@playwright/test";

// Records the demo walkthrough against the local stack with fixture drafting:
//   docker compose -f compose.yaml -f compose.e2e.yaml up -d --build --wait db keycloak api console
//   npx playwright test -c demo
// The video lands in demo/output and is copied to docs/demo by hand after review.
export default defineConfig({
  testDir: ".",
  outputDir: "output",
  workers: 1,
  timeout: 300_000,
  reporter: "list",
  use: {
    baseURL: process.env.CONSOLE_URL ?? "http://localhost:3000",
    viewport: { width: 1280, height: 800 },
    video: { mode: "on", size: { width: 1280, height: 800 } },
    launchOptions: { slowMo: 250 },
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], viewport: { width: 1280, height: 800 } } }],
});
