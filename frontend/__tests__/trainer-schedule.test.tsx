/**
 * TrainerScheduleSection tests (issue #80) — weekly schedule view/manage:
 * list rendering, role gating, create/edit/delete flows, client-side
 * duplicate-day + inverted-window validation, and server-error surfacing.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { TrainerScheduleSection } from "@/features/trainers/components/TrainerScheduleSection";
import {
  ApiError,
  createTrainerScheduleSlot,
  deleteTrainerScheduleSlot,
  fetchTrainerSchedule,
  updateTrainerScheduleSlot,
} from "@/lib/api";
import { DAY_OF_WEEK, type TrainerScheduleSlot } from "@/types/trainer";

jest.mock("@/lib/auth", () => ({
  getToken: () => "tok",
  getStoredUser: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchTrainerSchedule: jest.fn(),
  createTrainerScheduleSlot: jest.fn(),
  updateTrainerScheduleSlot: jest.fn(),
  deleteTrainerScheduleSlot: jest.fn(),
}));

const sampleSlot = (overrides: Partial<TrainerScheduleSlot> = {}): TrainerScheduleSlot => ({
  id: 7,
  trainer: 1,
  day_of_week: "monday",
  start_time: "06:00:00",
  end_time: "10:00:00",
  is_available: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

function renderSection(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("TrainerScheduleSection — list states", () => {
  it("shows a loading spinner while the schedule loads", () => {
    (fetchTrainerSchedule as jest.Mock).mockReturnValue(new Promise(() => {}));
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);

    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("renders the seven-day grid with each slot's window, status and manage actions", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([
      sampleSlot(),
      sampleSlot({
        id: 8,
        day_of_week: "wednesday",
        start_time: "17:00:00",
        end_time: "19:00:00",
        is_available: false,
      }),
    ]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);

    const monday = await screen.findByTestId("schedule-day-monday");
    for (const day of DAY_OF_WEEK) {
      expect(screen.getByTestId(`schedule-day-${day}`)).toBeInTheDocument();
    }

    expect(monday).toHaveTextContent(/06:00|6:00/);
    expect(within(monday).getByText("available")).toBeInTheDocument();
    expect(within(monday).getByLabelText("Edit Monday slot")).toBeInTheDocument();
    expect(within(monday).getByLabelText("Delete Monday slot")).toBeInTheDocument();

    const wednesday = screen.getByTestId("schedule-day-wednesday");
    expect(within(wednesday).getByText("off")).toBeInTheDocument();

    // Empty days offer a per-day Add affordance; the header has the primary one.
    expect(screen.getByLabelText("Add Tuesday slot")).toBeInTheDocument();
    expect(screen.getByTestId("schedule-add")).toBeInTheDocument();
  });

  it("hides manage affordances for view-only users but keeps the schedule visible", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage={false} />);

    const monday = await screen.findByTestId("schedule-day-monday");
    expect(monday).toHaveTextContent(/06:00|6:00/);
    expect(screen.queryByTestId("schedule-add")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Edit Monday slot")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Delete Monday slot")).not.toBeInTheDocument();
    expect(screen.queryByLabelText("Add Tuesday slot")).not.toBeInTheDocument();
  });

  it("shows the error state and refetches on Try again", async () => {
    (fetchTrainerSchedule as jest.Mock)
      .mockRejectedValueOnce(new Error("Request failed with status 500"))
      .mockResolvedValueOnce([sampleSlot()]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Request failed with status 500",
    );

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByTestId("schedule-day-monday")).toBeInTheDocument();
    expect(fetchTrainerSchedule).toHaveBeenCalledTimes(2);
  });

  it("shows the empty state with per-day add actions", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);

    expect(await screen.findByTestId("schedule-empty")).toHaveTextContent(
      /No weekly schedule configured/,
    );
    expect(screen.getAllByLabelText(/Add .* slot$/)).toHaveLength(7);
  });
});

describe("TrainerScheduleSection — create", () => {
  it("creates a slot from the header Add button and refetches the list", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
    (createTrainerScheduleSlot as jest.Mock).mockResolvedValue(
      sampleSlot({ id: 9, start_time: "08:00:00", end_time: "12:00:00" }),
    );
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-empty");

    fireEvent.click(screen.getByTestId("schedule-add"));
    expect(
      screen.getByRole("heading", { name: "Add schedule slot" }),
    ).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "08:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "12:00" },
    });
    fireEvent.click(screen.getByTestId("schedule-slot-submit"));

    await waitFor(() =>
      expect(createTrainerScheduleSlot).toHaveBeenCalledWith(
        {
          trainer: 1,
          day_of_week: "monday",
          start_time: "08:00",
          end_time: "12:00",
          is_available: true,
        },
        "tok",
      ),
    );
    // The mutation invalidates the schedule query → the list refetches.
    await waitFor(() =>
      expect(fetchTrainerSchedule).toHaveBeenCalledTimes(2),
    );
    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Add schedule slot" }),
      ).not.toBeInTheDocument(),
    );
  });

  it("preselects the day when adding from an empty day card", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    (createTrainerScheduleSlot as jest.Mock).mockResolvedValue(
      sampleSlot({ id: 10, day_of_week: "friday", start_time: "07:00:00", end_time: "09:00:00" }),
    );
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByLabelText("Add Friday slot"));
    expect(screen.getByLabelText("Day of week")).toHaveValue("friday");

    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "07:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "09:00" },
    });
    fireEvent.click(screen.getByTestId("schedule-slot-submit"));

    await waitFor(() =>
      expect(createTrainerScheduleSlot).toHaveBeenCalledWith(
        expect.objectContaining({ trainer: 1, day_of_week: "friday" }),
        "tok",
      ),
    );
  });

  it("blocks an inverted window client-side without calling the API", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-empty");

    fireEvent.click(screen.getByTestId("schedule-add"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "10:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "08:00" },
    });
    fireEvent.click(screen.getByTestId("schedule-slot-submit"));

    expect(
      await screen.findByText("End time must be after start time."),
    ).toBeInTheDocument();
    expect(createTrainerScheduleSlot).not.toHaveBeenCalled();
  });

  it("blocks a duplicate weekday client-side", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByTestId("schedule-add"));
    // The dialog defaults to monday — already taken by the fixture slot.
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "12:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "14:00" },
    });
    fireEvent.click(screen.getByTestId("schedule-slot-submit"));

    expect(
      await screen.findByText(
        "A slot already exists for Monday — edit that slot instead.",
      ),
    ).toBeInTheDocument();
    expect(createTrainerScheduleSlot).not.toHaveBeenCalled();
  });

  it("surfaces the server's duplicate-day 400 on the form", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
    (createTrainerScheduleSlot as jest.Mock).mockRejectedValue(
      new ApiError(
        400,
        { non_field_errors: ["The fields trainer, day_of_week must make a unique set."] },
        "Request failed with status 400",
      ),
    );
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-empty");

    fireEvent.click(screen.getByTestId("schedule-add"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "08:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "10:00" },
    });
    fireEvent.click(screen.getByTestId("schedule-slot-submit"));

    expect(
      await screen.findByText(
        "The fields trainer, day_of_week must make a unique set.",
      ),
    ).toBeInTheDocument();
    // The dialog stays open so the user can pick another day.
    expect(
      screen.getByRole("heading", { name: "Add schedule slot" }),
    ).toBeInTheDocument();
  });

  it("shows a banner when the server is unreachable", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
    (createTrainerScheduleSlot as jest.Mock).mockRejectedValue(
      new TypeError("Failed to fetch"),
    );
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-empty");

    fireEvent.click(screen.getByTestId("schedule-add"));
    fireEvent.change(screen.getByLabelText("Start time"), {
      target: { value: "08:00" },
    });
    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "10:00" },
    });
    fireEvent.click(screen.getByTestId("schedule-slot-submit"));

    expect(
      await screen.findByText(/Could not reach the server/),
    ).toBeInTheDocument();
  });

  it("closes the dialog without calling the API on cancel", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByTestId("schedule-add"));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(
        screen.queryByRole("heading", { name: "Add schedule slot" }),
      ).not.toBeInTheDocument(),
    );
    expect(createTrainerScheduleSlot).not.toHaveBeenCalled();
  });
});

describe("TrainerScheduleSection — edit", () => {
  it("prefills the dialog from the slot and patches on save", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    (updateTrainerScheduleSlot as jest.Mock).mockResolvedValue(
      sampleSlot({ end_time: "12:00:00" }),
    );
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByLabelText("Edit Monday slot"));
    expect(
      screen.getByRole("heading", { name: "Edit schedule slot" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Day of week")).toHaveValue("monday");
    expect(screen.getByLabelText("Start time")).toHaveValue("06:00");
    expect(screen.getByLabelText("End time")).toHaveValue("10:00");

    fireEvent.change(screen.getByLabelText("End time"), {
      target: { value: "12:00" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTrainerScheduleSlot).toHaveBeenCalledWith(
        7,
        {
          trainer: 1,
          day_of_week: "monday",
          start_time: "06:00",
          end_time: "12:00",
          is_available: true,
        },
        "tok",
      ),
    );
  });

  it("blocks moving a slot onto an occupied day before the API call", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([
      sampleSlot(),
      sampleSlot({ id: 8, day_of_week: "friday" }),
    ]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByLabelText("Edit Friday slot"));
    fireEvent.change(screen.getByLabelText("Day of week"), {
      target: { value: "monday" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText(
        "A slot already exists for Monday — edit that slot instead.",
      ),
    ).toBeInTheDocument();
    expect(updateTrainerScheduleSlot).not.toHaveBeenCalled();
  });
});

describe("TrainerScheduleSection — delete", () => {
  it("deletes a slot after confirmation", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    (deleteTrainerScheduleSlot as jest.Mock).mockResolvedValue(undefined);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByLabelText("Delete Monday slot"));
    expect(screen.getByText("Delete Monday slot?")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));

    await waitFor(() =>
      expect(deleteTrainerScheduleSlot).toHaveBeenCalledWith(7, "tok"),
    );
    await waitFor(() =>
      expect(screen.queryByText("Delete Monday slot?")).not.toBeInTheDocument(),
    );
  });

  it("keeps the slot when the delete confirmation is dismissed", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
    renderSection(<TrainerScheduleSection trainerId={1} canManage />);
    await screen.findByTestId("schedule-day-monday");

    fireEvent.click(screen.getByLabelText("Delete Monday slot"));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    await waitFor(() =>
      expect(screen.queryByText("Delete Monday slot?")).not.toBeInTheDocument(),
    );
    expect(deleteTrainerScheduleSlot).not.toHaveBeenCalled();
  });
});
