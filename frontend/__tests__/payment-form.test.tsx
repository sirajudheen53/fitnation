import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  PaymentForm,
  pickLatestMembership,
  summarizePending,
} from "@/features/payments/components/PaymentForm";
import { fetchMemberships, fetchPayments, searchCustomers } from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { Membership } from "@/types/membership";
import type { Payment } from "@/types/payment";

// Only the network surface is mocked; errorMessage and friends stay real.
jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  searchCustomers: jest.fn(),
  fetchMemberships: jest.fn(),
  fetchPayments: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockedSearchCustomers = searchCustomers as jest.Mock;
const mockedFetchMemberships = fetchMemberships as jest.Mock;
const mockedFetchPayments = fetchPayments as jest.Mock;

const customer: Customer = {
  id: 5,
  email: null,
  user: 51,
  name: "Arjun Kumar",
  branch: null,
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
};

const membership = (overrides: Partial<Membership> = {}): Membership => ({
  id: 31,
  customer_id: 5,
  customer_name: "Arjun Kumar",
  plan_id: 7,
  plan_name: "Monthly Unlimited",
  start_date: "2026-10-01",
  end_date: "2026-10-31",
  status: "active",
  price: 2500,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  ...overrides,
});

const pendingPayment = (overrides: Partial<Payment> = {}): Payment => ({
  id: 901,
  customer_id: 5,
  customer_name: "Arjun Kumar",
  amount: "1500.00",
  method: "upi",
  status: "pending",
  kind: "membership",
  membership_id: 31,
  invoice_id: null,
  notes: null,
  payment_date: "2026-10-15T00:00:00Z",
  created_at: "2026-10-15T00:00:00Z",
  updated_at: "2026-10-15T00:00:00Z",
  ...overrides,
});

/** Render the form and pick the given customer through the search picker. */
async function pickCustomer(list = [customer]) {
  mockedSearchCustomers.mockResolvedValue(list);
  render(<PaymentForm onSubmit={jest.fn()} />);
  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "arjun" } });
  fireEvent.click(await screen.findByRole("option", { name: /Arjun Kumar/ }));
  // The link load settles asynchronously; waiting on the panel means the
  // membership field and link info have both rendered.
  await screen.findByTestId("membership-link");
}

beforeEach(() => {
  mockedSearchCustomers.mockReset();
  mockedFetchMemberships.mockReset();
  mockedFetchPayments.mockReset();
  mockedFetchMemberships.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  mockedFetchPayments.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

describe("pickLatestMembership", () => {
  it("prefers the customer's active membership", () => {
    const mine = [
      membership({ id: 30, customer_id: 5, status: "expired" }),
      membership({ id: 31, customer_id: 5, status: "active" }),
      membership({ id: 32, customer_id: 6, status: "active" }),
    ];
    expect(pickLatestMembership(mine, 5)?.id).toBe(31);
  });

  it("falls back to the customer's latest membership when none is active", () => {
    const mine = [
      membership({ id: 30, customer_id: 5, status: "expired" }),
      membership({ id: 29, customer_id: 5, status: "cancelled" }),
    ];
    // Backend orders newest-first, so the first row for the customer wins.
    expect(pickLatestMembership(mine, 5)?.id).toBe(30);
  });

  it("returns null when the customer holds no membership", () => {
    expect(pickLatestMembership([membership({ customer_id: 6 })], 5)).toBeNull();
    expect(pickLatestMembership([], 5)).toBeNull();
  });
});

describe("summarizePending", () => {
  it("sums pending amounts and counts them", () => {
    expect(
      summarizePending([pendingPayment(), pendingPayment({ amount: "250.50", id: 902 })]),
    ).toEqual({ total: 1750.5, count: 2 });
    expect(summarizePending([])).toEqual({ total: 0, count: 0 });
  });
});

describe("PaymentForm auto-link (#103)", () => {
  it("keeps the searchable picker and form fields", () => {
    render(<PaymentForm onSubmit={jest.fn()} />);
    expect(screen.getByLabelText("Customer")).toBeInTheDocument();
    expect(screen.getByLabelText("Amount")).toBeInTheDocument();
    expect(screen.getByLabelText("Membership ID")).toBeInTheDocument();
    expect(screen.queryByLabelText("Customer ID")).not.toBeInTheDocument();
  });

  it("shows a validation error when submitting without a customer", async () => {
    render(<PaymentForm onSubmit={jest.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Record payment" }));
    await screen.findByText("Select a customer");
  });

  it("auto-fills the membership field and surfaces plan + pending dues", async () => {
    mockedFetchMemberships.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [membership({ id: 31, status: "active", plan_name: "Monthly Unlimited" })],
    });
    mockedFetchPayments.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [pendingPayment({ amount: "1500.00" })],
    });

    await pickCustomer();

    expect(screen.getByLabelText("Membership ID")).toHaveValue(31);
    expect(screen.getByTestId("membership-link")).toHaveTextContent(
      "Auto-linked membership #31 · Monthly Unlimited",
    );
    expect(screen.getByTestId("membership-link")).toHaveTextContent(
      "Pending dues: ₹1500.00 across 1 payment",
    );
  });

  it("falls back to the latest membership when none is active and says no dues when pending list is empty", async () => {
    mockedFetchMemberships.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [membership({ id: 30, status: "expired", plan_name: "Quarterly Pro" })],
    });

    await pickCustomer();

    expect(screen.getByLabelText("Membership ID")).toHaveValue(30);
    expect(screen.getByTestId("membership-link")).toHaveTextContent("Quarterly Pro");
    expect(screen.getByTestId("membership-link")).toHaveTextContent("No pending dues.");
  });

  it("reports when the customer holds no membership and leaves the field empty", async () => {
    await pickCustomer();

    expect(screen.getByLabelText("Membership ID")).toHaveValue(null);
    expect(screen.getByTestId("membership-link")).toHaveTextContent(
      "No membership found for this customer.",
    );
    expect(screen.getByTestId("membership-link")).toHaveTextContent("No pending dues.");
  });

  it("keeps the membership field editable after the auto-fill", async () => {
    mockedFetchMemberships.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [membership({ id: 31, status: "active" })],
    });

    const onSubmit = jest.fn();
    mockedSearchCustomers.mockResolvedValue([customer]);
    render(<PaymentForm onSubmit={onSubmit} />);
    fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "arjun" } });
    fireEvent.click(await screen.findByRole("option", { name: /Arjun Kumar/ }));
    await waitFor(() => expect(screen.getByLabelText("Membership ID")).toHaveValue(31));

    fireEvent.change(screen.getByLabelText("Membership ID"), { target: { value: "99" } });
    fireEvent.change(screen.getByLabelText("Amount"), { target: { value: "2500" } });
    fireEvent.click(screen.getByRole("button", { name: "Record payment" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ customer_id: 5, membership_id: 99, amount: 2500 }),
      ),
    );
  });

  it("clears the membership link when the customer is cleared", async () => {
    mockedFetchMemberships.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [membership({ id: 31, status: "active" })],
    });

    await pickCustomer();
    await waitFor(() => expect(screen.getByLabelText("Membership ID")).toHaveValue(31));

    fireEvent.click(screen.getByRole("button", { name: "Clear customer" }));
    expect(screen.getByLabelText("Membership ID")).toHaveValue(null);
    expect(screen.queryByTestId("membership-link")).not.toBeInTheDocument();
    // Resolver validation settles asynchronously after setValue.
    await screen.findByText("Select a customer");
  });

  it("is non-fatal when the membership fetch fails", async () => {
    mockedFetchMemberships.mockRejectedValue(new Error("boom"));

    await pickCustomer();

    expect(screen.getByTestId("membership-link")).toHaveTextContent(
      "No membership found for this customer.",
    );
    expect(screen.getByLabelText("Membership ID")).toHaveValue(null);
  });

  it("is non-fatal when the pending-payments fetch fails", async () => {
    mockedFetchMemberships.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [membership({ id: 31, status: "active" })],
    });
    mockedFetchPayments.mockRejectedValue(new Error("boom"));

    await pickCustomer();

    expect(screen.getByLabelText("Membership ID")).toHaveValue(31);
    expect(screen.getByTestId("membership-link")).toHaveTextContent("No pending dues.");
  });

  it("ignores a stale link load after the customer changes", async () => {
    const otherCustomer: Customer = { ...customer, id: 6, name: "Beta User", phone: "9000000001" };
    let resolveFirst: (value: unknown) => void = () => {};
    mockedFetchMemberships
      .mockImplementationOnce(
        () =>
          new Promise((resolve) => {
            resolveFirst = resolve;
          }),
      )
      .mockResolvedValue({
        count: 1,
        next: null,
        previous: null,
        results: [membership({ id: 44, customer_id: 6, plan_name: "Yearly Max" })],
      });

    mockedSearchCustomers
      .mockResolvedValueOnce([customer])
      .mockResolvedValueOnce([otherCustomer]);

    render(<PaymentForm onSubmit={jest.fn()} />);
    // Pick customer 5 (slow load hangs), then switch to customer 6.
    fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "arjun" } });
    fireEvent.click(await screen.findByRole("option", { name: /Arjun Kumar/ }));
    fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "beta" } });
    fireEvent.click(await screen.findByRole("option", { name: /Beta User/ }));

    await waitFor(() => expect(screen.getByLabelText("Membership ID")).toHaveValue(44));

    // The hung load for customer 5 resolves late — it must not win.
    resolveFirst({
      count: 1,
      next: null,
      previous: null,
      results: [membership({ id: 31, customer_id: 5, status: "active" })],
    });
    await waitFor(() => expect(mockedFetchMemberships).toHaveBeenCalledTimes(2));
    expect(screen.getByLabelText("Membership ID")).toHaveValue(44);
    expect(screen.getByTestId("membership-link")).toHaveTextContent("Yearly Max");
  });
});
