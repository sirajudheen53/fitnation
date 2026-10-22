/**
 * Renewal flow (frontend wire-up of the backend `renewal` action): the Renew
 * action extends the SAME membership instead of forcing a new assignment.
 * Covers the API wire contract, the memberships-page flow (dialog opens with
 * the computed new end date; a successful call refreshes the row) and the
 * customer-detail membership card.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import MembershipsPage from "@/app/memberships/page";
import AssignMembershipPage from "@/app/memberships/assign/page";
import { OverviewTab } from "@/features/customers/components/OverviewTab";
import {
  fetchCustomers,
  fetchMembershipPlans,
  fetchMemberships,
  renewMembership,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { Membership, MembershipPlan } from "@/types/membership";
import { toast } from "sonner";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/memberships",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "test-token",
  getStoredUser: () => ({
    id: 1,
    email: "owner@fitnation.app",
    name: "Gym Owner",
    role: "gym_owner",
    tenant_id: 1,
    tenant_name: "FitNation",
    is_owner: true,
  }),
  // ImpersonationBanner mounts inside DashboardLayout on every page.
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
  logout: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchMembershipPlans: jest.fn(),
  fetchMemberships: jest.fn(),
  cancelMembership: jest.fn(),
  renewMembership: jest.fn(),
  fetchCustomers: jest.fn(),
}));

const mockedFetchPlans = fetchMembershipPlans as jest.Mock;
const mockedFetchMemberships = fetchMemberships as jest.Mock;
const mockedRenew = renewMembership as jest.Mock;
const mockedFetchCustomers = fetchCustomers as jest.Mock;

/** Same conversion the table uses, so assertions stay locale-safe. */
const fmt = (iso: string) => new Date(iso).toLocaleDateString();

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

const membership = (overrides: Partial<Membership> = {}): Membership => ({
  id: 2,
  customer_id: 1,
  customer_name: "Meera Nair",
  plan_id: 2,
  plan_name: "Gold",
  start_date: "2026-04-01",
  end_date: "2026-09-30",
  status: "expired",
  price: 1999,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-01T00:00:00Z",
  ...overrides,
});

const customer: Customer = {
  id: 1,
  user: 11,
  name: "Meera Nair",
  first_name: "Meera",
  last_name: "Nair",
  email: "meera@example.com",
  phone: "+91 98765 43210",
  branch: null,
  status: "active",
  notes: "",
  gender: "female",
  date_of_birth: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  address_street: "",
  address_city: "",
  address_state: "",
  address_postal_code: "",
  is_active: true,
  profile_photo: null,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-01T00:00:00Z",
};

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.setItem("fbos_user", JSON.stringify({ role: "gym_owner" }));
  mockedFetchPlans.mockResolvedValue({
    count: 1,
    next: null,
    previous: null,
    results: [plan()],
  });
});

/* ── API wire contract ────────────────────────────────────────── */

describe("renewMembership API contract", () => {
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

  it("POSTs the renewal action with the given days", async () => {
    const fetchMock = mockFetch({ id: 7, status: "active" });
    const realRenew = jest.requireActual<typeof import("@/lib/api")>("@/lib/api")
      .renewMembership;
    await realRenew(7, "tok", 45);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/memberships/memberships/7/renewal/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ days: 45 });
    expect((init.headers as Record<string, string>).Authorization).toBe("Token tok");
  });

  it("omits the body so the backend applies its plan-duration default", async () => {
    const fetchMock = mockFetch({ id: 7 });
    const realRenew = jest.requireActual<typeof import("@/lib/api")>("@/lib/api")
      .renewMembership;
    await realRenew(7, "tok");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(init.body).toBeUndefined();
  });
});

/* ── Memberships page renew flow ──────────────────────────────── */

describe("MembershipsPage renew flow", () => {
  const activeM = membership({
    id: 1,
    customer_name: "Arjun Kumar",
    end_date: "2026-12-15",
    status: "active",
  });
  const expiredM = membership({ id: 2 });
  const cancelledM = membership({
    id: 3,
    customer_name: "Old Customer",
    status: "cancelled",
  });

  function mockMemberships(list: Membership[]) {
    mockedFetchMemberships.mockResolvedValue({
      count: list.length,
      next: null,
      previous: null,
      results: list,
    });
  }

  async function renderPage(list: Membership[] = [activeM, expiredM, cancelledM]) {
    mockMemberships(list);
    render(<MembershipsPage />);
    await screen.findByText("Meera Nair");
  }

  it("shows the renew confusion-resolver hint", async () => {
    await renderPage();
    expect(screen.getByText(/extends the same membership/i)).toBeInTheDocument();
  });

  it("offers Renew on active and expired rows but not cancelled rows", async () => {
    await renderPage();
    expect(screen.getAllByRole("button", { name: "Renew membership" })).toHaveLength(2);

    const cancelledRow = screen.getByText("Old Customer").closest("tr");
    expect(
      within(cancelledRow!).queryByRole("button", { name: "Renew membership" }),
    ).not.toBeInTheDocument();
  });

  it("opens the confirm dialog with customer, plan and computed new end date", async () => {
    await renderPage();
    const expiredRow = screen.getByText("Meera Nair").closest("tr");
    fireEvent.click(
      within(expiredRow!).getByRole("button", { name: "Renew membership" }),
    );

    expect(await screen.findByText("Renew membership")).toBeInTheDocument();
    expect(screen.getByText(/membership by 30 days\?/)).toBeInTheDocument();
    expect(screen.getByText(/Current end date:/).textContent).toContain(
      fmt("2026-09-30"),
    );
    expect(screen.getByText(/New end date:/).textContent).toContain(fmt("2026-10-30"));
    expect(
      screen.getByText(/no new membership record/i),
    ).toBeInTheDocument();
  });

  it("renews and refreshes the row with the response (status + end date)", async () => {
    await renderPage([expiredM]);
    fireEvent.click(screen.getByRole("button", { name: "Renew membership" }));

    mockedRenew.mockResolvedValue({
      ...expiredM,
      status: "active",
      end_date: "2026-10-30",
    });
    const dialog = await screen.findByText("Renew membership").then((el) =>
      el.closest(".max-w-md") as HTMLElement,
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Renew" }));

    await waitFor(() =>
      expect(mockedRenew).toHaveBeenCalledWith(2, "test-token", 30),
    );
    await waitFor(() =>
      expect(toast.success).toHaveBeenCalledWith(`Renewed until ${fmt("2026-10-30")}`),
    );

    // Row refreshed from the response: new end date, expired badge gone.
    const row = screen.getByText("Meera Nair").closest("tr");
    await waitFor(() => expect(row?.textContent).toContain(fmt("2026-10-30")));
    expect(row?.textContent).not.toContain("Expired");
    // Dialog closed after success.
    expect(screen.queryByText(/Current end date:/)).not.toBeInTheDocument();
  });

  it("keeps the dialog open and the row untouched when the renewal fails", async () => {
    mockedRenew.mockRejectedValue(new Error("Renewal must extend the membership."));
    await renderPage([expiredM]);
    const row = screen.getByText("Meera Nair").closest("tr");
    fireEvent.click(screen.getByRole("button", { name: "Renew membership" }));

    const dialog = await screen.findByText("Renew membership").then((el) =>
      el.closest(".max-w-md") as HTMLElement,
    );
    fireEvent.click(within(dialog).getByRole("button", { name: "Renew" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByText(/Current end date:/)).toBeInTheDocument();
    expect(row?.textContent).toContain(fmt("2026-09-30"));
  });
});

/* ── Customer detail membership card ──────────────────────────── */

describe("OverviewTab memberships card", () => {
  it("stays hidden when memberships are not loaded", () => {
    render(<OverviewTab customer={customer} summary={null} />);
    expect(screen.queryByText("Memberships")).not.toBeInTheDocument();
  });

  it("shows the empty state", () => {
    render(<OverviewTab customer={customer} summary={null} memberships={[]} />);
    expect(screen.getByText("No memberships on file.")).toBeInTheDocument();
  });

  it("renders membership rows with status and offers Renew for active/expired", () => {
    render(
      <OverviewTab
        customer={customer}
        summary={null}
        memberships={[
          membership({ id: 1, status: "active", end_date: "2026-12-15" }),
          membership({ id: 2 }),
          membership({ id: 3, customer_name: "Old Customer", status: "cancelled" }),
        ]}
        membershipPlans={[plan()]}
        onRenewMembership={jest.fn()}
      />,
    );
    expect(screen.getAllByText("Gold")).toHaveLength(3);
    expect(screen.getByText("Expired")).toBeInTheDocument();
    // active + expired rows only
    expect(screen.getAllByRole("button", { name: "Renew" })).toHaveLength(2);
    expect(screen.getByText("Cancelled")).toBeInTheDocument();
  });

  it("renews from the card and closes the dialog on success", async () => {
    const onRenewMembership = jest.fn().mockResolvedValue({
      ...membership(),
      status: "active",
      end_date: "2026-10-30",
    });
    render(
      <OverviewTab
        customer={customer}
        summary={null}
        memberships={[membership()]}
        membershipPlans={[plan()]}
        onRenewMembership={onRenewMembership}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Renew" }));
    expect(await screen.findByText("Renew membership")).toBeInTheDocument();
    expect(screen.getByText(/New end date:/).textContent).toContain(fmt("2026-10-30"));

    const dialog = screen.getByText("Renew membership").closest(".max-w-md") as HTMLElement;
    fireEvent.click(within(dialog).getByRole("button", { name: "Renew" }));

    await waitFor(() =>
      expect(onRenewMembership).toHaveBeenCalledWith(membership(), 30),
    );
    await waitFor(() =>
      expect(screen.queryByText(/Current end date:/)).not.toBeInTheDocument(),
    );
  });
});

/* ── Assign page hint ─────────────────────────────────────────── */

describe("AssignMembershipPage renewal hint", () => {
  it("shows the confusion-resolver hint", async () => {
    mockedFetchCustomers.mockResolvedValue({
      count: 0,
      next: null,
      previous: null,
      results: [],
    });
    render(<AssignMembershipPage />);
    await screen.findByLabelText("Customer");
    expect(screen.getByText(/extends the same membership/i)).toBeInTheDocument();
  });
});
