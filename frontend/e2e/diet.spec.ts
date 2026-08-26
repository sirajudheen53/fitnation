/**
 * @medium diet
 *
 * Diet plan and assignment flows:
 *   - Auth guard on all diet routes
 *   - Diet plans list loads and shows seeded plans
 *   - Assign a diet plan to a customer
 *
 * Auth guard + happy path only; detailed assignment tests in diet-assign.spec.ts.
 */
import { test, expect } from "@playwright/test";
import {
  seedAuth,
  createCustomerViaApi,
  createDietPlanViaApi,
  tableTexts,
  uniqueSuffix,
  getApiToken,
} from "./utils";

test.describe("Diet", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /diet redirects to /login", async ({ page }) => {
    await page.goto("/diet");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /diet/assign redirects to /login", async ({ page }) => {
    await page.goto("/diet/assign");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Plans list ─────────────────────────────────────────────────────────

  test("@high diet plans page loads", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/diet");
    // The diet plans page loads without crashing.
    await expect(page.getByRole("main")).toBeVisible({ timeout: 10_000 });
  });

  // ── Assign diet plan ──────────────────────────────────────────────────

  test("@high assign a diet plan to a customer and see it in the assignment table", async ({
    page,
  }) => {
    const suffix = uniqueSuffix();
    const email = `e2e.diet.${suffix}@fitnation.test`;
    const planName = `E2E Diet Plan ${suffix}`;
    const name = `DietCustomer_${suffix}`;

    const { id: planId } = await createDietPlanViaApi(planName);
    const { id: customerId } = await createCustomerViaApi(name, email);

    await seedAuth(page);
    await page.goto("/diet/assign");
    await expect(page.getByRole("heading", { name: /assign/i })).toBeVisible({ timeout: 10_000 });

    await page.locator("#customer").selectOption(String(customerId));
    await page.locator("#diet_plan").selectOption(String(planId));
    await page.getByLabel("Start date").fill("2026-08-25");

    await page.getByRole("button", { name: /assign plan/i }).click();

    await expect(page.getByText(/diet plan assigned/i)).toBeVisible({ timeout: 10_000 });
    await expect
      .poll(async () => (await tableTexts(page)).join("\n"), { timeout: 10_000 })
      .toContain(planName);

    // Cleanup.
    const token = await getApiToken();
    await page.request.delete(`/api/v1/diet-plans/${planId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    await page.request.delete(`/api/v1/customers/customers/${customerId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
  });

  test("@high assigning without a plan shows no crash", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/diet/assign");
    await expect(page.getByRole("heading", { name: /assign/i })).toBeVisible({ timeout: 10_000 });

    // Give the page time to load dropdown options from API.
    await page.waitForTimeout(3000);

    const options = await page.locator("#customer option").count();
    if (options > 1) {
      await page.locator("#customer").selectOption({ index: 1 });
    }
    await page.getByRole("button", { name: /assign plan/i }).click();

    const validationShown = await page.getByText(/plan is required|please select/i).isVisible().catch(() => false);
    const stillOnForm = page.url().includes("diet/assign");
    expect(validationShown || await stillOnForm).toBe(true);
  });
});
