import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { BranchForm } from "@/features/branches/components/BranchForm";
import {
  BranchTable,
  formatBranchAddress,
  formatBranchTime,
  getBranchStatus,
} from "@/features/branches/components/BranchTable";
import {
  BranchInfo,
  BranchStatsGrid,
  emptyBranchStats,
} from "@/features/branches/components/BranchDetail";
import type { Branch } from "@/types/branch";

const baseBranch: Branch = {
  id: 1,
  uuid: "uuid-1",
  name: "Downtown Gym",
  branch_type: "main",
  address_line1: "123 Main Street",
  address_line2: "",
  city: "Bengaluru",
  state: "Karnataka",
  postal_code: "560001",
  country: "India",
  latitude: null,
  longitude: null,
  phone: "+91 98765 43210",
  email: "downtown@example.com",
  opening_time: "05:00:00",
  closing_time: "23:00:00",
  operating_days: ["Monday", "Friday"],
  is_active: true,
  is_headquarters: true,
  metadata: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("BranchTable helpers", () => {
  it("formats an address from city, state and postal code", () => {
    expect(formatBranchAddress(baseBranch)).toBe("Bengaluru, Karnataka, 560001");
  });

  it("returns em dash for an empty address", () => {
    expect(formatBranchAddress({ city: "", state: "", postal_code: "" })).toBe("—");
  });

  it("formats a full 24h time to 12-hour format", () => {
    expect(formatBranchTime("05:00:00")).toBe("5:00 AM");
    expect(formatBranchTime("13:30:00")).toBe("1:30 PM");
  });

  it("handles null or empty time strings", () => {
    expect(formatBranchTime(null)).toBe("—");
    expect(formatBranchTime("")).toBe("—");
  });

  it("marks active branches as Active/success", () => {
    expect(getBranchStatus({ is_active: true })).toEqual({
      label: "Active",
      variant: "success",
    });
  });

  it("marks inactive branches as Inactive/danger", () => {
    expect(getBranchStatus({ is_active: false })).toEqual({
      label: "Inactive",
      variant: "danger",
    });
  });
});

describe("BranchTable", () => {
  it("renders branch rows with name, status and hours", () => {
    render(<BranchTable branches={[baseBranch]} />);
    expect(screen.getByText("Downtown Gym")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText(/5:00 AM – 11:00 PM/)).toBeInTheDocument();
    expect(screen.getByText("HQ")).toBeInTheDocument();
  });

  it("renders an empty message when there are no branches", () => {
    render(<BranchTable branches={[]} />);
    // Header row only — no body rows rendered.
    expect(screen.getByText("Branch")).toBeInTheDocument();
  });

  it("calls onDelete when delete action is clicked", () => {
    const onDelete = jest.fn();
    render(<BranchTable branches={[baseBranch]} onDelete={onDelete} />);
    fireEvent.click(screen.getByLabelText("Delete Downtown Gym"));
    expect(onDelete).toHaveBeenCalledWith(baseBranch);
  });
});

describe("BranchForm", () => {
  it("renders all required fields", () => {
    render(<BranchForm onSubmit={jest.fn()} />);
    expect(screen.getByLabelText("Branch name")).toBeInTheDocument();
    expect(screen.getByLabelText("Street address")).toBeInTheDocument();
    expect(screen.getByLabelText("City")).toBeInTheDocument();
    expect(screen.getByLabelText("State")).toBeInTheDocument();
    expect(screen.getByLabelText("PIN code")).toBeInTheDocument();
    expect(screen.getByLabelText("Opening time")).toBeInTheDocument();
    expect(screen.getByLabelText("Closing time")).toBeInTheDocument();
  });

  it("rejects an invalid PIN code on submit", async () => {
    const onSubmit = jest.fn();
    render(<BranchForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Branch name"), {
      target: { value: "Test Gym" },
    });
    fireEvent.change(screen.getByLabelText("Street address"), {
      target: { value: "1 Road" },
    });
    fireEvent.change(screen.getByLabelText("City"), {
      target: { value: "City" },
    });
    fireEvent.change(screen.getByLabelText("State"), {
      target: { value: "State" },
    });
    fireEvent.change(screen.getByLabelText("PIN code"), {
      target: { value: "12" },
    });

    fireEvent.click(screen.getByText("Save branch"));
    await waitFor(() =>
      expect(screen.getByText("PIN code must be 6 digits")).toBeInTheDocument(),
    );
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits valid data to onSubmit", async () => {
    const onSubmit = jest.fn();
    render(<BranchForm onSubmit={onSubmit} />);

    fireEvent.change(screen.getByLabelText("Branch name"), {
      target: { value: "Test Gym" },
    });
    fireEvent.change(screen.getByLabelText("Street address"), {
      target: { value: "1 Road" },
    });
    fireEvent.change(screen.getByLabelText("City"), {
      target: { value: "City" },
    });
    fireEvent.change(screen.getByLabelText("State"), {
      target: { value: "State" },
    });
    fireEvent.change(screen.getByLabelText("PIN code"), {
      target: { value: "560001" },
    });

    fireEvent.click(screen.getByText("Save branch"));
    await waitFor(() => expect(onSubmit).toHaveBeenCalledTimes(1));
  });

  it("toggles operating days via chip buttons", () => {
    render(<BranchForm onSubmit={jest.fn()} />);
    const monday = screen.getByRole("button", { name: "Monday" });
    expect(monday.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(monday);
    expect(monday.getAttribute("aria-pressed")).toBe("true");
  });
});

describe("BranchDetail helpers", () => {
  it("renders branch info and HQ badge", () => {
    render(<BranchInfo branch={baseBranch} />);
    expect(screen.getByText("Downtown Gym")).toBeInTheDocument();
    expect(screen.getByText("Headquarters")).toBeInTheDocument();
  });

  it("renders stat cards with the given values", () => {
    const stats = emptyBranchStats();
    stats.total_customers = 120;
    stats.assigned_trainers = 5;
    render(<BranchStatsGrid stats={stats} />);
    expect(screen.getByText("120")).toBeInTheDocument();
    expect(screen.getByText("Total customers")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("Assigned trainers")).toBeInTheDocument();
  });
});
