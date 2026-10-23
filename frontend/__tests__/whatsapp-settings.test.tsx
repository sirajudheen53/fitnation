import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { WhatsAppConfigForm } from "@/features/settings/components/WhatsAppConfigForm";
import { GupshupConfigForm } from "@/features/settings/components/GupshupConfigForm";
import {
  fetchTenant,
  fetchWhatsappStatus,
  sendWhatsappTest,
  updateTenantGupshupConfig,
  updateTenantWhatsappConfig,
  errorMessage,
} from "@/lib/api";

jest.mock("@/lib/api", () => ({
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
  fetchTenant: jest.fn(),
  fetchWhatsappStatus: jest.fn(),
  sendWhatsappTest: jest.fn(),
  updateTenantGupshupConfig: jest.fn(),
  updateTenantWhatsappConfig: jest.fn(),
}));

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(() => "test-token"),
}));

const mockedFetchTenant = fetchTenant as jest.Mock;
const mockedFetchWhatsappStatus = fetchWhatsappStatus as jest.Mock;
const mockedSendWhatsappTest = sendWhatsappTest as jest.Mock;
const mockedUpdate = updateTenantWhatsappConfig as jest.Mock;
const mockedGupshupUpdate = updateTenantGupshupConfig as jest.Mock;

beforeEach(() => {
  jest.clearAllMocks();
  mockedFetchTenant.mockResolvedValue({});
  mockedFetchWhatsappStatus.mockRejectedValue(new Error("not implemented yet"));
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
});
