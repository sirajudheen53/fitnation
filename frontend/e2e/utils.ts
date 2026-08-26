import { expect, type Page } from "@playwright/test";

/**
 * Shared helpers for FBOS E2E tests.
 *
 * These helpers drive the real UI and make direct API calls to the real
 * Django backend for setup/teardown (e.g. creating a fresh customer to
 * assign a plan to), keeping tests deterministic without mocking.
 */

// Credentials for the seeded owner user (python manage.py seed_dummy_data).
export const TEST_OWNER = {
  email: "owner@fitnation.test",
  password: "FitLocal!23",
};
const TEST_EMAIL = TEST_OWNER;

export const API_BASE = process.env.E2E_API_URL || "http://localhost:8000/api/v1";

/** localStorage keys used by lib/auth.ts and lib/api.ts */
export const TOKEN_KEY = "fbos_auth_token";
export const USER_KEY = "fbos_user";
export const PERMISSIONS_KEY = "fbos_permissions";

/** A short, unique suffix for test-created records to avoid collisions. */
export function uniqueSuffix(): string {
  return `${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
}

/**
 * Log in through the real UI form. Fills the login page, submits, and waits
 * for the redirect to `next` (default /dashboard).
 */
export async function login(page: Page, next = "/dashboard"): Promise<void> {
  await page.goto(`/login?next=${next}`);
  await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();

  await page.getByLabel("Email").fill(TEST_EMAIL.email);
  await page.getByRole("textbox", { name: "Password" }).fill(TEST_EMAIL.password);
  await page.getByRole("button", { name: /Sign in/i }).click();

  // Wait for the authenticated redirect to land.
  await page.waitForURL(`**${next}`, { timeout: 15_000 });
}

/**
 * Seed auth state directly into localStorage (fast path for tests that don't
 * need to exercise the login form itself). Logs in over the API once to get a
 * real token, then injects it into the page context.
 */
export async function seedAuth(page: Page): Promise<void> {
  const token = await getApiToken();
  await page.goto("/");
  await page.evaluate(
    (token) => {
      localStorage.setItem("fbos_auth_token", token);
      localStorage.setItem(
        "fbos_user",
        JSON.stringify({
          id: 1,
          email: "owner@fitnation.test",
          name: "Rajesh Mehta",
          role: "gym_owner",
          tenant_id: 1,
          tenant_name: "FitNation Test Gym",
          is_owner: true,
        }),
      );
      localStorage.setItem("fbos_permissions", JSON.stringify([]));
    },
    token,
  );
}

/** Get a fresh API token via the real login endpoint. */
export async function getApiToken(): Promise<string> {
  const res = await fetch(`${API_BASE}/users/auth/login/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email: TEST_EMAIL.email, password: TEST_EMAIL.password, device_type: "web" }),
  });
  if (!res.ok) {
    throw new Error(`API login failed: ${res.status}`);
  }
  const data = (await res.json()) as { token: string };
  return data.token;
}

/**
 * Delete every test-created record of a given list resource whose name/email
 * starts with a marker. Used in beforeEach to keep the DB clean.
 */
export async function cleanupByPrefix(resource: string, field: string, prefix: string): Promise<void> {
  const token = await getApiToken();
  const res = await fetch(`${API_BASE}${resource}`, {
    headers: { Authorization: `Token ${token}` },
  });
  if (!res.ok) return;
  const body = (await res.json()) as { results?: Array<Record<string, unknown>> };
  const results = body.results ?? (body as unknown as Array<Record<string, unknown>>);
  for (const item of Array.isArray(results) ? results : []) {
    const val = item[field];
    if (typeof val === "string" && val.startsWith(prefix)) {
      const id = item.id;
      if (id != null) {
        await fetch(`${API_BASE}${resource}${id}/`, {
          method: "DELETE",
          headers: { Authorization: `Token ${token}` },
        }).catch(() => {});
      }
    }
  }
}

/**
 * Create a customer via the API and return its id. Useful as deterministic
 * setup for plan-assignment tests.
 *
 * In the backend, creating a `customer`-role user auto-creates the linked
 * Customer profile (see apps/users/services.py). We therefore create the
 * user and then look up the auto-created customer by email — we do NOT call
 * the customers/ create endpoint directly (it expects `user`/`name` and is a
 * separate path).
 */
export async function createCustomerViaApi(
  name: string,
  email: string,
): Promise<{ id: number; userId: number }> {
  const token = await getApiToken();
  const [firstName, ...rest] = name.split(" ");
  const lastName = rest.join(" ") || "E2E";

  // Create a customer-role user; the backend auto-creates the Customer profile.
  const userRes = await fetch(`${API_BASE}/users/users/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Token ${token}` },
    body: JSON.stringify({
      email,
      first_name: firstName,
      last_name: lastName,
      role: "customer",
      password: "TestPass123!",
    }),
  });
  if (!userRes.ok) {
    throw new Error(`createCustomerViaApi: user create failed ${userRes.status} ${await userRes.text()}`);
  }
  const createdUser = (await userRes.json()) as { id: number };

  // Look up the auto-created customer by the unique email.
  const listRes = await fetch(`${API_BASE}/customers/customers/?email=${encodeURIComponent(email)}`, {
    headers: { Authorization: `Token ${token}` },
  });
  if (!listRes.ok) {
    throw new Error(`createCustomerViaApi: customer lookup failed ${listRes.status}`);
  }
  const body = (await listRes.json()) as { results?: Array<{ id: number }> };
  const customer = (body.results ?? []).find((c) => c.id != null);
  if (!customer) {
    throw new Error(`createCustomerViaApi: customer not found for ${email}`);
  }
  return { id: customer.id, userId: createdUser.id };
}

/** Extract text rows from a data table for asserting a record is present. */
export async function tableTexts(page: Page): Promise<string[]> {
  return page.locator("table tbody tr").allTextContents();
}

/**
 * Delete a customer record by email lookup, then delete the associated user.
 * Used in afterEach to ensure test-created records are always cleaned up.
 */
export async function cleanupCustomerByEmail(email: string): Promise<void> {
  const token = await getApiToken();
  const listRes = await fetch(
    `${API_BASE}/customers/customers/?email=${encodeURIComponent(email)}`,
    { headers: { Authorization: `Token ${token}` } },
  );
  if (!listRes.ok) return;
  const body = (await listRes.json()) as { results?: Array<{ id: number; user?: number }> };
  const customer = (body.results ?? []).find((c) => c.id != null);
  if (!customer) return;
  // Delete customer profile first.
  await fetch(`${API_BASE}/customers/customers/${customer.id}/`, {
    method: "DELETE",
    headers: { Authorization: `Token ${token}` },
  }).catch(() => {});
  // Then delete the user account.
  if (customer.user) {
    await fetch(`${API_BASE}/users/users/${customer.user}/`, {
      method: "DELETE",
      headers: { Authorization: `Token ${token}` },
    }).catch(() => {});
  }
}

/**
 * Delete a customer record by ID, then delete the associated user.
 * Used in afterEach for tests that create customers via the API.
 */
export async function cleanupCustomerById(customerId: number, userId?: number): Promise<void> {
  const token = await getApiToken();
  await fetch(`${API_BASE}/customers/customers/${customerId}/`, {
    method: "DELETE",
    headers: { Authorization: `Token ${token}` },
  }).catch(() => {});
  if (userId) {
    await fetch(`${API_BASE}/users/users/${userId}/`, {
      method: "DELETE",
      headers: { Authorization: `Token ${token}` },
    }).catch(() => {});
  }
}

/**
 * Create a workout plan via the API and return its id.
 * The plan is created with no days so it is assignable right away.
 */
export async function createWorkoutPlanViaApi(name: string): Promise<{ id: number }> {
  const token = await getApiToken();
  const res = await fetch(`${API_BASE}/workouts/workout-plans/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Token ${token}` },
    body: JSON.stringify({
      name,
      description: "E2E seeded plan",
      goal: "general_fitness",
      difficulty: "beginner",
      duration_weeks: 4,
      is_template: false,
      days: [],
    }),
  });
  if (!res.ok) {
    throw new Error(`createWorkoutPlanViaApi failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as { id: number };
}

/**
 * Create a diet plan via the API and return its id.
 */
export async function createDietPlanViaApi(name: string): Promise<{ id: number }> {
  const token = await getApiToken();
  const res = await fetch(`${API_BASE}/diet-plans/`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Token ${token}` },
    body: JSON.stringify({ name, description: "E2E seeded diet plan" }),
  });
  if (!res.ok) {
    throw new Error(`createDietPlanViaApi failed: ${res.status} ${await res.text()}`);
  }
  return (await res.json()) as { id: number };
}
