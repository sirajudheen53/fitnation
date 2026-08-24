import { render, screen, fireEvent } from "@testing-library/react";
import {
  PerformanceTable,
  filterRows,
  formatCurrency,
  formatPercent,
  formatRating,
  sortRows,
  uniqueSpecializations,
} from "@/features/trainers/components/PerformanceTable";
import {
  PlansBarChart,
  TrendChart,
  formatMonthLabel,
  monthlySeries,
} from "@/features/trainers/components/PerformanceCharts";
import { PerformanceMetricCard } from "@/features/trainers/components/PerformanceMetricCard";
import type { TrainerPerformanceRow } from "@/types/trainer-performance";

const rows: TrainerPerformanceRow[] = [
  {
    trainer_id: 1,
    name: "Rahul Sharma",
    specialization: "Strength & Conditioning",
    rating: 4.6,
    assigned_customers: 12,
    active_plans: 5,
    attendance_rate: 88,
    revenue: 25000,
    sessions_completed: 40,
  },
  {
    trainer_id: 2,
    name: "Priya Verma",
    specialization: "Yoga",
    rating: 4.9,
    assigned_customers: 20,
    active_plans: 8,
    attendance_rate: 95,
    revenue: 40000,
    sessions_completed: 60,
  },
  {
    trainer_id: 3,
    name: "Amit Patel",
    specialization: null,
    rating: null,
    assigned_customers: 4,
    active_plans: 2,
    attendance_rate: null,
    revenue: 8000,
    sessions_completed: 15,
  },
];

describe("PerformanceTable helpers", () => {
  it("formats currency in Indian locale", () => {
    expect(formatCurrency(25000)).toBe("₹25,000");
    expect(formatCurrency(40000)).toBe("₹40,000");
  });

  it("formats ratings to one decimal place", () => {
    expect(formatRating(4.56)).toBe("4.6");
    expect(formatRating("4.9")).toBe("4.9");
  });

  it("returns em dash for null ratings", () => {
    expect(formatRating(null)).toBe("—");
    expect(formatRating("")).toBe("—");
  });

  it("formats percentage values", () => {
    expect(formatPercent(88)).toBe("88.0%");
    expect(formatPercent(null)).toBe("—");
  });

  it("collects unique non-empty specializations", () => {
    expect(uniqueSpecializations(rows)).toEqual([
      "Strength & Conditioning",
      "Yoga",
    ]);
  });
});

describe("sortRows", () => {
  it("sorts by revenue descending by default semantics", () => {
    const sorted = sortRows(rows, "revenue", "desc");
    expect(sorted[0].trainer_id).toBe(2);
    expect(sorted[2].trainer_id).toBe(3);
  });

  it("sorts by name ascending", () => {
    const sorted = sortRows(rows, "name", "asc");
    expect(sorted[0].name).toBe("Amit Patel");
    expect(sorted[2].name).toBe("Rahul Sharma");
  });

  it("sorts by rating descending", () => {
    const sorted = sortRows(rows, "rating", "desc");
    expect(sorted[0].trainer_id).toBe(2);
  });
});

describe("filterRows", () => {
  it("filters by specialization", () => {
    const result = filterRows(rows, { specialization: "yoga" });
    expect(result).toHaveLength(1);
    expect(result[0].trainer_id).toBe(2);
  });

  it("filters by minimum rating", () => {
    const result = filterRows(rows, { minRating: 4.5 });
    expect(result).toHaveLength(2);
  });

  it("keeps all rows when no filters provided", () => {
    expect(filterRows(rows, {})).toHaveLength(3);
  });
});

describe("PerformanceTable", () => {
  it("renders trainer rows with metrics", () => {
    render(
      <PerformanceTable
        rows={rows}
        sortKey="revenue"
        sortDirection="desc"
        onSort={jest.fn()}
      />,
    );
    expect(screen.getByText("Rahul Sharma")).toBeInTheDocument();
    expect(screen.getByText("Yoga")).toBeInTheDocument();
    expect(screen.getByText("₹40,000")).toBeInTheDocument();
    expect(screen.getByText("4.9")).toBeInTheDocument();
  });

  it("renders em dash for trainers without rating/specialization", () => {
    render(
      <PerformanceTable
        rows={[rows[2]]}
        sortKey="name"
        sortDirection="asc"
        onSort={jest.fn()}
      />,
    );
    expect(screen.getAllByText("—").length).toBeGreaterThan(0);
  });

  it("triggers sort when a column header is clicked", () => {
    const onSort = jest.fn();
    render(
      <PerformanceTable
        rows={rows}
        sortKey="name"
        sortDirection="asc"
        onSort={onSort}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /Revenue/i }));
    expect(onSort).toHaveBeenCalledWith("revenue");
  });
});

describe("PerformanceCharts helpers", () => {
  it("formats YYYY-MM month labels", () => {
    expect(formatMonthLabel("2026-01")).toBe("Jan 26");
    expect(formatMonthLabel("2025-11")).toBe("Nov 25");
  });

  it("returns the raw string for malformed months", () => {
    expect(formatMonthLabel("unknown")).toBe("unknown");
  });

  it("builds a sorted monthly series with revenue, rating and plans", () => {
    const series = monthlySeries([
      { month: "2026-03", revenue: "30", rating_avg: "4.2", sessions_completed: 10 } as never,
      { month: "2026-01", revenue: "10", rating_avg: null, sessions_completed: 5 } as never,
    ]);
    expect(series[0].month).toBe("Jan 26");
    expect(series[0].rating).toBeNull();
    expect(series[1].month).toBe("Mar 26");
    expect(series[1].revenue).toBe(30);
  });
});

describe("TrendChart & PlansBarChart", () => {
  it("shows empty state when no data", () => {
    render(<TrendChart title="Revenue trend" data={[]} color="#000" />);
    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });

  it("shows empty state for bar chart without data", () => {
    render(<PlansBarChart data={[]} />);
    expect(screen.getByText("No data available.")).toBeInTheDocument();
  });
});

describe("PerformanceMetricCard", () => {
  it("renders label, value and icon container", () => {
    render(
      <PerformanceMetricCard label="Revenue" value="₹25,000" icon={<span>💰</span>} />,
    );
    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("₹25,000")).toBeInTheDocument();
  });
});
