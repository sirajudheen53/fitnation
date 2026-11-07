/**
 * API contract tests - list endpoints must tolerate both plain arrays and
 * paginated envelopes. Regression tests for the P0 dashboard crash
 * (`t.map is not a function` when the backend wrapped lists in `{results}`)
 * and the analytics crash (`t is not iterable` with DRF envelopes).
 */
import {
  ApiError,
  describeValidationErrors,
  errorMessage,
  extractFieldErrors,
  fetchDashboardTrainers,
  fetchRevenueReport,
  fetchAttendanceHeatmap,
  fetchMembershipFunnel,
  fetchTopCustomers,
  hasFieldErrors,
  isPhoneConflict,
  isPhoneConflictError,
  login,
  unwrapList,
  unwrapNotificationLogs,
} from "@/lib/api";
import type {
  AttendanceHeatmap,
  MembershipFunnel,
  RevenueReport,
  TopCustomer,
} from "@/types/analytics";
import type {
  NotificationLog,
  NotificationLogListResponse,
} from "@/types/notification";
import type { TrainerOverviewData } from "@/types/dashboard";

function mockFetchOnce(payload: unknown, status = 200) {
  const fetchMock = jest.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(payload),
  });
  global.fetch = fetchMock as unknown as typeof fetch;
  return fetchMock;
}

afterEach(() => {
  jest.restoreAllMocks();
});

describe("unwrapList", () => {
  it("passes plain arrays through", () => {
    expect(unwrapList([1, 2, 3])).toEqual([1, 2, 3]);
  });
  it("unwraps DRF paginated envelopes", () => {
    expect(unwrapList({ count: 2, next: null, previous: null, results: [1, 2] })).toEqual([1, 2]);
  });

  it("unwraps {results, total} envelopes", () => {
    expect(unwrapList({ results: ["a"], total: 1 })).toEqual(["a"]);
  });

  it("returns [] for non-array payloads", () => {
    expect(unwrapList({ detail: "Not found." })).toEqual([]);
    expect(unwrapList(null)).toEqual([]);
    expect(unwrapList(undefined)).toEqual([]);
  });
});

describe("errorMessage", () => {
  it("translates network-level fetch failures into an actionable message", () => {
    // Browser: a CORS/preflight-blocked or offline request rejects with a
    // bare TypeError — no status, no body (issue #61 wizard symptom).
    expect(errorMessage(new TypeError("Failed to fetch"))).toBe(
      "Could not reach the server — check your connection and try again.",
    );
    expect(errorMessage(new TypeError("fetch failed"))).toBe(
      "Could not reach the server — check your connection and try again.",
    );
  });

  it("keeps real backend errors readable", () => {
    expect(errorMessage(new Error("Something specific happened"))).toBe(
      "Something specific happened",
    );
  });

  it("renders DRF field errors human-readably instead of 'error 400' (#96)", () => {
    const err = new ApiError(
      400,
      { phone: ["This phone is already registered to a different account. Resolve manually."] },
      "Request failed with status 400",
    );
    const rendered = errorMessage(err);
    expect(rendered).toContain("already registered to another account");
    expect(rendered).toContain("returning-member lookup");
    expect(rendered).not.toContain("Resolve manually");
    expect(rendered).not.toContain("status 400");
  });

  it("falls back to the generic message when the body has no field errors", () => {
    const err = new ApiError(502, {}, "Payment gateway is down");
    expect(errorMessage(err)).toBe("Payment gateway is down");
  });
});

describe("DRF field-error extraction (#96)", () => {
  it("flattens flat message lists with a label", () => {
    expect(
      describeValidationErrors({ branch: ["This field is required.", "Invalid pk."] }),
    ).toBe("Branch is required. Invalid pk.");
  });

  it("unwraps nested wizard blocks without the block prefix", () => {
    expect(
      describeValidationErrors({
        customer: { name: ["Provide a name (or first/last name)."] },
      }),
    ).toBe("Enter the member's name to continue.");
    expect(
      describeValidationErrors({ membership: { plan: ["This field is required."] } }),
    ).toBe("Plan is required.");
  });

  it("renders the known backend 400s with actionable copy", () => {
    expect(
      describeValidationErrors({
        phone: ["This phone is already registered to a different account. Resolve manually."],
      }),
    ).toMatch(/returning-member lookup/i);
    expect(
      describeValidationErrors({ email: ["A user with this email already exists."] }),
    ).toMatch(/Leave the email blank/);
    expect(
      describeValidationErrors({ email: ["Enter a valid email address."] }),
    ).toMatch(/not a valid email address/);
    expect(describeValidationErrors({ name: ["Provide a name (or first/last name)."] })).toBe(
      "Enter the member's name to continue.",
    );
  });

  it("walks list-serializer items with an index label", () => {
    const rendered = describeValidationErrors({
      biometrics: [{ device_user_id: ["This field is required."] }, {}],
    });
    expect(rendered).toBe("Biometrics #1 Device user ID is required.");
    expect(extractFieldErrors({ biometrics: [{}, {}] })).toEqual([]);
  });

  it("handles bare-string values and non_field_errors", () => {
    expect(describeValidationErrors({ phone: "This field is required." })).toBe(
      "Phone is required.",
    );
    expect(describeValidationErrors({ non_field_errors: ["Nope."] })).toBe("Nope.");
  });

  it("returns null for bodies without field errors", () => {
    expect(describeValidationErrors({ error: "Payment order could not be created." })).toBeNull();
    expect(describeValidationErrors({ detail: "Not found." })).toBeNull();
    expect(describeValidationErrors({})).toBeNull();
    expect(describeValidationErrors(null)).toBeNull();
    expect(describeValidationErrors(undefined)).toBeNull();
  });

  it("detects the phone-already-registered conflict for body and caught values", () => {
    const body = {
      phone: ["This phone is already registered to a different account. Resolve manually."],
    };
    expect(isPhoneConflict(body)).toBe(true);
    expect(isPhoneConflictError(new ApiError(400, body, "400"))).toBe(true);
    expect(isPhoneConflict({ name: ["Provide a name (or first/last name)."] })).toBe(false);
    expect(isPhoneConflictError(new Error("nope"))).toBe(false);
  });

  it("hasFieldErrors flags inline-renderable fields but not message containers", () => {
    expect(hasFieldErrors({ phone: ["This field is required."] })).toBe(true);
    expect(hasFieldErrors({ detail: "Not found." })).toBe(false);
    expect(hasFieldErrors({ error: "Payment order could not be created." })).toBe(false);
    expect(hasFieldErrors({ non_field_errors: ["Nope."] })).toBe(false);
    expect(hasFieldErrors({})).toBe(false);
    // A relation the form cannot render inline (e.g. an invisible FK).
    expect(hasFieldErrors({ trainer: ["This field is required."] }, ["trainer"])).toBe(false);
  });

  it("builds the readable copy into ApiError.message at request time", async () => {
    mockFetchOnce({ customer: { name: ["Provide a name (or first/last name)."] } }, 400);
    await expect(login({ email: "a@b.c", password: "x" })).rejects.toThrow(
      /Enter the member's name to continue/,
    );
  });

  it("keeps extractFieldErrors paths faithful for programmatic use", () => {
    const fields = extractFieldErrors({
      customer: { phone: ["This field is required."] },
      biometrics: [{ device: ["A valid integer is required."] }],
    });
    expect(fields.map((f) => f.field)).toEqual([
      "customer.phone",
      "biometrics.0.device",
    ]);
    expect(fields[1]?.label).toBe("Biometrics #1 Device");
  });
});

describe("fetchDashboardTrainers", () => {
  const trainers: TrainerOverviewData[] = [
    { id: 1, name: "Meera", revenue: 12000, rating: 4.8, active_clients: 12 },
  ];

  it("passes a plain array through", async () => {
    mockFetchOnce(trainers);
    await expect(fetchDashboardTrainers("tok")).resolves.toEqual(trainers);
  });

  it("unwraps a {results, total} envelope and sends the auth header", async () => {
    const fetchMock = mockFetchOnce({ results: trainers, total: 1 });
    await expect(fetchDashboardTrainers("tok")).resolves.toEqual(trainers);
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Token tok");
  });

  it("returns [] when the payload is not a list", async () => {
    mockFetchOnce({ detail: "Unexpected shape" });
    await expect(fetchDashboardTrainers("tok")).resolves.toEqual([]);
  });
});

describe("analytics fetchers tolerate paginated envelopes", () => {
  it("fetchRevenueReport unwraps results", async () => {
    const rows = [{ month: "2026-08", revenue: 100 }] as unknown as RevenueReport[];
    mockFetchOnce({ count: 1, next: null, previous: null, results: rows });
    await expect(fetchRevenueReport("tok")).resolves.toEqual(rows);
  });

  it("fetchAttendanceHeatmap unwraps results", async () => {
    const rows = [{ day: "2026-08-01", count: 5 }] as unknown as AttendanceHeatmap[];
    mockFetchOnce({ count: 1, next: null, previous: null, results: rows });
    await expect(fetchAttendanceHeatmap("tok")).resolves.toEqual(rows);
  });

  it("fetchMembershipFunnel unwraps results", async () => {
    const rows = [{ stage: "leads", count: 3 }] as unknown as MembershipFunnel[];
    mockFetchOnce({ count: 1, next: null, previous: null, results: rows });
    await expect(fetchMembershipFunnel("tok")).resolves.toEqual(rows);
  });

  it("fetchTopCustomers unwraps results", async () => {
    const rows = [{ id: 1, name: "A" }] as unknown as TopCustomer[];
    mockFetchOnce({ count: 1, next: null, previous: null, results: rows });
    await expect(fetchTopCustomers("tok")).resolves.toEqual(rows);
  });

  it.each([
    ["fetchRevenueReport", fetchRevenueReport],
    ["fetchAttendanceHeatmap", fetchAttendanceHeatmap],
    ["fetchMembershipFunnel", fetchMembershipFunnel],
    ["fetchTopCustomers", fetchTopCustomers],
  ])("%s returns [] for a non-list payload", async (_name, fetcher) => {
    mockFetchOnce({ detail: "Not found." });
    await expect(fetcher("tok")).resolves.toEqual([]);
  });
});

describe("unwrapNotificationLogs", () => {
  const log = {
    id: 1,
    notification_type: "test",
    status: "sent",
    created_at: "2026-09-05T00:00:00Z",
  } as unknown as NotificationLog;

  it("still unwraps envelopes", () => {
    const res = { results: [log] } as unknown as NotificationLogListResponse;
    expect(unwrapNotificationLogs(res)).toEqual([log]);
  });

  it("still passes arrays through", () => {
    expect(unwrapNotificationLogs([log])).toEqual([log]);
  });
});
