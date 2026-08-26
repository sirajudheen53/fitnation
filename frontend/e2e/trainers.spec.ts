/**
 * @medium trainers
 *
 * Trainer management flows:
 *   - Auth guard on all trainer routes
 *   - Trainers list page loads
 *   - Trainer detail page loads (with a valid ID)
 *   - Create trainer form renders
 */
import { test, expect } from "@playwright/test";
import { seedAuth } from "./utils";

test.describe("Trainers", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /trainers redirects to /login", async ({ page }) => {
    await page.goto("/trainers");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /trainers/performance redirects to /login", async ({ page }) => {
    await page.goto("/trainers/performance");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /trainers/schedule redirects to /login", async ({ page }) => {
    await page.goto("/trainers/schedule");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Trainers list ─────────────────────────────────────────────────────

  test("@high trainers list page loads without crashing", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/trainers");
    await expect(page.getByRole("heading", { name: /trainer/i })).toBeVisible({ timeout: 10_000 });
  });

  // ── Trainer performance ───────────────────────────────────────────────

  test("@high trainer performance page loads", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/trainers/performance");
    await expect(page.getByRole("heading", { name: /performance/i })).toBeVisible({ timeout: 10_000 });
  });

  // ── Trainer schedule ─────────────────────────────────────────────────

  test("@high trainer schedule page loads", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/trainers/schedule");
    await expect(page.getByRole("heading", { name: /schedule/i })).toBeVisible({ timeout: 10_000 });
  });
});
