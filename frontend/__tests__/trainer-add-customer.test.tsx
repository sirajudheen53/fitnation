/**
 * Trainer profile "Add customer" (issue #73, frontend half) — API helper.
 *
 * Pins the wire contract of the addTrainerCustomer helper: the
 * customer-create payload mapped onto POST /trainers/{id}/add-customer/
 * (branch_id → branch per ADR-001, E.164 phone, empty phone omitted) and
 * DRF errors surfacing as ApiError.data for the dialog's inline mapping.
 */
import { addTrainerCustomer } from "@/lib/api";
import type { BranchTrainerAssignment } from "@/types/trainer";
import type { Customer } from "@/types/customer";

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

const sampleAssignment = (
  overrides: Partial<BranchTrainerAssignment> = {},
): BranchTrainerAssignment => ({
  id: 200,
  trainer: 1,
  customer: 501,
  branch: 1,
  assigned_at: "2026-11-06T00:00:00Z",
  unassigned_at: null,
  is_active: true,
  trainer_email: "asha@fit.test",
  customer_name: "New Member",
  branch_name: "HSR Layout",
  ...overrides,
});

describe("addTrainerCustomer API helper", () => {
  const okResponse = {
    ok: true,
    status: 201,
    json: () =>
      Promise.resolve({
        customer: sampleCustomer(),
        assignment: sampleAssignment(),
      }),
  };

  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("POSTs the customer-create contract to the trainer action URL", async () => {
    const fetchMock = jest.fn().mockResolvedValue(okResponse);
    global.fetch = fetchMock as unknown as typeof fetch;

    const result = await addTrainerCustomer(
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

    await addTrainerCustomer(
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

    const promise = addTrainerCustomer(
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
