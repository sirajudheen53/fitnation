import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  GOAL_LABELS,
  DIFFICULTY_LABELS,
  DAY_OF_WEEK_LABELS,
  dayLabel,
  formatDate,
  goalBadgeVariant,
  difficultyBadgeVariant,
} from "@/features/workouts/components/helpers";
import { WorkoutPlanCard } from "@/features/workouts/components/WorkoutPlanCard";
import { AssignmentTable } from "@/features/workouts/components/AssignmentTable";
import { LogTable } from "@/features/workouts/components/LogTable";
import { WorkoutPlanForm } from "@/features/workouts/components/WorkoutPlanForm";
import { AssignmentForm } from "@/features/workouts/components/AssignmentForm";
import { LogForm } from "@/features/workouts/components/LogForm";
import type { Exercise } from "@/types/exercise";
import type {
  WorkoutAssignment,
  WorkoutLog,
  WorkoutPlan,
} from "@/types/workout";

/* ── Helper functions ─────────────────────────────────────────── */

describe("workout helpers", () => {
  it("exposes goal, difficulty and day-of-week labels", () => {
    expect(GOAL_LABELS.strength).toBe("Strength");
    expect(GOAL_LABELS.hypertrophy).toBe("Hypertrophy");
    expect(DIFFICULTY_LABELS.beginner).toBe("Beginner");
    expect(DAY_OF_WEEK_LABELS.monday).toBe("Monday");
  });

  it("derives a human-readable day label", () => {
    expect(dayLabel({ focus: "Push Day" })).toBe("Push Day");
    expect(dayLabel({ day_of_week: "monday" })).toBe("Monday");
    expect(dayLabel({ day_number: 3 })).toBe("Day 3");
    expect(dayLabel({})).toBe("Day");
  });

  it("formats dates and handles null", () => {
    expect(formatDate("2026-01-10")).not.toBe("—");
    expect(formatDate(null)).toBe("—");
    expect(formatDate(undefined)).toBe("—");
  });

  it("maps goals and difficulties to badge variants", () => {
    expect(goalBadgeVariant("strength")).toBe("danger");
    expect(goalBadgeVariant("general_fitness")).toBe("default");
    expect(difficultyBadgeVariant("beginner")).toBe("success");
    expect(difficultyBadgeVariant("advanced")).toBe("danger");
  });
});

/* ── WorkoutPlanCard rendering ────────────────────────────────── */

const plan: WorkoutPlan = {
  id: 1,
  name: "Push / Pull / Legs",
  description: "A 3-day split",
  goal: "hypertrophy",
  difficulty: "intermediate",
  duration_weeks: 8,
  is_template: false,
  created_by: 1,
  created_by_name: "Trainer",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  days: [
    {
      id: 1,
      workout_plan: 1,
      day_of_week: "monday",
      day_number: 1,
      focus: "Push Day",
      notes: null,
      exercises: [],
    },
  ],
};

describe("WorkoutPlanCard", () => {
  it("renders plan name, goal, difficulty and duration", () => {
    render(<WorkoutPlanCard plan={plan} />);
    expect(screen.getByText("Push / Pull / Legs")).toBeInTheDocument();
    expect(screen.getByText("Hypertrophy")).toBeInTheDocument();
    expect(screen.getByText("Intermediate")).toBeInTheDocument();
    expect(screen.getByText("8 weeks")).toBeInTheDocument();
    expect(screen.getByText("1 days")).toBeInTheDocument();
  });

  it("shows a template badge for template plans", () => {
    render(<WorkoutPlanCard plan={{ ...plan, is_template: true }} />);
    expect(screen.getByText("Template")).toBeInTheDocument();
  });

  it("links to the plan detail page", () => {
    render(<WorkoutPlanCard plan={plan} />);
    const view = screen.getByText("View").closest("a");
    expect(view).toHaveAttribute("href", "/workouts/plans/1");
  });

  it("shows edit link when canEdit is true", () => {
    render(<WorkoutPlanCard plan={plan} canEdit />);
    const edit = screen.getByLabelText("Edit plan").closest("a");
    expect(edit).toHaveAttribute("href", "/workouts/plans/1/edit");
  });

  it("triggers duplicate callback", () => {
    const onDuplicate = jest.fn();
    render(<WorkoutPlanCard plan={plan} onDuplicate={onDuplicate} />);
    fireEvent.click(screen.getByLabelText("Duplicate plan"));
    expect(onDuplicate).toHaveBeenCalledWith(plan);
  });
});

/* ── AssignmentTable rendering ───────────────────────────────── */

const assignments: WorkoutAssignment[] = [
  {
    id: 1,
    customer: 1,
    workout_plan: 1,
    workout_plan_name: "Push / Pull / Legs",
    customer_name: "Arjun Kumar",
    start_date: "2026-01-10",
    end_date: "2026-02-10",
    is_active: true,
    assigned_by: 1,
    notes: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("AssignmentTable", () => {
  it("renders assignments with customer, plan and status", () => {
    render(<AssignmentTable assignments={assignments} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.getByText("Push / Pull / Legs")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<AssignmentTable assignments={[]} />);
    expect(screen.getByText("No workout assignments yet.")).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    render(<AssignmentTable assignments={[]} loading />);
    expect(screen.getByText("Loading assignments…")).toBeInTheDocument();
  });
});

/* ── LogTable rendering ──────────────────────────────────────── */

const logs: WorkoutLog[] = [
  {
    id: 1,
    customer: 1,
    workout_exercise: 1,
    workout_day: 1,
    exercise_name: "Bench Press",
    customer_name: "Arjun Kumar",
    date_completed: "2026-01-10",
    set_number: 1,
    actual_reps: 10,
    actual_weight: 60,
    actual_rest_seconds: 90,
    notes: null,
    created_at: "2026-01-10T00:00:00Z",
  },
];

describe("LogTable", () => {
  it("renders logs with exercise, reps, weight and rest", () => {
    render(<LogTable logs={logs} />);
    expect(screen.getByText("Bench Press")).toBeInTheDocument();
    expect(screen.getByText("Set 1")).toBeInTheDocument();
    expect(screen.getByText("10 reps")).toBeInTheDocument();
    expect(screen.getByText("60 kg")).toBeInTheDocument();
    expect(screen.getByText("90s")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<LogTable logs={[]} />);
    expect(screen.getByText("No workout logs yet.")).toBeInTheDocument();
  });
});

/* ── WorkoutPlanForm builder ──────────────────────────────────── */

const exercises: Exercise[] = [
  {
    id: 1,
    name: "Bench Press",
    description: "Chest press",
    category: 1,
    category_name: "Chest",
    muscle_groups: ["chest", "triceps"],
    equipment_needed: ["barbell"],
    difficulty: "intermediate",
    instructions: [],
    media_url: null,
    tips: "",
    contraindications: "",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Squat",
    description: "Leg press",
    category: 2,
    category_name: "Legs",
    muscle_groups: ["quadriceps", "glutes"],
    equipment_needed: ["barbell"],
    difficulty: "intermediate",
    instructions: [],
    media_url: null,
    tips: "",
    contraindications: "",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("WorkoutPlanForm", () => {
  it("renders plan details fields", () => {
    render(
      <WorkoutPlanForm exercises={exercises} onSubmit={jest.fn()} submitLabel="Create plan" />,
    );
    expect(screen.getByLabelText("Plan name")).toBeInTheDocument();
    expect(screen.getByLabelText("Goal")).toBeInTheDocument();
    expect(screen.getByLabelText("Difficulty")).toBeInTheDocument();
    expect(screen.getByLabelText("Duration (weeks)")).toBeInTheDocument();
    expect(screen.getByText("Days & exercises")).toBeInTheDocument();
  });

  it("adds a day and an exercise, then submits nested payload", async () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <WorkoutPlanForm exercises={exercises} onSubmit={onSubmit} submitLabel="Create plan" />,
    );

    // Add a day
    fireEvent.click(screen.getByText("Add day"));
    expect(screen.getAllByText("Day 1").length).toBeGreaterThan(0);

    // Select an exercise and add it
    fireEvent.change(screen.getByLabelText("Exercise"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Sets"), {
      target: { value: "4" },
    });
    fireEvent.change(screen.getByLabelText("Reps"), {
      target: { value: "10" },
    });
    fireEvent.click(screen.getByRole("button", { name: /add exercise/i }));

    // The exercise should appear in the day's table
    expect(screen.getAllByText("Bench Press").length).toBeGreaterThan(0);

    // Submit the form
    const form = container.querySelector("form");
    fireEvent.submit(form!);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.name).toBe("");
    expect(payload.days).toHaveLength(1);
    expect(payload.days[0].exercises).toHaveLength(1);
    expect(payload.days[0].exercises[0]).toMatchObject({
      exercise: 1,
      sets: 4,
      reps: "10",
    });
  });

  it("disables submit until at least one day is added", () => {
    render(
      <WorkoutPlanForm exercises={exercises} onSubmit={jest.fn()} submitLabel="Create plan" />,
    );
    const submit = screen.getByText("Create plan").closest("button");
    expect(submit).toBeDisabled();
  });

  it("reorders exercises within a day", () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <WorkoutPlanForm exercises={exercises} onSubmit={onSubmit} submitLabel="Create plan" />,
    );

    fireEvent.click(screen.getByText("Add day"));
    fireEvent.change(screen.getByLabelText("Exercise"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: /add exercise/i }));
    fireEvent.change(screen.getByLabelText("Exercise"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: /add exercise/i }));

    // Move the second exercise up
    const downButtons = screen.getAllByLabelText("Move exercise down");
    fireEvent.click(downButtons[0]);

    const form = container.querySelector("form");
    fireEvent.submit(form!);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.days[0].exercises[0].exercise).toBe(2);
    expect(payload.days[0].exercises[1].exercise).toBe(1);
  });

  it("pre-populates fields from an existing plan", () => {
    const existingPlan: WorkoutPlan = {
      ...plan,
      days: [
        {
          id: 1,
          workout_plan: 1,
          day_of_week: "monday",
          day_number: 1,
          focus: "Push Day",
          notes: null,
          exercises: [
            {
              id: 1,
              workout_day: 1,
              exercise: 1,
              exercise_name: "Bench Press",
              exercise_details: null,
              sets: 4,
              reps: "10",
              rest_seconds: 90,
              tempo: "3-1-2",
              rpe: 8,
              notes: null,
              order: 0,
              alternate_exercise: null,
              alternate_exercise_name: null,
            },
          ],
        },
      ],
    };
    render(
      <WorkoutPlanForm
        plan={existingPlan}
        exercises={exercises}
        onSubmit={jest.fn()}
        submitLabel="Save changes"
      />,
    );
    expect(screen.getByLabelText("Plan name")).toHaveValue("Push / Pull / Legs");
    expect(screen.getAllByText("Push Day").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Bench Press").length).toBeGreaterThan(0);
  });
});

/* ── AssignmentForm ──────────────────────────────────────────── */

const customers = [
  {
    id: 1,
    email: "arjun@example.com",
    first_name: "Arjun",
    last_name: "Kumar",
    phone: null,
    gender: null,
    date_of_birth: null,
    branch_id: null,
    emergency_contact_name: null,
    emergency_contact_phone: null,
    is_active: true,
    height_cm: null,
    weight_kg: null,
    bmi: null,
    fitness_goal: null,
    injuries: null,
    medical_info: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

describe("AssignmentForm", () => {
  it("submits customer, plan and start date", async () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <AssignmentForm customers={customers} plans={[plan]} onSubmit={onSubmit} />,
    );
    fireEvent.change(screen.getByLabelText("Customer"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Workout plan"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Start date"), {
      target: { value: "2026-01-10" },
    });
    const form = container.querySelector("form");
    fireEvent.submit(form!);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      customer: 1,
      workout_plan: 1,
      start_date: "2026-01-10",
    });
  });

  it("shows an error when required fields are missing", () => {
    const { container } = render(
      <AssignmentForm customers={customers} plans={[plan]} onSubmit={jest.fn()} />,
    );
    const form = container.querySelector("form");
    fireEvent.submit(form!);
    expect(screen.getByText("Customer, plan and start date are required.")).toBeInTheDocument();
  });
});

/* ── LogForm ────────────────────────────────────────────────── */

const workoutExercises = [
  {
    id: 1,
    workout_day: 1,
    exercise: 1,
    exercise_name: "Bench Press",
    exercise_details: null,
    sets: 4,
    reps: "10",
    rest_seconds: 90,
    tempo: null,
    rpe: null,
    notes: null,
    order: 0,
    alternate_exercise: null,
    alternate_exercise_name: null,
  },
];

describe("LogForm", () => {
  it("submits a logged set", async () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <LogForm exercises={workoutExercises} onSubmit={onSubmit} />,
    );
    fireEvent.change(screen.getByLabelText("Exercise"), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText("Set number"), { target: { value: "2" } });
    fireEvent.change(screen.getByLabelText("Actual reps"), { target: { value: "10" } });
    fireEvent.change(screen.getByLabelText("Actual weight (kg)"), {
      target: { value: "60" },
    });
    const form = container.querySelector("form");
    fireEvent.submit(form!);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
    expect(onSubmit.mock.calls[0][0]).toMatchObject({
      workout_exercise: 1,
      set_number: 2,
      actual_reps: 10,
      actual_weight: 60,
    });
  });

  it("shows an error when exercise is missing", () => {
    const { container } = render(
      <LogForm exercises={workoutExercises} onSubmit={jest.fn()} />,
    );
    const form = container.querySelector("form");
    fireEvent.submit(form!);
    expect(screen.getByText("Exercise and date are required.")).toBeInTheDocument();
  });
});
