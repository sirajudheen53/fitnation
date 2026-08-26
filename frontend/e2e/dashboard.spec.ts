/**
 * @critical dashboard
 *
 * Dashboard page tests:
 *   - Authenticated owner can load the dashboard
 *   - Dashboard shows the 6 metric cards
 *   - Dashboard does NOT crash when one or more API endpoints fail (404/500)
 *   - Unauthenticated access redirects to /login
 *
 * The dashboard fires 6 concurrent requests. The page must handle partial
 * failure gracefully — if one endpoint 404s (e.g. pending-payments not yet
 * implemented), the other 5 should still render their data.
 */
import { test, expect } from "@playwright/test";
import { seedAuth, login } from "./utils";

test.describe("Dashboard", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /dashboard redirects to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Happy path ────────────────────────────────────────────────────────

  test("@high authenticated user sees the dashboard with 6 metric cards", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/dashboard");

    // Heading is visible.
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10_000 });

    // All 6 metric card titles are present.
    await expect(page.getByText("Total members")).toBeVisible();
    await expect(page.getByText("Active memberships")).toBeVisible();
    await expect(page.getByText("Today's attendance")).toBeVisible();
    await expect(page.getByText("Trainers")).toBeVisible();
    await expect(page.getByText("Pending payments")).toBeVisible();
    await expect(page.getByText("MRR")).toBeVisible();
  });

  test("@high dashboard renders even when one API endpoint returns 404", async ({ page }) => {
    await seedAuth(page);

    // Intercept the pending-payments endpoint to return 404.
    await page.route("**/api/v1/dashboard/pending-payments/**", route =>
      route.fulfill({ status: 404, body: JSON.stringify({ detail: "Not found." }) }),
    );

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10_000 });

    // Other metric cards still render (no white-screen).
    await expect(page.getByText("Total members")).toBeVisible();
    await expect(page.getByText("Active memberships")).toBeVisible();

    // No raw "Request failed" error banner at the top.
    await expect(page.getByRole("alert")).not.toBeVisible();
  });

  test("@high dashboard renders when multiple API endpoints fail", async ({ page }) => {
    await seedAuth(page);

    // Simulate two endpoints failing.
    await page.route("**/api/v1/dashboard/pending-payments/**", route =>
      route.fulfill({ status: 404, body: JSON.stringify({}) }),
    );
    await page.route("**/api/v1/dashboard/revenue/**", route =>
      route.fulfill({ status: 500, body: JSON.stringify({}) }),
    );

    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible({ timeout: 10_000 });

    // Remaining working endpoints still show their cards.
    await expect(page.getByText("Total members")).toBeVisible();
    await expect(page.getByRole("alert")).not.toBeVisible();
  });
});
