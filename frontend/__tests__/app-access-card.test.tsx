import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AppAccessCard } from "@/features/customers/components/AppAccessCard";
import { sendAppInvite, errorMessage } from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  sendAppInvite: jest.fn(),
}));

const mockedSendAppInvite = sendAppInvite as jest.Mock;
const mockedErrorMessage = errorMessage as jest.Mock;

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

const memberships: Membership[] = [
  {
    id: 31,
    customer_id: 1,
    customer_name: "Asha Nair",
    plan_id: 7,
    plan_name: "Monthly",
    start_date: "2026-09-21",
    // Computed relative to today so the derivation stays valid over time:
    // active for the next 10 days.
    end_date: new Date(Date.now() + 10 * 86_400_000).toISOString().slice(0, 10),
    status: "active",
    price: 2500,
    created_at: "2026-09-21T00:00:00Z",
    updated_at: "2026-09-21T00:00:00Z",
  },
];

const plans: MembershipPlan[] = [
  {
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
  },
];

beforeEach(() => {
  jest.clearAllMocks();
});

describe("AppAccessCard", () => {
  it("shows the entitled state from the server block with the granting plan", () => {
    render(
      <AppAccessCard
        customer={customer({
          app_access: { status: "active", read_only: false, plan_name: "Yearly", end_date: "2027-01-01", grace_end_date: null },
          app_invite_status: { status: "sent", channel: "whatsapp", sent_at: "2026-10-21T10:00:00Z", error_message: null },
        })}
        memberships={memberships}
        plans={plans}
      />,
    );
    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Entitled");
    expect(screen.getByText("Yearly")).toBeInTheDocument();
    expect(screen.getByTestId("app-invite-state")).toHaveTextContent("Invite sent via WhatsApp");
  });

  it("shows the read-only grace state with its date", () => {
    render(
      <AppAccessCard
        customer={customer({
          app_access: { status: "grace", read_only: true, plan_name: "Monthly", end_date: "2026-10-14", grace_end_date: "2026-10-25" },
        })}
        memberships={memberships}
        plans={plans}
      />,
    );
    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Read-only grace");
    expect(screen.getByText(/read-only until 2026-10-25/i)).toBeInTheDocument();
  });

  it("falls back to plan derivation when the server block is absent (pre-B2 payloads)", () => {
    render(
      <AppAccessCard customer={customer()} memberships={memberships} plans={plans} />,
    );
    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Entitled");
    expect(screen.getByText("Monthly")).toBeInTheDocument();
  });

  it("offers a first send for a never-invited member and reports success", async () => {
    mockedSendAppInvite.mockResolvedValue({ status: "sent", channel: "whatsapp", reason: null, sent_at: "2026-10-21T11:00:00Z", resend_allowed_after: null });
    const onInviteSent = jest.fn();
    render(
      <AppAccessCard customer={customer()} memberships={memberships} plans={plans} onInviteSent={onInviteSent} />,
    );
    expect(screen.getByTestId("app-invite-state")).toHaveTextContent("Never invited");
    fireEvent.click(screen.getByRole("button", { name: "Send app invite" }));
    await waitFor(() => expect(mockedSendAppInvite).toHaveBeenCalledWith(1, expect.anything(), false));
    await waitFor(() => expect(screen.getByTestId("app-invite-state")).toHaveTextContent("Invite sent via WhatsApp"));
    expect(onInviteSent).toHaveBeenCalled();
  });

  it("forces the resend for an already-sent invite", async () => {
    mockedSendAppInvite.mockResolvedValue({ status: "already_sent", channel: "whatsapp", reason: null, sent_at: "2026-10-21T10:00:00Z", resend_allowed_after: "2026-10-22T10:00:00Z" });
    render(
      <AppAccessCard
        customer={customer({
          app_invite_status: { status: "sent", channel: "whatsapp", sent_at: "2026-10-21T10:00:00Z", error_message: null },
        })}
        memberships={memberships}
        plans={plans}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Resend invite" }));
    await waitFor(() => expect(mockedSendAppInvite).toHaveBeenCalledWith(1, expect.anything(), true));
  });

  it("shows the failed state with the error detail and retries without forcing", async () => {
    mockedSendAppInvite.mockResolvedValue({ status: "sent", channel: "sms", reason: null, sent_at: "2026-10-21T11:00:00Z", resend_allowed_after: null });
    render(
      <AppAccessCard
        customer={customer({
          app_invite_status: { status: "failed", channel: null, sent_at: null, error_message: "WATI down" },
        })}
        memberships={memberships}
        plans={plans}
      />,
    );
    expect(screen.getByTestId("app-invite-state")).toHaveTextContent("Invite failed");
    expect(screen.getByText("WATI down")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry invite" }));
    await waitFor(() => expect(mockedSendAppInvite).toHaveBeenCalledWith(1, expect.anything(), false));
    await waitFor(() => expect(screen.getByTestId("app-invite-state")).toHaveTextContent("Invite sent via SMS"));
  });

  it("flags members on plans without app access as not entitled", () => {
    render(
      <AppAccessCard
        customer={customer()}
        memberships={[{ ...memberships[0] }]}
        plans={[{ ...plans[0], includes_app_access: false }]}
      />,
    );
    expect(screen.getByTestId("app-access-state")).toHaveTextContent("Plan excludes app");
  });

  it("surfaces the API error via toast path without crashing", async () => {
    mockedSendAppInvite.mockRejectedValue(new Error("429"));
    render(<AppAccessCard customer={customer()} memberships={memberships} plans={plans} />);
    fireEvent.click(screen.getByRole("button", { name: "Send app invite" }));
    await waitFor(() => expect(mockedErrorMessage).toHaveBeenCalled());
  });
});
