import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// ResponsiveContainer measures its parent in jsdom (width/height = 0) and throws;
// stub it to render children directly so chart components are testable.
jest.mock("recharts", () => {
  const React = require("react");
  const passthrough = (props: any) =>
    React.createElement("div", { "data-testid": props?.dataKey || "chart" }, props?.children);
  return {
    ResponsiveContainer: ({ children }: any) =>
      React.createElement("div", null, children),
    LineChart: passthrough,
    BarChart: passthrough,
    Line: passthrough,
    Bar: passthrough,
    XAxis: () => React.createElement("div"),
    YAxis: () => React.createElement("div"),
    Tooltip: () => React.createElement("div"),
    CartesianGrid: () => React.createElement("div"),
    Legend: () => React.createElement("div"),
  };
});

import { CustomerTabs } from "@/features/customers/components/CustomerTabs";
import {
  OverviewTab,
  formatMemberSince,
  toNumber,
} from "@/features/customers/components/OverviewTab";
import {
  FitnessGoalsTab,
  clampProgress,
  getGoalStatusMeta,
} from "@/features/customers/components/FitnessGoalsTab";
import {
  BodyMeasurementsTab,
  formatMeasurementDate,
  formatNum,
  measurementChartData,
  type MeasurementComparison,
} from "@/features/customers/components/BodyMeasurementsTab";
import {
  HealthProfileTab,
  TagList,
  TagInput,
} from "@/features/customers/components/HealthProfileTab";
import { ProgressPhotosTab } from "@/features/customers/components/ProgressPhotosTab";
import type { Customer } from "@/types/customer";
import type {
  BodyMeasurement,
  CustomerFitnessGoal,
  HealthProfile,
  ProgressPhoto,
} from "@/types/customer-detail";

/* ── Fixtures ─────────────────────────────────────────────────── */

const customer: Customer = {
  id: 1,
  email: "arjun@example.com",
  first_name: "Arjun",
  last_name: "Kumar",
  phone: "+91 98765 43210",
  gender: "male",
  date_of_birth: "1995-01-01",
  branch_id: 2,
  emergency_contact_name: "Ravi",
  emergency_contact_phone: "+91 90000 00000",
  is_active: true,
  height_cm: 172,
  weight_kg: 75,
  bmi: 25.4,
  fitness_goal: null,
  injuries: null,
  medical_info: null,
  created_at: "2025-06-15T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const goal: CustomerFitnessGoal = {
  id: 1,
  customer: 1,
  goal_type: "lose_weight",
  is_active: true,
  status: "active",
  target_value: 70,
  target_unit: "kg",
  target_date: "2026-06-01",
  current_value: 75,
  progress_percentage: 50,
  notes: "",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const achievedGoal: CustomerFitnessGoal = {
  id: 2,
  customer: 1,
  goal_type: "build_muscle",
  is_active: false,
  status: "achieved",
  target_value: 80,
  target_unit: "kg",
  target_date: null,
  current_value: 80,
  progress_percentage: 100,
  notes: "",
  created_at: "2025-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const measurement: BodyMeasurement = {
  id: 1,
  customer: 1,
  date_logged: "2026-01-15",
  weight_kg: 75,
  height_cm: 172,
  bmi: 25.4,
  body_fat_percentage: 18,
  chest_cm: 98,
  waist_cm: 82,
  hips_cm: 96,
  biceps_cm: 34,
  thighs_cm: 58,
  neck_cm: 38,
  arms_cm: null,
  legs_cm: null,
  notes: "",
  created_at: "2026-01-15T00:00:00Z",
  updated_at: "2026-01-15T00:00:00Z",
};

const photo: ProgressPhoto = {
  id: 1,
  customer: 1,
  image: "https://example.com/1.jpg",
  caption: "Front",
  taken_at: "2026-01-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

/* ── CustomerTabs ─────────────────────────────────────────────── */

describe("CustomerTabs", () => {
  it("renders all six tabs", () => {
    render(<CustomerTabs active="overview" onChange={jest.fn()} />);
    expect(screen.getByText("Overview")).toBeInTheDocument();
    expect(screen.getByText("Fitness Goals")).toBeInTheDocument();
    expect(screen.getByText("Body Measurements")).toBeInTheDocument();
    expect(screen.getByText("Health Profile")).toBeInTheDocument();
    expect(screen.getByText("Progress Photos")).toBeInTheDocument();
    expect(screen.getByText("Payment History")).toBeInTheDocument();
  });

  it("calls onChange when a tab is clicked", () => {
    const onChange = jest.fn();
    render(<CustomerTabs active="overview" onChange={onChange} />);
    fireEvent.click(screen.getByText("Health Profile"));
    expect(onChange).toHaveBeenCalledWith("health");
  });

  it("applies active style to the active tab", () => {
    render(<CustomerTabs active="goals" onChange={jest.fn()} />);
    const btn = screen.getByRole("button", { name: /Fitness Goals/i });
    expect(btn).toHaveAttribute("aria-current", "page");
  });
});

/* ── OverviewTab helpers ─────────────────────────────────────── */

describe("OverviewTab helpers", () => {
  it("formats member-since dates", () => {
    const formatted = formatMemberSince("2025-06-15T00:00:00Z");
    expect(formatted).toContain("2025");
  });

  it("returns em dash for missing dates", () => {
    expect(formatMemberSince(null)).toBe("—");
  });

  it("converts numeric strings to numbers, defaulting to 0", () => {
    expect(toNumber("25.4")).toBe(25.4);
    expect(toNumber(30)).toBe(30);
    expect(toNumber(null)).toBe(0);
    expect(toNumber("abc")).toBe(0);
  });

  it("renders customer summary with BMI and photos count", () => {
    render(
      <OverviewTab
        customer={customer}
        summary={{
          customer_id: 1,
          customer_name: "Arjun Kumar",
          health_profile: {
            height_cm: 172,
            weight_kg: 75,
            bmi: 25.4,
            blood_group: "unknown",
            injuries: "",
            current_injuries: [],
            past_injuries: [],
            medical_info: {},
            medical_conditions: [],
            allergies: [],
            food_allergies: [],
            medications: [],
            dietary_restrictions: [],
            created_at: "",
            updated_at: "",
          } as HealthProfile,
          latest_measurement: null,
          weight_trend: [],
          fitness_goals: [goal],
          progress_photo_count: 3,
        }}
      />,
    );
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("BMI")).toBeInTheDocument();
  });

  it("renders tab navigation links", () => {
    render(<OverviewTab customer={customer} summary={null} />);
    expect(screen.getByText("Fitness Goals")).toBeInTheDocument();
    expect(screen.getByText("Body Measurements")).toBeInTheDocument();
    expect(screen.getByText("Health Profile")).toBeInTheDocument();
  });

  it("shows inactive badge when customer is not active", () => {
    render(<OverviewTab {...{ customer: { ...customer, is_active: false } }} summary={null} />);
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });
});

/* ── FitnessGoalsTab helpers ─────────────────────────────────── */

describe("FitnessGoalsTab helpers", () => {
  it("clamps progress to 0-100", () => {
    expect(clampProgress(50)).toBe(50);
    expect(clampProgress(150)).toBe(100);
    expect(clampProgress(-5)).toBe(0);
    expect(clampProgress(null)).toBe(0);
    expect(clampProgress(undefined)).toBe(0);
  });

  it("maps goal statuses to badge metadata", () => {
    expect(getGoalStatusMeta("active")).toEqual({ label: "Active", variant: "success" });
    expect(getGoalStatusMeta("achieved")).toEqual({ label: "Achieved", variant: "default" });
    expect(getGoalStatusMeta("abandoned")).toEqual({ label: "Abandoned", variant: "danger" });
  });
});

describe("FitnessGoalsTab", () => {
  it("renders goals with progress bar and status", () => {
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} />);
    expect(screen.getByText("Lose Weight")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("50%")).toBeInTheDocument();
  });

  it("shows empty state when no goals", () => {
    render(<FitnessGoalsTab goals={[]} onAdd={jest.fn()} />);
    expect(screen.getByText("No fitness goals set yet.")).toBeInTheDocument();
  });

  it("opens the add-goal form", () => {
    render(<FitnessGoalsTab goals={[]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByText("Add goal"));
    expect(screen.getByText("Goal type")).toBeInTheDocument();
    expect(screen.getByText("Target value")).toBeInTheDocument();
  });

  it("calls onAdd when form is submitted", async () => {
    const onAdd = jest.fn();
    render(<FitnessGoalsTab goals={[]} onAdd={onAdd} />);
    fireEvent.click(screen.getByText("Add goal"));

    // Select goal type
    fireEvent.change(screen.getByLabelText("Goal type"), {
      target: { value: "lose_weight" },
    });
    // Fill target value
    const targetInputs = screen.getAllByPlaceholderText("e.g. 70");
    await userEvent.type(targetInputs[0], "70");

    // Submit
    fireEvent.click(screen.getByRole("button", { name: "Add goal" }));

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(
        expect.objectContaining({
          goal_type: "lose_weight",
          target_value: 70,
        }),
      );
    });
  });

  it("renders achieved goal with achieved badge", () => {
    render(<FitnessGoalsTab goals={[achievedGoal]} onAdd={jest.fn()} />);
    expect(screen.getByText("Achieved")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
  });

  it("shows Edit button when onUpdate is provided", () => {
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} onUpdate={jest.fn()} />);
    expect(screen.getByText("Edit")).toBeInTheDocument();
  });

  it("does not show Edit button when onUpdate is not provided", () => {
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} />);
    expect(screen.queryByText("Edit")).not.toBeInTheDocument();
  });

  it("opens inline edit form when Edit is clicked", () => {
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} onUpdate={jest.fn()} />);
    fireEvent.click(screen.getByText("Edit"));
    expect(screen.getByLabelText("Current")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save" })).toBeInTheDocument();
  });

  it("calls onUpdate with current_value when Save is clicked in edit mode", async () => {
    const onUpdate = jest.fn();
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} onUpdate={onUpdate} />);

    fireEvent.click(screen.getByText("Edit"));
    const currentInput = screen.getByLabelText("Current");
    await userEvent.clear(currentInput);
    await userEvent.type(currentInput, "73");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      expect(onUpdate).toHaveBeenCalledWith(
        goal.id,
        expect.objectContaining({ current_value: 73 }),
      );
    });
  });

  it("shows quick-achieve and quick-abandon buttons when onUpdate is provided", () => {
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} onUpdate={jest.fn()} />);
    // There are two icon buttons (CheckCircle2 and XCircle)
    const iconButtons = screen.getAllByRole("button");
    const iconBtnCount = iconButtons.length;
    expect(iconBtnCount).toBeGreaterThan(2); // Add goal + Edit + quick status buttons
  });

  it("closes edit form when Cancel is clicked", () => {
    render(<FitnessGoalsTab goals={[goal]} onAdd={jest.fn()} onUpdate={jest.fn()} />);
    fireEvent.click(screen.getByText("Edit"));
    expect(screen.getByLabelText("Current")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByLabelText("Current")).not.toBeInTheDocument();
  });

  it("calls onAdd with target_unit and target_date", async () => {
    const onAdd = jest.fn();
    render(<FitnessGoalsTab goals={[]} onAdd={onAdd} />);
    fireEvent.click(screen.getByText("Add goal"));

    fireEvent.change(screen.getByLabelText("Goal type"), {
      target: { value: "build_muscle" },
    });
    const targetInputs = screen.getAllByPlaceholderText("e.g. 70");
    await userEvent.type(targetInputs[0], "80");
    await userEvent.type(screen.getByPlaceholderText("kg"), "kg");

    // Set a date
    fireEvent.change(screen.getByLabelText("Target date"), {
      target: { value: "2026-12-31" },
    });

    fireEvent.click(screen.getByRole("button", { name: "Add goal" }));

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(
        expect.objectContaining({
          goal_type: "build_muscle",
          target_value: 80,
          target_unit: "kg",
          target_date: "2026-12-31",
        }),
      );
    });
  });
});

/* ── BodyMeasurementsTab helpers ──────────────────────────────── */

describe("BodyMeasurementsTab helpers", () => {
  it("formats measurement dates", () => {
    expect(formatMeasurementDate("2026-01-15")).toContain("Jan");
  });

  it("formats numbers or returns em dash", () => {
    expect(formatNum(75)).toBe("75");
    expect(formatNum(null)).toBe("—");
    expect(formatNum(undefined)).toBe("—");
  });

  it("builds chart data sorted by date", () => {
    const data = measurementChartData([
      { ...measurement, date_logged: "2026-02-01" },
      { ...measurement, id: 2, date_logged: "2026-01-01" },
    ]);
    expect(data).toHaveLength(2);
    expect(data[0].weight).toBe(75);
    expect(data[0].bmi).toBe(25.4);
  });

  it("sorts chart data chronologically", () => {
    const feb1 = { ...measurement, id: 2, date_logged: "2026-02-01", weight_kg: 74 };
    const jan1 = { ...measurement, id: 3, date_logged: "2026-01-01", weight_kg: 76 };
    const data = measurementChartData([feb1, jan1]);
    // Should be sorted oldest → newest
    expect(data[0].weight).toBe(76);
    expect(data[1].weight).toBe(74);
  });
});

describe("BodyMeasurementsTab", () => {
  it("renders a measurements table", () => {
    render(<BodyMeasurementsTab measurements={[measurement]} onAdd={jest.fn()} />);
    expect(screen.getByText("Weight over time (kg)")).toBeInTheDocument();
    expect(screen.getByText("75 kg")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<BodyMeasurementsTab measurements={[]} onAdd={jest.fn()} />);
    expect(screen.getByText("No body measurements recorded yet.")).toBeInTheDocument();
  });

  it("renders the comparison card when measurementComparison is provided", () => {
    const comparison: MeasurementComparison = {
      first: { ...measurement, id: 2, date_logged: "2026-01-01", weight_kg: 80 },
      latest: measurement,
      diff: { weight_kg: "-5", bmi: "-0.5" },
    };
    render(
      <BodyMeasurementsTab
        measurements={[measurement]}
        measurementComparison={comparison}
        onAdd={jest.fn()}
      />,
    );
    expect(screen.getByText(/Progress:/)).toBeInTheDocument();
    // "Weight" appears in both the comparison card and the table header
    expect(screen.getAllByText("Weight").length).toBeGreaterThan(0);
    expect(screen.getByText("-5")).toBeInTheDocument();
  });

  it("renders both charts when measurements exist", () => {
    render(<BodyMeasurementsTab measurements={[measurement]} onAdd={jest.fn()} />);
    expect(screen.getByText("Weight over time (kg)")).toBeInTheDocument();
    expect(screen.getByText("BMI over time")).toBeInTheDocument();
  });

  it("shows Add measurement form", () => {
    render(<BodyMeasurementsTab measurements={[]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByText("Add measurement"));
    expect(screen.getByLabelText("Weight (kg) *")).toBeInTheDocument();
  });

  it("calls onAdd when measurement form is submitted", async () => {
    const onAdd = jest.fn();
    render(<BodyMeasurementsTab measurements={[]} onAdd={onAdd} />);
    fireEvent.click(screen.getByText("Add measurement"));
    await userEvent.type(screen.getByLabelText("Weight (kg) *"), "72");
    fireEvent.click(screen.getByRole("button", { name: "Save measurement" }));

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith(
        expect.objectContaining({ weight_kg: 72 }),
      );
    });
  });

  it("sorts table by date descending (newest first)", () => {
    const older = { ...measurement, id: 2, date_logged: "2026-01-01", weight_kg: 80 };
    const newer = { ...measurement, id: 3, date_logged: "2026-02-01", weight_kg: 78 };
    render(<BodyMeasurementsTab measurements={[older, newer]} onAdd={jest.fn()} />);
    const rows = screen.getAllByRole("row");
    // row[0] is header, row[1] should be the newer date
    expect(rows[1]).toHaveTextContent("Feb");
  });
});

/* ── HealthProfileTab ─────────────────────────────────────────── */

describe("HealthProfileTab", () => {
  it("renders vitals and tag lists", () => {
    render(
      <HealthProfileTab
        profile={{
          height_cm: 172,
          weight_kg: 75,
          bmi: 25.4,
          blood_group: "O+",
          current_injuries: ["Knee"],
          past_injuries: [],
          allergies: ["Peanuts"],
          food_allergies: [],
          medications: [],
          dietary_restrictions: ["Vegan"],
          medical_conditions: ["Hypertension"],
        } as HealthProfile}
        onSave={jest.fn()}
      />,
    );
    expect(screen.getByText("172 cm")).toBeInTheDocument();
    expect(screen.getByText("O+")).toBeInTheDocument();
    expect(screen.getByText("Peanuts")).toBeInTheDocument();
    expect(screen.getByText("Vegan")).toBeInTheDocument();
    expect(screen.getByText("Knee")).toBeInTheDocument();
    expect(screen.getByText("Hypertension")).toBeInTheDocument();
  });

  it("shows add-health-profile state when no profile", () => {
    render(<HealthProfileTab profile={null} onSave={jest.fn()} />);
    expect(screen.getByText("No health profile on file yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Add health profile/i })).toBeInTheDocument();
  });

  it("shows edit form when Edit is clicked", () => {
    render(
      <HealthProfileTab
        profile={{
          height_cm: 172,
          weight_kg: 75,
          bmi: 25.4,
          blood_group: "O+",
          current_injuries: [],
          past_injuries: [],
          allergies: [],
          food_allergies: [],
          medications: [],
          dietary_restrictions: [],
          medical_conditions: [],
          injuries: "",
        } as HealthProfile}
        onSave={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Edit/i }));
    expect(screen.getByLabelText("Height (cm)")).toBeInTheDocument();
    expect(screen.getByLabelText("Weight (kg)")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save health profile" })).toBeInTheDocument();
  });

  it("shows medical tag-input fields in edit mode", () => {
    render(
      <HealthProfileTab
        profile={{
          height_cm: 172,
          weight_kg: 75,
          bmi: 25.4,
          blood_group: "O+",
          current_injuries: [],
          past_injuries: [],
          allergies: [],
          food_allergies: [],
          medications: [],
          dietary_restrictions: [],
          medical_conditions: [],
          injuries: "",
        } as HealthProfile}
        onSave={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Edit/i }));
    expect(screen.getByText("Medical conditions")).toBeInTheDocument();
    expect(screen.getByText("Allergies")).toBeInTheDocument();
    expect(screen.getByText("Medications")).toBeInTheDocument();
    expect(screen.getByText("Dietary restrictions")).toBeInTheDocument();
    expect(screen.getByText("Current injuries")).toBeInTheDocument();
    expect(screen.getByText("Past injuries")).toBeInTheDocument();
  });

  it("calls onSave when form is submitted", async () => {
    const onSave = jest.fn();
    render(
      <HealthProfileTab
        profile={null}
        onSave={onSave}
      />,
    );
    // Start from the "add health profile" state
    fireEvent.click(screen.getByRole("button", { name: /Add health profile/i }));

    // Fill required vitals before submitting
    await userEvent.type(screen.getByLabelText("Height (cm)"), "172");
    await userEvent.type(screen.getByLabelText("Weight (kg)"), "75");

    // Blood group should be pre-filled; just submit
    fireEvent.click(screen.getByRole("button", { name: "Save health profile" }));

    await waitFor(() => {
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ blood_group: "A+", height_cm: 172, weight_kg: 75 }),
      );
    });
  });

  it("renders emergency contact section", () => {
    render(
      <HealthProfileTab
        profile={{
          height_cm: 172,
          weight_kg: 75,
          bmi: 25.4,
          blood_group: "O+",
          current_injuries: [],
          past_injuries: [],
          allergies: [],
          food_allergies: [],
          medications: [],
          dietary_restrictions: [],
          medical_conditions: [],
          injuries: "",
          medical_info: {
            emergency_contact_name: "Ravi Kumar",
            emergency_contact_phone: "+91 90000 00000",
          },
        } as HealthProfile}
        onSave={jest.fn()}
      />,
    );
    expect(screen.getByText("Ravi Kumar")).toBeInTheDocument();
    expect(screen.getByText("+91 90000 00000")).toBeInTheDocument();
  });
});

/* ── TagInput helper ───────────────────────────────────────────── */

describe("TagInput", () => {
  it("renders existing tags", () => {
    render(<TagInput value={["Peanuts", "Dust"]} onChange={jest.fn()} />);
    expect(screen.getByText("Peanuts")).toBeInTheDocument();
    expect(screen.getByText("Dust")).toBeInTheDocument();
  });

  it("adds a tag on Enter", async () => {
    const onChange = jest.fn();
    render(<TagInput value={[]} onChange={onChange} />);
    const input = screen.getByPlaceholderText("Add…");
    await userEvent.type(input, "Lactose{enter}");
    expect(onChange).toHaveBeenCalledWith(["Lactose"]);
  });

  it("adds a tag on comma", async () => {
    const onChange = jest.fn();
    render(<TagInput value={[]} onChange={onChange} />);
    const input = screen.getByPlaceholderText("Add…");
    await userEvent.type(input, "Gluten,");
    expect(onChange).toHaveBeenCalledWith(["Gluten"]);
  });

  it("removes a tag when X is clicked", async () => {
    const onChange = jest.fn();
    render(<TagInput value={["Peanuts"]} onChange={onChange} />);
    const removeBtn = screen.getByRole("button", { name: "" });
    fireEvent.click(removeBtn);
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it("removes last tag on Backspace when input is empty", async () => {
    const onChange = jest.fn();
    render(<TagInput value={["Peanuts", "Dust"]} onChange={onChange} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "{Backspace}");
    expect(onChange).toHaveBeenCalledWith(["Peanuts"]);
  });

  it("does not add duplicate tags", async () => {
    const onChange = jest.fn();
    render(<TagInput value={["Peanuts"]} onChange={onChange} />);
    const input = screen.getByRole("textbox");
    await userEvent.type(input, "Peanuts{enter}");
    expect(onChange).not.toHaveBeenCalled();
  });
});

/* ── TagList ─────────────────────────────────────────────────── */

describe("TagList", () => {
  it("renders tags for non-empty lists", () => {
    render(<TagList items={["A", "B"]} />);
    expect(screen.getByText("A")).toBeInTheDocument();
    expect(screen.getByText("B")).toBeInTheDocument();
  });

  it("renders em dash for empty lists", () => {
    render(<TagList items={[]} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders em dash for undefined", () => {
    render(<TagList items={undefined} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});

/* ── ProgressPhotosTab ────────────────────────────────────────── */

describe("ProgressPhotosTab", () => {
  it("shows empty state", () => {
    render(<ProgressPhotosTab photos={[]} onAdd={jest.fn()} />);
    expect(screen.getByText("No progress photos uploaded yet.")).toBeInTheDocument();
  });

  it("renders a photo gallery", () => {
    render(<ProgressPhotosTab photos={[photo]} onAdd={jest.fn()} />);
    expect(screen.getByAltText("Front")).toBeInTheDocument();
  });

  it("opens the upload form", () => {
    render(<ProgressPhotosTab photos={[]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByText("Upload"));
    expect(screen.getByText("Image URL")).toBeInTheDocument();
  });

  it("calls onAdd when form is submitted", async () => {
    const onAdd = jest.fn();
    render(<ProgressPhotosTab photos={[]} onAdd={onAdd} />);
    fireEvent.click(screen.getByText("Upload"));
    await userEvent.type(
      screen.getByPlaceholderText("https://…/photo.jpg"),
      "https://example.com/new.jpg",
    );
    await userEvent.type(
      screen.getByPlaceholderText("Front view"),
      "Week 1 progress",
    );
    fireEvent.click(screen.getByRole("button", { name: "Upload photo" }));

    await waitFor(() => {
      expect(onAdd).toHaveBeenCalledWith({
        image: "https://example.com/new.jpg",
        caption: "Week 1 progress",
      });
    });
  });

  it("opens compare mode when there are at least 2 photos", () => {
    const oldPhoto: ProgressPhoto = {
      id: 2,
      customer: 1,
      image: "https://example.com/old.jpg",
      caption: "Before",
      taken_at: "2025-01-01T00:00:00Z",
      created_at: "2025-01-01T00:00:00Z",
      updated_at: "2025-01-01T00:00:00Z",
    };
    render(<ProgressPhotosTab photos={[photo, oldPhoto]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByText("Compare"));
    expect(screen.getByText("Select two photos to compare side by side.")).toBeInTheDocument();
  });

  it("shows image lightbox on click", () => {
    render(<ProgressPhotosTab photos={[photo]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByAltText("Front"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("closes lightbox on backdrop click", () => {
    render(<ProgressPhotosTab photos={[photo]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByAltText("Front"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("dialog"));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });
});
