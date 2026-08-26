/**
 * @high workouts
 *
 * Workout plan assignment flow: a fresh customer and a fresh workout plan are
 * seeded via the API, then an authenticated owner assigns the plan to the
 * customer through the UI and verifies the assignment appears in the
 * assignment table on the same page.
 *
 * The plan/customer are seeded via API (deterministic, no reliance on prior
 * data) while the assignment itself is performed through the real UI — this is
 * the critical user journey under test.
 */
import { test, expect } from "@playwright/test";
import {
  login,
  seedAuth,
  createCustomerViaApi,
  createWorkoutPlanViaApi,
  tableTexts,
  uniqueSuffix,
} from "./utils";

test.describe("Workout plan assignment", () => {
  test("@high assign a workout plan to a customer and verify the assignment", async ({
    page,
  }) => {
    const suffix = uniqueSuffix();
    const customerEmail = `e2e.wk.customer.${suffix}@fitnation.test`;
    const planName = `E2E Plan ${suffix}`;
    const customerName = `WkCustomer${suffix}`;

    // Deterministic setup via API.
    const { id: customerId } = await createCustomerViaApi(customerName, customerEmail);
    const { id: planId } = await createWorkoutPlanViaApi(planName);

    await seedAuth(page);
    await page.goto("/workouts/assign");
    await expect(page.getByRole("heading", { name: /Assign/i })).toBeVisible();

    // Fill the assignment form (select by value to avoid label-suffix fragility).
    await page.locator("#customer").selectOption(String(customerId));
    await page.locator("#workout_plan").selectOption(String(planId));
    await page.getByLabel("Start date").fill("2026-08-25");
    await page.getByLabel("Notes").fill("E2E assignment");

    await page.getByRole("button", { name: /Assign plan/i }).click();

    // Success toast + the new assignment row appears in the table.
    await expect(page.getByText("Workout plan assigned")).toBeVisible();
    await expect
      .poll(async () => (await tableTexts(page)).join("\n"))
      .toContain(planName);

    // Cleanup seeded data so reruns stay green.
    await page.request.delete(`/api/v1/workouts/workout-plans/${planId}/`, {
      headers: { Authorization: `Token ${await getApiTokenLocal(page)}` },
    });
    await page.request.delete(`/api/v1/customers/customers/${customerId}/`, {
      headers: { Authorization: `Token ${await getApiTokenLocal(page)}` },
    });
  });
});

/** Grab a token from the seeded page context for cleanup API calls. */
async function getApiTokenLocal(page: import("@playwright/test").Page): Promise<string> {
  return page.evaluate(() => localStorage.getItem("fbos_auth_token") ?? "");
}
