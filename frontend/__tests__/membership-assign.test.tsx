/**
 * Assign-membership page (msg 2441 400 fix): the form shape must be mapped
 * onto the backend contract (`customer`/`plan` primary keys) before POST,
 * the amount paid becomes a separate kind=membership payment linked to the
 * created membership, and the dead coupon input is gone.
 */
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import AssignMembershipPage from "@/app/memberships/assign/page";
import {
  assignMembership,
  buildMembershipBody,
  createPayment,
  fetchCustomers,
  fetchMembershipPlans,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { MembershipPlan } from "@/types/membership";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/memberships/assign",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "test-token",
  getStoredUser: () => ({
    id: 1,
    email: "owner@fitnation.app",
    name: "Gym Owner",
    role: "owner",
    tenant_id: 1,
    tenant_name: "FitNation",
    is_owner: true,
  }),
  logout: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchCustomers: jest.fn(),
  fetchMembershipPlans: jest.fn(),
  assignMembership: jest.fn(),
  createPayment: jest.fn(),
}));

const mockedFetchCustomers = fetchCustomers as jest.Mock;
const mockedFetchPlans = fetchMembershipPlans as jest.Mock;
const mockedAssign = assignMembership as jest.Mock;
const mockedCreatePayment = createPayment as jest.Mock;

const customer = (overrides: Partial<Customer> = {}): Customer => ({
  id: 5,
  user: 51,
  name: "Arjun Kumar",
  email: "arjun@example.com",
  first_name: "Arjun",
  last_name: "Kumar",
  branch: null,
  status: "active",
  notes: "",
  phone: "+91 98765 43210",
  gender: null,
  date_of_birth: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  address_street: "",
  address_city: "",
  address_state: "",
  address_postal_code: "",
  is_active: true,
  profile_photo: null,
  created_at: "2026-09-01T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  ...overrides,
});

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan => ({
  id: 2,
  name: "Gold",
  price: "1999.00",
  duration_days: 30,
  plan_type: "monthly",
  description: null,
  is_active: true,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockedFetchCustomers.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [customer()],
  });
  mockedFetchPlans.mockResolvedValue({
    count: 2,
    next: null,
    previous: null,
    results: [
      plan({ id: 2, name: "Gold", duration_days: 30, price: "1999.00" }),
      plan({ id: 3, name: "Platinum", duration_days: 90, price: "4999.00" }),
    ],
  });
  mockedAssign.mockResolvedValue({ id: 77 });
  mockedCreatePayment.mockResolvedValue({ id: 9 });
});

async function renderFilledForm() {
  render(<AssignMembershipPage />);
  await waitFor(() => expect(screen.getByLabelText("Customer")).toBeInTheDocument());
  fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "5" } });
  fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "2" } });
  fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-10-01" } });
  fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-10-31" } });
}

async function submitForm() {
  fireEvent.click(screen.getByRole("button", { name: "Assign membership" }));
}

describe("assignMembership wire format (msg 2441 400 fix)", () => {
  function mockFetch(payload: unknown) {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    });
    global.fetch = fetchMock as unknown as typeof fetch;
    return fetchMock;
  }

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("posts customer/plan primary keys, not the form's *_id shape", async () => {
    const fetchMock = mockFetch({ id: 3 });
    // The module is mocked for the page tests — grab the real fetcher.
    const realAssign = jest.requireActual<typeof import("@/lib/api")>("@/lib/api")
      .assignMembership;
    await realAssign(
      { customer_id: 5, plan_id: 2, start_date: "2026-10-01", end_date: "2026-10-31" },
      "tok",
    );
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/memberships/memberships/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      customer: 5,
      plan: 2,
      start_date: "2026-10-01",
      end_date: "2026-10-31",
    });
  });

  it("never leaks form-only keys (customer_id/plan_id/coupon_code/amount_paid)", () => {
    const body = buildMembershipBody({
      customer_id: 5,
      plan_id: 2,
      start_date: "2026-10-01",
      end_date: "2026-10-31",
    }) as Record<string, unknown>;
    expect(Object.keys(body).sort()).toEqual(["customer", "end_date", "plan", "start_date"]);
  });
});

describe("AssignMembershipPage coupon removal", () => {
  it("no longer renders the dead coupon input", async () => {
    await renderFilledForm();
    expect(screen.queryByLabelText("Coupon code")).not.toBeInTheDocument();
  });
});

describe("AssignMembershipPage payment capture", () => {
  it("hides the method select until an amount is entered (cash default)", async () => {
    await renderFilledForm();
    expect(screen.queryByLabelText("Method")).not.toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "1999" } });
    expect(screen.getByLabelText("Method")).toBeInTheDocument();
    expect(screen.getByLabelText("Method")).toHaveValue("cash");
  });

  it("assigns without posting a payment when the amount is left empty", async () => {
    await renderFilledForm();
    await submitForm();

    await waitFor(() => expect(mockedAssign).toHaveBeenCalledTimes(1));
    expect(mockedAssign).toHaveBeenCalledWith(
      { customer_id: 5, plan_id: 2, start_date: "2026-10-01", end_date: "2026-10-31" },
      "test-token",
    );
    expect(mockedCreatePayment).not.toHaveBeenCalled();
    expect(mockRouter.push).toHaveBeenCalledWith("/memberships");
  });

  it("records a completed membership payment linked to the created membership", async () => {
    await renderFilledForm();
    fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "1999" } });
    fireEvent.change(screen.getByLabelText("Method"), { target: { value: "upi" } });
    await submitForm();

    await waitFor(() => expect(mockedCreatePayment).toHaveBeenCalledTimes(1));
    expect(mockedCreatePayment).toHaveBeenCalledWith(
      {
        customer_id: 5,
        amount: 1999,
        method: "upi",
        status: "completed",
        kind: "membership",
        membership_id: 77,
      },
      "test-token",
    );
    expect(mockRouter.push).toHaveBeenCalledWith("/memberships");
  });

  it("regression: clearing the amount records no payment (zod '' → 0 bug)", async () => {
    await renderFilledForm();
    fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "1999" } });
    fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "" } });
    await submitForm();

    await waitFor(() => expect(mockedAssign).toHaveBeenCalledTimes(1));
    expect(mockedCreatePayment).not.toHaveBeenCalled();
  });

  it("keeps the assignment and warns when the payment POST fails", async () => {
    mockedCreatePayment.mockRejectedValue(new Error("gateway down"));
    const { toast } = require("sonner");

    await renderFilledForm();
    fireEvent.change(screen.getByLabelText("Amount paid"), { target: { value: "1999" } });
    await submitForm();

    await waitFor(() =>
      expect(toast.warning).toHaveBeenCalledWith(
        expect.stringContaining("Membership assigned, but the payment wasn't recorded"),
      ),
    );
    expect(mockRouter.push).toHaveBeenCalledWith("/memberships");
  });
});

describe("AssignMembershipPage end-date suggestion", () => {
  it("suggests start + plan duration when the end date is untouched", async () => {
    render(<AssignMembershipPage />);
    await waitFor(() => expect(screen.getByLabelText("Plan")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-10-01" } });

    expect(screen.getByLabelText("End date")).toHaveValue("2026-10-31");
  });

  it("never overrides an end date the user typed", async () => {
    render(<AssignMembershipPage />);
    await waitFor(() => expect(screen.getByLabelText("Plan")).toBeInTheDocument());
    fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-10-01" } });
    fireEvent.change(screen.getByLabelText("End date"), { target: { value: "2026-12-15" } });

    // Switching to a 90-day plan must not rewrite the user's date.
    fireEvent.change(screen.getByLabelText("Plan"), { target: { value: "3" } });
    expect(screen.getByLabelText("End date")).toHaveValue("2026-12-15");
  });
});
