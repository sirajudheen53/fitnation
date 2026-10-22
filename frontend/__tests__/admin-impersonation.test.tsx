import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ImpersonationBanner } from "@/components/layout/ImpersonationBanner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import AdminGymsPage from "@/app/admin/page";
import { fetchAdminTenants, impersonateTenant } from "@/lib/api";
import {
  endImpersonationSession,
  getImpersonationSession,
  getToken,
  getStoredUser,
  logout,
  setStoredUser,
  setToken,
  startImpersonationSession,
  type ImpersonationSession,
  type StoredUser,
} from "@/lib/auth";
import { toast } from "sonner";
import type { AdminTenant } from "@/types/admin";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/admin",
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchAdminTenants: jest.fn(),
  impersonateTenant: jest.fn(),
}));

/* ── Shared fixtures ───────────────────────────────────────────── */

const adminUser: StoredUser = {
  id: 1,
  email: "ops@fitnation.app",
  name: "Platform Admin",
  role: "platform_admin",
  tenant_id: null,
  tenant_name: null,
  is_owner: false,
};

const futureIso = (minutes: number) =>
  new Date(Date.now() + minutes * 60_000).toISOString();

const sampleSession = (
  overrides: Partial<ImpersonationSession> = {},
): ImpersonationSession => ({
  token: "imp-token-1",
  expires_at: futureIso(30),
  owner_email: "owner@irontemple.com",
  tenant_id: 7,
  tenant_name: "Iron Temple Fitness",
  admin_token: "admin-token",
  admin_user: adminUser,
  ...overrides,
});

const sampleTenant = (overrides: Partial<AdminTenant> = {}): AdminTenant => ({
  id: 7,
  name: "Iron Temple Fitness",
  subscription_plan: "starter",
  status: "active",
  contact_email: "owner@irontemple.com",
  contact_phone: "+91 98765 43210",
  member_count: 120,
  branch_count: 2,
  created_at: "2026-01-15T00:00:00Z",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.clear();
  // Admin's own session, as after login.
  setToken("admin-token");
  setStoredUser(adminUser);
});

afterEach(() => {
  localStorage.clear();
});

/* ── lib/auth impersonation session ────────────────────────────── */

describe("impersonation session (lib/auth)", () => {
  it("swaps the active session to the owner and back on exit", () => {
    startImpersonationSession(sampleSession());

    expect(getToken()).toBe("imp-token-1");
    const owner = getStoredUser();
    expect(owner?.role).toBe("gym_owner");
    expect(owner?.email).toBe("owner@irontemple.com");
    expect(owner?.tenant_id).toBe(7);
    expect(owner?.tenant_name).toBe("Iron Temple Fitness");
    expect(getImpersonationSession()).not.toBeNull();

    const ended = endImpersonationSession();
    expect(ended?.owner_email).toBe("owner@irontemple.com");
    expect(getToken()).toBe("admin-token");
    expect(getStoredUser()?.email).toBe("ops@fitnation.app");
    expect(getImpersonationSession()).toBeNull();
  });

  it("collapses an expired session back to the admin session", () => {
    startImpersonationSession(sampleSession({ expires_at: futureIso(-1) }));

    // Reading the session is a pure check — the stale stash is still there…
    expect(getImpersonationSession()).not.toBeNull();
    // …but the dead owner token never leaks: the admin session is back.
    expect(getToken()).toBe("admin-token");
    expect(getStoredUser()?.email).toBe("ops@fitnation.app");
    // The collapse already cleared the stash.
    expect(getImpersonationSession()).toBeNull();
  });

  it("discards the stashed admin session on explicit logout", () => {
    startImpersonationSession(sampleSession());
    logout();

    expect(getToken()).toBeNull();
    expect(getStoredUser()).toBeNull();
    expect(getImpersonationSession()).toBeNull();
  });
});

/* ── ImpersonationBanner ───────────────────────────────────────── */

describe("ImpersonationBanner", () => {
  it("renders nothing without an active session", () => {
    const { container } = render(<ImpersonationBanner />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the owner, the gym, and a countdown while impersonating", () => {
    startImpersonationSession(sampleSession());
    render(<ImpersonationBanner />);

    const banner = screen.getByTestId("impersonation-banner");
    expect(banner).toHaveTextContent("owner@irontemple.com");
    expect(banner).toHaveTextContent("Iron Temple Fitness");
    expect(banner).toHaveTextContent(/\d{2}:\d{2}/);
    expect(screen.getByRole("button", { name: /Exit Impersonation/ })).toBeInTheDocument();
  });

  it("restores the admin session and navigates back on exit", async () => {
    startImpersonationSession(sampleSession());
    render(<ImpersonationBanner />);

    fireEvent.click(screen.getByRole("button", { name: /Exit Impersonation/ }));

    expect(getToken()).toBe("admin-token");
    expect(getStoredUser()?.email).toBe("ops@fitnation.app");
    expect(getImpersonationSession()).toBeNull();
    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/admin"));
    expect(toast.success).toHaveBeenCalledWith(
      expect.stringContaining("Exited owner@irontemple.com"),
    );
  });

  it("auto-exits and redirects when the token lifetime is over", async () => {
    startImpersonationSession(sampleSession({ expires_at: futureIso(-1) }));
    render(<ImpersonationBanner />);

    await waitFor(() => expect(mockRouter.replace).toHaveBeenCalledWith("/admin"));
    expect(getToken()).toBe("admin-token");
    expect(getImpersonationSession()).toBeNull();
  });
});

/* ── DashboardLayout integration ───────────────────────────────── */

describe("DashboardLayout with impersonation", () => {
  it("shows the persistent banner and the owner's nav while impersonating", () => {
    startImpersonationSession(sampleSession());
    render(
      <DashboardLayout title="Dashboard">
        <p>content</p>
      </DashboardLayout>,
    );

    expect(screen.getByTestId("impersonation-banner")).toBeInTheDocument();
    // The owner nav (not the operator nav) is what the admin now sees.
    expect(screen.getAllByText("Customers").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Gyms" })).toBeNull();
  });
});

/* ── Gyms dashboard: impersonate action ────────────────────────── */

describe("AdminGymsPage impersonation", () => {
  beforeEach(() => {
    (fetchAdminTenants as jest.Mock).mockResolvedValue([
      sampleTenant(),
      sampleTenant({ id: 8, name: "Legacy Barbell", status: "archived" }),
    ]);
  });

  it("starts an audited session from the row action and enters the owner view", async () => {
    (impersonateTenant as jest.Mock).mockResolvedValue({
      token: "imp-token-9",
      expires_at: futureIso(30),
      owner_email: "owner@irontemple.com",
    });

    render(<AdminGymsPage />);
    await screen.findByText("Iron Temple Fitness");

    fireEvent.click(screen.getByLabelText("Impersonate Iron Temple Fitness"));
    expect(
      await screen.findByText(/Log in as Iron Temple Fitness's owner\?/),
    ).toBeInTheDocument();
    expect(screen.getByText(/recorded in the impersonation audit log/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Start Impersonation" }));

    await waitFor(() =>
      expect(impersonateTenant).toHaveBeenCalledWith(7, "admin-token"),
    );
    // The browser session is now the owner's: every page and API call
    // behaves exactly as the owner's own browser would…
    await waitFor(() => expect(getToken()).toBe("imp-token-9"));
    expect(getStoredUser()?.email).toBe("owner@irontemple.com");
    expect(getStoredUser()?.role).toBe("gym_owner");
    // …and the admin lands in the owner's dashboard.
    await waitFor(() => expect(mockRouter.push).toHaveBeenCalledWith("/dashboard"));
    expect(endImpersonationSession()).not.toBeNull(); // session recorded in the stash
  });

  it("keeps the archived gym read-only", async () => {
    render(<AdminGymsPage />);
    await screen.findByText("Legacy Barbell");

    expect(screen.getByLabelText("Impersonate Legacy Barbell")).toBeDisabled();
  });

  it("surfaces the error and stays on the dashboard when the API fails", async () => {
    (impersonateTenant as jest.Mock).mockRejectedValue(new Error("no owner"));

    render(<AdminGymsPage />);
    await screen.findByText("Iron Temple Fitness");

    fireEvent.click(screen.getByLabelText("Impersonate Iron Temple Fitness"));
    fireEvent.click(
      await screen.findByRole("button", { name: "Start Impersonation" }),
    );

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("no owner"));
    // Nothing was swapped — still the admin's own session on the dashboard.
    expect(getToken()).toBe("admin-token");
    expect(getImpersonationSession()).toBeNull();
    expect(mockRouter.push).not.toHaveBeenCalledWith("/dashboard");
  });
});
