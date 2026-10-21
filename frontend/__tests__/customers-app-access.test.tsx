import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  CustomerTable,
  getAppAccessBadge,
  getCustomerMembershipStatus,
} from "@/features/customers/components/CustomerTable";
import {
  invitableIds,
  isInvitable,
  sendBulkInvites,
} from "@/features/customers/lib/bulkInvite";
import type { AppAccessDisplay } from "@/features/customers/lib/appAccess";
import type { Customer } from "@/types/customer";
import type { AppInviteBlock } from "@/types/onboarding";

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const display = (status: AppAccessDisplay["status"]): AppAccessDisplay => ({
  status,
  label:
    status === "active"
      ? "Entitled"
      : status === "grace"
        ? "Read-only grace"
        : status === "expired"
          ? "Expired"
          : status === "none"
            ? "Plan excludes app"
            : "No membership",
  variant:
    status === "active"
      ? "success"
      : status === "grace"
        ? "warning"
        : status === "expired" || status === "none"
          ? "danger"
          : "default",
  planName: "Monthly",
  endDate: "2026-11-20",
  graceEndDate: null,
});

const customer = (id: number, overrides: Partial<Customer> = {}): Customer =>
  ({
    id,
    email: null,
    user: 100 + id,
    name: `Member ${id}`,
    branch: 2,
    status: "active",
    notes: "",
    address_street: "",
    address_city: "",
    address_state: "",
    address_postal_code: "",
    phone: `980000000${id}`,
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

describe("CustomerTable — app access column + selection (FBOS-011 F5)", () => {
  it("renders the derived app-access badge per row", () => {
    render(
      <CustomerTable
        customers={[customer(1), customer(2)]}
        appAccessByCustomer={{ 1: display("active"), 2: display("grace") }}
      />,
    );
    const cells = screen.getAllByRole("cell");
    const texts = cells.map((c) => c.textContent);
    expect(texts).toContain("Entitled");
    expect(texts).toContain("Read-only grace");
  });

  it("renders an em-dash badge when no derivation exists for a row", () => {
    render(<CustomerTable customers={[customer(1)]} />);
    expect(screen.getAllByRole("cell").map((c) => c.textContent)).toContain("—");
  });

  it("exposes row selection when a bulk-action callback is provided", () => {
    const onSelectionChange = jest.fn();
    render(
      <CustomerTable
        customers={[customer(1), customer(2)]}
        onSelectionChange={onSelectionChange}
      />,
    );
    fireEvent.click(screen.getByLabelText("Select Member 1"));
    expect(onSelectionChange).toHaveBeenLastCalledWith([1]);
    fireEvent.click(screen.getByLabelText("Select Member 2"));
    expect(onSelectionChange).toHaveBeenLastCalledWith([1, 2]);
    // Select-all on a fully-selected table clears it (toggle semantics).
    fireEvent.click(screen.getByLabelText("Select all customers"));
    expect(onSelectionChange).toHaveBeenLastCalledWith([]);
    // And selecting all from empty picks every row in order.
    fireEvent.click(screen.getByLabelText("Select all customers"));
    expect(onSelectionChange).toHaveBeenLastCalledWith([1, 2]);
  });

  it("keeps the membership-status helper intact (existing consumers)", () => {
    expect(getCustomerMembershipStatus(customer(1))).toMatchObject({ label: "Active", variant: "success" });
    expect(getAppAccessBadge(display("active")).label).toBe("Entitled");
    expect(getAppAccessBadge(undefined)).toMatchObject({ label: "—", variant: "default" });
  });
});

describe("bulkInvite (FBOS-011 F5)", () => {
  const customers = [
    customer(1, { app_invite_status: { status: "sent", channel: "whatsapp", sent_at: null, error_message: null } }),
    customer(2),
    customer(3),
    customer(4, { app_invite_status: { status: "failed", channel: null, sent_at: null, error_message: null } }),
  ];
  const access = {
    1: display("active"),
    2: display("active"),
    3: display("expired"),
    4: display("grace"),
  };

  it("selects entitled members who were not successfully invited", () => {
    // 1 already sent → skip; 3 not entitled → skip; 2 and 4 (grace = still
    // entitled, failed invite) → invitable.
    expect(invitableIds([1, 2, 3, 4], access, customers)).toEqual([2, 4]);
  });

  it("isInvitable rejects unknown states outright", () => {
    expect(isInvitable(undefined, null)).toBe(false);
  });

  it("fans out one POST per member and tallies sent/already/failed", async () => {
    const send = jest.fn((id: number) => {
      if (id === 2) {
        return Promise.resolve<AppInviteBlock>({
          status: "sent", reason: null, channel: "whatsapp", sent_at: null, resend_allowed_after: null,
        });
      }
      if (id === 4) {
        return Promise.resolve<AppInviteBlock>({
          status: "already_sent", reason: null, channel: "whatsapp", sent_at: null, resend_allowed_after: null,
        });
      }
      return Promise.reject(new Error("network"));
    });
    const outcome = await sendBulkInvites([2, 4, 9], send);
    expect(send).toHaveBeenCalledTimes(3);
    expect(outcome).toEqual({ sent: 1, already_sent: 1, failed: 1 });
  });

  it("counts non-sent 200 outcomes (skipped/not_applicable) as failed for the summary", async () => {
    const outcome = await sendBulkInvites([5], () =>
      Promise.resolve<AppInviteBlock>({
        status: "not_applicable", reason: "plan_excludes_app", channel: null, sent_at: null, resend_allowed_after: null,
      }),
    );
    expect(outcome).toEqual({ sent: 0, already_sent: 0, failed: 1 });
  });
});

describe("customers table smoke", () => {
  it("renders without crashing and shows the empty state", async () => {
    render(<CustomerTable customers={[]} />);
    await waitFor(() => expect(screen.getByText(/No customers found/i)).toBeInTheDocument());
  });
});
