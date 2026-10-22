import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
import { BiometricTab } from "@/features/access/components/BiometricTab";
import {
  enrollBiometricCredential,
  deactivateBiometricCredential,
  fetchAccessCredentials,
  fetchCustomerAttendance,
  fetchDevices,
  errorMessage,
} from "@/lib/api";
import type { Customer } from "@/types/customer";
import type { AccessCredential, AccessDevice } from "@/types/access";
import type { AttendanceRecord } from "@/types/attendance";
import {
  formatAttendanceDate,
  formatAttendanceTime,
  recentAttendance,
} from "@/features/access/components/BiometricTab";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  enrollBiometricCredential: jest.fn(),
  deactivateBiometricCredential: jest.fn(),
  fetchAccessCredentials: jest.fn(),
  fetchCustomerAttendance: jest.fn(),
  fetchDevices: jest.fn(),
}));

const mockedEnroll = enrollBiometricCredential as jest.Mock;
const mockedDeactivate = deactivateBiometricCredential as jest.Mock;
const mockedFetchCredentials = fetchAccessCredentials as jest.Mock;
const mockedFetchAttendance = fetchCustomerAttendance as jest.Mock;
const mockedFetchDevices = fetchDevices as jest.Mock;
const mockedErrorMessage = errorMessage as jest.Mock;

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const customer = { id: 1 } as Customer;

const devices: AccessDevice[] = [
  {
    id: 5,
    branch: 2,
    vendor: "zkteco",
    model: "uFace 800",
    serial_number: "ZK-001",
    name: "Front Door",
    connection_type: "webhook",
    api_endpoint: "",
    is_active: true,
    last_sync_at: null,
    last_seen_at: null,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  },
  {
    ...({} as AccessDevice),
    id: 6,
    name: "Old Gate",
    is_active: false,
  },
];

const credentials: AccessCredential[] = [
  {
    id: 101,
    customer: 1,
    device: 5,
    credential_type: "fingerprint",
    device_user_id: "42",
    enrolled_at: "2026-10-20T09:00:00Z",
    is_active: true,
  },
  {
    id: 102,
    customer: 1,
    device: 6,
    credential_type: "face",
    device_user_id: "42",
    enrolled_at: "2026-10-01T09:00:00Z",
    is_active: false,
  },
];

const attendance: AttendanceRecord[] = [
  {
    id: 501,
    customer: 1,
    person_id: 1,
    person_name: "Asha Nair",
    person_type: "customer",
    branch_id: 2,
    branch_name: "HQ",
    check_in_time: "2026-10-22T03:35:00Z",
    check_out_time: "2026-10-22T05:05:00Z",
    status: "present",
    date: "2026-10-22",
    created_at: "2026-10-22T03:35:00Z",
    updated_at: "2026-10-22T05:05:00Z",
  },
  {
    id: 500,
    customer: 1,
    person_id: 1,
    person_name: "Asha Nair",
    person_type: "customer",
    branch_id: 2,
    branch_name: "HQ",
    check_in_time: "2026-10-21T04:00:00Z",
    check_out_time: null,
    status: "present",
    date: "2026-10-21",
    created_at: "2026-10-21T04:00:00Z",
    updated_at: "2026-10-21T04:00:00Z",
  },
];

function mockLoaded() {
  mockedFetchCredentials.mockResolvedValue(credentials);
  mockedFetchDevices.mockResolvedValue(devices);
  mockedFetchAttendance.mockResolvedValue({ count: 2, next: null, previous: null, results: attendance });
}

beforeEach(() => {
  jest.clearAllMocks();
  // clearAllMocks keeps mockReturnValue set by earlier tests — restore the default.
  mockedErrorMessage.mockImplementation((err) => (err instanceof Error ? err.message : "error"));
  mockLoaded();
});

async function renderTab() {
  render(<BiometricTab customer={customer} />);
  await waitFor(() => expect(screen.getByTestId("credential-row-101")).toBeInTheDocument());
}

describe("BiometricTab credentials list", () => {
  it("lists credentials with device name, credential type, device user ID and state", async () => {
    await renderTab();
    const row = screen.getByTestId("credential-row-101");
    expect(within(row).getByText("Front Door")).toBeInTheDocument();
    expect(within(row).getByText("Fingerprint")).toBeInTheDocument();
    expect(within(row).getByText("42")).toBeInTheDocument();
    expect(within(row).getByText("Active")).toBeInTheDocument();
    expect(within(row).getByTestId("deactivate-credential-101")).toBeInTheDocument();

    const revoked = screen.getByTestId("credential-row-102");
    expect(within(revoked).getByText("Deactivated")).toBeInTheDocument();
    expect(within(revoked).queryByRole("button")).not.toBeInTheDocument();
  });

  it("shows the credentials empty state", async () => {
    mockedFetchCredentials.mockResolvedValue([]);
    render(<BiometricTab customer={customer} />);
    await waitFor(() =>
      expect(screen.getByTestId("credentials-empty")).toHaveTextContent(
        "No biometric credentials enrolled",
      ),
    );
  });

  it("warns and disables enroll when no active devices exist", async () => {
    mockedFetchDevices.mockResolvedValue([devices[1]]);
    render(<BiometricTab customer={customer} />);
    await waitFor(() => expect(screen.getByTestId("biometric-enroll-btn")).toBeDisabled());
    expect(
      screen.getByText(/No active devices registered yet/i),
    ).toBeInTheDocument();
  });

  it("shows the load error", async () => {
    mockedErrorMessage.mockReturnValue("Tenant mismatch");
    mockedFetchCredentials.mockRejectedValue(new Error("boom"));
    render(<BiometricTab customer={customer} />);
    await waitFor(() => expect(screen.getByText("Tenant mismatch")).toBeInTheDocument());
  });
});

describe("BiometricTab enroll flow", () => {
  it("enrolls without sending device_user_id and shows the returned ID prominently", async () => {
    mockedEnroll.mockResolvedValue({
      credential: {
        id: 201,
        customer: 1,
        device: 5,
        credential_type: "face",
        device_user_id: "77",
        enrolled_at: "2026-10-22T10:00:00Z",
        is_active: true,
      },
      sync: { synced: true, pushed: 3, detail: "Queued 3 users" },
    });
    await renderTab();

    fireEvent.click(screen.getByTestId("biometric-enroll-btn"));
    expect(screen.getByTestId("biometric-enroll-dialog")).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText("Device"), { target: { value: "5" } });
    fireEvent.change(screen.getByLabelText("Credential type"), { target: { value: "face" } });
    fireEvent.click(screen.getByTestId("biometric-enroll-submit"));

    await waitFor(() => expect(mockedEnroll).toHaveBeenCalled());
    expect(mockedEnroll).toHaveBeenCalledWith(
      { customer: 1, device: 5, credential_type: "face" },
      "test-token",
    );
    expect(mockedEnroll.mock.calls[0][0]).not.toHaveProperty("device_user_id");

    await waitFor(() => expect(screen.getByTestId("enroll-result")).toBeInTheDocument());
    expect(screen.getByTestId("enrolled-device-user-id")).toHaveTextContent("77");
    expect(
      screen.getByText("Type this exact ID on the device during enrollment."),
    ).toBeInTheDocument();
    // The dialog closed and the new credential joined the list.
    expect(screen.queryByTestId("biometric-enroll-dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(screen.getByTestId("credential-row-201")).toBeInTheDocument());
  });

  it("keeps the dialog open and shows the API error when enroll fails", async () => {
    mockedErrorMessage.mockReturnValue("Device offline");
    mockedEnroll.mockRejectedValue(new Error("boom"));
    await renderTab();

    fireEvent.click(screen.getByTestId("biometric-enroll-btn"));
    fireEvent.change(screen.getByLabelText("Device"), { target: { value: "5" } });
    fireEvent.click(screen.getByTestId("biometric-enroll-submit"));

    await waitFor(() =>
      expect(within(screen.getByTestId("biometric-enroll-dialog")).getByText("Device offline")).toBeInTheDocument(),
    );
    expect(screen.getByTestId("biometric-enroll-dialog")).toBeInTheDocument();
    expect(screen.queryByTestId("enroll-result")).not.toBeInTheDocument();
  });

  it("asks for a device before calling the API", async () => {
    await renderTab();

    fireEvent.click(screen.getByTestId("biometric-enroll-btn"));
    fireEvent.click(screen.getByTestId("biometric-enroll-submit"));

    // "Select a device" also matches the empty <option>, so assert via the alert role.
    const alert = await waitFor(() => {
      const alertEl = within(screen.getByTestId("biometric-enroll-dialog")).getByRole("alert");
      expect(alertEl).toHaveTextContent("Select a device");
      return alertEl;
    });
    expect(alert).toBeInTheDocument();
    expect(mockedEnroll).not.toHaveBeenCalled();
  });
});

describe("BiometricTab deactivate flow", () => {
  it("deactivates after confirm and flips the row state", async () => {
    mockedDeactivate.mockResolvedValue({ ...credentials[0], is_active: false });
    await renderTab();

    fireEvent.click(screen.getByTestId("deactivate-credential-101"));
    const confirm = screen.getByTestId("deactivate-confirm");
    expect(
      within(confirm).getByText(/Deactivate credential\?/),
    ).toBeInTheDocument();

    fireEvent.click(within(confirm).getByRole("button", { name: "Deactivate" }));
    await waitFor(() => expect(mockedDeactivate).toHaveBeenCalledWith(101, "test-token"));

    await waitFor(() => {
      const row = screen.getByTestId("credential-row-101");
      expect(within(row).getByText("Deactivated")).toBeInTheDocument();
    });
    expect(screen.queryByTestId("deactivate-confirm")).not.toBeInTheDocument();
  });

  it("keeps the credential active when the confirm is cancelled", async () => {
    await renderTab();

    fireEvent.click(screen.getByTestId("deactivate-credential-101"));
    fireEvent.click(within(screen.getByTestId("deactivate-confirm")).getByRole("button", { name: "Cancel" }));

    expect(mockedDeactivate).not.toHaveBeenCalled();
    expect(screen.queryByTestId("deactivate-confirm")).not.toBeInTheDocument();
    expect(within(screen.getByTestId("credential-row-101")).getByText("Active")).toBeInTheDocument();
  });

  it("surfaces a deactivate failure via the toast path without crashing", async () => {
    mockedDeactivate.mockRejectedValue(new Error("403"));
    await renderTab();

    fireEvent.click(screen.getByTestId("deactivate-credential-101"));
    fireEvent.click(
      within(screen.getByTestId("deactivate-confirm")).getByRole("button", { name: "Deactivate" }),
    );
    await waitFor(() => expect(mockedErrorMessage).toHaveBeenCalled());
    // Row stays active when the call fails.
    expect(within(screen.getByTestId("credential-row-101")).getByText("Active")).toBeInTheDocument();
  });
});

describe("BiometricTab attendance history", () => {
  it("lists recent attendance newest first with date, check-in and check-out", async () => {
    await renderTab();
    const rows = screen.getAllByTestId(/^attendance-row-/);
    expect(rows).toHaveLength(2);
    expect(rows[0]).toHaveAttribute("data-testid", "attendance-row-501");

    expect(within(rows[0]).getByText("22 Oct 2026")).toBeInTheDocument();
    // Exact IST renderings — 03:35Z/05:05Z pinned via timeZone in the component,
    // so these hold under any runner clock (CI runs TZ=UTC).
    expect(within(rows[0]).getByText("9:05 am")).toBeInTheDocument();
    expect(within(rows[0]).getByText("10:35 am")).toBeInTheDocument();
    // Open session (no check-out yet) renders an em dash.
    expect(within(rows[1]).getByText("—")).toBeInTheDocument();
  });

  it("caps the list at the 10 most recent records", () => {
    const many: AttendanceRecord[] = Array.from({ length: 14 }, (_, i) => ({
      ...attendance[0],
      id: i + 1,
      date: `2026-09-${String(i + 1).padStart(2, "0")}`,
    }));
    expect(recentAttendance(many)).toHaveLength(10);
    expect(recentAttendance(many)[0].date).toBe("2026-09-14");
  });

  it("shows the attendance empty state", async () => {
    mockedFetchAttendance.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    render(<BiometricTab customer={customer} />);
    await waitFor(() =>
      expect(screen.getByTestId("attendance-empty")).toHaveTextContent(
        "No attendance records for this customer yet.",
      ),
    );
  });
});

describe("attendance formatting helpers", () => {
  it("formats dates as day-month-year in IST", () => {
    expect(formatAttendanceDate("2026-10-22")).toBe("22 Oct 2026");
    expect(formatAttendanceDate("not-a-date")).toBe("not-a-date");
  });

  it("formats times in IST and falls back to an em dash", () => {
    expect(formatAttendanceTime("2026-10-22T03:35:00Z")).toBe("9:05 am");
    expect(formatAttendanceTime(null)).toBe("—");
    expect(formatAttendanceTime(undefined)).toBe("—");
  });
});
