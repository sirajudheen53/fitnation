import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Recharts' ResponsiveContainer measures its parent in jsdom (0x0) and throws;
// stub chart primitives to render children directly so chart components are testable.
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

import {
  revenueToCSV,
  attendanceToCSV,
  funnelToCSV,
  topCustomersToCSV,
  buildAnalyticsCSV,
} from "@/features/analytics/lib/csvExport";
import {
  resolveAnalyticsFilters,
} from "@/features/analytics/store/analyticsFilters";
import { RevenueChart } from "@/features/analytics/components/RevenueChart";
import { AttendanceHeatmapChart } from "@/features/analytics/components/AttendanceHeatmapChart";
import { MembershipFunnelChart } from "@/features/analytics/components/MembershipFunnelChart";
import {
  TopCustomersTable,
  formatSpend,
} from "@/features/analytics/components/TopCustomersTable";
import { AnalyticsFilterBar } from "@/features/analytics/components/AnalyticsFilterBar";
import type {
  RevenueReport,
  AttendanceHeatmap,
  MembershipFunnel,
  TopCustomer,
} from "@/types/analytics";
import type { Branch } from "@/types/branch";

/* ── Fixtures ─────────────────────────────────────────────────── */

const revenue: RevenueReport[] = [
  { period: "2026-08-01", amount: 1000 },
  { period: "2026-08-02", amount: 2500 },
];

const attendance: AttendanceHeatmap[] = [
  { date: "2026-08-01", count: 5 },
  { date: "2026-08-02", count: 12 },
];

const funnel: MembershipFunnel[] = [
  { stage: "prospect", count: 40 },
  { stage: "trial", count: 20 },
  { stage: "active", count: 15 },
  { stage: "cancelled", count: 5 },
];

const topCustomers: TopCustomer[] = [
  { customer_id: 1, customer_name: "Arjun Kumar", total_spent: 50000 },
  { customer_id: 2, customer_name: null, total_spent: 30000 },
];

const branches: Branch[] = [
  {
    id: 1,
    uuid: "uuid-1",
    name: "Downtown Gym",
    branch_type: "main",
    address_line1: "1 Main St",
    address_line2: "",
    city: "Bengaluru",
    state: "KA",
    postal_code: "560001",
    country: "India",
    latitude: null,
    longitude: null,
    phone: "+91 90000 00000",
    email: "downtown@example.com",
    opening_time: "05:00:00",
    closing_time: "23:00:00",
    operating_days: ["Monday"],
    is_active: true,
    is_headquarters: true,
    metadata: {},
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
  },
];

/* ── CSV export helpers ───────────────────────────────────────── */

describe("csvExport helpers", () => {
  it("builds a revenue CSV with header and rows", () => {
    expect(revenueToCSV(revenue)).toBe(
      "period,amount\n2026-08-01,1000\n2026-08-02,2500",
    );
  });

  it("builds an attendance CSV", () => {
    expect(attendanceToCSV(attendance)).toBe(
      "date,count\n2026-08-01,5\n2026-08-02,12",
    );
  });

  it("builds a funnel CSV", () => {
    expect(funnelToCSV(funnel)).toBe(
      "stage,count\nprospect,40\ntrial,20\nactive,15\ncancelled,5",
    );
  });

  it("builds a top-customers CSV with empty name fallback", () => {
    expect(topCustomersToCSV(topCustomers)).toBe(
      "customer_id,customer_name,total_spent\n1,Arjun Kumar,50000\n2,,30000",
    );
  });

  it("escapes cells containing commas", () => {
    const rows: TopCustomer[] = [
      { customer_id: 3, customer_name: "Doe, John", total_spent: 100 },
    ];
    expect(topCustomersToCSV(rows)).toContain('"Doe, John"');
  });

  it("combines all datasets into a multi-section CSV", () => {
    const csv = buildAnalyticsCSV(revenue, attendance, funnel, topCustomers);
    expect(csv).toContain("Revenue Report");
    expect(csv).toContain("Attendance Heatmap");
    expect(csv).toContain("Membership Funnel");
    expect(csv).toContain("Top Customers");
  });
});

/* ── Filter resolution ────────────────────────────────────────── */

describe("resolveAnalyticsFilters", () => {
  it("maps the month preset to a concrete date range", () => {
    const filters = resolveAnalyticsFilters({
      preset: "month",
      dateFrom: "",
      dateTo: "",
      branch: "",
    });
    expect(filters.date_from).toBeTruthy();
    expect(filters.date_to).toBeTruthy();
    expect(filters.branch).toBeUndefined();
  });

  it("uses custom dates when preset is custom", () => {
    const filters = resolveAnalyticsFilters({
      preset: "custom",
      dateFrom: "2026-08-01",
      dateTo: "2026-08-15",
      branch: "",
    });
    expect(filters.date_from).toBe("2026-08-01");
    expect(filters.date_to).toBe("2026-08-15");
  });

  it("includes the branch filter when selected", () => {
    const filters = resolveAnalyticsFilters({
      preset: "week",
      dateFrom: "",
      dateTo: "",
      branch: "1",
    });
    expect(filters.branch).toBe("1");
  });
});

/* ── Chart components ────────────────────────────────────────── */

describe("RevenueChart", () => {
  it("renders the period label", () => {
    render(<RevenueChart data={revenue} periodLabel="Revenue" />);
    expect(screen.getByText("Revenue")).toBeInTheDocument();
  });
});

describe("AttendanceHeatmapChart", () => {
  it("renders a heatmap grid for the given days", () => {
    const { container } = render(<AttendanceHeatmapChart data={attendance} />);
    expect(screen.getByText("Attendance Heatmap")).toBeInTheDocument();
    // Two days → two cells.
    expect(container.querySelectorAll("div[title]").length).toBe(2);
  });

  it("shows an empty state when there is no data", () => {
    render(<AttendanceHeatmapChart data={[]} />);
    expect(screen.getByText(/no attendance data/i)).toBeInTheDocument();
  });
});

describe("MembershipFunnelChart", () => {
  it("renders the funnel title", () => {
    render(<MembershipFunnelChart data={funnel} />);
    expect(screen.getByText("Membership Funnel")).toBeInTheDocument();
  });
});

/* ── Top customers table ──────────────────────────────────────── */

describe("TopCustomersTable", () => {
  it("formats spend as INR", () => {
    expect(formatSpend(50000)).toBe("₹50,000");
  });

  it("renders ranked customers with names and spend", () => {
    render(<TopCustomersTable data={topCustomers} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.getByText("Customer #2")).toBeInTheDocument();
    expect(screen.getByText("₹50,000")).toBeInTheDocument();
    expect(screen.getByText("₹30,000")).toBeInTheDocument();
  });

  it("shows an empty state when there are no customers", () => {
    render(<TopCustomersTable data={[]} />);
    expect(screen.getByText(/no customer data available/i)).toBeInTheDocument();
  });

  it("shows a loading state", () => {
    render(<TopCustomersTable data={[]} loading />);
    expect(screen.getByText(/loading/i)).toBeInTheDocument();
  });
});

/* ── Filter bar ──────────────────────────────────────────────── */

describe("AnalyticsFilterBar", () => {
  const baseProps = {
    preset: "month" as const,
    dateFrom: "",
    dateTo: "",
    branch: "",
    branches,
    onPresetChange: jest.fn(),
    onDateFromChange: jest.fn(),
    onDateToChange: jest.fn(),
    onBranchChange: jest.fn(),
    onExport: jest.fn(),
  };

  it("renders preset buttons and branch selector", () => {
    render(<AnalyticsFilterBar {...baseProps} />);
    expect(screen.getByRole("button", { name: "Today" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Last 7 days" })).toBeInTheDocument();
    expect(screen.getByLabelText("Branch")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /export to csv/i })).toBeInTheDocument();
  });

  it("calls onPresetChange when a preset is clicked", async () => {
    const user = userEvent.setup();
    render(<AnalyticsFilterBar {...baseProps} />);
    await user.click(screen.getByRole("button", { name: "Today" }));
    expect(baseProps.onPresetChange).toHaveBeenCalledWith("today");
  });

  it("shows custom date inputs only when preset is custom", () => {
    const { rerender } = render(<AnalyticsFilterBar {...baseProps} />);
    expect(screen.queryByLabelText("From")).not.toBeInTheDocument();

    rerender(<AnalyticsFilterBar {...baseProps} preset="custom" />);
    expect(screen.getByLabelText("From")).toBeInTheDocument();
    expect(screen.getByLabelText("To")).toBeInTheDocument();
  });

  it("calls onBranchChange when a branch is selected", () => {
    render(<AnalyticsFilterBar {...baseProps} />);
    fireEvent.change(screen.getByLabelText("Branch"), { target: { value: "1" } });
    expect(baseProps.onBranchChange).toHaveBeenCalledWith("1");
  });

  it("calls onExport when the export button is clicked", async () => {
    const user = userEvent.setup();
    render(<AnalyticsFilterBar {...baseProps} />);
    await user.click(screen.getByRole("button", { name: /export to csv/i }));
    expect(baseProps.onExport).toHaveBeenCalled();
  });
});
