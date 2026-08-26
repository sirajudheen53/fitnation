/**
 * @critical sanity
 *
 * Minimal smoke test: the Next.js app boots and the public landing page
 * renders. This is the first check that runs and verifies the whole harness
 * (webServer, browser launch, base URL) is wired up correctly.
 */
import { test, expect } from "@playwright/test";

test("homepage renders the FitNation landing page", async ({ page }) => {
  await page.goto("/");

  // Visible from the landing page <h1>.
  await expect(page.getByRole("heading", { name: "FitNation FBOS" })).toBeVisible();

  // Primary CTA links to the signup flow.
  await expect(page.getByRole("link", { name: /Get started/i })).toBeVisible();
});
