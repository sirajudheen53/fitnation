/**
 * P0 regression suite (2026-09-07): detail-tab API functions were calling
 * `/customers/${id}/...` instead of the real backend routes, 404ing every
 * tab load and save on the detail page. These tests pin the exact wire
 * URLs so route drift can never ship silently again.
 *
 * Backend routes (apps/customers/):
 * - nested actions on CustomerViewSet: /customers/customers/{id}/...
 * - flat viewsets: /customers/fitness-goals/{goalId}/, /customers/body-measurements/
 */
import { render, screen } from "@testing-library/react";
import {
  fetchFitnessGoals,
  createFitnessGoal,
  updateFitnessGoal,
  fetchBodyMeasurements,
  createBodyMeasurement,
  fetchHealthProfile,
  updateCustomerHealthProfile,
  fetchProgressPhotos,
  createProgressPhoto,
  fetchProgressSummary,
} from "@/lib/api";
import { HealthProfileTab } from "@/features/customers/components/HealthProfileTab";

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

const TOKEN = "tok";
const payload = {} as never;

describe("detail-tab API routes (P0 regression)", () => {
  it("fetchFitnessGoals uses the nested customer action", async () => {
    const fetchMock = mockFetchOnce([]);
    await fetchFitnessGoals(1, TOKEN);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/fitness-goals/");
  });

  it("createFitnessGoal POSTs the nested customer action", async () => {
    const fetchMock = mockFetchOnce(payload);
    await createFitnessGoal(1, {} as never, TOKEN);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/fitness-goals/");
    expect(init.method).toBe("POST");
  });

  it("updateFitnessGoal PATCHes the FLAT fitness-goals viewset by goalId", async () => {
    const fetchMock = mockFetchOnce(payload);
    await updateFitnessGoal(1, 7, {} as never, TOKEN);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    // No nested detail route exists — the flat viewset is the only way.
    expect(url).toBe("http://localhost:8000/api/v1/customers/fitness-goals/7/");
    expect(init.method).toBe("PATCH");
    expect(url).not.toContain("/customers/1/");
  });

  it("fetchBodyMeasurements uses the FLAT viewset filtered by customer and unwraps the page envelope", async () => {
    const row = { id: 9, customer: 1 } as never;
    const fetchMock = mockFetchOnce({ count: 1, next: null, previous: null, results: [row] });
    await expect(fetchBodyMeasurements(1, TOKEN)).resolves.toEqual([row]);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://localhost:8000/api/v1/customers/body-measurements/?customer=1");
  });

  it("fetchBodyMeasurements passes plain arrays through and degrades garbage to []", async () => {
    mockFetchOnce([{ id: 5, customer: 1 } as never]);
    await expect(fetchBodyMeasurements(1, TOKEN)).resolves.toHaveLength(1);
    mockFetchOnce({ detail: "Unexpected shape" });
    await expect(fetchBodyMeasurements(1, TOKEN)).resolves.toEqual([]);
  });

  it("createBodyMeasurement POSTs the flat viewset with customer in the body", async () => {
    const fetchMock = mockFetchOnce(payload);
    await createBodyMeasurement(1, {} as never, TOKEN);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/customers/body-measurements/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string).customer).toBe(1);
  });

  it("fetchHealthProfile uses the nested customer action", async () => {
    const fetchMock = mockFetchOnce(payload);
    await fetchHealthProfile(1, TOKEN);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/health-profile/");
  });

  it("updateCustomerHealthProfile PATCHes the nested customer action", async () => {
    const fetchMock = mockFetchOnce(payload);
    await updateCustomerHealthProfile(1, {} as never, TOKEN);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/health-profile/");
    expect(init.method).toBe("PATCH");
  });

  it("fetchProgressPhotos uses the nested customer action", async () => {
    const fetchMock = mockFetchOnce([]);
    await fetchProgressPhotos(1, TOKEN);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/progress-photos/");
  });

  it("createProgressPhoto POSTs the nested customer action", async () => {
    const fetchMock = mockFetchOnce(payload);
    await createProgressPhoto(1, {} as never, TOKEN);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/progress-photos/");
    expect(init.method).toBe("POST");
  });

  it("fetchProgressSummary uses the nested customer action", async () => {
    const fetchMock = mockFetchOnce(payload);
    await fetchProgressSummary(1, TOKEN);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toBe("http://localhost:8000/api/v1/customers/customers/1/progress-summary/");
  });
});

describe("health profile 404 → empty state", () => {
  it("renders the empty state (not an error) when no profile exists yet", () => {
    // The detail page degrades a 404 GET to profile=null; the tab must show
    // the "add" empty state so PATCH (get_or_create) can create the profile.
    render(<HealthProfileTab profile={null} onSave={jest.fn()} />);
    expect(screen.getByText(/no health profile on file yet/i)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /add health profile/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});