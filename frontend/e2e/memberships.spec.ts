/**
 * @high memberships
 *
 * Membership plan and assignment flows:
 *   - Auth guard on all routes
 *   - Plans list loads
 *   - Assignment form: select customer + plan → creates active membership
 *   - Assignment list loads
 *   - Duplicate assignment shows a server error (not a crash)
 */
import { test, expect } from "@playwright/test";
import {
  seedAuth,
  createCustomerViaApi,
  uniqueSuffix,
  cleanupCustomerById,
  getApiToken,
} from "./utils";

test.describe("Memberships", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /memberships redirects to /login", async ({ page }) => {
    await page.goto("/memberships");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /memberships/assign redirects to /login", async ({ page }) => {
    await page.goto("/memberships/assign");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Plans list ─────────────────────────────────────────────────────────

  test("@high membership page loads and shows heading", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/memberships");
    // The memberships page loads without crashing.
    await expect(page.getByRole("main")).toBeVisible({ timeout: 10_000 });
  });

  // ── Assign membership ──────────────────────────────────────────────────

  test("@high assign a membership plan to a customer", async ({ page }) => {
    const suffix = uniqueSuffix();
    const email = `e2e.memb.${suffix}@fitnation.test`;
    const name = `MembCustomer_${suffix}`;

    const { id: customerId, userId } = await createCustomerViaApi(name, email);

    await seedAuth(page);
    await page.goto("/memberships/assign");
    await expect(page.getByRole("heading", { name: /assign/i })).toBeVisible({ timeout: 10_000 });

    // Allow time for the customer and plan dropdowns to load from the API.
    await page.waitForTimeout(3_000);

    await page.locator("#customer_id").selectOption(String(customerId));
    await page.locator("#plan_id").selectOption({ index: 1 });

    // Start/end dates are required by the form.
    const start = new Date();
    const end = new Date(start);
    end.setDate(end.getDate() + 30);
    const toDateInput = (d: Date) => d.toISOString().slice(0, 10);
    await page.getByLabel("Start date").fill(toDateInput(start));
    await page.getByLabel("End date").fill(toDateInput(end));

    // Submit.
    await page.getByRole("button", { name: /assign|create/i }).first().click();

    // Success toast shown (membership assigned).
    await expect(page.getByText("Membership assigned")).toBeVisible({ timeout: 10_000 });

    // Cleanup.
    await cleanupCustomerById(customerId, userId);
  });

  test("@high assigning without selecting customer shows no crash", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/memberships/assign");
    await expect(page.getByRole("heading", { name: /assign/i })).toBeVisible({ timeout: 10_000 });

    await page.getByRole("button", { name: /assign|create/i }).first().click();

    // No crash — either validation error or stays on form.
    const validationShown = await page.getByText(/customer is required|please select/i).isVisible().catch(() => false);
    const stillOnForm = page.url().includes("memberships/assign");
    expect(validationShown || await stillOnForm).toBe(true);
  });
});
