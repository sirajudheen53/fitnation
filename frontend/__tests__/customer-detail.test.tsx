import { render, screen, fireEvent, waitFor } from "@testing-library/react";

// ResponsiveContainer measures its parent in jsdom (width/height = 0) and throws;
// stub it to render children directly so chart components are testable.
jest.mock("recharts", () => {
  const React = require("react");
  const passthrough = (props: any) =>
    React.createElement("div", {"data-testid": props?.dataKey || "chart"}, props?.children);
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
} from "@/features/customers/components/BodyMeasurementsTab";
import { HealthProfileTab, TagList } from "@/features/customers/components/HealthProfileTab";
import { ProgressPhotosTab } from "@/features/customers/components/ProgressPhotosTab";
import type { Customer } from "@/types/customer";
import type { BodyMeasurement, CustomerFitnessGoal } from "@/types/customer-detail";

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
});

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
          health_profile: { height_cm: 172, weight_kg: 75, bmi: 25.4 } as never,
          latest_measurement: null,
          weight_trend: [],
          fitness_goals: [],
          progress_photo_count: 3,
        }}
      />,
    );
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("BMI")).toBeInTheDocument();
  });
});

describe("FitnessGoalsTab helpers", () => {
  it("clamps progress to 0-100", () => {
    expect(clampProgress(50)).toBe(50);
    expect(clampProgress(150)).toBe(100);
    expect(clampProgress(-5)).toBe(0);
    expect(clampProgress(null)).toBe(0);
  });

  it("maps goal statuses to badges", () => {
    expect(getGoalStatusMeta("active")).toEqual({ label: "Active", variant: "success" });
    expect(getGoalStatusMeta("achieved")).toEqual({ label: "Achieved", variant: "default" });
    expect(getGoalStatusMeta("abandoned")).toEqual({ label: "Abandoned", variant: "danger" });
  });

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
});

describe("BodyMeasurementsTab helpers", () => {
  it("formats measurement dates", () => {
    expect(formatMeasurementDate("2026-01-15")).toContain("Jan");
  });

  it("formats numbers or returns em dash", () => {
    expect(formatNum(75)).toBe("75");
    expect(formatNum(null)).toBe("—");
  });

  it("builds chart data sorted by date", () => {
    const data = measurementChartData([
      { ...measurement, date_logged: "2026-02-01" },
      { ...measurement, id: 2, date_logged: "2026-01-01" },
    ]);
    expect(data[0].date).toBeDefined();
    expect(data).toHaveLength(2);
    expect(data[0].weight).toBe(75);
    expect(data[0].bmi).toBe(25.4);
  });

  it("renders a measurements table", () => {
    render(<BodyMeasurementsTab measurements={[measurement]} onAdd={jest.fn()} />);
    expect(screen.getByText("Weight over time (kg)")).toBeInTheDocument();
    expect(screen.getByText("75 kg")).toBeInTheDocument();
  });

  it("shows empty state", () => {
    render(<BodyMeasurementsTab measurements={[]} onAdd={jest.fn()} />);
    expect(screen.getByText("No body measurements recorded yet.")).toBeInTheDocument();
  });
});

describe("HealthProfileTab", () => {
  it("renders vitals and tag lists", () => {
    render(
      <HealthProfileTab
        profile={{
          ...({
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
            medical_conditions: [],
          } as never),
        }}
        onSave={jest.fn()}
      />,
    );
    expect(screen.getByText("172 cm")).toBeInTheDocument();
    expect(screen.getByText("O+")).toBeInTheDocument();
    expect(screen.getByText("Peanuts")).toBeInTheDocument();
    expect(screen.getByText("Vegan")).toBeInTheDocument();
    expect(screen.getByText("Knee")).toBeInTheDocument();
  });

  it("shows add-health-profile state when no profile", () => {
    render(<HealthProfileTab profile={null} onSave={jest.fn()} />);
    expect(screen.getByText("No health profile on file yet.")).toBeInTheDocument();
  });
});

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
});

describe("ProgressPhotosTab", () => {
  it("shows empty state", () => {
    render(<ProgressPhotosTab photos={[]} onAdd={jest.fn()} />);
    expect(screen.getByText("No progress photos uploaded yet.")).toBeInTheDocument();
  });

  it("renders a photo gallery", () => {
    render(
      <ProgressPhotosTab
        photos={[
          {
            id: 1,
            customer: 1,
            image: "https://example.com/1.jpg",
            caption: "Front",
            taken_at: "2026-01-01T00:00:00Z",
            created_at: "2026-01-01T00:00:00Z",
            updated_at: "2026-01-01T00:00:00Z",
          },
        ]}
        onAdd={jest.fn()}
      />,
    );
    expect(screen.getByAltText("Front")).toBeInTheDocument();
  });

  it("opens the upload form", () => {
    render(<ProgressPhotosTab photos={[]} onAdd={jest.fn()} />);
    fireEvent.click(screen.getByText("Upload"));
    expect(screen.getByText("Image URL")).toBeInTheDocument();
  });
});
