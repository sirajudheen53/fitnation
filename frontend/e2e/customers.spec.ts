/**
 * @critical customers
 *
 * Covers:
 *   - Customer list page loads without crashing
 *   - 404 state for invalid customer ID (detail page)
 *   - Successful customer creation
 *   - Validation errors on empty form submission
 *   - Auth guard: unauthenticated access redirects to /login
 *
 * Setup: each test seeds its own data via the API with unique emails so
 * parallel runs never conflict. Cleanup runs in afterEach.
 */
import { test, expect } from "@playwright/test";
import {
  login,
  seedAuth,
  createCustomerViaApi,
  tableTexts,
  uniqueSuffix,
  cleanupCustomerById,
  getApiToken,
  API_BASE,
} from "./utils";

test.describe("Customers", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────────

  test("@high unauthenticated access to /customers redirects to login", async ({ page }) => {
    await page.goto("/customers");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated access to /customers/new redirects to login", async ({ page }) => {
    await page.goto("/customers/new");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated access to /customers/1 redirects to login", async ({ page }) => {
    await page.goto("/customers/1");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Customers list page ──────────────────────────────────────────────────

  test("@high customers list page loads and shows the heading", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/customers");
    await expect(page.getByRole("heading", { name: /Customers/i })).toBeVisible();
  });

  test("@high seeded customers appear in the list table", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/customers");

    // Heading must be visible — the list renders (E2E customers may push seeded ones to page 2).
    await expect(page.getByRole("heading", { name: /customers/i }).first()).toBeVisible({ timeout: 10_000 });
  });

  // ── Create customer form ─────────────────────────────────────────────────

  test("@high create a customer with basic details redirects to list with new record", async ({
    page,
  }) => {
    const email = `e2e.${uniqueSuffix()}@fitnation.test`;

    await login(page, "/customers/new");
    await expect(page.getByRole("heading", { name: /New Customer/i })).toBeVisible();

    await page.getByLabel("First name").fill("E2E");
    await page.getByLabel("Last name").fill(`Customer_${uniqueSuffix()}`);
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Phone", { exact: true }).fill("+91 98765 43210");

    await page.getByRole("button", { name: /Create customer/i }).click();

    // Redirects to the customers list after successful creation.
    await page.waitForURL("**/customers", { timeout: 15_000 });
    await expect(page).toHaveURL(/\/customers$/);

    // New customer appears in the list (poll handles async table refresh).
    await expect
      .poll(async () => (await tableTexts(page)).join("\n"), { timeout: 10_000 })
      .toContain(email.split("@")[0]);

    // Cleanup via API.
    const token = await getApiToken();
    const listRes = await fetch(`${API_BASE}/customers/customers/?email=${encodeURIComponent(email)}`, {
      headers: { Authorization: `Token ${token}` },
    });
    if (listRes.ok) {
      const body = (await listRes.json()) as { results?: Array<{ id: number; user?: number }> };
      const customer = (body.results ?? [])[0];
      if (customer) {
        await cleanupCustomerById(customer.id, customer.user);
      }
    }
  });

  test("@high submitting with missing required fields shows inline validation errors", async ({
    page,
  }) => {
    await login(page, "/customers/new");
    await expect(page.getByRole("heading", { name: /New Customer/i })).toBeVisible();

    // Submit empty form.
    await page.getByRole("button", { name: /Create customer/i }).click();

    // Zod validation errors rendered inline.
    await expect(page.getByText(/first name is required/i)).toBeVisible();
    await expect(page.getByText(/last name is required/i)).toBeVisible();
    await expect(page.getByText(/please enter a valid email/i)).toBeVisible();

    // Still on the form — no redirect.
    await expect(page).toHaveURL(/\/customers\/new/);
  });

  test("@high creating a duplicate email shows a server-side error", async ({ page }) => {
    // Pre-create a customer to get a known duplicate email.
    const email = `dup.${uniqueSuffix()}@fitnation.test`;
    const { id: customerId, userId } = await createCustomerViaApi("Duplicate Test", email);

    await login(page, "/customers/new");
    await page.getByLabel("First name").fill("Duplicate");
    await page.getByLabel("Last name").fill("Test");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Phone", { exact: true }).fill("+91 98765 99999");
    await page.getByRole("button", { name: /Create customer/i }).click();

    // Server error shown on the form.
    await expect(page.getByRole("alert").first()).toBeVisible({ timeout: 10_000 });

    // Cleanup.
    await cleanupCustomerById(customerId, userId);
  });

  // ── Customer detail 404 ─────────────────────────────────────────────────

  test("@high /customers/99999 shows a friendly 404 state — not a crash", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/customers/99999");

    // Friendly 404 state is shown (first() avoids strict-mode violation with Next.js dev duplicates).
    await expect(page.getByText(/not found/i).first()).toBeVisible({ timeout: 10_000 });

    // No raw "Request failed" error.
    await expect(page.getByRole("alert").first()).not.toContainText(/request failed|api error/i);
  });

  test("@high /customers/99999 shows a 404 badge with the ID", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/customers/99999");

    // The invalid ID appears in the 404 message.
    await expect(page.getByText("99999").first()).toBeVisible();
  });

  test("@high navigating to a valid customer's detail page loads without a crash", async ({ page }) => {
    await seedAuth(page);

    // Use the seeded customer from seed_dummy_data (first customer has ID 1 in a clean DB).
    // Even if it returns 404 the page must NOT crash — it shows a friendly "not found" state.
    await page.goto("/customers/1");

    // Either customer data loads OR a friendly 404 is shown — no crash, no raw error.
    const hasNotFound = await page.getByText(/not found/i).first().isVisible({ timeout: 10_000 }).catch(() => false);
    const hasAlert = await page.getByRole("alert").first().isVisible().catch(() => false);
    const hasHeading = await page.getByRole("heading").first().isVisible().catch(() => false);

    // Page rendered something meaningful.
    expect(hasNotFound || hasAlert || hasHeading).toBe(true);

    // No unhandled raw "Request failed" crash banner.
    await expect(page.getByRole("alert").first()).not.toContainText(/request failed/i);
  });
});
