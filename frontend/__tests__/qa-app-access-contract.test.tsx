/**
 * QA regression tests for the customer app-access workflow (Shield / QA).
 *
 * These pin the contract gap found during the FBOS-011 end-to-end
 * verification (docs/qa/app-access-e2e-verification.md): the ERP's
 * "App access" panel prefers a server-supplied `app_access` entitlement
 * block, but the backend's CustomerSerializer never emits one — so the
 * panel always falls back to a client-side guess that can disagree with
 * the server (the only authority on entitlement).
 *
 * These are regression guards, not fixes.
 *
 * Deterministic: no network, no real WhatsApp/SMS, no Play uploads.
 */

import { render, screen } from "@testing-library/react";
import { AppAccessCard } from "@/features/customers/components/AppAccessCard";
import { deriveAppAccessDisplay } from "@/features/customers/lib/appAccess";
import type { Customer } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  sendAppInvite: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const customer = (overrides: Partial<Customer> = {}): Customer =>
  ({
    id: 1,
    email: null,
    user: 11,
    name: "Asha Nair",
    branch: 2,
    status: "active",
    notes: "",
    address_street: "",
    address_city: "",
    address_state: "",
    address_postal_code: "",
    phone: "9876543210",
    gender: null,
    date_of_birth: null,
    emergency_contact_name: null,
    emergency_contact_phone: null,
    is_active: true,
    profile_photo: null,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  }) as Customer;

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan =>
  ({
    id: 7,
    name: "Monthly",
    price: "2500.00",
    duration_days: 30,
    plan_type: "monthly",
    description: null,
    is_active: true,
    includes_app_access: true,
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-01T00:00:00Z",
    ...overrides,
  }) as MembershipPlan;

const membership = (overrides: Partial<Membership> = {}): Membership =>
  ({
    id: 31,
    customer_id: 1,
    customer_name: "Asha Nair",
    plan_id: 7,
    plan_name: "Monthly",
    start_date: "2026-09-21",
    end_date: "2026-10-20",
    status: "active",
    price: 2500,
    created_at: "2026-09-21T00:00:00Z",
    updated_at: "2026-09-21T00:00:00Z",
    ...overrides,
  }) as Membership;

const TODAY = "2026-10-21";

describe("QA-03 — the customer payload must carry the server entitlement block", () => {
  /**
   * `deriveAppAccessDisplay` prefers the backend's `app_access` block when
   * present and only falls back to deriving from the member's membership
   * otherwise. The backend's CustomerSerializer does NOT emit `app_access`
   * today, so the ERP badge is always a client-side guess that can
   * disagree with the server — which is the only authority on entitlement.
   *
   * The expected behaviour: the customer payload carries the entitlement
   * block, so the panel reflects the server's verdict.
   */
  it("the server entitlement block is the source of truth when present", () => {
    const withServer = customer({
      app_access: {
        status: "grace",
        read_only: true,
        plan_name: "Monthly",
        end_date: "2026-10-20",
        grace_end_date: "2026-10-27",
      },
    });

    const display = deriveAppAccessDisplay(withServer, null, [], TODAY);

    expect(display.status).toBe("grace");
    expect(display.graceEndDate).toBe("2026-10-27");
  });

  it("a server 'expired' verdict is not overridden by a local active membership", () => {
    // The server says expired (the authority) while the local membership
    // rows still look active. The server must win.
    const withServer = customer({
      app_access: {
        status: "expired",
        read_only: false,
        plan_name: "Monthly",
        end_date: "2026-10-01",
        grace_end_date: "2026-10-08",
      },
    });
    const localActive = [membership({ end_date: "2026-12-31", status: "active" })];

    const display = deriveAppAccessDisplay(withServer, localActive, [plan()], TODAY);

    expect(display.status).toBe("expired");
  });
});

describe("QA-03b — the ERP panel renders the server's state, not a local guess", () => {
  /**
   * With no `app_access` block and no membership rows, the panel falls back
   * to "unknown / No membership" even though the backend knows the truth
   * (it computes the entitlement per request) — the panel just never asks
   * for it. These cases assert the expected rendering once the block is
   * delivered.
   */
  it("shows the entitled state from the server block", () => {
    render(
      <AppAccessCard
        customer={customer({
          app_access: {
            status: "active",
            read_only: false,
            plan_name: "Monthly",
            end_date: "2026-11-20",
            grace_end_date: null,
          },
        })}
        memberships={null}
        plans={[plan()]}
      />,
    );

    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Entitled");
  });

  it("shows the grace state with its read-only copy", () => {
    render(
      <AppAccessCard
        customer={customer({
          app_access: {
            status: "grace",
            read_only: true,
            plan_name: "Monthly",
            end_date: "2026-10-20",
            grace_end_date: "2026-10-27",
          },
        })}
        memberships={null}
        plans={[plan()]}
      />,
    );

    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Read-only grace");
    expect(screen.getByText(/read-only until/i)).toBeInTheDocument();
  });

  it("shows the not-entitled state for a member without app access", () => {
    render(
      <AppAccessCard
        customer={customer({
          app_access: {
            status: "none",
            read_only: false,
            plan_name: "Gym-only",
            end_date: "2026-11-20",
            grace_end_date: null,
          },
        })}
        memberships={null}
        plans={[plan()]}
      />,
    );

    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Not entitled");
  });
});
