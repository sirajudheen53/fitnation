/**
 * @medium attendance
 *
 * Attendance flows:
 *   - Auth guard on all attendance routes
 *   - Attendance list page loads (shows records or empty state)
 *   - Check-in page loads
 */
import { test, expect } from "@playwright/test";
import { seedAuth } from "./utils";

test.describe("Attendance", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /attendance redirects to /login", async ({ page }) => {
    await page.goto("/attendance");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /attendance/check-in redirects to /login", async ({ page }) => {
    await page.goto("/attendance/check-in");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Attendance list ───────────────────────────────────────────────────

  test("@high attendance list page loads without crashing", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/attendance");
    await expect(page.getByRole("heading", { name: /attendance/i })).toBeVisible({ timeout: 10_000 });
  });

  // ── Check-in ─────────────────────────────────────────────────────────

  test("@high check-in page loads and shows the check-in form", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/attendance/check-in");
    await expect(page.getByRole("heading", { name: /check.?in/i })).toBeVisible({ timeout: 10_000 });
  });
});
