import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright E2E configuration for FitNation FBOS frontend.
 *
 * These tests exercise the real Next.js app against the real Django REST
 * backend (default: http://localhost:8000/api/v1). They do NOT mock the
 * browser or the network — they drive the actual UI.
 *
 * Prerequisites to run `npm run test:e2e`:
 *   1. Backend dev server running on :8000 (Django `manage.py runserver`)
 *      with data seeded via `python setup_local.py`.
 *   2. Frontend dev server running on :3000 (`npm run dev`).
 *
 * The webServer block below will auto-start the Next.js dev server when the
 * port is free, but the Django API must be running separately.
 */
export default defineConfig({
  testDir: "./e2e",
  // Each test gets up to 30s before being failed.
  timeout: 30_000,
  // Fail if a test leaves the worker in a broken state.
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: [["html", { outputFolder: "playwright-report" }], ["list"]],
  outputDir: "test-results",

  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    // True in CI, false locally so failures can be visually debugged.
    headless: process.env.CI ? true : !process.env.E2E_HEADED,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  webServer: {
    // Auto-start the Next.js dev server if it isn't already running.
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
