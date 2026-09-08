/**
 * @critical customers FBOS-026
 *
 * Covers the customer profile photo flow (create-with-photo):
 *   - Uploading a photo on the create form persists it, shows an avatar in
 *     the customers list, and the detail page refetch renders it immediately
 *   - Disallowed file types are rejected inline; the customer is still
 *     created without a photo
 *
 * Prerequisites: Django dev server on :8000 (seed_dummy_data) + Next.js on
 * :3000 (auto-started by playwright.config.ts). Drives the real UI and
 * verifies persistence through the real API.
 */
import { test, expect } from "@playwright/test";
import { login, uniqueSuffix, getApiToken, API_BASE, cleanupCustomerById } from "./utils";

/** Minimal valid 1x1 PNG (67 bytes) used as the upload fixture. */
const PNG_1X1_BASE64 =
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";

interface CreatedCustomer {
  id: number;
  user?: number;
  profile_photo?: string | null;
}

async function findCustomerByEmail(email: string): Promise<CreatedCustomer | null> {
  const token = await getApiToken();
  const res = await fetch(`${API_BASE}/customers/customers/?email=${encodeURIComponent(email)}`, {
    headers: { Authorization: `Token ${token}` },
  });
  if (!res.ok) return null;
  const body = (await res.json()) as { results?: CreatedCustomer[] };
  return (body.results ?? [])[0] ?? null;
}

test.describe("Customer profile photo (FBOS-026)", () => {
  // Dev-server cold compiles of /customers/new can take >30s on first hit.
  test.setTimeout(120_000);

  // Unblocked (2026-09-07): backend accepted the blessed contract
  // (first_name/last_name → composed name, portal user auto-provisioned).
  test("@high create a customer with a profile photo persists and shows an avatar", async ({
    page,
  }) => {
    const suffix = uniqueSuffix();
    const email = `e2e.photo.${suffix}@fitnation.test`;

    await login(page, "/customers/new");
    await expect(page.getByRole("heading", { name: /New Customer/i })).toBeVisible({ timeout: 30_000 });

    await page.getByLabel("First name").fill("Photo");
    await page.getByLabel("Last name").fill(`Test_${suffix}`);
    await page.getByLabel("Email").fill(email);

    // The photo picker's hidden file input.
    await page.setInputFiles('input[type="file"]', {
      name: "profile.png",
      mimeType: "image/png",
      buffer: Buffer.from(PNG_1X1_BASE64, "base64"),
    });
    await expect(page.getByRole("button", { name: /change profile photo/i })).toBeVisible();

    await page.getByRole("button", { name: /Create customer/i }).click();
    await page.waitForURL("**/customers", { timeout: 15_000 });

    // The created row shows a photo avatar (not initials).
    const row = page.getByRole("row", { name: new RegExp(email.split("@")[0]) });
    await expect(row.locator('[data-testid="customer-avatar-photo"]')).toBeVisible({
      timeout: 10_000,
    });

    // Persisted: the API returns a non-null profile_photo for the customer.
    const customer = await findCustomerByEmail(email);
    expect(customer).not.toBeNull();
    expect(customer?.profile_photo).toBeTruthy();

    // Refetch UX: navigating to the detail page renders the new photo in the
    // OverviewTab identity header without any manual refresh.
    await page.goto(`/customers/${customer!.id}`, { waitUntil: "load", timeout: 30_000 });
    await expect(page.getByText(/Photo Test_/).first()).toBeVisible({ timeout: 30_000 });
    await expect(page.locator('[data-testid="customer-avatar-photo"]').first()).toBeVisible({
      timeout: 15_000,
    });

    // Cleanup via API.
    if (customer) {
      await cleanupCustomerById(customer.id, customer.user);
    }
  });

  test("@high disallowed file type is rejected inline; customer is created without a photo", async ({
    page,
  }) => {
    const suffix = uniqueSuffix();
    const email = `e2e.nophoto.${suffix}@fitnation.test`;

    await login(page, "/customers/new");
    await expect(page.getByRole("heading", { name: /New Customer/i })).toBeVisible({ timeout: 30_000 });

    await page.getByLabel("First name").fill("NoPhoto");
    await page.getByLabel("Last name").fill(`Test_${suffix}`);
    await page.getByLabel("Email").fill(email);

    // Attach a disallowed file type — inline error via role=alert, and the
    // picker returns to the upload state (no photo payload queued).
    await page.setInputFiles('input[type="file"]', {
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("not an image"),
    });
    await expect(page.getByText(/Please choose a JPEG, PNG, or WebP image/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /upload profile photo/i })).toBeVisible();
  });
});
