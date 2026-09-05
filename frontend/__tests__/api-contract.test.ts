/**
 * API contract tests - list endpoints must tolerate both plain arrays and
 * paginated envelopes. Regression tests for the P0 dashboard crash
 * (`t.map is not a function` when the backend wrapped lists in `{results}`)
 * and the analytics crash (`t is not iterable` with DRF envelopes).
 */
import {
  fetchDashboardTrainers,
  fetchRevenueReport,
  fetchAttendanceHeatmap,
  fetchMembershipFunnel,
  fetchTopCustomers,
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
