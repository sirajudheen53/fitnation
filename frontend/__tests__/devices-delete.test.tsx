import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import DevicesPage from "@/app/devices/page";
import {
  ApiError,
  deleteDevice,
  fetchBranches,
  fetchCustomers,
  fetchDevices,
} from "@/lib/api";
import { toast } from "sonner";
import type { AccessDevice } from "@/types/access";
import type { Branch } from "@/types/branch";

const WARNING = "Deleting stops attendance sync for this device until it is re-added.";

/* Stable router object — the page's load effect depends on `router`, so a
   fresh object per render would refetch the list on every state update. */
const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };

jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/devices",
}));

jest.mock("@/lib/auth", () => ({
  getToken: () => "device-token",
  getStoredUser: () => ({
    id: 1,
    email: "owner@fitnation.test",
    name: "Gym Owner",
    role: "gym_owner",
    tenant_id: 1,
    tenant_name: "Iron Temple",
    is_owner: false,
  }),
  logout: jest.fn(),
  getImpersonationSession: () => null,
  endImpersonationSession: jest.fn(),
  startImpersonationSession: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  ...jest.requireActual("@/lib/api"),
  fetchDevices: jest.fn(),
  fetchBranches: jest.fn(),
  fetchCustomers: jest.fn(),
  deleteDevice: jest.fn(),
}));

const branch = (): Branch => ({
  id: 1,
  uuid: "branch-uuid-1",
  name: "Main Branch",
  branch_type: "main",
  address_line1: "1 MG Road",
  address_line2: "",
  city: "Bengaluru",
  state: "KA",
  postal_code: "560001",
  country: "IN",
  latitude: null,
  longitude: null,
  phone: "",
  email: "",
  opening_time: "06:00",
  closing_time: "22:00",
  operating_days: ["Mon"],
  is_active: true,
  is_headquarters: true,
  metadata: {},
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
});

/* The phantom TBS-sticker row from ticket #64 — the row an owner needs to delete. */
const device = (overrides: Partial<AccessDevice> = {}): AccessDevice => ({
  id: 4,
  branch: 1,
  vendor: "essl",
  model: "BioFace C1",
  serial_number: "TBS2261001009",
  name: "Kannu Hash",
  connection_type: "cloud_api",
  api_endpoint: "",
  is_active: true,
  last_sync_at: null,
  last_seen_at: null,
  created_at: "2026-10-23T00:00:00Z",
  updated_at: "2026-10-23T00:00:00Z",
  ...overrides,
});

/** Develop's ConfirmDialog is a Card overlay without role="dialog" — scope to its Card. */
function confirmCard(message: string): HTMLElement {
  const node = screen.getByText(message).closest("div.rounded-xl");
  if (!(node instanceof HTMLElement)) {
    throw new Error("ConfirmDialog card not found");
  }
  return node;
}

beforeEach(() => {
  jest.clearAllMocks();
  localStorage.setItem("fbos_user", JSON.stringify({ role: "gym_owner" }));
  (fetchDevices as jest.Mock).mockResolvedValue([device()]);
  (fetchBranches as jest.Mock).mockResolvedValue([branch()]);
  (fetchCustomers as jest.Mock).mockResolvedValue({ results: [] });
});

describe("DevicesPage delete (issue #64)", () => {
  it("gates the delete behind a confirm dialog showing name, serial, and the sync warning", async () => {
    render(<DevicesPage />);
    await screen.findByText("Kannu Hash");

    fireEvent.click(screen.getByRole("button", { name: "Delete Kannu Hash" }));

    expect(screen.getByText("Delete Kannu Hash?")).toBeInTheDocument();
    const card = confirmCard(WARNING);
    expect(within(card).getByText("TBS2261001009")).toBeInTheDocument();
    expect(deleteDevice).not.toHaveBeenCalled();
  });

  it("does not call the API when the confirmation is cancelled", async () => {
    render(<DevicesPage />);
    await screen.findByText("Kannu Hash");

    fireEvent.click(screen.getByRole("button", { name: "Delete Kannu Hash" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

    expect(deleteDevice).not.toHaveBeenCalled();
    expect(screen.queryByText(WARNING)).not.toBeInTheDocument();
    expect(screen.getByText("Kannu Hash")).toBeInTheDocument();
  });

  it("deletes after confirmation, refreshes the list, and toasts success", async () => {
    (deleteDevice as jest.Mock).mockResolvedValue(undefined);
    // Initial load returns the row; the post-delete reconcile returns an empty list.
    (fetchDevices as jest.Mock)
      .mockResolvedValueOnce([device()])
      .mockResolvedValue([]);

    render(<DevicesPage />);
    await screen.findByText("Kannu Hash");

    fireEvent.click(screen.getByRole("button", { name: "Delete Kannu Hash" }));
    fireEvent.click(
      within(confirmCard(WARNING)).getByRole("button", { name: "Delete" }),
    );

    await waitFor(() =>
      expect(deleteDevice).toHaveBeenCalledWith(4, "device-token"),
    );
    // Row gone and the reconcile refetch re-rendered the (now empty) list.
    await screen.findByText(/No devices registered yet/);
    expect(screen.queryByText("Kannu Hash")).not.toBeInTheDocument();
    expect(toast.success).toHaveBeenCalledWith("Kannu Hash deleted");
    await waitFor(() => expect(fetchDevices).toHaveBeenCalledTimes(2));
  });

  it("renders the server error 1:1 and keeps the dialog open on failure", async () => {
    (deleteDevice as jest.Mock).mockRejectedValue(
      new ApiError(
        409,
        { detail: "Cannot delete device: 3 attendance logs reference it." },
        "Cannot delete device: 3 attendance logs reference it.",
      ),
    );

    render(<DevicesPage />);
    await screen.findByText("Kannu Hash");

    fireEvent.click(screen.getByRole("button", { name: "Delete Kannu Hash" }));
    fireEvent.click(
      within(confirmCard(WARNING)).getByRole("button", { name: "Delete" }),
    );

    expect(await screen.findByTestId("device-delete-error")).toHaveTextContent(
      "Cannot delete device: 3 attendance logs reference it.",
    );
    expect(toast.error).toHaveBeenCalledWith(
      "Cannot delete device: 3 attendance logs reference it.",
    );
    // Dialog stays open so the message stays visible.
    expect(screen.getByText(WARNING)).toBeInTheDocument();
  });

  it("disables the confirm button while the delete is in flight", async () => {
    let resolveDelete: () => void = () => undefined;
    (deleteDevice as jest.Mock).mockReturnValue(
      new Promise<void>((resolve) => {
        resolveDelete = resolve;
      }),
    );

    render(<DevicesPage />);
    await screen.findByText("Kannu Hash");

    fireEvent.click(screen.getByRole("button", { name: "Delete Kannu Hash" }));
    fireEvent.click(
      within(confirmCard(WARNING)).getByRole("button", { name: "Delete" }),
    );

    expect(screen.getByRole("button", { name: "Working…" })).toBeDisabled();
    resolveDelete();
    await waitFor(() =>
      expect(screen.queryByText(WARNING)).not.toBeInTheDocument(),
    );
  });
});

describe("deleteDevice API contract", () => {
  it("DELETEs /access/devices/{id}/ with the token and no body", async () => {
    const originalFetch = global.fetch;
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: () => Promise.resolve({}),
    });
    global.fetch = fetchMock as unknown as typeof fetch;
    try {
      const realDelete =
        jest.requireActual<typeof import("@/lib/api")>("@/lib/api").deleteDevice;
      await realDelete(4, "tok");

      const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(url).toBe("http://localhost:8000/api/v1/access/devices/4/");
      expect(init.method).toBe("DELETE");
      expect(init.body).toBeUndefined();
      expect((init.headers as Record<string, string>).Authorization).toBe("Token tok");
    } finally {
      global.fetch = originalFetch;
    }
  });
});
