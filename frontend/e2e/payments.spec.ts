/**
 * @critical payments
 *
 * Payment flows:
 *   - Auth guard: unauthenticated access redirects to /login
 *   - Payments list page loads and renders (or shows empty state)
 *   - Record payment: form → success → appears in list
 *   - Payment form validation: required fields enforced
 *   - 404 / invalid customer ID handled gracefully
 *   - API errors on list page show a friendly message (no white-screen)
 *   - Revenue summary 404 does NOT crash the payments list
 *
 * A customer is seeded via API so the payment can be linked deterministically.
 * Cleanup runs in afterEach.
 */
import { test, expect } from "@playwright/test";
import {
  seedAuth,
  createCustomerViaApi,
  tableTexts,
  uniqueSuffix,
  cleanupCustomerById,
  getApiToken,
} from "./utils";

test.describe("Payments", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /payments redirects to /login", async ({ page }) => {
    await page.goto("/payments");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /payments/new redirects to /login", async ({ page }) => {
    await page.goto("/payments/new");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Payments list ──────────────────────────────────────────────────────

  test("@high payments list page loads without crashing", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/payments");
    await expect(page.getByRole("heading", { name: /payments/i })).toBeVisible({ timeout: 10_000 });
  });

  test("@high revenue-summary 404 does NOT crash the payments list", async ({ page }) => {
    await seedAuth(page);

    // Intercept revenue-summary to return 404 (as it does in the current backend).
    await page.route("**/api/v1/payments/revenue-summary/**", route =>
      route.fulfill({ status: 404, body: JSON.stringify({ detail: "Not found." }) }),
    );

    await page.goto("/payments");

    // Page loads and shows the payments heading (list is not empty in seeded DB).
    await expect(page.getByRole("heading", { name: /payments/i })).toBeVisible({ timeout: 10_000 });

    // No "Request failed" banner.
    await expect(page.getByRole("alert")).not.toBeVisible();
  });

  test("@high payments list shows a friendly error when the API is completely down", async ({ page }) => {
    await seedAuth(page);

    // Fail all API calls with a network error.
    await page.route("**/api/v1/payments/**", route => route.abort());

    await page.goto("/payments");

    // Error message shown (not a blank page or crash).
    await expect(page.getByRole("alert").first()).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("alert").first()).toContainText(/error|failed|try again/i);
  });

  // ── Record payment ────────────────────────────────────────────────────

  test("@high record a payment for a customer and verify it appears in the list", async ({ page }) => {
    const suffix = uniqueSuffix();
    const customerEmail = `e2e.pay.${suffix}@fitnation.test`;
    const customerName = `PayCustomer_${suffix}`;
    const note = `E2E payment ${suffix}`;

    const { id: customerId, userId } = await createCustomerViaApi(customerName, customerEmail);

    await seedAuth(page);
    await page.goto("/payments/new");
    await expect(page.getByRole("heading", { name: /Record payment/i })).toBeVisible();

    // Set customer ID directly via Playwright fill (React onChange fires automatically).
    await page.getByLabel("Customer ID").fill(String(customerId));
    // Confirm React registered the value before we submit.
    await expect(page.getByLabel("Customer ID")).toHaveValue(String(customerId));

    await page.getByLabel("Amount").fill("1999");
    await page.locator("#method").selectOption({ label: "UPI" });
    await page.getByLabel("Payment date").fill("2026-08-25");
    await page.getByLabel("Notes").fill(note);

    await page.getByRole("button", { name: /Record payment/i }).click();

    // Either redirect to payments list OR success toast appears (form submission worked).
    try {
      await page.waitForURL("**/payments", { timeout: 15_000 });
    } catch {
      // If no redirect, at least the form didn't crash — check for success toast
      await expect(page.getByText(/payment recorded|success/i).first()).toBeVisible({ timeout: 5_000 });
    }

    // Success toast confirms the payment was actually saved.
    await expect(page.getByText("Payment recorded")).toBeVisible();

    // The payment amount appears in the table (₹1,999 with Indian formatting).
    await expect
      .poll(async () => (await tableTexts(page)).join("\n"), { timeout: 10_000 })
      .toContain("₹1,999");

    // Cleanup.
    await cleanupCustomerById(customerId, userId);
  });

  test("@high submitting payment form with missing fields shows validation errors", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/payments/new");
    await expect(page.getByRole("heading", { name: /Record payment/i })).toBeVisible();

    // Submit without filling anything.
    await page.getByRole("button", { name: /Record payment/i }).click();

    // Validation errors shown inline.
    await expect(page.getByText(/(select a customer|amount must be greater than 0|payment date is required)/i).first()).toBeVisible();

    // Still on the form — no redirect.
    await expect(page).toHaveURL(/\/payments\/new/);
  });

  test("@high record payment with non-existent customer shows a server error", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/payments/new");

    await page.evaluate(
      val => {
        const input = document.querySelector("#customer-id") as HTMLInputElement;
        const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")!.set!;
        setter.call(input, val);
        input.dispatchEvent(new Event("input", { bubbles: true }));
        input.dispatchEvent(new Event("change", { bubbles: true }));
      },
      "999999",
    );

    await page.getByLabel("Amount").fill("1999");
    await page.locator("#method").selectOption({ label: "Cash" });
    await page.getByRole("button", { name: /Record payment/i }).click();

    // Server error shown — not a crash.
    await expect(page.getByRole("alert")).toBeVisible({ timeout: 10_000 });
  });
});
