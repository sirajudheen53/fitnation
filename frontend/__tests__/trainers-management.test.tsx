import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import TrainersPage from "@/app/trainers/page";
import TrainerProfilePage from "@/app/trainers/[id]/page";
import { TrainerFormDialog } from "@/features/trainers/components/TrainerFormDialog";
import {
  createTrainer,
  fetchTrainer,
  fetchTrainerAssignments,
  fetchTrainerSchedule,
  fetchTrainers,
  updateTrainer,
} from "@/lib/api";
import type { BranchTrainerAssignment, Trainer, TrainerScheduleSlot } from "@/types/trainer";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/trainers",
  useParams: () => ({ id: "1" }),
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "trainer-admin-token",
  getStoredUser: () => ({
    id: 1,
    email: "owner@fit.test",
    name: "Gym Owner",
    role: "gym_owner",
    tenant_id: 1,
    tenant_name: "Fit Test",
    is_owner: true,
  }),
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchTrainers: jest.fn(),
  fetchTrainer: jest.fn(),
  fetchTrainerAssignments: jest.fn(),
  fetchTrainerSchedule: jest.fn(),
  createTrainer: jest.fn(),
  updateTrainer: jest.fn(),
}));

const sampleTrainer = (overrides: Partial<Trainer> = {}): Trainer => ({
  id: 1,
  user_id: 11,
  email: "asha@fit.test",
  first_name: "Asha",
  last_name: "Menon",
  phone: "+91 90000 00001",
  specialization: "Strength",
  bio: "Powerlifting coach",
  is_active: true,
  certifications: ["ACE-CPT"],
  experience_years: 6,
  rating: "4.50",
  profile_photo: "",
  max_clients: 20,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

const sampleAssignment = (
  overrides: Partial<BranchTrainerAssignment> = {},
): BranchTrainerAssignment => ({
  id: 100,
  trainer: 1,
  customer: 500,
  branch: 1,
  assigned_at: "2026-02-01T00:00:00Z",
  unassigned_at: null,
  is_active: true,
  trainer_email: "asha@fit.test",
  customer_name: "Ravi Kumar",
  branch_name: "HSR Layout",
  ...overrides,
});

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

beforeEach(() => {
  jest.clearAllMocks();
  (fetchTrainers as jest.Mock).mockResolvedValue([
    sampleTrainer(),
    sampleTrainer({
      id: 2,
      first_name: "Vikram",
      last_name: "Rathore",
      email: "vikram@fit.test",
      specialization: "Yoga",
      is_active: false,
    }),
  ]);
  (fetchTrainerAssignments as jest.Mock).mockResolvedValue([
    sampleAssignment(),
    sampleAssignment({ id: 101, customer: 501, customer_name: "Sara Ali", is_active: true }),
    sampleAssignment({ id: 102, customer: 502, customer_name: "Old Client", is_active: false }),
  ]);
});

describe("TrainersPage — list", () => {
  it("renders trainer rows with clients, rating and status", async () => {
    render(<TrainersPage />);

    expect(await screen.findByText("Asha Menon")).toBeInTheDocument();
    expect(screen.getByText("Vikram Rathore")).toBeInTheDocument();
    // Asha: 2 active assignments of max 20.
    const rows = screen.getAllByTestId("trainer-row");
    expect(rows).toHaveLength(2);
    expect(within(rows[0]).getByTestId("clients-count")).toHaveTextContent("2 / 20");
    expect(within(rows[0]).getByText("4.5")).toBeInTheDocument();
    expect(within(rows[0]).getByText("active")).toBeInTheDocument();
    expect(within(rows[1]).getByText("inactive")).toBeInTheDocument();
  });

  it("filters rows by search text", async () => {
    render(<TrainersPage />);
    await screen.findByText("Asha Menon");

    fireEvent.change(screen.getByLabelText("Search trainers"), {
      target: { value: "vikram" },
    });

    expect(screen.queryByText("Asha Menon")).not.toBeInTheDocument();
    expect(screen.getByText("Vikram Rathore")).toBeInTheDocument();
  });

  it("filters rows by status", async () => {
    render(<TrainersPage />);
    await screen.findByText("Asha Menon");

    fireEvent.change(screen.getByLabelText("Filter by status"), {
      target: { value: "inactive" },
    });

    expect(screen.queryByText("Asha Menon")).not.toBeInTheDocument();
    expect(screen.getByText("Vikram Rathore")).toBeInTheDocument();
  });

  it("shows the empty state when no trainers exist", async () => {
    (fetchTrainers as jest.Mock).mockResolvedValue([]);
    render(<TrainersPage />);

    expect(
      await screen.findByText(/No trainers yet/),
    ).toBeInTheDocument();
  });

  it("shows the error state when the fetch fails", async () => {
    (fetchTrainers as jest.Mock).mockRejectedValue(
      new Error("Request failed with status 500"),
    );
    render(<TrainersPage />);

    expect(
      await screen.findByText("Request failed with status 500"),
    ).toBeInTheDocument();
  });
});

describe("TrainersPage — create trainer", () => {
  it("opens the dialog and submits a create payload", async () => {
    const created = sampleTrainer({ id: 9, first_name: "New", last_name: "Coach" });
    (createTrainer as jest.Mock).mockResolvedValue(created);
    render(<TrainersPage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: /New trainer/i }));
    expect(screen.getByRole("heading", { name: "New trainer" })).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "New" } });
    fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Coach" } });
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "new.coach@fit.test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create trainer" }));

    await waitFor(() =>
      expect(createTrainer).toHaveBeenCalledWith(
        expect.objectContaining({
          email: "new.coach@fit.test",
          first_name: "New",
          last_name: "Coach",
          max_clients: 50,
        }),
        "trainer-admin-token",
      ),
    );
    expect(await screen.findByText("New Coach")).toBeInTheDocument();
  });

  it("blocks submission when required fields are missing", async () => {
    render(<TrainersPage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: /New trainer/i }));
    fireEvent.click(screen.getByRole("button", { name: "Create trainer" }));

    expect(await screen.findByText("First name is required.")).toBeInTheDocument();
    expect(createTrainer).not.toHaveBeenCalled();
  });
});

describe("TrainersPage — deactivate", () => {
  it("shows the assignment impact and deactivates on confirm", async () => {
    const deactivated = sampleTrainer({ is_active: false });
    (updateTrainer as jest.Mock).mockResolvedValue(deactivated);
    render(<TrainersPage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Deactivate Asha Menon" }));
    // Impact: 2 active assignments for Asha.
    expect(screen.getByTestId("deactivate-impact")).toHaveTextContent(
      /2 active client assignment/,
    );

    fireEvent.click(screen.getByRole("button", { name: "Deactivate" }));
    await waitFor(() =>
      expect(updateTrainer).toHaveBeenCalledWith(
        1,
        { is_active: false },
        "trainer-admin-token",
      ),
    );
    // The row flips to inactive.
    const rows = screen.getAllByTestId("trainer-row");
    expect(within(rows[0]).getByText("inactive")).toBeInTheDocument();
  });

  it("does not call the API when the confirm dialog is dismissed", async () => {
    render(<TrainersPage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Deactivate Asha Menon" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(updateTrainer).not.toHaveBeenCalled();
  });
});

describe("TrainerFormDialog — edit mode", () => {
  it("prefills profile fields and PATCHes on save", async () => {
    const saved = sampleTrainer({ specialization: "Mobility" });
    (updateTrainer as jest.Mock).mockResolvedValue(saved);

    render(<TrainerFormDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={() => {}} />);

    expect(screen.getByLabelText("Specialization")).toHaveValue("Strength");
    fireEvent.change(screen.getByLabelText("Specialization"), {
      target: { value: "Mobility" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(updateTrainer).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ specialization: "Mobility", is_active: true }),
        "trainer-admin-token",
      ),
    );
    expect(createTrainer).not.toHaveBeenCalled();
  });
});

describe("TrainerProfilePage — tabs", () => {
  beforeEach(() => {
    (fetchTrainer as jest.Mock).mockResolvedValue(sampleTrainer());
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([sampleSlot()]);
  });

  it("renders the overview with rating and client count", async () => {
    render(<TrainerProfilePage />);

    expect(await screen.findByText("Asha Menon")).toBeInTheDocument();
    expect(screen.getByTestId("rating")).toHaveTextContent("4.5");
    expect(screen.getByTestId("clients")).toHaveTextContent("2 / 20");
  });

  it("shows assigned customers with links on the Customers tab", async () => {
    render(<TrainerProfilePage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Customers" }));

    expect(await screen.findByText("Ravi Kumar")).toBeInTheDocument();
    expect(screen.getByText("Sara Ali")).toBeInTheDocument();
    expect(screen.getByText("Old Client")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Ravi Kumar" })[0]).toHaveAttribute(
      "href",
      "/customers/500",
    );
  });

  it("renders the weekly schedule on the Schedule tab", async () => {
    render(<TrainerProfilePage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Schedule" }));

    const monday = await screen.findByTestId("schedule-day-monday");
    expect(monday).toHaveTextContent(/06:00|6:00/);
    expect(monday).toHaveTextContent("available");
  });

  it("shows the empty schedule state", async () => {
    (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
    render(<TrainerProfilePage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Schedule" }));

    expect(
      await screen.findByText(/No weekly schedule configured/),
    ).toBeInTheDocument();
  });
});
