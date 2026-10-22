import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import PtSessionsPage from "@/app/pt-sessions/page";
import {
  bookTrainerSession,
  cancelTrainerSession,
  completeTrainerSession,
  fetchCustomers,
  fetchPtRemaining,
  fetchTrainerSessions,
  fetchTrainers,
  noShowTrainerSession,
} from "@/lib/api";
import {
  dayLabel,
  rangeBounds,
  sessionDayKey,
  sessionTimeLabel,
} from "@/features/trainers/components/sessionBoardHelpers";
import type { Trainer, TrainerSession } from "@/types/trainer";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/pt-sessions",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "desk-token",
  getStoredUser: () => ({
    id: 1,
    email: "desk@fit.test",
    name: "Front Desk",
    role: "manager",
    tenant_id: 1,
    tenant_name: "Fit Test",
    is_owner: false,
  }),
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchTrainerSessions: jest.fn(),
  fetchTrainers: jest.fn(),
  fetchCustomers: jest.fn(),
  fetchPtRemaining: jest.fn(),
  bookTrainerSession: jest.fn(),
  completeTrainerSession: jest.fn(),
  noShowTrainerSession: jest.fn(),
  cancelTrainerSession: jest.fn(),
}));

const sampleTrainer = (overrides: Partial<Trainer> = {}): Trainer => ({
  id: 1,
  user_id: 11,
  email: "asha@fit.test",
  first_name: "Asha",
  last_name: "Menon",
  phone: null,
  specialization: "Strength",
  bio: null,
  is_active: true,
  certifications: [],
  experience_years: 6,
  rating: "4.50",
  profile_photo: "",
  max_clients: 20,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

/** Build an ISO datetime for today at the given local hour. */
function todayAt(hour: number): string {
  const d = new Date();
  d.setHours(hour, 0, 0, 0);
  return d.toISOString();
}

const sampleSession = (overrides: Partial<TrainerSession> = {}): TrainerSession => ({
  id: 1,
  trainer: 1,
  customer: 500,
  branch: 1,
  scheduled_at: todayAt(9),
  duration_minutes: 60,
  status: "booked",
  notes: "",
  trainer_email: "asha@fit.test",
  customer_name: "Ravi Kumar",
  branch_name: "HSR Layout",
  created_at: "2026-10-01T00:00:00Z",
  updated_at: "2026-10-01T00:00:00Z",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  (fetchTrainerSessions as jest.Mock).mockResolvedValue([
    sampleSession(),
    sampleSession({
      id: 2,
      customer: 501,
      customer_name: "Sara Ali",
      scheduled_at: todayAt(17),
      status: "completed",
    }),
    // Last week — outside both ranges, exercises range filtering.
    sampleSession({
      id: 3,
      customer: 502,
      customer_name: "Old Booking",
      scheduled_at: new Date(Date.now() - 7 * 86_400_000).toISOString(),
    }),
  ]);
  (fetchTrainers as jest.Mock).mockResolvedValue([sampleTrainer()]);
});

describe("session board helpers", () => {
  it("derives a local day key", () => {
    const d = new Date(2026, 9, 22, 14, 30);
    expect(sessionDayKey(d.toISOString())).toBe("2026-10-22");
  });

  it("bounds today and week ranges", () => {
    const now = new Date(2026, 9, 21, 15, 0); // Wednesday
    const today = rangeBounds("today", now);
    expect(today.start.getHours()).toBe(0);
    expect(today.end.getDate()).toBe(22);

    const week = rangeBounds("week", now);
    expect(week.start.getDay()).toBe(1); // Monday
    expect(week.start.getDate()).toBe(19);
    expect(week.end.getDate()).toBe(26);
  });

  it("labels today and tomorrow", () => {
    const now = new Date(2026, 9, 22, 8, 0);
    expect(dayLabel("2026-10-22", now)).toBe("Today");
    expect(dayLabel("2026-10-23", now)).toBe("Tomorrow");
    // Locale-safe: not Today/Tomorrow, but the date itself.
    expect(dayLabel("2026-10-19", now)).not.toBe("Today");
    expect(dayLabel("2026-10-19", now)).toContain("Oct 19");
  });

  it("formats the session time label", () => {
    expect(sessionTimeLabel(todayAt(9))).toMatch(/^\d{1,2}:\d{2}/);
  });
});

describe("PtSessionsPage — board", () => {
  it("groups today's sessions chronologically with status badges", async () => {
    render(<PtSessionsPage />);

    await screen.findByTestId(
      `day-group-${sessionDayKey(new Date().toISOString())}`,
    );
    const rows = await screen.findAllByTestId("session-row");
    expect(rows).toHaveLength(2); // last week's session is out of range
    expect(within(rows[0]).getByTestId("session-parties")).toHaveTextContent(
      "Ravi Kumar",
    );
    expect(within(rows[0]).getByText("booked")).toBeInTheDocument();
    expect(within(rows[1]).getByTestId("session-parties")).toHaveTextContent(
      "Sara Ali",
    );
    expect(within(rows[1]).getByText("completed")).toBeInTheDocument();
  });

  it("shows the week range including past-week sessions? no — only within the week", async () => {
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.click(screen.getByRole("button", { name: "This week" }));

    const rows = await screen.findAllByTestId("session-row");
    // Today's two sessions always belong to the current week; the 7-day-old
    // one belongs to the previous week (or is a boundary flake — excluded).
    expect(rows.length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("Old Booking")).not.toBeInTheDocument();
  });

  it("refetches server-side when a status chip is selected", async () => {
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.click(screen.getByRole("button", { name: "Completed" }));

    await waitFor(() =>
      expect(fetchTrainerSessions).toHaveBeenLastCalledWith("desk-token", {
        trainer: undefined,
        status: "completed",
      }),
    );
  });

  it("refetches server-side when a trainer filter is selected", async () => {
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.change(screen.getByLabelText("Filter by trainer"), {
      target: { value: "1" },
    });

    await waitFor(() =>
      expect(fetchTrainerSessions).toHaveBeenLastCalledWith("desk-token", {
        trainer: 1,
        status: undefined,
      }),
    );
  });

  it("shows the empty state when nothing is booked", async () => {
    (fetchTrainerSessions as jest.Mock).mockResolvedValue([]);
    render(<PtSessionsPage />);

    expect(await screen.findByTestId("sessions-empty")).toHaveTextContent(
      /No PT sessions booked yet/,
    );
  });

  it("shows the error state when the fetch fails", async () => {
    (fetchTrainerSessions as jest.Mock).mockRejectedValue(
      new Error("Request failed with status 500"),
    );
    render(<PtSessionsPage />);

    expect(
      await screen.findByText("Request failed with status 500"),
    ).toBeInTheDocument();
  });
});

describe("PtSessionsPage — booking", () => {
  beforeEach(() => {
    (fetchCustomers as jest.Mock).mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [
        { id: 500, name: "Ravi Kumar", email: "ravi@fit.test", phone: null, branch: 1 },
      ],
    });
    (fetchPtRemaining as jest.Mock).mockResolvedValue({
      customer_id: 500,
      membership_id: 9,
      plan_name: "PT 12-pack",
      membership_status: "active",
      end_date: null,
      total: 12,
      redeemed: 4,
      remaining: 8,
      unlimited: false,
      can_book: true,
      reason: "ok",
    });
    (bookTrainerSession as jest.Mock).mockResolvedValue(sampleSession());
  });

  it("books through the dialog with the pack meter visible", async () => {
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.click(screen.getByRole("button", { name: /New booking/i }));
    await screen.findByTestId("customer-options");
    fireEvent.click(screen.getByRole("button", { name: /Ravi Kumar/ }));

    // Per-customer remaining-pack display (issue #55).
    expect(await screen.findByTestId("pt-pack-badge")).toHaveTextContent("8 / 12 left");

    fireEvent.change(screen.getByLabelText("Trainer"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm booking" }));

    await waitFor(() =>
      expect(bookTrainerSession).toHaveBeenCalledWith(
        expect.objectContaining({
          trainer: 1,
          customer: 500,
          branch: 1,
          duration_minutes: 60,
          scheduled_at: expect.stringMatching(/T\d{2}:\d{2}:/),
        }),
        "desk-token",
      ),
    );
    // Dialog closes after success.
    await waitFor(() =>
      expect(screen.queryByTestId("customer-options")).not.toBeInTheDocument(),
    );
  });

  it("disables booking when the selected customer's pack is exhausted", async () => {
    (fetchPtRemaining as jest.Mock).mockResolvedValue({
      customer_id: 500,
      membership_id: 9,
      plan_name: "PT 12-pack",
      membership_status: "active",
      end_date: null,
      total: 12,
      redeemed: 12,
      remaining: 0,
      unlimited: false,
      can_book: false,
      reason: "session_pack_exhausted",
    });
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.click(screen.getByRole("button", { name: /New booking/i }));
    await screen.findByTestId("customer-options");
    fireEvent.click(screen.getByRole("button", { name: /Ravi Kumar/ }));

    expect(await screen.findByText(/PT pack exhausted/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Confirm booking" })).toBeDisabled();
    expect(bookTrainerSession).not.toHaveBeenCalled();
  });

  it("surfaces a 409 slot conflict with clear copy", async () => {
    (bookTrainerSession as jest.Mock).mockRejectedValue({
      status: 409,
      data: {
        reason: "trainer_slot_conflict",
        detail: "Trainer already has a session from 2026-10-22 09:00 to 2026-10-22 10:00.",
      },
      message: "Trainer already has a session from 2026-10-22 09:00 to 2026-10-22 10:00.",
    });
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.click(screen.getByRole("button", { name: /New booking/i }));
    await screen.findByTestId("customer-options");
    fireEvent.click(screen.getByRole("button", { name: /Ravi Kumar/ }));
    await screen.findByTestId("pt-pack-badge");
    fireEvent.click(screen.getByRole("button", { name: "Confirm booking" }));

    expect(await screen.findByTestId("booking-conflict")).toHaveTextContent(
      /That slot clashes with the trainer's schedule/,
    );
  });
});

describe("PtSessionsPage — status actions", () => {
  it("completes a booked session after confirm, updating the row inline", async () => {
    (completeTrainerSession as jest.Mock).mockResolvedValue(
      sampleSession({ status: "completed" }),
    );
    render(<PtSessionsPage />);
    const rows = await screen.findAllByTestId("session-row");

    fireEvent.click(within(rows[0]).getByRole("button", { name: "Complete" }));
    expect(screen.getByText(/One session credit is redeemed/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Complete session" }));
    await waitFor(() =>
      expect(completeTrainerSession).toHaveBeenCalledWith(1, "desk-token"),
    );
    await waitFor(() =>
      expect(within(rows[0]).getByTestId("session-status")).toHaveTextContent(
        "completed",
      ),
    );
  });

  it("marks no-show after confirm", async () => {
    (noShowTrainerSession as jest.Mock).mockResolvedValue(
      sampleSession({ status: "no_show" }),
    );
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    const bookedRows = await screen.findAllByTestId("session-row");
    fireEvent.click(within(bookedRows[0]).getByRole("button", { name: "No-show" }));
    fireEvent.click(screen.getByRole("button", { name: "Mark no-show" }));

    await waitFor(() =>
      expect(noShowTrainerSession).toHaveBeenCalledWith(1, "desk-token"),
    );
  });

  it("offers cancel to a booked session with the no-credit copy", async () => {
    (cancelTrainerSession as jest.Mock).mockResolvedValue(
      sampleSession({ status: "cancelled" }),
    );
    render(<PtSessionsPage />);
    await screen.findByText("Today");

    fireEvent.click(screen.getAllByRole("button", { name: "Cancel" })[0]);
    expect(screen.getByText(/No credit is redeemed/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Cancel session" }));
    await waitFor(() =>
      expect(cancelTrainerSession).toHaveBeenCalledWith(1, "desk-token"),
    );
  });
});
