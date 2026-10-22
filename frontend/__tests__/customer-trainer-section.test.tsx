import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { TrainerSection } from "@/features/customers/components/TrainerSection";
import { AssignTrainerModal } from "@/features/trainers/components/AssignTrainerModal";
import {
  createTrainerAssignment,
  fetchBranches,
  fetchPtRemaining,
  fetchTrainerAssignments,
  fetchTrainers,
  unassignTrainerAssignment,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { BranchTrainerAssignment, PtRemaining, Trainer } from "@/types/trainer";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/customers/500",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "front-desk-token",
  getStoredUser: () => ({
    id: 1,
    email: "desk@fit.test",
    name: "Front Desk",
    role: "manager",
    tenant_id: 1,
    tenant_name: "Fit Test",
    is_owner: false,
  }),
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchTrainerAssignments: jest.fn(),
  fetchTrainers: jest.fn(),
  fetchBranches: jest.fn(),
  fetchPtRemaining: jest.fn(),
  createTrainerAssignment: jest.fn(),
  unassignTrainerAssignment: jest.fn(),
}));

const sampleCustomer = {
  id: 500,
  name: "Ravi Kumar",
  email: "ravi@fit.test",
  branch: 1,
} as Customer;

const sampleTrainer = (overrides: Partial<Trainer> = {}): Trainer => ({
  id: 1,
  user_id: 11,
  email: "asha@fit.test",
  first_name: "Asha",
  last_name: "Menon",
  phone: null,
  specialization: "Strength",
  bio: null,
  is_active: true,
  certifications: [],
  experience_years: 6,
  rating: "4.50",
  profile_photo: "",
  max_clients: 20,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const sampleAssignment = (
  overrides: Partial<BranchTrainerAssignment> = {},
): BranchTrainerAssignment => ({
  id: 100,
  trainer: 1,
  customer: 500,
  branch: 1,
  assigned_at: "2026-02-01T00:00:00Z",
  unassigned_at: null,
  is_active: true,
  trainer_email: "asha@fit.test",
  customer_name: "Ravi Kumar",
  branch_name: "HSR Layout",
  ...overrides,
});

const samplePack = (overrides: Partial<PtRemaining> = {}): PtRemaining => ({
  customer_id: 500,
  membership_id: 9,
  plan_name: "PT 12-pack",
  membership_status: "active",
  end_date: "2026-12-31",
  total: 12,
  redeemed: 4,
  remaining: 8,
  unlimited: false,
  can_book: true,
  reason: "ok",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  (fetchTrainerAssignments as jest.Mock).mockResolvedValue([sampleAssignment()]);
  (fetchTrainers as jest.Mock).mockResolvedValue([
    sampleTrainer(),
    sampleTrainer({ id: 2, first_name: "Vikram", last_name: "Rathore", email: "vikram@fit.test" }),
  ]);
  (fetchBranches as jest.Mock).mockResolvedValue([
    { id: 1, name: "HSR Layout" },
    { id: 2, name: "Indiranagar" },
  ]);
  (fetchPtRemaining as jest.Mock).mockResolvedValue(samplePack());
});

describe("TrainerSection", () => {
  it("renders the assigned trainer with specialization and profile link", async () => {
    render(<TrainerSection customer={sampleCustomer} />);

    const card = await screen.findByTestId("assigned-trainer");
    expect(card).toHaveTextContent("Asha Menon");
    expect(card).toHaveTextContent("Strength");
    expect(screen.getByRole("link", { name: "Asha Menon" })).toHaveAttribute(
      "href",
      "/trainers/1",
    );
  });

  it("shows the PT pack badge with remaining/total", async () => {
    render(<TrainerSection customer={sampleCustomer} />);

    expect(await screen.findByTestId("pt-pack-badge")).toHaveTextContent(
      "PT pack: 8 / 12 left · PT 12-pack",
    );
  });

  it("hides the PT pack badge when the entitlement API fails", async () => {
    (fetchPtRemaining as jest.Mock).mockRejectedValue(
      new Error("Request failed with status 403"),
    );
    render(<TrainerSection customer={sampleCustomer} />);

    expect(await screen.findByTestId("assigned-trainer")).toBeInTheDocument();
    expect(screen.queryByTestId("pt-pack-badge")).not.toBeInTheDocument();
  });

  it("shows the blocked-pack warning copy when the pack is exhausted", async () => {
    (fetchPtRemaining as jest.Mock).mockResolvedValue(
      samplePack({ remaining: 0, redeemed: 12, can_book: false, reason: "session_pack_exhausted" }),
    );
    render(<TrainerSection customer={sampleCustomer} />);

    expect(
      await screen.findByText(/PT pack exhausted — all 12 sessions redeemed/),
    ).toBeInTheDocument();
  });

  it("shows the empty state and assign action when unassigned", async () => {
    (fetchTrainerAssignments as jest.Mock).mockResolvedValue([]);
    render(<TrainerSection customer={sampleCustomer} />);

    expect(await screen.findByTestId("trainer-empty")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign trainer" })).toBeInTheDocument();
  });

  it("assigns optimistically and rolls back on failure", async () => {
    // No existing assignment → start from the empty state.
    (fetchTrainerAssignments as jest.Mock).mockResolvedValue([]);
    // Create resolves to a conflict the front desk cares about (duplicate pair).
    (createTrainerAssignment as jest.Mock).mockRejectedValue(
      new Error("Request failed with status 400"),
    );
    render(<TrainerSection customer={sampleCustomer} />);
    await screen.findByTestId("trainer-empty");

    fireEvent.click(screen.getByRole("button", { name: "Assign trainer" }));
    // Modal lists both active trainers.
    await screen.findByTestId("trainer-options");
    fireEvent.click(screen.getByRole("button", { name: /Asha Menon/ }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm assignment" }));

    // Optimistic row appears, then rolls back after the failure.
    await waitFor(() => expect(createTrainerAssignment).toHaveBeenCalled());
    expect(await screen.findByTestId("trainer-empty")).toBeInTheDocument();
  });

  it("unassigns with confirm, optimistically removing the row", async () => {
    (unassignTrainerAssignment as jest.Mock).mockResolvedValue(
      sampleAssignment({ is_active: false, unassigned_at: "2026-10-22T00:00:00Z" }),
    );
    render(<TrainerSection customer={sampleCustomer} />);
    await screen.findByTestId("assigned-trainer");

    fireEvent.click(screen.getByRole("button", { name: "Unassign Asha Menon" }));
    expect(screen.getByText(/will no longer be listed as Ravi Kumar/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Unassign" }));
    await waitFor(() =>
      expect(unassignTrainerAssignment).toHaveBeenCalledWith(100, "front-desk-token"),
    );
    await waitFor(() =>
      expect(screen.queryByTestId("assigned-trainer")).not.toBeInTheDocument(),
    );
  });
});

describe("AssignTrainerModal", () => {
  it("filters trainers by search and submits the branch-scoped payload", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(
      <AssignTrainerModal customerBranchId={1} onSubmit={onSubmit} onClose={() => {}} />,
    );

    await screen.findByText("Asha Menon");
    expect(screen.getByText("Vikram Rathore")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Search active trainers"), {
      target: { value: "vikram" },
    });
    expect(screen.queryByText("Asha Menon")).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Vikram Rathore/ }));
    // Branch select prefilled with the customer's branch (value "1").
    expect(screen.getByLabelText("Branch")).toHaveValue("1");
    fireEvent.click(screen.getByRole("button", { name: "Confirm assignment" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith({ trainer: 2, branch: 1 }),
    );
  });

  it("shows the empty state when there are no active trainers", async () => {
    (fetchTrainers as jest.Mock).mockResolvedValue([]);
    render(
      <AssignTrainerModal customerBranchId={null} onSubmit={jest.fn()} onClose={() => {}} />,
    );

    expect(await screen.findByText("No active trainers available.")).toBeInTheDocument();
  });

  it("shows the error state when trainers fail to load", async () => {
    (fetchTrainers as jest.Mock).mockRejectedValue(
      new Error("Request failed with status 500"),
    );
    render(
      <AssignTrainerModal customerBranchId={null} onSubmit={jest.fn()} onClose={() => {}} />,
    );

    expect(
      await screen.findByText("Request failed with status 500"),
    ).toBeInTheDocument();
  });
});
