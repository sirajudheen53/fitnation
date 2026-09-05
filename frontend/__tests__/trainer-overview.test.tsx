/**
 * Component tests for TrainerOverview — the component that crashed in
 * production (P0, 2026-09-05): the deployed backend returned a
 * `{results, total}` envelope for /dashboard/trainers/ and the component
 * called `.map` on the object ("t.map is not a function").
 *
 * These tests pin the defensive contract: the component must render an
 * empty state — never crash — no matter what shape reaches it.
 */
import { render, screen } from "@testing-library/react";
import { TrainerOverview } from "@/features/dashboard/components/TrainerOverview";
import type { TrainerOverviewData } from "@/types/dashboard";

const trainers: TrainerOverviewData[] = [
  { id: 1, name: "Meera Nair", revenue: 12000, rating: 4.8, active_clients: 12 },
  { id: 2, name: "Arjun Das", revenue: 8000, rating: 4.2, active_clients: 8 },
];

describe("TrainerOverview", () => {
  it("renders one row per trainer", () => {
    render(<TrainerOverview trainers={trainers} />);
    expect(screen.getByText("Meera Nair")).toBeInTheDocument();
    expect(screen.getByText("Arjun Das")).toBeInTheDocument();
  });

  it("renders the empty state for a valid empty array", () => {
    render(<TrainerOverview trainers={[]} />);
    expect(screen.getByText("No trainers to show.")).toBeInTheDocument();
  });

  it("does NOT crash on the real-world {results, total} payload shape (P0 regression)", () => {
    // This is the exact shape the deployed backend returned on 2026-09-05.
    const envelope = { results: trainers, total: 2 } as unknown as TrainerOverviewData[];
    render(<TrainerOverview trainers={envelope} />);
    expect(screen.getByText("No trainers to show.")).toBeInTheDocument();
  });

  it("does NOT crash on arbitrary non-array payloads", () => {
    const garbage = { detail: "Not found." } as unknown as TrainerOverviewData[];
    render(<TrainerOverview trainers={garbage} />);
    expect(screen.getByText("No trainers to show.")).toBeInTheDocument();
  });

  it("renders the loading skeleton", () => {
    const { container } = render(<TrainerOverview loading />);
    expect(container.querySelector(".animate-pulse")).not.toBeNull();
  });
});
