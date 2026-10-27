import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { toast } from "sonner";
import {
  PlanAssignmentsSection,
} from "@/features/customers/components/PlanAssignmentsSection";
import { AssignPlanModal } from "@/features/customers/components/AssignPlanModal";
import {
  assignDietPlan,
  assignWorkoutPlan,
  fetchActiveDietAssignments,
  fetchActiveWorkoutAssignments,
  fetchDietPlans,
  fetchWorkoutPlans,
  unassignDietAssignment,
  unassignWorkoutAssignment,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { DietAssignment, DietPlan } from "@/types/diet";
import type { WorkoutAssignment, WorkoutPlan } from "@/types/workout";

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
  fetchActiveWorkoutAssignments: jest.fn(),
  fetchActiveDietAssignments: jest.fn(),
  fetchWorkoutPlans: jest.fn(),
  fetchDietPlans: jest.fn(),
  assignWorkoutPlan: jest.fn(),
  assignDietPlan: jest.fn(),
  unassignWorkoutAssignment: jest.fn(),
  unassignDietAssignment: jest.fn(),
}));

const sampleCustomer = { id: 500, name: "Ravi Kumar" } as Customer;

const workoutAssignment = (overrides: Partial<WorkoutAssignment> = {}): WorkoutAssignment => ({
  id: 11,
  customer: 500,
  workout_plan: 1,
  workout_plan_name: "Strength Plan",
  customer_name: "Ravi Kumar",
  start_date: "2026-10-01",
  end_date: null,
  is_active: true,
  assigned_by: 1,
  notes: null,
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  ...overrides,
});

const dietAssignment = (overrides: Partial<DietAssignment> = {}): DietAssignment => ({
  id: 22,
  customer: 500,
  diet_plan: 2,
  diet_plan_name: "Bulk Plan",
  customer_name: "Ravi Kumar",
  start_date: "2026-10-05",
  end_date: "2026-11-05",
  is_active: true,
  assigned_by: 1,
  notes: null,
  created_at: "2026-10-05T00:00:00Z",
  updated_at: "2026-10-05T00:00:00Z",
  ...overrides,
});

const workoutPlan = (overrides: Partial<WorkoutPlan> = {}): WorkoutPlan =>
  ({
    id: 1,
    name: "Strength Plan",
    description: "",
    goal: "strength",
    difficulty: "intermediate",
    duration_weeks: 4,
    is_template: false,
    created_by: null,
    created_by_name: "",
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    days: [],
    ...overrides,
  }) as WorkoutPlan;

const dietPlan = (overrides: Partial<DietPlan> = {}): DietPlan =>
  ({
    id: 2,
    name: "Bulk Plan",
    description: "",
    goal: "bulk",
    daily_calories: 2500,
    protein_ratio: 30,
    carb_ratio: 40,
    fat_ratio: 30,
    duration_days: 7,
    is_template: false,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-01T00:00:00Z",
    days: [],
    ...overrides,
  }) as DietPlan;

beforeEach(() => {
  jest.clearAllMocks();
  (fetchActiveWorkoutAssignments as jest.Mock).mockResolvedValue([]);
  (fetchActiveDietAssignments as jest.Mock).mockResolvedValue([]);
  (fetchWorkoutPlans as jest.Mock).mockResolvedValue({ results: [workoutPlan()] });
  (fetchDietPlans as jest.Mock).mockResolvedValue({ results: [dietPlan()] });
});

describe("PlanAssignmentsSection (issue #90)", () => {
  it("shows empty states and assign actions when no plans are assigned", async () => {
    render(<PlanAssignmentsSection customer={sampleCustomer} />);

    expect(await screen.findByText("No workout plan assigned")).toBeInTheDocument();
    expect(screen.getByText("No meal plan assigned")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Assign" })).toHaveLength(2);
  });

  it("shows the active workout and meal plan with date ranges", async () => {
    (fetchActiveWorkoutAssignments as jest.Mock).mockResolvedValue([workoutAssignment()]);
    (fetchActiveDietAssignments as jest.Mock).mockResolvedValue([dietAssignment()]);
    render(<PlanAssignmentsSection customer={sampleCustomer} />);

    const workoutRow = await screen.findByTestId("workout-plan-row");
    expect(workoutRow).toHaveTextContent("Strength Plan");
    expect(workoutRow).toHaveTextContent("From 2026-10-01 · ongoing");
    const dietRow = screen.getByTestId("diet-plan-row");
    expect(dietRow).toHaveTextContent("Bulk Plan");
    expect(dietRow).toHaveTextContent("From 2026-10-05 until 2026-11-05");
    expect(screen.getByRole("button", { name: "Unassign Strength Plan" })).toBeInTheDocument();
  });

  it("assigns a workout plan without replace when none is active", async () => {
    (fetchActiveWorkoutAssignments as jest.Mock)
      .mockResolvedValueOnce([]) // initial load: nothing assigned
      .mockResolvedValue([workoutAssignment()]); // post-assign reload
    (assignWorkoutPlan as jest.Mock).mockResolvedValue(workoutAssignment());
    render(<PlanAssignmentsSection customer={sampleCustomer} />);
    await screen.findByText("No workout plan assigned");

    fireEvent.click(screen.getAllByRole("button", { name: "Assign" })[0]);
    await waitFor(() => expect(screen.getByTestId("plan-select")).toBeInTheDocument());

    fireEvent.change(screen.getByTestId("plan-select"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm plan assignment" }));

    await waitFor(() =>
      expect(assignWorkoutPlan).toHaveBeenCalledWith(
        expect.objectContaining({
          customer: 500,
          workout_plan: 1,
          replace_active: false,
        }),
        "owner-token",
      ),
    );
    // Row refreshes to the server assignment.
    await waitFor(() =>
      expect(screen.getByTestId("workout-plan-row")).toHaveTextContent("Strength Plan"),
    );
  });

  it("replaces the current plan (replace checkbox pre-checked) on Change", async () => {
    (fetchActiveWorkoutAssignments as jest.Mock).mockResolvedValue([workoutAssignment()]);
    (fetchWorkoutPlans as jest.Mock).mockResolvedValue({
      results: [workoutPlan(), workoutPlan({ id: 3, name: "Cardio Plan" })],
    });
    (assignWorkoutPlan as jest.Mock).mockResolvedValue(
      workoutAssignment({ workout_plan: 3, workout_plan_name: "Cardio Plan" }),
    );
    render(<PlanAssignmentsSection customer={sampleCustomer} />);
    await screen.findByTestId("workout-plan-row");

    fireEvent.click(screen.getByRole("button", { name: "Change" }));
    const replaceToggle = await screen.findByLabelText("Replace current assignment");
    expect(replaceToggle).toBeChecked();

    fireEvent.change(screen.getByTestId("plan-select"), { target: { value: "3" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm plan assignment" }));

    await waitFor(() =>
      expect(assignWorkoutPlan).toHaveBeenCalledWith(
        expect.objectContaining({ workout_plan: 3, replace_active: true }),
        "owner-token",
      ),
    );
    expect(toast.success).toHaveBeenCalled();
  });

  it("unassigns after confirmation and refreshes the rows", async () => {
    (fetchActiveDietAssignments as jest.Mock)
      .mockResolvedValueOnce([dietAssignment()]) // initial load: assigned
      .mockResolvedValue([]); // post-unassign reload
    (unassignDietAssignment as jest.Mock).mockResolvedValue(dietAssignment({ is_active: false }));
    render(<PlanAssignmentsSection customer={sampleCustomer} />);
    await screen.findByTestId("diet-plan-row");

    fireEvent.click(screen.getByRole("button", { name: "Unassign Bulk Plan" }));
    expect(screen.getByText(/will no longer be active for Ravi Kumar/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Unassign" }));
    await waitFor(() =>
      expect(unassignDietAssignment).toHaveBeenCalledWith(22, "owner-token"),
    );
    expect(await screen.findByText("No meal plan assigned")).toBeInTheDocument();
    expect(toast.success).toHaveBeenCalled();
  });

  it("shows an error toast and keeps the row when unassign fails", async () => {
    (fetchActiveWorkoutAssignments as jest.Mock).mockResolvedValue([workoutAssignment()]);
    (unassignWorkoutAssignment as jest.Mock).mockRejectedValue(
      new Error("Request failed with status 403"),
    );
    render(<PlanAssignmentsSection customer={sampleCustomer} />);
    await screen.findByTestId("workout-plan-row");

    fireEvent.click(screen.getByRole("button", { name: "Unassign Strength Plan" }));
    fireEvent.click(screen.getByRole("button", { name: "Unassign" }));

    await waitFor(() => expect(toast.error).toHaveBeenCalled());
    expect(screen.getByTestId("workout-plan-row")).toHaveTextContent("Strength Plan");
  });
});

describe("AssignPlanModal (issue #90)", () => {
  it("lists the catalogue plans and submits the picked plan", async () => {
    const onSubmit = jest.fn().mockResolvedValue(undefined);
    render(
      <AssignPlanModal kind="workout" hasActiveAssignment={false} onSubmit={onSubmit} onClose={() => {}} />,
    );

    await screen.findByTestId("plan-select");
    fireEvent.change(screen.getByTestId("plan-select"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Start date"), { target: { value: "2026-11-01" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm plan assignment" }));

    await waitFor(() =>
      expect(onSubmit).toHaveBeenCalledWith(
        expect.objectContaining({ planId: 1, startDate: "2026-11-01", replaceActive: false }),
      ),
    );
  });

  it("hides the replace toggle when no assignment is active", async () => {
    render(
      <AssignPlanModal kind="diet" hasActiveAssignment={false} onSubmit={jest.fn()} onClose={() => {}} />,
    );
    await screen.findByTestId("plan-select");
    expect(screen.queryByLabelText("Replace current assignment")).not.toBeInTheDocument();
  });

  it("shows the empty-catalogue hint when no plans exist", async () => {
    (fetchDietPlans as jest.Mock).mockResolvedValue({ results: [] });
    render(
      <AssignPlanModal kind="diet" hasActiveAssignment={false} onSubmit={jest.fn()} onClose={() => {}} />,
    );
    expect(await screen.findByText(/No meal plans yet/)).toBeInTheDocument();
  });

  it("shows the error state when plans fail to load", async () => {
    (fetchWorkoutPlans as jest.Mock).mockRejectedValue(new Error("Request failed with status 500"));
    render(
      <AssignPlanModal kind="workout" hasActiveAssignment={false} onSubmit={jest.fn()} onClose={() => {}} />,
    );
    expect(await screen.findByText("Request failed with status 500")).toBeInTheDocument();
  });
});
