import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import {
  mealNutrition,
  sumNutrition,
  formatNumber,
  round1,
  GOAL_LABELS,
  MEAL_TYPE_LABELS,
} from "@/features/diet/components/nutritionHelpers";
import { NutritionBars } from "@/features/diet/components/NutritionBars";
import { FoodItemTable } from "@/features/diet/components/FoodItemTable";
import { AssignmentTable, formatAssignmentDate } from "@/features/diet/components/AssignmentTable";
import { DietPlanForm } from "@/features/diet/components/DietPlanForm";
import type { FoodItem, DietPlan, DietAssignment } from "@/types/diet";

/* ── Helper functions ─────────────────────────────────────────── */

describe("nutritionHelpers", () => {
  it("computes meal nutrition from food item and quantity", () => {
    const food = { calories: 200, protein: 10, carbs: 30, fat: 5 };
    expect(mealNutrition(food, 2)).toEqual({
      calories: 400,
      protein: 20,
      carbs: 60,
      fat: 10,
    });
  });

  it("rounds nutrition to one decimal place", () => {
    const food = { calories: 100, protein: 3.33, carbs: 10, fat: 2.5 };
    expect(mealNutrition(food, 1.5)).toEqual({
      calories: 150,
      protein: 5,
      carbs: 15,
      fat: 3.8,
    });
  });

  it("sums nutrition across meals", () => {
    const meals = [
      { calories: 100, protein: 5, carbs: 10, fat: 2 },
      { calories: 200, protein: 10, carbs: 20, fat: 4 },
    ];
    expect(sumNutrition(meals)).toEqual({
      calories: 300,
      protein: 15,
      carbs: 30,
      fat: 6,
    });
  });

  it("handles missing nutrition fields when summing", () => {
    const meals = [{ calories: 100 }, { protein: 5 }];
    expect(sumNutrition(meals)).toEqual({
      calories: 100,
      protein: 5,
      carbs: 0,
      fat: 0,
    });
  });

  it("formats integers without decimals", () => {
    expect(formatNumber(200)).toBe("200");
  });

  it("formats decimals to one place", () => {
    expect(formatNumber(3.75)).toBe("3.8");
  });

  it("rounds to one decimal place", () => {
    expect(round1(3.75)).toBe(3.8);
  });

  it("exposes goal and meal type labels", () => {
    expect(GOAL_LABELS.bulk).toBe("Bulk");
    expect(GOAL_LABELS.cut).toBe("Cut");
    expect(GOAL_LABELS.maintain).toBe("Maintain");
    expect(MEAL_TYPE_LABELS.breakfast).toBe("Breakfast");
    expect(MEAL_TYPE_LABELS.dinner).toBe("Dinner");
  });
});

/* ── NutritionBars rendering ──────────────────────────────────── */

describe("NutritionBars", () => {
  it("renders total calories and macro bars", () => {
    render(
      <NutritionBars calories={2000} protein={120} carbs={250} fat={60} />,
    );
    expect(screen.getByText("2000 kcal")).toBeInTheDocument();
    expect(screen.getByText("Protein")).toBeInTheDocument();
    expect(screen.getByText("Carbs")).toBeInTheDocument();
    expect(screen.getByText("Fat")).toBeInTheDocument();
    expect(screen.getByText("120 g")).toBeInTheDocument();
    expect(screen.getByText("250 g")).toBeInTheDocument();
    expect(screen.getByText("60 g")).toBeInTheDocument();
  });

  it("scales bars against a target calorie value", () => {
    render(
      <NutritionBars
        calories={1000}
        protein={50}
        carbs={100}
        fat={20}
        targetCalories={2000}
      />,
    );
    const bars = screen.getAllByRole("progressbar");
    expect(bars).toHaveLength(3);
    expect(bars[0]).toHaveAttribute("aria-valuenow", "3");
  });
});

/* ── FoodItemTable rendering & interaction ───────────────────── */

const foodItems: FoodItem[] = [
  {
    id: 1,
    name: "Chicken Breast",
    serving_size: "100g",
    calories: 165,
    protein: 31,
    carbs: 0,
    fat: 3.6,
    fiber: 0,
    glycemic_index: null,
    food_group: "protein",
    is_veg: false,
    created_at: "2026-01-01T00:00:00Z",
  },
  {
    id: 2,
    name: "Brown Rice",
    serving_size: "100g",
    calories: 111,
    protein: 2.6,
    carbs: 23,
    fat: 0.9,
    fiber: 1.8,
    glycemic_index: 50,
    food_group: "grains",
    is_veg: true,
    created_at: "2026-01-01T00:00:00Z",
  },
];

describe("FoodItemTable", () => {
  it("renders food items with veg / non-veg badges", () => {
    render(<FoodItemTable foodItems={foodItems} />);
    expect(screen.getByText("Chicken Breast")).toBeInTheDocument();
    expect(screen.getByText("Brown Rice")).toBeInTheDocument();
    // Badge text also appears in the filter dropdown, so assert at least one badge each
    expect(screen.getAllByText("Non-veg").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Veg").length).toBeGreaterThanOrEqual(1);
  });

  it("shows an empty state when there are no items", () => {
    render(<FoodItemTable foodItems={[]} />);
    expect(screen.getByText("No food items found.")).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    render(<FoodItemTable foodItems={[]} loading />);
    expect(screen.getByText("Loading food items…")).toBeInTheDocument();
  });

  it("opens a detail modal when a row is clicked", () => {
    render(<FoodItemTable foodItems={foodItems} />);
    fireEvent.click(screen.getByText("Chicken Breast"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("165 kcal")).toBeInTheDocument();
    expect(screen.getByText("31 g")).toBeInTheDocument();
  });

  it("triggers search callback on typing", () => {
    const onSearch = jest.fn();
    render(<FoodItemTable foodItems={foodItems} onSearch={onSearch} />);
    fireEvent.change(screen.getByLabelText("Search food items"), {
      target: { value: "chicken" },
    });
    expect(onSearch).toHaveBeenCalledWith("chicken");
  });
});

/* ── AssignmentTable rendering ───────────────────────────────── */

const assignments: DietAssignment[] = [
  {
    id: 1,
    customer: 1,
    diet_plan: 1,
    diet_plan_name: "Lean Bulk",
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
    expect(screen.getByText("Lean Bulk")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows an empty state", () => {
    render(<AssignmentTable assignments={[]} />);
    expect(screen.getByText("No diet assignments yet.")).toBeInTheDocument();
  });

  it("formats assignment dates", () => {
    expect(formatAssignmentDate("2026-01-10")).not.toBe("—");
    expect(formatAssignmentDate(null)).toBe("—");
  });
});

/* ── DietPlanForm builder ────────────────────────────────────── */

const planFoodItems: FoodItem[] = [
  {
    id: 1,
    name: "Chicken Breast",
    serving_size: "100g",
    calories: 165,
    protein: 31,
    carbs: 0,
    fat: 3.6,
    fiber: 0,
    glycemic_index: null,
    food_group: "protein",
    is_veg: false,
    created_at: "2026-01-01T00:00:00Z",
  },
];

describe("DietPlanForm", () => {
  it("renders plan details fields", () => {
    render(
      <DietPlanForm foodItems={planFoodItems} onSubmit={jest.fn()} submitLabel="Create plan" />,
    );
    expect(screen.getByLabelText("Plan name")).toBeInTheDocument();
    expect(screen.getByLabelText("Goal")).toBeInTheDocument();
    expect(screen.getByLabelText("Daily calories")).toBeInTheDocument();
    expect(screen.getByText("Days & meals")).toBeInTheDocument();
  });

  it("adds a day and a meal, then submits nested payload", async () => {
    const onSubmit = jest.fn();
    const { container } = render(
      <DietPlanForm foodItems={planFoodItems} onSubmit={onSubmit} submitLabel="Create plan" />,
    );

    // Add a day
    fireEvent.click(screen.getByText("Add day"));
    expect(screen.getAllByText("Day 1").length).toBeGreaterThan(0);

    // Select food item and add meal
    fireEvent.change(screen.getByLabelText("Food item"), {
      target: { value: "1" },
    });
    fireEvent.change(screen.getByLabelText("Quantity"), {
      target: { value: "2" },
    });
    // Wait for the food item selection to propagate to state
    await waitFor(() =>
      expect(screen.getByText(/165 kcal × 2 = 330 kcal/)).toBeInTheDocument(),
    );
    fireEvent.click(screen.getByText("Add meal"));

    // Nutrition summary should reflect 165 * 2 = 330 kcal
    expect(screen.getAllByText("330 kcal").length).toBeGreaterThan(0);

    // Submit the form (jsdom does not fire submit on button click in React 19)
    const form = container.querySelector("form");
    fireEvent.submit(form!);
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));

    const payload = onSubmit.mock.calls[0][0];
    expect(payload.name).toBe("");
    expect(payload.days).toHaveLength(1);
    expect(payload.days[0].meals).toHaveLength(1);
    expect(payload.days[0].meals[0]).toEqual({
      meal_type: "breakfast",
      food_item: 1,
      quantity: 2,
    });
  });

  it("disables submit until at least one day is added", () => {
    render(
      <DietPlanForm foodItems={planFoodItems} onSubmit={jest.fn()} submitLabel="Create plan" />,
    );
    const submit = screen.getByText("Create plan").closest("button");
    expect(submit).toBeDisabled();
  });

  it("pre-populates fields from an existing plan", () => {
    const plan: DietPlan = {
      id: 1,
      name: "Lean Bulk",
      description: "For bulking",
      goal: "bulk",
      daily_calories: 3000,
      protein_ratio: 30,
      carb_ratio: 40,
      fat_ratio: 30,
      duration_days: 7,
      is_template: false,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      days: [
        {
          id: 1,
          diet_plan: 1,
          day_number: 1,
          total_calories: 330,
          notes: null,
          meals: [
            {
              id: 1,
              diet_day: 1,
              meal_type: "breakfast",
              food_item: 1,
              food_item_name: "Chicken Breast",
              quantity: 2,
              calories: 330,
              protein: 62,
              carbs: 0,
              fat: 7.2,
            },
          ],
        },
      ],
    };
    render(
      <DietPlanForm plan={plan} foodItems={planFoodItems} onSubmit={jest.fn()} submitLabel="Save changes" />,
    );
    expect(screen.getByLabelText("Plan name")).toHaveValue("Lean Bulk");
    expect(screen.getAllByText("Day 1").length).toBeGreaterThan(0);
    expect(screen.getByText("Chicken Breast")).toBeInTheDocument();
  });
});
