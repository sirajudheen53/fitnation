import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WhatsAppConfigForm } from "@/features/settings/components/WhatsAppConfigForm";
import { GupshupConfigForm } from "@/features/settings/components/GupshupConfigForm";
import { WhatsAppChannels } from "@/features/settings/components/WhatsAppChannels";
import {
  fetchTenant,
  fetchNotificationLogs,
  fetchWhatsappStatus,
  sendWhatsappTest,
  updateTenantGupshupConfig,
  updateTenantWhatsappConfig,
  errorMessage,
  unwrapNotificationLogs,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  fetchTenant: jest.fn(),
  fetchNotificationLogs: jest.fn(),
  fetchWhatsappStatus: jest.fn(),
  sendWhatsappTest: jest.fn(),
  updateTenantGupshupConfig: jest.fn(),
  updateTenantWhatsappConfig: jest.fn(),
  unwrapNotificationLogs: jest.fn(
    (res: { results: unknown[] } | unknown[]) => (Array.isArray(res) ? res : res?.results ?? []),
  ),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockedFetchTenant = fetchTenant as jest.Mock;
const mockedFetchNotificationLogs = fetchNotificationLogs as jest.Mock;
const mockedFetchWhatsappStatus = fetchWhatsappStatus as jest.Mock;
const mockedSendWhatsappTest = sendWhatsappTest as jest.Mock;
const mockedUpdate = updateTenantWhatsappConfig as jest.Mock;
const mockedGupshupUpdate = updateTenantGupshupConfig as jest.Mock;
const mockedUnwrapLogs = unwrapNotificationLogs as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
  mockedFetchTenant.mockResolvedValue({});
  mockedFetchWhatsappStatus.mockRejectedValue(new Error("not implemented yet"));
  // Logs default to empty — the "last test" line reads "none yet".
  mockedFetchNotificationLogs.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
});

describe("WhatsAppConfigForm", () => {
  it("starts unconfigured and unchecked against a pre-B9 payload without the WATI fields", async () => {
    render(<WhatsAppConfigForm />);
    expect(await screen.findByTestId("wati-key-missing")).toHaveTextContent("Not configured");
    expect(screen.getByLabelText(/Enable WhatsApp for this gym/i)).not.toBeChecked();
    expect(screen.queryByTestId("whatsapp-usage")).not.toBeInTheDocument();
  });

  it("shows a masked configured state without ever rendering the key value", async () => {
    mockedFetchTenant.mockResolvedValue({
      is_wati_enabled: true,
      wati_endpoint: "https://api.wati.io",
      wati_api_key_configured: true,
    });
    render(<WhatsAppConfigForm />);
    expect(await screen.findByTestId("wati-key-configured")).toHaveTextContent("Configured");
    // The password input is blank — the secret never comes back.
    expect(screen.getByLabelText("WATI API key")).toHaveValue("");
  });

  it("saves the toggle + endpoint and sends the key only when a new one is typed", async () => {
    mockedUpdate.mockResolvedValue({ wati_api_key_configured: true });
    render(<WhatsAppConfigForm />);

    fireEvent.change(await screen.findByLabelText("WATI endpoint"), {
      target: { value: "https://api.wati.io" },
    });
    fireEvent.change(screen.getByLabelText("WATI API key"), { target: { value: "secret-1" } });
    fireEvent.click(screen.getByLabelText(/Enable WhatsApp for this gym/i));
    fireEvent.click(screen.getByRole("button", { name: /Save configuration/i }));

    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith(
        {
          is_wati_enabled: true,
          wati_endpoint: "https://api.wati.io",
          wati_api_key: "secret-1",
        },
        expect.anything(),
      ),
    );
    expect(await screen.findByText("WhatsApp configuration saved.")).toBeInTheDocument();
    // Key field cleared after save (masked again).
    expect(screen.getByLabelText("WATI API key")).toHaveValue("");
  });

  it("omits the key from the payload when left blank (write-only keep-existing)", async () => {
    mockedFetchTenant.mockResolvedValue({
      is_wati_enabled: true,
      wati_endpoint: "https://api.wati.io",
      wati_api_key_configured: true,
    });
    mockedUpdate.mockResolvedValue({});
    render(<WhatsAppConfigForm />);

    await screen.findByTestId("wati-key-configured");
    fireEvent.click(screen.getByRole("button", { name: /Save configuration/i }));

    await waitFor(() =>
      expect(mockedUpdate).toHaveBeenCalledWith(
        { is_wati_enabled: true, wati_endpoint: "https://api.wati.io" },
        expect.anything(),
      ),
    );
  });

  it("sends the test message to the typed phone and reports success", async () => {
    mockedSendWhatsappTest.mockResolvedValue({ status: "sent" });
    render(<WhatsAppConfigForm />);

    await screen.findByTestId("wati-key-missing");
    fireEvent.change(screen.getByLabelText("Phone to message"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: /Send test message/i }));

    await waitFor(() =>
      expect(mockedSendWhatsappTest).toHaveBeenCalledWith("9876543210", expect.anything()),
    );
    expect(await screen.findByText(/Test message sent to \+919876543210/i)).toBeInTheDocument();
  });

  it("surfaces a failed test send without crashing", async () => {
    mockedSendWhatsappTest.mockResolvedValue({ status: "failed", detail: "WATI 500" });
    render(<WhatsAppConfigForm />);

    await screen.findByTestId("wati-key-missing");
    fireEvent.change(screen.getByLabelText("Phone to message"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: /Send test message/i }));

    expect(await screen.findByText(/status "failed"/i)).toBeInTheDocument();
  });

  it("shows today's usage counters when the status endpoint exists (B9)", async () => {
    mockedFetchWhatsappStatus.mockResolvedValue({
      otp_sent_today: 12,
      invites_sent_today: 3,
      daily_cap: 200,
    });
    render(<WhatsAppConfigForm />);
    const usage = await screen.findByTestId("whatsapp-usage");
    expect(usage).toHaveTextContent(/12 OTPs · 3 invites · cap 200/);
  });
});

describe("GupshupConfigForm (issue #67)", () => {
  it("starts unconfigured and unchecked against a payload without the Gupshup fields", async () => {
    render(<GupshupConfigForm />);
    expect(await screen.findByTestId("gupshup-key-missing")).toHaveTextContent("Not configured");
    expect(screen.getByLabelText(/Enable Gupshup for this gym/i)).not.toBeChecked();
  });

  it("shows a masked configured state without ever rendering the key value", async () => {
    mockedFetchTenant.mockResolvedValue({
      is_gupshup_enabled: true,
      gupshup_source: "917899876543",
      gupshup_app_name: "FitNation App",
      gupshup_api_key_configured: true,
    });
    render(<GupshupConfigForm />);
    expect(await screen.findByTestId("gupshup-key-configured")).toHaveTextContent("Configured");
    // The password input is blank — the secret never comes back.
    expect(screen.getByLabelText("Gupshup API key")).toHaveValue("");
    expect(screen.getByLabelText("Gupshup source number")).toHaveValue("917899876543");
    expect(screen.getByLabelText("Gupshup app name")).toHaveValue("FitNation App");
  });

  it("saves toggle + source + app name and sends the key only when a new one is typed", async () => {
    mockedGupshupUpdate.mockResolvedValue({ gupshup_api_key_configured: true });
    render(<GupshupConfigForm />);

    fireEvent.change(await screen.findByLabelText("Gupshup source number"), {
      target: { value: "917899876543" },
    });
    fireEvent.change(screen.getByLabelText("Gupshup app name"), {
      target: { value: "FitNation App" },
    });
    fireEvent.change(screen.getByLabelText("Gupshup API key"), { target: { value: "secret-1" } });
    fireEvent.click(screen.getByLabelText(/Enable Gupshup for this gym/i));
    fireEvent.click(screen.getByRole("button", { name: /Save configuration/i }));

    await waitFor(() =>
      expect(mockedGupshupUpdate).toHaveBeenCalledWith(
        {
          is_gupshup_enabled: true,
          gupshup_source: "917899876543",
          gupshup_app_name: "FitNation App",
          gupshup_api_key: "secret-1",
        },
        expect.anything(),
      ),
    );
    expect(await screen.findByText("Gupshup configuration saved.")).toBeInTheDocument();
    // Key field cleared after save (masked again).
    expect(screen.getByLabelText("Gupshup API key")).toHaveValue("");
  });

  it("omits the key from the payload when left blank (write-only keep-existing)", async () => {
    mockedFetchTenant.mockResolvedValue({
      is_gupshup_enabled: true,
      gupshup_source: "917899876543",
      gupshup_app_name: "FitNation App",
      gupshup_api_key_configured: true,
    });
    mockedGupshupUpdate.mockResolvedValue({});
    render(<GupshupConfigForm />);

    await screen.findByTestId("gupshup-key-configured");
    fireEvent.click(screen.getByRole("button", { name: /Save configuration/i }));

    await waitFor(() =>
      expect(mockedGupshupUpdate).toHaveBeenCalledWith(
        {
          is_gupshup_enabled: true,
          gupshup_source: "917899876543",
          gupshup_app_name: "FitNation App",
        },
        expect.anything(),
      ),
    );
  });

  it("sends the test message through Gupshup and reports success", async () => {
    mockedSendWhatsappTest.mockResolvedValue({ status: "sent" });
    render(<GupshupConfigForm />);

    await screen.findByTestId("gupshup-key-missing");
    fireEvent.change(screen.getByLabelText("Phone to message"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: /Send test message/i }));

    await waitFor(() =>
      expect(mockedSendWhatsappTest).toHaveBeenCalledWith(
        "9876543210",
        expect.anything(),
        "gupshup",
      ),
    );
    expect(await screen.findByText(/Test message sent to \+919876543210/i)).toBeInTheDocument();
  });

  it("surfaces a failed Gupshup test send without crashing", async () => {
    mockedSendWhatsappTest.mockResolvedValue({ status: "failed", detail: "Gupshup 401" });
    render(<GupshupConfigForm />);

    await screen.findByTestId("gupshup-key-missing");
    fireEvent.change(screen.getByLabelText("Phone to message"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: /Send test message/i }));

    expect(await screen.findByText(/status "failed"/i)).toBeInTheDocument();
  });

  it("shows the provider's verbatim acceptance after a successful send (issue #73)", async () => {
    // SUCCESS reflects the provider's own response (status + message id),
    // not merely an HTTP 200.
    mockedSendWhatsappTest.mockResolvedValue({
      status: "sent",
      detail: "",
      provider: "gupshup",
      provider_status: "submitted",
      message_id: "gs-ack-1",
    });
    render(<GupshupConfigForm />);

    await screen.findByTestId("gupshup-key-missing");
    fireEvent.change(screen.getByLabelText("Phone to message"), { target: { value: "9876543210" } });
    fireEvent.click(screen.getByRole("button", { name: /Send test message/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Test message sent to \+919876543210/i);
    expect(alert).toHaveTextContent(/Provider accepted it \(status: submitted\)/i);
    expect(alert).toHaveTextContent(/Message id: gs-ack-1/i);
  });
});

describe("WhatsAppChannels — settings-index cards (issue #73)", () => {
  const configuredTenant = {
    is_wati_enabled: false,
    wati_endpoint: "",
    wati_api_key_configured: false,
    is_gupshup_enabled: true,
    gupshup_source: "918281265866",
    gupshup_app_name: "getfitwithus",
    gupshup_api_key_configured: true,
  };

  it("shows the live configured state matching the saved backend payload", async () => {
    mockedFetchTenant.mockResolvedValue(configuredTenant);
    // The last gupshup welcome test send — sent, from today's audit log.
    mockedFetchNotificationLogs.mockImplementation((_t, params) =>
      Promise.resolve({
        count: params?.provider === "gupshup" ? 1 : 0,
        next: null,
        previous: null,
        results: params?.provider === "gupshup" ? [
          {
            id: 40,
            notification_type: "welcome",
            status: "sent",
            provider: "gupshup",
            channel: "whatsapp",
            content: "Welcome to Hash Fit",
            wati_message_id: "",
            error_message: "",
            created_at: "2026-10-24T14:18:11.212272Z",
            updated_at: "2026-10-24T14:18:11.212272Z",
          },
        ] : [],
      }),
    );
    render(<WhatsAppChannels />);

    // Gupshup card: enabled + saved details + key state, live from the API.
    expect(await screen.findByTestId("gupshup-channel-active")).toHaveTextContent("Enabled");
    const gupshupDetails = screen.getAllByTestId("gupshup-channel-detail");
    expect(gupshupDetails.some((el) => el.textContent === "Source: 918281265866")).toBe(true);
    expect(gupshupDetails.some((el) => el.textContent === "App: getfitwithus")).toBe(true);
    expect(screen.getByTestId("gupshup-channel-key-configured")).toHaveTextContent("Configured");
    expect(screen.getByTestId("gupshup-channel-last-test")).toHaveTextContent(/Last test: sent/);

    // WATI card stays honest: disabled, no endpoint, no key.
    expect(screen.getByTestId("wati-channel-inactive")).toHaveTextContent("Not enabled");
    expect(screen.getByTestId("wati-channel-key-missing")).toHaveTextContent("Not configured");
    expect(screen.getByTestId("wati-channel-last-test")).toHaveTextContent(/none yet/);

    // Both cards link through to their dedicated config pages.
    const gupshupCard = screen.getByTestId("gupshup-channel-card").closest("a");
    expect(gupshupCard).toHaveAttribute("href", "/settings/gupshup");
    const watiCard = screen.getByTestId("wati-channel-card").closest("a");
    expect(watiCard).toHaveAttribute("href", "/settings/whatsapp");
  });

  it("starts 'Not enabled' against a payload without the channel fields", async () => {
    mockedFetchTenant.mockResolvedValue({});
    render(<WhatsAppChannels />);

    expect(await screen.findByTestId("wati-channel-inactive")).toHaveTextContent("Not enabled");
    expect(screen.getByTestId("gupshup-channel-inactive")).toHaveTextContent("Not enabled");
    expect(screen.getByTestId("wati-channel-key-missing")).toBeInTheDocument();
    expect(screen.getByTestId("gupshup-channel-key-missing")).toBeInTheDocument();
  });

  it("shows the last failed test with the provider's error text verbatim", async () => {
    mockedFetchTenant.mockResolvedValue(configuredTenant);
    mockedFetchNotificationLogs.mockImplementation(
      (_token: string, params?: { provider?: string }) =>
        Promise.resolve({
          count: params?.provider === "gupshup" ? 1 : 0,
          next: null,
          previous: null,
          results:
            params?.provider === "gupshup"
              ? [
                  {
                    id: 41,
                    notification_type: "welcome",
                    status: "failed",
                    provider: "gupshup",
                    channel: "whatsapp",
                    content: "Welcome to Hash Fit",
                    wati_message_id: "",
                    error_message: 'Invalid template name "fitnation_otp"',
                    created_at: "2026-10-24T14:20:11.212272Z",
                    updated_at: "2026-10-24T14:20:11.212272Z",
                  },
                ]
              : [],
        }),
    );
    render(<WhatsAppChannels />);

    const lastTest = await screen.findByTestId("gupshup-channel-last-test");
    expect(lastTest).toHaveTextContent(/failed/);
    expect(lastTest).toHaveTextContent(/Invalid template name/i);
  });

  it("degrades gracefully when the logs endpoint is unavailable", async () => {
    mockedFetchTenant.mockResolvedValue(configuredTenant);
    mockedFetchNotificationLogs.mockRejectedValue(new Error("403"));
    render(<WhatsAppChannels />);

    expect(await screen.findByTestId("gupshup-channel-active")).toBeInTheDocument();
    expect(screen.getByTestId("gupshup-channel-last-test")).toHaveTextContent(/Last test: none yet/);
  });
});
