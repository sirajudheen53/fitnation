/**
 * Plan upgrade flow (#105, owner decision 2026-11-07): the upgrade amount is
 * SUGGESTED (prorated difference, pre-filled) and staff can override it — the
 * entered amount is what gets recorded. The end date stays UNCHANGED (the
 * upgrade swaps the plan within the paid window). Covers the API wire
 * contract, the dialog (prefill, override, #96 error treatment, empty state)
 * and the memberships-page flow (active-only action, row refresh, toasts).
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";

import MembershipsPage from "@/app/memberships/page";
import { UpgradeMembershipDialog } from "@/features/memberships/components/UpgradeMembershipDialog";
import { fetchUpgradePreview, upgradeMembership } from "@/lib/api";
import type { Membership, UpgradePreview } from "@/types/membership";
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
  fetchUpgradePreview: jest.fn(),
  upgradeMembership: jest.fn(),
}));

const mockedFetchPreview = fetchUpgradePreview as jest.Mock;
const mockedUpgrade = upgradeMembership as jest.Mock;
const mockedFetchPlans = jest.requireMock("@/lib/api").fetchMembershipPlans as jest.Mock;
const mockedFetchMemberships = jest.requireMock("@/lib/api").fetchMemberships as jest.Mock;

const fmt = (iso: string) => new Date(iso).toLocaleDateString();

const membership = (overrides: Partial<Membership> = {}): Membership => ({
  id: 7,
  customer_id: 1,
  customer_name: "Meera Nair",
  plan_id: 2,
  plan_name: "Gold",
  start_date: "2026-04-01",
  end_date: "2026-12-15",
  status: "active",
  price: 1999,
  created_at: "2026-04-01T00:00:00Z",
  updated_at: "2026-04-01T00:00:00Z",
  ...overrides,
});

const preview = (overrides: Partial<UpgradePreview> = {}): UpgradePreview => ({
  membership_id: 7,
  end_date: "2026-12-15",
  remaining_days: 38,
  current_plan: { id: 2, name: "Gold", price: "1999.00", duration_days: 30 },
  eligible_plans: [
    {
      id: 3,
      name: "Platinum",
      price: "4999.00",
      duration_days: 90,
      suggested_amount: "3800.00",
    },
    {
      id: 4,
      name: "Diamond",
      price: "7999.00",
      duration_days: 180,
      suggested_amount: "7500.00",
    },
  ],
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.setItem("fbos_user", JSON.stringify({ role: "gym_owner" }));
  mockedFetchPreview.mockResolvedValue(preview());
});

/* ── API wire contract ────────────────────────────────────────── */

describe("upgrade API contract", () => {
  function mockFetch(payload: unknown, ok = true, status = 200) {
    const fetchMock = jest.fn().mockResolvedValue({
      ok,
      status,
      json: () => Promise.resolve(payload),
    });
    global.fetch = fetchMock as unknown as typeof fetch;
    return fetchMock;
  }

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("fetchUpgradePreview GETs the upgrade action", async () => {
    const fetchMock = mockFetch(preview());
    const realPreview = jest.requireActual<typeof import("@/lib/api")>("@/lib/api")
      .fetchUpgradePreview;
    await realPreview(7, "tok");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/memberships/memberships/7/upgrade/");
    expect(init.method).toBe("GET");
    expect((init.headers as Record<string, string>).Authorization).toBe("Token tok");
  });

  it("upgradeMembership POSTs plan_id, amount and payment_method", async () => {
    const fetchMock = mockFetch({ membership: {}, payment: {} });
    const realUpgrade = jest.requireActual<typeof import("@/lib/api")>("@/lib/api")
      .upgradeMembership;
    await realUpgrade(7, { plan_id: 3, amount: 500, payment_method: "upi" }, "tok");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/memberships/memberships/7/upgrade/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      plan_id: 3,
      amount: 500,
      payment_method: "upi",
    });
  });

  it("upgradeMembership carries notes only when given", async () => {
    const fetchMock = mockFetch({ membership: {}, payment: {} });
    const realUpgrade = jest.requireActual<typeof import("@/lib/api")>("@/lib/api")
      .upgradeMembership;
    await realUpgrade(
      7,
      { plan_id: 3, amount: 500, payment_method: "cash", notes: "Loyalty discount" },
      "tok",
    );
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      plan_id: 3,
      amount: 500,
      payment_method: "cash",
      notes: "Loyalty discount",
    });
  });
});

/* ── Upgrade dialog ───────────────────────────────────────────── */

describe("UpgradeMembershipDialog", () => {
  function renderDialog(overrides: Partial<Membership> = {}) {
    const onSaved = jest.fn();
    render(
      <UpgradeMembershipDialog
        key="fixed"
        membership={membership(overrides)}
        onSaved={onSaved}
        onClose={jest.fn()}
      />,
    );
    return onSaved;
  }

  async function openForm(overrides: Partial<Membership> = {}) {
    const onSaved = renderDialog(overrides);
    await screen.findByText("Upgrade to");
    return onSaved;
  }

  it("loads the preview, lists eligible plans, and pre-fills the suggestion", async () => {
    await openForm();
    expect(mockedFetchPreview).toHaveBeenCalledWith(7, "test-token");
    const selector = screen.getByLabelText("Upgrade to") as HTMLSelectElement;
    expect(selector.value).toBe("3");
    expect(within(selector).getByRole("option", { name: /Platinum/ })).toBeInTheDocument();
    expect(within(selector).getByRole("option", { name: /Diamond/ })).toBeInTheDocument();
    const amount = screen.getByLabelText("Amount") as HTMLInputElement;
    expect(amount.value).toBe("3800");
    // The suggestion is advisory and the end date is unchanged — both stated.
    expect(screen.getByText(/prorated for 38 remaining days/)).toBeInTheDocument();
    expect(screen.getByText(/Change it freely/)).toBeInTheDocument();
    expect(screen.getByText(/end date stays/i).textContent).toContain(fmt("2026-12-15"));
    expect(screen.getByText(/within the already-paid window/)).toBeInTheDocument();
  });

  it("switching plans re-fills the amount with that plan's suggestion", async () => {
    await openForm();
    fireEvent.change(screen.getByLabelText("Upgrade to"), { target: { value: "4" } });
    const amount = screen.getByLabelText("Amount") as HTMLInputElement;
    expect(amount.value).toBe("7500");
    expect(screen.getByText(/prorated for 38 remaining days/)).toBeInTheDocument();
  });

  it("submits the entered amount — staff override wins over the suggestion", async () => {
    const onSaved = await openForm();
    mockedUpgrade.mockResolvedValue({
      membership: membership({ plan_id: 3, plan_name: "Platinum" }),
      payment: { id: 99, amount: "500.00" },
      suggested_amount: "3800.00",
      amount_charged: "500.00",
    });

    const amount = screen.getByLabelText("Amount") as HTMLInputElement;
    fireEvent.change(amount, { target: { value: "500" } });
    fireEvent.change(screen.getByLabelText("Payment method"), { target: { value: "upi" } });
    fireEvent.change(screen.getByLabelText("Notes"), { target: { value: "Loyalty discount" } });
    fireEvent.click(screen.getByRole("button", { name: /Upgrade & record payment/ }));

    await waitFor(() =>
      expect(mockedUpgrade).toHaveBeenCalledWith(
        7,
        { plan_id: 3, amount: 500, payment_method: "upi", notes: "Loyalty discount" },
        "test-token",
      ),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
    const [savedMembership] = onSaved.mock.calls[0];
    expect(savedMembership.plan_name).toBe("Platinum");
  });

  it("renders DRF field errors inline and keeps the banner out (#96)", async () => {
    await openForm();
    // Downgrade guardrail, as the backend returns it (400 with a plan_id field).
    mockedUpgrade.mockRejectedValue({
      status: 400,
      data: { plan_id: ["Downgrade not allowed — Basic costs less than the current plan (Gold)."] },
      message: "Downgrade not allowed — Basic costs less than the current plan (Gold).",
    });
    fireEvent.click(screen.getByRole("button", { name: /Upgrade & record payment/ }));

    await waitFor(() =>
      expect(screen.getByText(/Downgrade not allowed — Basic costs less/)).toBeInTheDocument(),
    );
    // No banner: the body carried something inline-renderable (#96).
    expect(screen.queryByText(/status 400/)).not.toBeInTheDocument();
  });

  it("banners errors that carry no field errors (#96)", async () => {
    await openForm();
    mockedUpgrade.mockRejectedValue(new Error("Could not reach the server."));
    fireEvent.click(screen.getByRole("button", { name: /Upgrade & record payment/ }));

    await waitFor(() =>
      expect(screen.getByText("Could not reach the server.")).toBeInTheDocument(),
    );
    // Dialog stays open for a retry; nothing was saved.
    expect(screen.getByText("Upgrade to")).toBeInTheDocument();
  });

  it("shows an empty state and disables submit when nothing is upgradeable", async () => {
    mockedFetchPreview.mockResolvedValue(preview({ eligible_plans: [] }));
    renderDialog();
    await screen.findByText(/No higher-priced plans available/);
    expect(screen.getByRole("button", { name: /Upgrade & record payment/ })).toBeDisabled();
  });

  it("banners a failed preview fetch and never reaches the submit call", async () => {
    mockedFetchPreview.mockRejectedValue(new Error("Preview unavailable."));
    renderDialog();
    await screen.findByText("Preview unavailable.");
    expect(mockedUpgrade).not.toHaveBeenCalled();
    expect(screen.queryByLabelText("Upgrade to")).not.toBeInTheDocument();
  });
});

/* ── Memberships page flow ────────────────────────────────────── */

describe("MembershipsPage upgrade flow", () => {
  const activeM = membership({ id: 1, customer_name: "Arjun Kumar" });
  const expiredM = membership({ id: 2, status: "expired" });
  const cancelledM = membership({ id: 3, customer_name: "Old Customer", status: "cancelled" });

  function mockMemberships(list: Membership[]) {
    mockedFetchMemberships.mockResolvedValue({
      count: list.length,
      next: null,
      previous: null,
      results: list,
    });
  }

  beforeEach(() => {
    mockedFetchPlans.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
  });

  it("offers Upgrade on active rows only", async () => {
    mockMemberships([activeM, expiredM, cancelledM]);
    render(<MembershipsPage />);
    await screen.findByText("Arjun Kumar");

    const buttons = screen.getAllByRole("button", { name: "Upgrade membership" });
    expect(buttons).toHaveLength(1);
    const activeRow = screen.getByText("Arjun Kumar").closest("tr");
    expect(within(activeRow!).getByRole("button", { name: "Upgrade membership" })).toBeInTheDocument();
    const expiredRow = screen.getByText("Meera Nair").closest("tr");
    expect(
      within(expiredRow!).queryByRole("button", { name: "Upgrade membership" }),
    ).not.toBeInTheDocument();
    const cancelledRow = screen.getByText("Old Customer").closest("tr");
    expect(
      within(cancelledRow!).queryByRole("button", { name: "Upgrade membership" }),
    ).not.toBeInTheDocument();
  });

  it("opens the dialog, upgrades, refreshes the row and toasts", async () => {
    mockMemberships([activeM]);
    render(<MembershipsPage />);
    await screen.findByText("Arjun Kumar");
    fireEvent.click(screen.getByRole("button", { name: "Upgrade membership" }));

    expect(await screen.findByText("Upgrade to")).toBeInTheDocument();
    mockedUpgrade.mockResolvedValue({
      membership: membership({ id: 1, customer_name: "Arjun Kumar", plan_id: 3, plan_name: "Platinum" }),
      payment: { id: 99, amount: "3800.00" },
      suggested_amount: "3800.00",
      amount_charged: "3800.00",
    });
    fireEvent.click(screen.getByRole("button", { name: /Upgrade & record payment/ }));

    // The page state (row swap + dialog close) commits in the same batch as
    // the toast — wait on the DOM, not on the toast mock.
    await screen.findByText("Platinum");
    await waitFor(() => expect(toast.success).toHaveBeenCalledWith("Upgraded to Platinum"));
    const row = screen.getByText("Arjun Kumar").closest("tr");
    expect(row?.textContent).toContain("Platinum");
    // Dialog closed after success.
    expect(screen.queryByText("Upgrade to")).not.toBeInTheDocument();
  });

  it("keeps the row untouched when the upgrade fails", async () => {
    mockMemberships([activeM]);
    render(<MembershipsPage />);
    await screen.findByText("Arjun Kumar");
    fireEvent.click(screen.getByRole("button", { name: "Upgrade membership" }));

    await screen.findByText("Upgrade to");
    mockedUpgrade.mockRejectedValue(new Error("Only an active membership can be upgraded."));
    fireEvent.click(screen.getByRole("button", { name: /Upgrade & record payment/ }));

    await waitFor(() => expect(screen.getByText(/Only an active membership/)).toBeInTheDocument());
    // Row still shows the old plan — nothing was saved.
    expect(screen.getByText("Arjun Kumar").closest("tr")?.textContent).toContain("Gold");
    // No success toast on failure.
    expect(toast.success).not.toHaveBeenCalled();
  });
});
