import {
  buildOnboardingPayload,
  describeAppInvite,
  initialFormState,
  isFreeTrial,
  paymentMethodLabel,
} from "@/features/onboarding/lib/wizard";
import type { MembershipPlan } from "@/types/membership";
import type { AppInviteBlock } from "@/types/onboarding";

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan => ({
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
});

const baseState = () => ({
  ...initialFormState(2),
  phone: "9876543210",
  name: "Asha Nair",
  branchId: 2,
  startDate: "2026-10-21",
  endDate: "2026-11-20",
  paymentMethod: "cash" as const,
  amount: "2500",
});

describe("buildOnboardingPayload", () => {
  it("maps the wizard state onto the backend contract (membership.plan, biometrics plural)", () => {
    const payload = buildOnboardingPayload(
      { ...baseState(), deviceId: 3, deviceUserId: "1017" },
      plan(),
    );
    expect(payload.customer).toEqual({
      phone: "9876543210",
      name: "Asha Nair",
      branch: 2,
    });
    expect(payload.membership).toEqual({
      plan: 7,
      start_date: "2026-10-21",
      end_date: "2026-11-20",
    });
    expect(payload.payment).toEqual({ method: "cash", amount: 2500, notes: undefined });
    expect(payload.biometrics).toEqual([
      { device: 3, credential_type: "fingerprint", device_user_id: "1017" },
    ]);
  });

  it("omits empty optional customer fields and keeps the emergency contact under the right keys", () => {
    const payload = buildOnboardingPayload(
      {
        ...baseState(),
        email: "asha@example.com",
        emergencyContactName: "Ravi",
        emergencyContactPhone: "9990001111",
        notes: "  morning batch  ",
      },
      plan(),
    );
    expect(payload.customer).toMatchObject({
      email: "asha@example.com",
      emergency_contact_name: "Ravi",
      emergency_contact_phone: "9990001111",
      notes: "morning batch",
    });
  });

  it("omits the payment block entirely for a ₹0 trial (no payment row backend-side)", () => {
    const trialPlan = plan({ id: 12, plan_type: "trial", price: "0.00" });
    const payload = buildOnboardingPayload(
      { ...baseState(), paymentMethod: null, amount: "" },
      trialPlan,
    );
    expect(payload.payment).toBeUndefined();
  });

  it("omits biometrics when the desk skipped enrollment", () => {
    const payload = buildOnboardingPayload({ ...baseState(), deviceId: null }, plan());
    expect(payload.biometrics).toEqual([]);
  });

  it("omits biometrics when the device user id is blank (incomplete enrollment)", () => {
    const payload = buildOnboardingPayload(
      { ...baseState(), deviceId: 3, deviceUserId: "  " },
      plan(),
    );
    expect(payload.biometrics).toEqual([]);
  });
});

describe("isFreeTrial", () => {
  it("is true only for trial plans priced at zero", () => {
    expect(isFreeTrial(plan({ plan_type: "trial", price: "0.00" }))).toBe(true);
    expect(isFreeTrial(plan({ plan_type: "trial", price: "100.00" }))).toBe(false);
    expect(isFreeTrial(plan({ plan_type: "monthly", price: "0.00" }))).toBe(false);
    expect(isFreeTrial(null)).toBe(false);
  });
});

describe("describeAppInvite", () => {
  const invite = (overrides: Partial<AppInviteBlock> = {}): AppInviteBlock => ({
    status: "sent",
    reason: null,
    channel: "whatsapp",
    sent_at: "2026-10-21T10:41:05Z",
    resend_allowed_after: null,
    ...overrides,
  });

  it("celebrates a sent WhatsApp invite and offers no resend", () => {
    const chip = describeAppInvite(invite());
    expect(chip.variant).toBe("success");
    expect(chip.label).toBe("WhatsApp invite sent");
    expect(chip.resend).toBe(false);
  });

  it("labels the SMS channel explicitly", () => {
    expect(describeAppInvite(invite({ channel: "sms" })).label).toBe("SMS invite sent");
  });

  it("offers a resend for failed invites and surfaces the reason copy", () => {
    const chip = describeAppInvite(
      invite({ status: "failed", reason: "wati_not_configured", channel: null }),
    );
    expect(chip.variant).toBe("danger");
    expect(chip.resend).toBe(true);
    expect(chip.description).toContain("WhatsApp is not configured");
  });

  it("treats not_applicable as a warning without resend (plan/flag excludes app)", () => {
    const chip = describeAppInvite(
      invite({ status: "not_applicable", reason: "plan_excludes_app", channel: null }),
    );
    expect(chip.variant).toBe("warning");
    expect(chip.resend).toBe(false);
    expect(chip.description).toContain("does not include app access");
  });

  it("treats skipped and already_sent as non-resend states", () => {
    expect(describeAppInvite(invite({ status: "skipped", reason: "wati_not_configured" })).resend).toBe(false);
    expect(describeAppInvite(invite({ status: "already_sent" })).variant).toBe("success");
  });

  it("falls back to a warning chip when the block is missing", () => {
    expect(describeAppInvite(null).variant).toBe("warning");
  });
});

describe("paymentMethodLabel", () => {
  it("labels the desk methods and the backend's online value", () => {
    expect(paymentMethodLabel("cash")).toBe("Cash");
    expect(paymentMethodLabel("upi")).toBe("UPI");
    expect(paymentMethodLabel("online")).toBe("Online (Razorpay)");
    expect(paymentMethodLabel(null)).toBe("—");
    expect(paymentMethodLabel("mystery")).toBe("mystery");
  });
});
