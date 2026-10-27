import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CustomersPage from "@/app/customers/page";
import {
  fetchCustomers,
  fetchDietPlans,
  fetchMembershipPlans,
  fetchMemberships,
  fetchWorkoutPlans,
} from "@/lib/api";
import type { Customer } from "@/types/customer";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/customers",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "owner-token",
  getStoredUser: () => ({
    id: 1,
    email: "owner@fit.test",
    name: "Owner",
    role: "gym_owner",
    tenant_id: 1,
    tenant_name: "Fit Test",
    is_owner: true,
  }),
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchCustomers: jest.fn(),
  fetchMemberships: jest.fn(),
  fetchMembershipPlans: jest.fn(),
  fetchWorkoutPlans: jest.fn(),
  fetchDietPlans: jest.fn(),
}));

const customer = (id: number, name: string): Customer =>
  ({
    id,
    email: null,
    user: 100 + id,
    name,
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
  }) as Customer;

beforeEach(() => {
  jest.clearAllMocks();
  (fetchCustomers as jest.Mock).mockResolvedValue({
    count: 2,
    next: null,
    previous: null,
    results: [customer(1, "Ravi Kumar"), customer(2, "Asha Menon")],
  });
  (fetchMemberships as jest.Mock).mockResolvedValue({ results: [] });
  (fetchMembershipPlans as jest.Mock).mockResolvedValue({ results: [] });
  (fetchWorkoutPlans as jest.Mock).mockResolvedValue({
    results: [{ id: 3, name: "Strength Plan" }],
  });
  (fetchDietPlans as jest.Mock).mockResolvedValue({
    results: [{ id: 4, name: "Bulk Plan" }],
  });
});

describe("CustomersPage assigned-plan filters (issue #90)", () => {
  it("loads the unfiltered list on mount and offers plan filters", async () => {
    render(<CustomersPage />);

    expect(await screen.findByText("Ravi Kumar")).toBeInTheDocument();
    expect(fetchCustomers).toHaveBeenCalledWith("owner-token", {
      assigned_workout_plan: undefined,
      assigned_diet_plan: undefined,
    });

    const workoutSelect = await screen.findByTestId("workout-plan-filter");
    const dietSelect = screen.getByTestId("diet-plan-filter");
    // Catalogue options are offered alongside the any/none shortcuts.
    expect(workoutSelect).toHaveValue("all");
    fireEvent.change(workoutSelect, { target: { value: "any" } });
    expect(workoutSelect).toHaveValue("any");
    expect(dietSelect).toHaveValue("all");
  });

  it("refetches with server-side filters when a plan filter changes", async () => {
    render(<CustomersPage />);
    await screen.findByText("Ravi Kumar");

    fireEvent.change(screen.getByTestId("workout-plan-filter"), { target: { value: "any" } });
    await waitFor(() =>
      expect(fetchCustomers).toHaveBeenLastCalledWith("owner-token", {
        assigned_workout_plan: "any",
        assigned_diet_plan: undefined,
      }),
    );

    fireEvent.change(screen.getByTestId("diet-plan-filter"), { target: { value: "none" } });
    await waitFor(() =>
      expect(fetchCustomers).toHaveBeenLastCalledWith("owner-token", {
        assigned_workout_plan: "any",
        assigned_diet_plan: "none",
      }),
    );

    // Picking a catalogue plan filters by that plan's id.
    fireEvent.change(screen.getByTestId("workout-plan-filter"), { target: { value: "3" } });
    await waitFor(() =>
      expect(fetchCustomers).toHaveBeenLastCalledWith("owner-token", {
        assigned_workout_plan: "3",
        assigned_diet_plan: "none",
      }),
    );
  });

  it("keeps the toolbar visible when a filter matches no customers", async () => {
    (fetchCustomers as jest.Mock)
      .mockResolvedValueOnce({
        count: 1,
        next: null,
        previous: null,
        results: [customer(1, "Ravi Kumar")],
      })
      .mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    render(<CustomersPage />);
    await screen.findByText("Ravi Kumar");

    // Filtering to an empty result keeps the toolbar (and the chosen filter)
    // on screen so it can be reset.
    fireEvent.change(screen.getByTestId("workout-plan-filter"), { target: { value: "any" } });
    await waitFor(() =>
      expect(fetchCustomers).toHaveBeenLastCalledWith("owner-token", {
        assigned_workout_plan: "any",
        assigned_diet_plan: undefined,
      }),
    );
    expect(screen.getByTestId("workout-plan-filter")).toHaveValue("any");
    expect(screen.getByTestId("diet-plan-filter")).toBeInTheDocument();
    expect(screen.queryByText("Ravi Kumar")).not.toBeInTheDocument();
  });
});
