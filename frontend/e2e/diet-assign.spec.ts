/**
 * @medium diet
 *
 * Diet plan assignment flow: a fresh customer and a fresh diet plan are seeded
 * via the API, then an authenticated owner assigns the diet plan to the
 * customer through the UI and verifies the assignment appears in the table.
 */
import { test, expect } from "@playwright/test";
import {
  seedAuth,
  createCustomerViaApi,
  createDietPlanViaApi,
  tableTexts,
  uniqueSuffix,
} from "./utils";

test.describe("Diet plan assignment", () => {
  test("@medium assign a diet plan to a customer and verify the assignment", async ({
    page,
  }) => {
    const suffix = uniqueSuffix();
    const customerEmail = `e2e.diet.customer.${suffix}@fitnation.test`;
    const planName = `E2E Diet Plan ${suffix}`;
    const customerName = `DietCustomer${suffix}`;

    const { id: customerId } = await createCustomerViaApi(customerName, customerEmail);
    const { id: planId } = await createDietPlanViaApi(planName);

    await seedAuth(page);
    await page.goto("/diet/assign");
    await expect(page.getByRole("heading", { name: /Assign/i })).toBeVisible();

    // Select by value to avoid option-label fragility.
    await page.locator("#customer").selectOption(String(customerId));
    await page.locator("#diet_plan").selectOption(String(planId));
    await page.getByLabel("Start date").fill("2026-08-25");

    await page.getByRole("button", { name: /Assign plan/i }).click();

    await expect(page.getByText(/Diet plan assigned/i)).toBeVisible();
    await expect
      .poll(async () => (await tableTexts(page)).join("\n"))
      .toContain(planName);

    const token = await page.evaluate(() => localStorage.getItem("fbos_auth_token") ?? "");
    await page.request.delete(`/api/v1/diet-plans/${planId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    await page.request.delete(`/api/v1/customers/customers/${customerId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
  });
});
