import {
  deriveAppAccessDisplay,
  describeInviteStatus,
  inviteOutcomeToast,
} from "@/features/customers/lib/appAccess";
import type { Customer } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";

const TODAY = "2026-10-21";

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

describe("deriveAppAccessDisplay", () => {
  it("prefers the server entitlement block when present (active)", () => {
    const display = deriveAppAccessDisplay(
      customer({ app_access: { status: "active", read_only: false, plan_name: "Yearly", end_date: "2027-01-01", grace_end_date: null } }),
      null,
      [],
      TODAY,
    );
    expect(display).toMatchObject({ status: "active", label: "Entitled", variant: "success", planName: "Yearly" });
  });

  it("maps the server grace block to the read-only label with its grace date", () => {
    const display = deriveAppAccessDisplay(
      customer({ app_access: { status: "grace", read_only: true, plan_name: "Monthly", end_date: "2026-10-14", grace_end_date: "2026-10-21" } }),
      null,
      [],
      TODAY,
    );
    expect(display).toMatchObject({ status: "grace", label: "Read-only grace", variant: "warning", graceEndDate: "2026-10-21" });
  });

  it("falls back to derivation: active membership on an app-included plan is entitled", () => {
    const display = deriveAppAccessDisplay(
      customer(),
      [membership({ end_date: "2026-11-20", status: "active" })],
      [plan()],
      TODAY,
    );
    expect(display).toMatchObject({
      status: "active",
      label: "Entitled",
      variant: "success",
      planName: "Monthly",
      endDate: "2026-11-20",
    });
  });

  it("derives read-only grace within 7 days after end_date (ADR-003 D2)", () => {
    // end_date 2026-10-20 → grace until 2026-10-27; today 2026-10-21 is day 1.
    const display = deriveAppAccessDisplay(
      customer(),
      [membership({ end_date: "2026-10-20", status: "expired" })],
      [plan()],
      TODAY,
    );
    expect(display).toMatchObject({ status: "grace", label: "Read-only grace", graceEndDate: "2026-10-27" });
  });

  it("derives expired beyond the grace window", () => {
    const display = deriveAppAccessDisplay(
      customer(),
      [membership({ end_date: "2026-09-01", status: "expired" })],
      [plan()],
      TODAY,
    );
    expect(display).toMatchObject({ status: "expired", label: "Expired", variant: "danger" });
  });

  it("treats a plan with includes_app_access=false as not entitled even when active", () => {
    const display = deriveAppAccessDisplay(
      customer(),
      [membership({ end_date: "2026-11-20", status: "active" })],
      [plan({ includes_app_access: false })],
      TODAY,
    );
    expect(display).toMatchObject({ status: "none", label: "Plan excludes app", variant: "danger" });
  });

  it("ignores cancelled memberships (immediate revoke, no grace)", () => {
    const display = deriveAppAccessDisplay(
      customer(),
      [membership({ status: "cancelled", end_date: "2026-11-20" })],
      [plan()],
      TODAY,
    );
    expect(display.status).toBe("unknown");
  });

  it("reports unknown when there is no membership data at all", () => {
    expect(deriveAppAccessDisplay(customer(), null, [], TODAY).status).toBe("unknown");
  });
});

describe("describeInviteStatus", () => {
  it("offers a first send when the member was never invited", () => {
    const display = describeInviteStatus(null);
    expect(display).toMatchObject({ label: "Never invited", actionLabel: "Send app invite", force: false });
  });

  it("shows a successful WhatsApp invite with a forced resend", () => {
    const display = describeInviteStatus({
      status: "sent",
      channel: "whatsapp",
      sent_at: "2026-10-21T10:00:00Z",
      error_message: null,
    });
    expect(display.variant).toBe("success");
    expect(display.label).toContain("WhatsApp");
    expect(display.actionLabel).toBe("Resend invite");
    expect(display.force).toBe(true);
  });

  it("surfaces failures with a retry that does not force", () => {
    const display = describeInviteStatus({
      status: "failed",
      channel: null,
      sent_at: null,
      error_message: "WATI down",
    });
    expect(display.variant).toBe("danger");
    expect(display.actionLabel).toBe("Retry invite");
    expect(display.force).toBe(false);
    expect(display.detail).toBe("WATI down");
  });

  it("maps skipped to the owner nudge copy", () => {
    const display = describeInviteStatus({
      status: "skipped",
      channel: null,
      sent_at: null,
      error_message: null,
    });
    expect(display.variant).toBe("warning");
    expect(display.detail).toContain("WhatsApp not configured");
  });

  // #102: the raw machine outcome ("Last invite: not_applicable") read like
  // "not available" and contradicted the card's Entitled badge. These pin the
  // explicit per-reason copy and the no-CTA behaviour.
  describe("not_applicable (#102)", () => {
    const invite = (reason: string | null) => ({
      status: "not_applicable",
      channel: null,
      sent_at: null,
      error_message: reason,
    });

    it("names the rollout flag as the blocker for flag_off", () => {
      const display = describeInviteStatus(invite("flag_off"));
      expect(display.status).toBe("not_applicable");
      expect(display.label).toBe("App invites not enabled for this gym");
      expect(display.detail).toContain("App access is not enabled for this gym");
    });

    it("names the plan for plan_excludes_app", () => {
      const display = describeInviteStatus(invite("plan_excludes_app"));
      expect(display.label).toBe("Plan does not include the app");
      expect(display.detail).toContain("plan does not include app access");
    });

    it("stays explicit for an unrecognized reason", () => {
      const display = describeInviteStatus(invite("something_new"));
      expect(display.label).toBe("Invite not applicable to this member");
      expect(display.label).not.toContain("_");
    });

    it("drops the CTA — resending returns the same verdict", () => {
      for (const reason of ["flag_off", "plan_excludes_app", null]) {
        expect(describeInviteStatus(invite(reason)).actionLabel).toBeNull();
      }
    });

    it("never leaks the raw machine code into the label", () => {
      for (const reason of ["flag_off", "plan_excludes_app", null, "mystery"]) {
        expect(describeInviteStatus(invite(reason)).label).not.toContain("not_applicable");
      }
    });
  });

  it("shows already_sent as its own explicit state instead of the raw code", () => {
    const display = describeInviteStatus({
      status: "already_sent",
      channel: "whatsapp",
      sent_at: "2026-11-07T04:47:22Z",
      error_message: null,
    });
    expect(display.label).toBe("Invite already sent");
    expect(display.variant).toBe("success");
    expect(display.actionLabel).toBe("Resend invite");
    expect(display.force).toBe(true);
    expect(display.detail).toContain("Last sent");
  });

  it("never shows a bare machine status for unknown outcomes", () => {
    const display = describeInviteStatus({
      status: "mystery_state",
      channel: null,
      sent_at: null,
      error_message: null,
    });
    expect(display.label).toBe("Unknown invite state");
    expect(display.detail).toContain('recorded as "mystery_state"');
  });

  describe("inviteOutcomeToast (#102)", () => {
    it("toasts success with the channel for a sent invite", () => {
      expect(
        inviteOutcomeToast({ status: "sent", channel: "whatsapp", sent_at: null, error_message: null }),
      ).toEqual({ kind: "success", message: "Invite sent via WhatsApp" });
    });

    it("toasts the flag blocker copy for not_applicable", () => {
      const toast = inviteOutcomeToast({
        status: "not_applicable",
        channel: null,
        sent_at: null,
        error_message: "flag_off",
      });
      expect(toast.kind).toBe("warning");
      expect(toast.message).toContain("App access is not enabled for this gym");
    });

    it("toasts the skipped nudge and surfaces the failure reason on failed", () => {
      expect(
        inviteOutcomeToast({ status: "skipped", channel: null, sent_at: null, error_message: null }),
      ).toMatchObject({ kind: "warning" });
      expect(
        inviteOutcomeToast({ status: "failed", channel: null, sent_at: null, error_message: "Gupshup down" }),
      ).toEqual({ kind: "error", message: "Invite failed: Gupshup down" });
    });

    it("quotes an unknown status as a system value, never as the outcome itself", () => {
      const toast = inviteOutcomeToast({ status: "mystery_state", channel: null, sent_at: null, error_message: null });
      expect(toast.kind).toBe("warning");
      expect(toast.message).toBe('Invite outcome was "mystery_state" — no message went out.');
    });
  });
});
