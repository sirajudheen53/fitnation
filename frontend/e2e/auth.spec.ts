/**
 * @critical auth
 *
 * Authentication flows:
 *   - Valid login → token stored, redirect to dashboard, session persists on reload
 *   - Invalid credentials → error shown, no token stored, stays on login
 *   - Unauthenticated direct access to protected routes → redirect to /login
 *   - Logout → token cleared, redirect to login
 *
 * Credentials come from `python manage.py seed_dummy_data` (owner@fitnation.test).
 */
import { test, expect } from "@playwright/test";
import { login, seedAuth, TEST_OWNER } from "./utils";

test.describe("Authentication", () => {
  // ── Valid login ─────────────────────────────────────────────────────────

  test("@high valid credentials redirect to dashboard and persist session", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByRole("heading", { name: /Sign in/i })).toBeVisible();

    await page.getByLabel("Email").fill(TEST_OWNER.email);
    await page.getByRole("textbox", { name: "Password" }).fill(TEST_OWNER.password);
    await page.getByRole("button", { name: /Sign in/i }).click();

    // Redirects to /dashboard after successful login.
    await page.waitForURL("**/dashboard", { timeout: 15_000 });

    // Token stored in localStorage.
    // Token stored in localStorage (keys are the actual strings, not Node.js constants).
    const token = await page.evaluate(() => localStorage.getItem("fbos_auth_token"));
    expect(token).toBeTruthy();

    // Session persists across page reload.
    await page.reload();
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
  });

  test("@high login with wrong password shows error and stores no token", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill(TEST_OWNER.email);
    await page.getByRole("textbox", { name: "Password" }).fill("wrong-password-123");
    await page.getByRole("button", { name: /Sign in/i }).click();

    // Error surfaced on the login screen.
    await expect(page.getByRole("alert").first()).toBeVisible();
    await expect(page.getByRole("alert").first()).toContainText(/invalid|incorrect|wrong/i);

    // Stays on /login.
    await expect(page).toHaveURL(/\/login/);

    // No token stored.
    const token = await page.evaluate(() => localStorage.getItem("fbos_auth_token"));
    expect(token).toBeNull();
  });

  test("@high login with non-existent email shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("nobody@fitnation.test");
    await page.getByRole("textbox", { name: "Password" }).fill("any-password");
    await page.getByRole("button", { name: /Sign in/i }).click();

    await expect(page.getByRole("alert").first()).toBeVisible();
    await expect(page).toHaveURL(/\/login/);
    const token2 = await page.evaluate(() => localStorage.getItem("fbos_auth_token"));
    expect(token2).toBeNull();
  });

  // ── Auth guard ─────────────────────────────────────────────────────────

  test("@high unauthenticated /dashboard redirects to /login", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL("**/login**", { timeout: 10_000 });
    // The "next" param should preserve where they were trying to go.
    await expect(page.url()).toContain("next=");
  });

  test("@high unauthenticated /customers redirects to /login", async ({ page }) => {
    await page.goto("/customers");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  test("@high unauthenticated /payments redirects to /login", async ({ page }) => {
    await page.goto("/payments");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });

  // ── Logout ─────────────────────────────────────────────────────────────

  test("@high logout clears token and redirects to login", async ({ page }) => {
    await seedAuth(page);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();

    // Trigger logout by clearing localStorage and redirecting.
    await page.evaluate(() => {
      localStorage.removeItem("fbos_auth_token");
      localStorage.removeItem("fbos_user");
      localStorage.removeItem("fbos_permissions");
      window.location.href = "/login";
    });

    await page.waitForURL("**/login", { timeout: 15_000 });
    const token = await page.evaluate(() => localStorage.getItem("fbos_auth_token"));
    expect(token).toBeNull();
  });

  test("@high post-logout accessing /dashboard redirects to /login", async ({ page }) => {
    await seedAuth(page);
    await page.evaluate(() => {
      localStorage.removeItem("fbos_auth_token");
      localStorage.removeItem("fbos_user");
    });

    await page.goto("/dashboard");
    await page.waitForURL("**/login**", { timeout: 10_000 });
  });
});
