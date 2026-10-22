import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import AdminPlansPage from "@/app/admin/plans/page";
import { PlanParityCheckCard } from "@/features/admin/components/PlanParityCheckCard";
import { PlanFormDialog } from "@/features/admin/components/PlanFormDialog";
import {
  ApiError,
  createAdminPlan,
  deactivateAdminPlan,
  fetchAdminPlans,
  getPlans,
  updateAdminPlan,
} from "@/lib/api";
import type { AdminSubscriptionPlan } from "@/types/admin";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/admin/plans",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "admin-token",
  getStoredUser: () => ({
    id: 1,
    email: "ops@fitnation.app",
    name: "Platform Admin",
    role: "platform_admin",
    tenant_id: null,
    tenant_name: null,
    is_owner: false,
  }),
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
  startImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchAdminPlans: jest.fn(),
  createAdminPlan: jest.fn(),
  updateAdminPlan: jest.fn(),
  deactivateAdminPlan: jest.fn(),
  getPlans: jest.fn(),
}));

const samplePlan = (overrides: Partial<AdminSubscriptionPlan> = {}): AdminSubscriptionPlan => ({
  id: 1,
  code: "starter",
  name: "Starter",
  price_monthly: "999.00",
  price_yearly: "9990.00",
  max_branches: 1,
  max_customers: 100,
  max_trainers: 5,
  features: { whatsapp: true },
  is_active: true,
  sort_order: 0,
  created_at: "2026-01-15T00:00:00Z",
  updated_at: "2026-09-01T00:00:00Z",
  ...overrides,
});

/** The full seeded catalog the parity check expects. */
const publicPlans = (codes: string[]) => ({
  plans: codes.map((code) => ({ code, name: code, price_monthly: "1", price_yearly: "1" })),
});

beforeEach(() => {
  jest.clearAllMocks();
  (getPlans as jest.Mock).mockResolvedValue(
    publicPlans(["starter", "professional", "enterprise"]),
  );
});

describe("PlanFormDialog — create", () => {
  it("submits the form fields and calls onSaved", async () => {
    const onSaved = jest.fn();
    const created = samplePlan({ id: 9, name: "Starter" });
    (createAdminPlan as jest.Mock).mockResolvedValue(created);

    render(<PlanFormDialog plan={null} onClose={() => {}} onSaved={onSaved} />);

    fireEvent.change(screen.getByLabelText("Plan name"), { target: { value: "Starter" } });
    fireEvent.change(screen.getByLabelText("Monthly price (₹)"), { target: { value: "999" } });
    fireEvent.change(screen.getByLabelText("Yearly price (₹)"), { target: { value: "9990" } });
    fireEvent.change(screen.getByLabelText("Max branches"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Max customers"), { target: { value: "100" } });
    fireEvent.change(screen.getByLabelText("Max trainers"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Plan" }));

    await waitFor(() =>
      expect(createAdminPlan).toHaveBeenCalledWith(
        {
          code: "starter",
          name: "Starter",
          price_monthly: "999",
          price_yearly: "9990",
          max_branches: 1,
          max_customers: 100,
          max_trainers: 5,
          sort_order: 0,
          is_active: true,
          features: {},
        },
        "admin-token",
      ),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(created));
  });

  it("blocks submission when validation fails and calls nothing", async () => {
    render(<PlanFormDialog plan={null} onClose={() => {}} onSaved={jest.fn()} />);

    fireEvent.change(screen.getByLabelText("Monthly price (₹)"), {
      target: { value: "not-a-price" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Plan" }));

    expect(await screen.findByText("Plan name is required.")).toBeInTheDocument();
    expect(screen.getAllByText(/Enter a valid amount/)).toHaveLength(2);
    expect(createAdminPlan).not.toHaveBeenCalled();
  });

  it("rejects non-JSON features without calling the API", () => {
    render(<PlanFormDialog plan={null} onClose={() => {}} onSaved={jest.fn()} />);

    fireEvent.change(screen.getByLabelText("Plan name"), { target: { value: "Starter" } });
    fireEvent.change(screen.getByLabelText("Features (JSON)"), {
      target: { value: "{not json" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create Plan" }));

    expect(screen.getByText("Features must be valid JSON.")).toBeInTheDocument();
    expect(createAdminPlan).not.toHaveBeenCalled();
  });
});

describe("PlanFormDialog — edit", () => {
  it("pre-fills from the plan, locks the code, and PATCHes", async () => {
    const onSaved = jest.fn();
    const updated = samplePlan({ name: "Starter Pro" });
    (updateAdminPlan as jest.Mock).mockResolvedValue(updated);

    render(<PlanFormDialog plan={samplePlan()} onClose={() => {}} onSaved={onSaved} />);

    expect(screen.getByText("Edit Subscription Plan")).toBeInTheDocument();
    expect(screen.getByLabelText("Plan name")).toHaveValue("Starter");
    expect(screen.getByLabelText("Monthly price (₹)")).toHaveValue(999);
    expect(screen.getByLabelText("Code")).toBeDisabled();

    fireEvent.change(screen.getByLabelText("Plan name"), { target: { value: "Starter Pro" } });
    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() =>
      expect(updateAdminPlan).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ code: "starter", name: "Starter Pro" }),
        "admin-token",
      ),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(updated));
  });

  it("shows backend field errors next to the input", async () => {
    (updateAdminPlan as jest.Mock).mockRejectedValue(
      new ApiError(400, { code: ["plan with this code already exists."] }, "Bad Request"),
    );

    render(<PlanFormDialog plan={samplePlan()} onClose={() => {}} onSaved={jest.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText(/already exists/)).toBeInTheDocument();
  });
});

describe("PlanParityCheckCard", () => {
  it("passes when the seeded catalog matches the public endpoint", async () => {
    render(
      <PlanParityCheckCard
        plans={[
          samplePlan(),
          samplePlan({ id: 2, code: "professional", name: "Professional" }),
          samplePlan({ id: 3, code: "enterprise", name: "Enterprise" }),
        ]}
      />,
    );

    expect(await screen.findByText(/Seeding parity OK — 3 active plans match/)).toBeInTheDocument();
    expect(getPlans).toHaveBeenCalledTimes(1);
  });

  it("warns when a required plan is missing or inactive in the database", async () => {
    render(
      <PlanParityCheckCard
        plans={[
          samplePlan(),
          samplePlan({ id: 2, code: "professional", name: "Professional" }),
          samplePlan({ id: 3, code: "enterprise", name: "Enterprise", is_active: false }),
        ]}
      />,
    );

    expect(
      await screen.findByText(/No active “enterprise” plan in the database/),
    ).toBeInTheDocument();
  });

  it("warns when an active plan is missing from the public catalog", async () => {
    (getPlans as jest.Mock).mockResolvedValue(publicPlans(["starter", "professional"]));

    render(
      <PlanParityCheckCard
        plans={[
          samplePlan(),
          samplePlan({ id: 2, code: "professional", name: "Professional" }),
          samplePlan({ id: 3, code: "enterprise", name: "Enterprise" }),
        ]}
      />,
    );

    expect(
      await screen.findByText(
        /Active plan “enterprise” is missing from the public catalog/,
      ),
    ).toBeInTheDocument();
  });

  it("warns when the public catalog cannot be loaded at all", async () => {
    (getPlans as jest.Mock).mockRejectedValue(new Error("network down"));

    render(<PlanParityCheckCard plans={[samplePlan()]} />);

    expect(
      await screen.findByText(/Couldn't load the public plans catalog/),
    ).toBeInTheDocument();
  });

  it("rechecks on demand", async () => {
    const allActive = [
      samplePlan(),
      samplePlan({ id: 2, code: "professional", name: "Professional" }),
      samplePlan({ id: 3, code: "enterprise", name: "Enterprise" }),
    ];
    render(<PlanParityCheckCard plans={allActive} />);
    await screen.findByText(/Seeding parity OK/);

    fireEvent.click(screen.getByRole("button", { name: /Recheck/ }));

    await waitFor(() => expect(getPlans).toHaveBeenCalledTimes(2));
  });
});

describe("AdminPlansPage", () => {
  it("renders the plan table with active and inactive rows", async () => {
    (fetchAdminPlans as jest.Mock).mockResolvedValue([
      samplePlan(),
      samplePlan({ id: 2, code: "professional", name: "Professional", is_active: false }),
    ]);

    render(<AdminPlansPage />);

    expect(await screen.findByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Professional")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Deactivate Starter" })).toBeInTheDocument();
    // Inactive plans have no deactivate action — they are already off.
    expect(
      screen.queryByRole("button", { name: "Deactivate Professional" }),
    ).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no plans", async () => {
    (fetchAdminPlans as jest.Mock).mockResolvedValue([]);

    render(<AdminPlansPage />);

    expect(await screen.findByText(/No subscription plans yet/)).toBeInTheDocument();
  });

  it("creates a plan from the New Plan action and appends the row", async () => {
    (fetchAdminPlans as jest.Mock).mockResolvedValue([samplePlan()]);
    (createAdminPlan as jest.Mock).mockResolvedValue(
      samplePlan({ id: 5, code: "professional", name: "Professional" }),
    );

    render(<AdminPlansPage />);
    await screen.findByText("Starter");

    fireEvent.click(screen.getByRole("button", { name: /New Plan/ }));
    fireEvent.change(await screen.findByLabelText("Plan name"), {
      target: { value: "Professional" },
    });
    fireEvent.change(screen.getByLabelText("Monthly price (₹)"), { target: { value: "1999" } });
    fireEvent.change(screen.getByLabelText("Yearly price (₹)"), { target: { value: "19990" } });
    fireEvent.click(screen.getByRole("button", { name: "Create Plan" }));

    // Wait for the dialog to close (the parity select's "Professional"
    // option would shadow the new table row while the dialog is open).
    await waitFor(() =>
      expect(screen.queryByLabelText("Plan name")).toBeNull(),
    );
    expect(screen.getByText("Professional")).toBeInTheDocument();
    expect(createAdminPlan).toHaveBeenCalled();
  });

  it("edits a plan from the row action", async () => {
    (fetchAdminPlans as jest.Mock).mockResolvedValue([samplePlan()]);
    (updateAdminPlan as jest.Mock).mockResolvedValue(samplePlan({ name: "Starter Renamed" }));

    render(<AdminPlansPage />);
    await screen.findByText("Starter");

    fireEvent.click(screen.getByLabelText("Edit Starter"));
    fireEvent.change(await screen.findByLabelText("Plan name"), {
      target: { value: "Starter Renamed" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByText("Starter Renamed")).toBeInTheDocument();
  });

  it("deactivates a plan after confirmation", async () => {
    (fetchAdminPlans as jest.Mock).mockResolvedValue([samplePlan()]);
    (deactivateAdminPlan as jest.Mock).mockResolvedValue(samplePlan({ is_active: false }));

    render(<AdminPlansPage />);
    await screen.findByText("Starter");

    fireEvent.click(screen.getByRole("button", { name: "Deactivate Starter" }));
    expect(screen.getByText(/Deactivate Starter\?/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Deactivate Plan" }));

    await waitFor(() =>
      expect(deactivateAdminPlan).toHaveBeenCalledWith(1, "admin-token"),
    );
    expect(await screen.findByText("inactive")).toBeInTheDocument();
  });

  it("shows an API error instead of the table", async () => {
    (fetchAdminPlans as jest.Mock).mockRejectedValue(new Error("boom"));

    render(<AdminPlansPage />);

    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
