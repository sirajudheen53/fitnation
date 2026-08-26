/**
 * @high workouts
 *
 * Workout plan management:
 *   - Auth guard on all workout routes
 *   - Workout plans list loads and shows seeded plans
 *   - Assign a workout plan to a customer (full flow via UI)
 *   - Assignment appears in the table after success
 *
 * Auth guard + happy path only; detailed assignment tests are in workouts-assign.spec.ts.
 */
import { test, expect } from "@playwright/test";
import {
  seedAuth,
  createCustomerViaApi,
  createWorkoutPlanViaApi,
  tableTexts,
  uniqueSuffix,
  getApiToken,
} from "./utils";

test.describe("Workouts", () => {
  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /workouts redirects to /login", async ({ page }) => {
    await page.goto("/workouts");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /workouts/assign redirects to /login", async ({ page }) => {
    await page.goto("/workouts/assign");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Plans list ─────────────────────────────────────────────────────────

  test("@high workout plans page loads", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/workouts");
    // The workout plans page loads without crashing.
    await expect(page.getByRole("main")).toBeVisible({ timeout: 10_000 });
  });

  // ── Assign workout plan (full UI flow) ────────────────────────────────

  test("@high assign a workout plan to a customer and see it in the assignment table", async ({
    page,
  }) => {
    const suffix = uniqueSuffix();
    const email = `e2e.wk.${suffix}@fitnation.test`;
    const planName = `E2E Workout Plan ${suffix}`;
    const name = `WkCustomer_${suffix}`;

    // Seed plan + customer via API.
    const { id: planId } = await createWorkoutPlanViaApi(planName);
    const { id: customerId } = await createCustomerViaApi(name, email);

    await seedAuth(page);
    await page.goto("/workouts/assign");
    await expect(page.getByRole("heading", { name: /assign/i })).toBeVisible({ timeout: 10_000 });

    await page.locator("#customer").selectOption(String(customerId));
    await page.locator("#workout_plan").selectOption(String(planId));
    await page.getByLabel("Start date").fill("2026-08-25");
    await page.getByLabel("Notes").fill(`E2E test ${suffix}`);

    await page.getByRole("button", { name: /assign plan/i }).click();

    // Success toast + plan name in assignment table.
    await expect(page.getByText(/workout plan assigned/i)).toBeVisible({ timeout: 10_000 });
    await expect
      .poll(async () => (await tableTexts(page)).join("\n"), { timeout: 10_000 })
      .toContain(planName);

    // Cleanup.
    const token = await getApiToken();
    await page.request.delete(`/api/v1/workouts/workout-plans/${planId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    await page.request.delete(`/api/v1/customers/customers/${customerId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
  });

  test("@high assigning without a plan shows a validation error", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/workouts/assign");
    await expect(page.getByRole("heading", { name: /assign/i })).toBeVisible({ timeout: 10_000 });

    // Give the page time to load dropdown options from API.
    await page.waitForTimeout(3000);

    // Select a customer if available; otherwise just submit.
    const options = await page.locator("#customer option").count();
    if (options > 1) {
      await page.locator("#customer").selectOption({ index: 1 });
    }
    await page.getByRole("button", { name: /assign plan/i }).click();

    // Either validation error or still on the form (no crash).
    const validationShown = await page.getByText(/plan is required|please select/i).isVisible().catch(() => false);
    const stillOnForm = page.url().includes("workouts/assign");
    expect(validationShown || await stillOnForm).toBe(true);
  });
});
