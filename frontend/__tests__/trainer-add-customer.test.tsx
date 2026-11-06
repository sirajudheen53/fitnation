/**
 * Trainer profile "Add customer" (issue #73, frontend half).
 *
 * Covers the API helper's wire contract (branch_id → branch, E.164 phone,
 * DRF errors surfaced as ApiError.data) and the dialog + profile-page
 * wiring: permission gating, inline validation/API errors, and the fresh
 * assignment landing on the Customers tab without a refetch.
 */
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import TrainerProfilePage from "@/app/trainers/[id]/page";
import { AddCustomerDialog } from "@/features/trainers/components/AddCustomerDialog";
import {
  addTrainerCustomer,
  fetchBranches,
  fetchTrainer,
  fetchTrainerAssignments,
  fetchTrainerSchedule,
} from "@/lib/api";
import type { Branch } from "@/types/branch";
import type { BranchTrainerAssignment, Trainer } from "@/types/trainer";
import type { Customer } from "@/types/customer";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/trainers/1",
  useParams: () => ({ id: "1" }),
}));

// Mutable so per-test role flips re-render through the same module mock.
const mockUser = {
  id: 1,
  email: "owner@fit.test",
  name: "Gym Owner",
  role: "gym_owner",
  tenant_id: 1,
  tenant_name: "Fit Test",
  is_owner: true,
};
jest.mock("@/lib/auth", () => ({
  getToken: () => "trainer-admin-token",
  getStoredUser: () => mockUser,
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchTrainer: jest.fn(),
  fetchTrainerAssignments: jest.fn(),
  fetchTrainerSchedule: jest.fn(),
  fetchBranches: jest.fn(),
  addTrainerCustomer: jest.fn(),
}));

const realApi = jest.requireActual("@/lib/api") as typeof import("@/lib/api");

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

const sampleCustomer = (overrides: Partial<Customer> = {}): Customer => ({
  id: 501,
  user: 601,
  name: "New Member",
  email: "new.member@fit.test",
  branch: 1,
  status: "active",
  notes: "",
  phone: "+919876543210",
  gender: null,
  date_of_birth: null,
  emergency_contact_name: null,
  emergency_contact_phone: null,
  address_street: "",
  address_city: "",
  address_state: "",
  address_postal_code: "",
  is_active: true,
  profile_photo: null,
  created_at: "2026-11-06T00:00:00Z",
  updated_at: "2026-11-06T00:00:00Z",
  ...overrides,
});

const sampleBranch = (overrides: Partial<Branch> = {}): Branch => ({
  id: 1,
  uuid: "b-1",
  name: "HSR Layout",
  branch_type: "main",
  address_line1: "MG Road",
  address_line2: "",
  city: "Bengaluru",
  state: "Karnataka",
  postal_code: "560001",
  country: "India",
  latitude: null,
  longitude: null,
  phone: "",
  email: "",
  opening_time: "06:00:00",
  closing_time: "22:00:00",
  operating_days: ["monday"],
  is_active: true,
  is_headquarters: true,
  metadata: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
  ...overrides,
});

/** The profile's Schedule tab fetches through React Query (issue #80). */
function renderWithQueryClient(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

/** Open the profile's Customers tab and then the Add-customer dialog. */
async function openDialogFromProfile() {
  renderWithQueryClient(<TrainerProfilePage />);
  await screen.findByText("Asha Menon");
  fireEvent.click(screen.getByRole("button", { name: "Customers" }));
  fireEvent.click(await screen.findByRole("button", { name: /Add customer/i }));
  await screen.findByRole("heading", { name: "Add customer to Asha Menon" });
  // The branch select is fed by an async fetch — wait for its options.
  await screen.findByRole("option", { name: "HSR Layout" });
}

/** Fill the required fields — first name plus an email channel. */
function fillRequired(email = "new.member@fit.test") {
  fireEvent.change(screen.getByLabelText("First name"), { target: { value: "New" } });
  fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "Member" } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockUser.role = "gym_owner";
  (fetchTrainer as jest.Mock).mockResolvedValue(sampleTrainer());
  (fetchTrainerAssignments as jest.Mock).mockResolvedValue([sampleAssignment()]);
  (fetchTrainerSchedule as jest.Mock).mockResolvedValue([]);
  (fetchBranches as jest.Mock).mockResolvedValue([
    sampleBranch(),
    sampleBranch({ id: 2, uuid: "b-2", name: "Indiranagar" }),
  ]);
});

describe("addTrainerCustomer API helper", () => {
  const okResponse = {
    ok: true,
    status: 201,
    json: () =>
      Promise.resolve({
        customer: sampleCustomer(),
        assignment: sampleAssignment({ id: 200, customer: 501, customer_name: "New Member" }),
      }),
  };

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("POSTs the customer-create contract to the trainer action URL", async () => {
    const fetchMock = jest.fn().mockResolvedValue(okResponse);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await realApi.addTrainerCustomer(
      1,
      {
        first_name: "New",
        last_name: "Member",
        email: "new.member@fit.test",
        phone: "+919876543210",
        branch_id: 1,
      },
      "trainer-admin-token",
    );

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/trainers/1/add-customer/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      first_name: "New",
      last_name: "Member",
      email: "new.member@fit.test",
      phone: "+919876543210",
      branch: 1,
    });
    expect((init.headers as Record<string, string>).Authorization).toBe(
      "Token trainer-admin-token",
    );
    expect(result.customer.name).toBe("New Member");
    expect(result.assignment.id).toBe(200);
  });

  it("omits empty phone from the body and still sends a blank email", async () => {
    const fetchMock = jest.fn().mockResolvedValue(okResponse);
    global.fetch = fetchMock as unknown as typeof fetch;

    await realApi.addTrainerCustomer(
      "1",
      { first_name: "Phone", last_name: "Only", email: "", phone: "" },
      "trainer-admin-token",
    );

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    const body = JSON.parse(init.body as string);
    expect(body).toEqual({ first_name: "Phone", last_name: "Only", email: "" });
    expect(body).not.toHaveProperty("phone");
    expect(body).not.toHaveProperty("branch");
  });

  it("throws an ApiError carrying the DRF field errors", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () =>
        Promise.resolve({ email: ["customer with this email already exists."] }),
    }) as unknown as typeof fetch;

    const promise = realApi.addTrainerCustomer(
      1,
      { first_name: "New", email: "taken@fit.test" },
      "trainer-admin-token",
    );
    await expect(promise).rejects.toMatchObject({
      name: "ApiError",
      status: 400,
      data: { email: ["customer with this email already exists."] },
    });
  });
});

describe("AddCustomerDialog — validation", () => {
  it("blocks submission without a first name or a contact channel", async () => {
    render(<AddCustomerDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={() => {}} />);

    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    expect(await screen.findByText("First name is required.")).toBeInTheDocument();
    expect(screen.getByText("Email or phone is required")).toBeInTheDocument();
    expect(addTrainerCustomer).not.toHaveBeenCalled();
  });

  it("rejects a malformed email address", async () => {
    render(<AddCustomerDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={() => {}} />);

    fillRequired("not-an-email");
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    expect(await screen.findByText("Please enter a valid email")).toBeInTheDocument();
    expect(addTrainerCustomer).not.toHaveBeenCalled();
  });
});

describe("AddCustomerDialog — submission", () => {
  it("submits the form payload and hands the created rows to onSaved", async () => {
    const customer = sampleCustomer();
    const assignment = sampleAssignment({ id: 200, customer: 501, customer_name: "New Member" });
    (addTrainerCustomer as jest.Mock).mockResolvedValue({ customer, assignment });
    const onSaved = jest.fn();

    render(<AddCustomerDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={onSaved} />);
    fillRequired();
    // Branch options arrive async — wait before selecting one.
    await screen.findByRole("option", { name: "Indiranagar" });
    fireEvent.change(screen.getByLabelText("Branch"), { target: { value: "2" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    await waitFor(() =>
      expect(addTrainerCustomer).toHaveBeenCalledWith(
        1,
        {
          first_name: "New",
          last_name: "Member",
          email: "new.member@fit.test",
          phone: "",
          branch_id: 2,
        },
        "trainer-admin-token",
      ),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalledWith(customer, assignment));
  });

  it("sends the E.164 phone composed by PhoneInput as the contact channel", async () => {
    (addTrainerCustomer as jest.Mock).mockResolvedValue({
      customer: sampleCustomer({ email: null, phone: "+919876543210" }),
      assignment: sampleAssignment(),
    });

    render(<AddCustomerDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={() => {}} />);
    fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Phone" } });
    fireEvent.change(screen.getByLabelText("Phone"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    await waitFor(() =>
      expect(addTrainerCustomer).toHaveBeenCalledWith(
        1,
        expect.objectContaining({ email: "", phone: "+919876543210" }),
        "trainer-admin-token",
      ),
    );
  });

  it("surfaces a DRF field error inline and keeps the dialog open", async () => {
    (addTrainerCustomer as jest.Mock).mockRejectedValue(
      new realApi.ApiError(400, { email: ["customer with this email already exists."] }, "Bad Request"),
    );
    const onSaved = jest.fn();

    render(<AddCustomerDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={onSaved} />);
    fillRequired("taken@fit.test");
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    expect(
      await screen.findByText("customer with this email already exists."),
    ).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add customer to Asha Menon" })).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
  });

  it("shows non-field failures as a banner", async () => {
    // request() builds ApiError with data.detail as the message.
    const detail = "You do not have permission to perform this action.";
    (addTrainerCustomer as jest.Mock).mockRejectedValue(
      new realApi.ApiError(403, { detail }, detail),
    );

    render(<AddCustomerDialog trainer={sampleTrainer()} onClose={() => {}} onSaved={() => {}} />);
    fillRequired();
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    expect(
      await screen.findByText(/You do not have permission to perform this action/),
    ).toBeInTheDocument();
  });
});

describe("TrainerProfilePage — Add customer action", () => {
  it("offers Add customer to owner/manager and opens the dialog from the Customers tab", async () => {
    await openDialogFromProfile();

    expect(screen.getByLabelText("First name")).toBeInTheDocument();
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
    expect(screen.getByLabelText("Phone")).toBeInTheDocument();
  });

  it("shows the action for a manager — the minimal role holding customers.create_customer", async () => {
    // The visibility gate mirrors the backend's permission (viewers without
    // customers.create_customer see no button); managers are the least
    // privileged role that can reach /trainers at all, so they pin the gate
    // being open. Roles below manager never load this page (route guard).
    mockUser.role = "manager";
    renderWithQueryClient(<TrainerProfilePage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Customers" }));

    expect(screen.getByRole("button", { name: /Add customer/i })).toBeInTheDocument();
  });

  it("offers the member-adding empty state copy alongside the action", async () => {
    (fetchTrainerAssignments as jest.Mock).mockResolvedValue([]);
    renderWithQueryClient(<TrainerProfilePage />);
    await screen.findByText("Asha Menon");

    fireEvent.click(screen.getByRole("button", { name: "Customers" }));

    expect(screen.getByRole("button", { name: /Add customer/i })).toBeInTheDocument();
    expect(
      screen.getByText(/Add a new member here, or assign an existing customer from their profile/),
    ).toBeInTheDocument();
  });

  it("appends the fresh assignment to the Customers tab without a refetch", async () => {
    const customer = sampleCustomer();
    const assignment = sampleAssignment({ id: 200, customer: 501, customer_name: "New Member" });
    (addTrainerCustomer as jest.Mock).mockResolvedValue({ customer, assignment });

    await openDialogFromProfile();
    fillRequired();
    fireEvent.change(screen.getByLabelText("Branch"), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    // The new member's row appears alongside the seeded one…
    expect(await screen.findByText("New Member")).toBeInTheDocument();
    expect(screen.getByText("Ravi Kumar")).toBeInTheDocument();
    // …linking to the fresh customer record.
    expect(screen.getAllByRole("link", { name: "New Member" })[0]).toHaveAttribute(
      "href",
      "/customers/501",
    );
    // No list refetch — the returned assignment row is appended locally.
    expect(fetchTrainerAssignments).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("heading", { name: "Add customer to Asha Menon" })).toBeNull();
  });

  it("keeps the dialog open with the API error when the backend rejects", async () => {
    (addTrainerCustomer as jest.Mock).mockRejectedValue(
      new realApi.ApiError(400, { email: ["This email is already registered."] }, "Bad Request"),
    );

    await openDialogFromProfile();
    fillRequired("taken@fit.test");
    fireEvent.click(screen.getByRole("button", { name: "Confirm add customer" }));

    expect(await screen.findByText("This email is already registered.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Add customer to Asha Menon" })).toBeInTheDocument();
    // The seeded assignment list is untouched by the failed submit.
    expect(screen.queryByText("New Member")).not.toBeInTheDocument();
  });
});
