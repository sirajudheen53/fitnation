import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { OnboardingWizard } from "@/features/onboarding/components/OnboardingWizard";
import {
  fetchBranches,
  fetchMembershipPlans,
  fetchDevices,
  searchCustomers,
  onboardMember,
  sendAppInvite,
  errorMessage,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { MembershipPlan } from "@/types/membership";
import type { OnboardingResult } from "@/types/onboarding";
import { todayISO, addDays } from "@/features/onboarding/lib/validity";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  fetchBranches: jest.fn(),
  fetchMembershipPlans: jest.fn(),
  fetchDevices: jest.fn(),
  searchCustomers: jest.fn(),
  onboardMember: jest.fn(),
  sendAppInvite: jest.fn(),
  syncDevice: jest.fn(),
  verifyOnboardingPayment: jest.fn(),
  fetchMembershipPlan: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
}));

const mockedFetchBranches = fetchBranches as jest.Mock;
const mockedFetchMembershipPlans = fetchMembershipPlans as jest.Mock;
const mockedFetchDevices = fetchDevices as jest.Mock;
const mockedSearchCustomers = searchCustomers as jest.Mock;
const mockedOnboardMember = onboardMember as jest.Mock;
const mockedSendAppInvite = sendAppInvite as jest.Mock;

const branch = { id: 2, name: "Main Branch", is_active: true };

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan => ({
  id: 7,
  name: "Monthly Unlimited",
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

const device = {
  id: 3,
  branch: 2,
  vendor: "generic" as const,
  model: "X",
  serial_number: "SN1",
  name: "Main Door",
  connection_type: "webhook" as const,
  api_endpoint: "",
  is_active: true,
  last_sync_at: null,
  last_seen_at: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const successResult = (overrides: Partial<OnboardingResult> = {}): OnboardingResult => ({
  onboarding_id: "b1c7",
  status: "completed",
  returning_member: false,
  customer: { id: 512, name: "Asha Nair", phone: "9876543210", email: null, branch: 2, is_active: true },
  membership: { id: 318, plan: 7, plan_name: "Monthly Unlimited", start_date: "2026-10-21", end_date: "2026-11-20", status: "active" },
  payment: { id: 901, method: "cash", amount: "2500.00", status: "completed", paid_at: "2026-10-21T10:41:02Z" },
  invoice_number: "INV-20261021-0042",
  biometrics: [],
  door_access: [],
  notifications: [{ type: "welcome", status: "sent" }],
  app_invite: { status: "sent", reason: null, channel: "whatsapp", sent_at: "2026-10-21T10:41:05Z", resend_allowed_after: null },
  entitlement_preview: { status: "active", read_only: false, plan_name: "Monthly Unlimited", end_date: "2026-11-20", grace_end_date: null },
  ...overrides,
});

async function fillStep1(phone = "9876543210") {
  render(<OnboardingWizard />);
  await screen.findByText("Main Branch"); // branches loaded → step 1 ready
  fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: phone } });
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "Asha Nair" } });
}

async function gotoStep2() {
  await fillStep1();
  fireEvent.click(screen.getByRole("button", { name: /Next: Plan & payment/i }));
  await screen.findByTestId("step-plan-payment");
}

async function selectPlanCard(name: string) {
  fireEvent.click(await screen.findByRole("button", { name: new RegExp(name) }));
}

/** Enter step 2, pick the monthly plan + cash, advance to the biometric step. */
async function gotoStep3() {
  await gotoStep2();
  await selectPlanCard("Monthly Unlimited");
  fireEvent.click(await screen.findByRole("button", { name: "Cash" }));
  await waitFor(() =>
    expect(screen.getByLabelText(/Amount collected/i)).toHaveValue(2500),
  );
  fireEvent.click(screen.getByRole("button", { name: /Next: Biometric/i }));
}

beforeEach(() => {
  jest.clearAllMocks();
  mockedFetchBranches.mockResolvedValue([branch]);
  mockedFetchMembershipPlans.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [plan()],
  });
  mockedFetchDevices.mockResolvedValue([device]);
  mockedSearchCustomers.mockResolvedValue([]);
  mockedOnboardMember.mockResolvedValue(successResult());
});

describe("OnboardingWizard — step 1 (Who)", () => {
  it("blocks advancing with validation errors when phone or name are missing", async () => {
    await fillStep1();
    fireEvent.change(screen.getByLabelText("Phone number"), { target: { value: "" } });
    fireEvent.change(screen.getByLabelText("Full name"), { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Next: Plan & payment/i }));
    expect(await screen.findByText("Enter a 10-digit phone number")).toBeInTheDocument();
    expect(screen.getByText("Name is required")).toBeInTheDocument();
    expect(screen.queryByTestId("step-plan-payment")).not.toBeInTheDocument();
  });

  it("shows the returning-member banner when the phone lookup matches (updated, not duplicated)", async () => {
    const existing: Partial<Customer> = { id: 41, name: "Asha Nair", phone: "9876543210" };
    mockedSearchCustomers.mockResolvedValue([existing as Customer]);
    await fillStep1();
    fireEvent.blur(screen.getByLabelText("Phone number"));
    const banner = await screen.findByTestId("returning-member-banner");
    expect(banner).toHaveTextContent(/Returning member/i);
    expect(banner).toHaveTextContent(/updated, not duplicated/i);
    expect(banner.closest("a") ?? banner.querySelector("a")).toBeTruthy();
  });

  it("does not show the banner when the lookup finds nothing", async () => {
    await fillStep1();
    fireEvent.blur(screen.getByLabelText("Phone number"));
    await waitFor(() => expect(mockedSearchCustomers).toHaveBeenCalledWith(expect.anything(), "9876543210"));
    expect(screen.queryByTestId("returning-member-banner")).not.toBeInTheDocument();
  });
});

describe("OnboardingWizard — step 2 (Plan & payment)", () => {
  it("computes the validity window from the plan duration and shows the app-included badge", async () => {
    await gotoStep2();
    await selectPlanCard("Monthly Unlimited");
    const summary = await screen.findByTestId("validity-summary");
    const today = todayISO();
    // Rendered in the en-IN long format the summary uses.
    const endLabel = new Date(`${addDays(today, 30)}T00:00:00`).toLocaleDateString("en-IN", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
    expect(summary).toHaveTextContent(`(30 days)`);
    expect(summary).toHaveTextContent(endLabel);
    expect(screen.getByText("App included")).toBeInTheDocument();
  });

  it("hides the payment block entirely for a ₹0 trial plan", async () => {
    mockedFetchMembershipPlans.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [plan({ id: 12, name: "3-Day Trial", plan_type: "trial", price: "0.00", duration_days: 3 })],
    });
    await gotoStep2();
    await selectPlanCard("3-Day Trial");
    expect(await screen.findByTestId("trial-no-payment")).toHaveTextContent(/Free trial — no payment needed/i);
    expect(screen.queryByLabelText(/Amount collected/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Razorpay/i })).not.toBeInTheDocument();
  });

  it("requires a plan and a payment method before advancing on a paid plan", async () => {
    await gotoStep2();
    fireEvent.click(screen.getByRole("button", { name: /Next: Biometric/i }));
    expect(await screen.findByText("Pick a plan to continue")).toBeInTheDocument();
    expect(screen.queryByTestId("step-biometric")).not.toBeInTheDocument();

    await selectPlanCard("Monthly Unlimited");
    fireEvent.click(screen.getByRole("button", { name: /Next: Biometric/i }));
    expect(await screen.findByText("Choose a payment method")).toBeInTheDocument();
    expect(screen.queryByTestId("step-biometric")).not.toBeInTheDocument();
  });

  it("rejects an end date on or before the start date", async () => {
    await gotoStep2();
    await selectPlanCard("Monthly Unlimited");
    const start = await screen.findByLabelText("Start date");
    fireEvent.change(start, { target: { value: "2026-10-21" } });
    fireEvent.change(screen.getByLabelText(/End date/i), { target: { value: "2026-10-21" } });
    fireEvent.click(screen.getByRole("button", { name: /Next: Biometric/i }));
    expect(await screen.findByText("End date must be after the start date")).toBeInTheDocument();
    expect(screen.queryByTestId("step-biometric")).not.toBeInTheDocument();
  });

  it("accepts a hand-edited end-date override and shows the edited day count", async () => {
    await gotoStep2();
    await selectPlanCard("Monthly Unlimited");
    const today = todayISO();
    fireEvent.change(await screen.findByLabelText(/End date/i), { target: { value: addDays(today, 15) } });
    expect(await screen.findByTestId("validity-summary")).toHaveTextContent("(15 days)");
  });
});

describe("OnboardingWizard — step 3 (Biometric)", () => {
  it("submits the whole member in one POST with biometrics and lands on the success screen", async () => {
    await gotoStep3();
    fireEvent.change(await screen.findByLabelText("Device"), { target: { value: "3" } });
    fireEvent.change(await screen.findByLabelText("Device user ID"), { target: { value: "1017" } });
    fireEvent.click(screen.getByRole("button", { name: "Finish onboarding" }));

    await screen.findByTestId("onboarding-success");
    const today = todayISO();
    expect(mockedOnboardMember).toHaveBeenCalledWith(
      expect.objectContaining({
        customer: expect.objectContaining({ phone: "9876543210", name: "Asha Nair", branch: 2 }),
        membership: { plan: 7, start_date: today, end_date: addDays(today, 30) },
        payment: expect.objectContaining({ method: "cash", amount: 2500 }),
        biometrics: [{ device: 3, credential_type: "fingerprint", device_user_id: "1017" }],
      }),
      expect.anything(),
      expect.any(String),
    );
  });

  it("shows the no-device empty state and submits without biometrics on finish", async () => {
    mockedFetchDevices.mockResolvedValue([]);
    await gotoStep3();
    expect(await screen.findByTestId("no-device-empty-state")).toHaveTextContent(
      /No biometric device at this branch/i,
    );
    fireEvent.click(screen.getByRole("button", { name: "Finish onboarding" }));

    await screen.findByTestId("onboarding-success");
    expect(mockedOnboardMember).toHaveBeenCalledWith(
      expect.objectContaining({ biometrics: [] }),
      expect.anything(),
      expect.any(String),
    );
  });

  it("allows skipping biometrics when devices exist (enroll later from the profile)", async () => {
    await gotoStep3();
    await screen.findByLabelText("Device");
    fireEvent.click(screen.getByTestId("skip-biometric"));
    await screen.findByTestId("onboarding-success");
    expect(mockedOnboardMember).toHaveBeenCalledWith(
      expect.objectContaining({ biometrics: [] }),
      expect.anything(),
      expect.any(String),
    );
  });

  it("disables finishing until the device user id is provided", async () => {
    await gotoStep3();
    fireEvent.change(await screen.findByLabelText("Device"), { target: { value: "3" } });
    expect(screen.getByRole("button", { name: "Finish onboarding" })).toBeDisabled();
    fireEvent.change(screen.getByLabelText("Device user ID"), { target: { value: "1017" } });
    expect(screen.getByRole("button", { name: "Finish onboarding" })).toBeEnabled();
  });
});

describe("OnboardingWizard — success screen", () => {
  it("renders the member card, invite chip, receipt and both CTAs", async () => {
    await gotoStep3();
    await screen.findByLabelText("Device");
    fireEvent.click(screen.getByTestId("skip-biometric"));

    await screen.findByTestId("onboarding-success");
    expect(screen.getByTestId("app-invite-chip")).toHaveTextContent("WhatsApp invite sent");
    expect(screen.getByTestId("member-card")).toHaveTextContent("Asha Nair");
    expect(screen.getByTestId("payment-receipt")).toHaveTextContent("INV-20261021-0042");
    expect(screen.getByRole("link", { name: /View member profile/i })).toHaveAttribute(
      "href",
      "/customers/512",
    );
    expect(screen.getByRole("button", { name: "Onboard next member" })).toBeInTheDocument();
  });

  it("shows a failed invite with a Resend action that calls the invite endpoint with resend", async () => {
    mockedOnboardMember.mockResolvedValue(
      successResult({
        app_invite: { status: "failed", reason: "wati_not_configured", channel: null, sent_at: null, resend_allowed_after: null },
      }),
    );
    mockedSendAppInvite.mockResolvedValue({
      status: "sent", reason: null, channel: "whatsapp",
      sent_at: "2026-10-21T11:00:00Z", resend_allowed_after: null,
    });

    await gotoStep3();
    await screen.findByLabelText("Device");
    fireEvent.click(screen.getByTestId("skip-biometric"));

    await screen.findByTestId("onboarding-success");
    const chip = screen.getByTestId("app-invite-chip");
    expect(chip).toHaveTextContent("Invite failed");
    expect(screen.getByText(/WhatsApp is not configured/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Resend invite/i }));
    await waitFor(() =>
      expect(mockedSendAppInvite).toHaveBeenCalledWith(512, expect.anything(), true),
    );
    await waitFor(() =>
      expect(screen.getByTestId("app-invite-chip")).toHaveTextContent("WhatsApp invite sent"),
    );
  });

  it("shows the not-configured invite as a warning without a resend", async () => {
    mockedOnboardMember.mockResolvedValue(
      successResult({
        app_invite: { status: "skipped", reason: "wati_not_configured", channel: null, sent_at: null, resend_allowed_after: null },
      }),
    );
    await gotoStep3();
    await screen.findByLabelText("Device");
    fireEvent.click(screen.getByTestId("skip-biometric"));

    await screen.findByTestId("onboarding-success");
    expect(screen.getByTestId("app-invite-chip")).toHaveTextContent("Invite not sent");
    expect(screen.queryByRole("button", { name: /Resend invite/i })).not.toBeInTheDocument();
  });

  it("resets to step 1 keeping the branch on 'Onboard next member'", async () => {
    await gotoStep3();
    await screen.findByLabelText("Device");
    fireEvent.click(screen.getByTestId("skip-biometric"));
    await screen.findByTestId("onboarding-success");

    fireEvent.click(screen.getByRole("button", { name: "Onboard next member" }));
    expect(await screen.findByTestId("step-who")).toBeInTheDocument();
    // Branch kept (busy-Saturday loop).
    expect(screen.getByLabelText("Branch")).toHaveValue("2");
    // Phone cleared.
    expect(screen.getByLabelText("Phone number")).toHaveValue("");
  });
});
