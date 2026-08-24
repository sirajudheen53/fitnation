import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { NotificationSettingsForm } from "@/features/notifications/components/NotificationSettingsForm";
import {
  NotificationLogsTable,
  formatLogTimestamp,
} from "@/features/notifications/components/NotificationLogsTable";
import { LogDetailModal } from "@/features/notifications/components/LogDetailModal";
import {
  getNotificationStatusMeta,
  getNotificationTypeLabel,
} from "@/types/notification";
import type { NotificationLog, WatiSettings } from "@/types/notification";

const baseSettings: WatiSettings = {
  is_wati_enabled: true,
  wati_endpoint: "https://api.wati.io/api/v1",
  wati_api_key_configured: true,
};

const baseLog: NotificationLog = {
  id: 1,
  customer: 10,
  customer_name: "Arjun Kumar",
  notification_type: "check_in",
  status: "sent",
  content: "Hi Arjun, you've checked in at FitNation. Keep it up! 💪",
  wati_message_id: "wa-123",
  error_message: "",
  created_at: "2026-08-25T10:30:00Z",
  updated_at: "2026-08-25T10:30:00Z",
};

describe("notification type helpers", () => {
  it("returns human-readable labels for each status", () => {
    expect(getNotificationStatusMeta("sent")).toEqual({ label: "Sent", variant: "success" });
    expect(getNotificationStatusMeta("failed")).toEqual({ label: "Failed", variant: "danger" });
    expect(getNotificationStatusMeta("pending")).toEqual({ label: "Pending", variant: "warning" });
    expect(getNotificationStatusMeta("skipped")).toEqual({ label: "Skipped", variant: "default" });
  });

  it("returns labels for each notification type", () => {
    expect(getNotificationTypeLabel("check_in")).toBe("Check-in");
    expect(getNotificationTypeLabel("membership_expiry")).toBe("Membership expiry");
    expect(getNotificationTypeLabel("workout_assigned")).toBe("Workout assigned");
    expect(getNotificationTypeLabel("payment_received")).toBe("Payment received");
  });
});

describe("formatLogTimestamp", () => {
  it("formats a valid ISO timestamp", () => {
    const formatted = formatLogTimestamp("2026-08-25T10:30:00Z");
    expect(formatted).toContain("2026");
    expect(formatted).toContain("Aug");
  });

  it("returns em dash for null or invalid timestamps", () => {
    expect(formatLogTimestamp(null)).toBe("—");
    expect(formatLogTimestamp("not-a-date")).toBe("—");
  });
});

describe("NotificationSettingsForm", () => {
  it("renders connection status as enabled when Wati is on", () => {
    render(
      <NotificationSettingsForm
        settings={baseSettings}
        onSave={jest.fn()}
        onTest={jest.fn()}
      />,
    );
    expect(screen.getByText("WhatsApp notifications enabled")).toBeInTheDocument();
    expect(screen.getByText("Connected")).toBeInTheDocument();
    expect(screen.getByText("API key configured")).toBeInTheDocument();
  });

  it("shows disconnected state when Wati is disabled", () => {
    render(
      <NotificationSettingsForm
        settings={{ ...baseSettings, is_wati_enabled: false }}
        onSave={jest.fn()}
        onTest={jest.fn()}
      />,
    );
    expect(screen.getByText("WhatsApp notifications disabled")).toBeInTheDocument();
    expect(screen.getByText("Disconnected")).toBeInTheDocument();
  });

  it("masks the API key input as password", () => {
    render(
      <NotificationSettingsForm settings={baseSettings} onSave={jest.fn()} onTest={jest.fn()} />,
    );
    const keyInput = screen.getByLabelText("Wati API Key");
    expect(keyInput).toHaveAttribute("type", "password");
  });

  it("submits saved settings with the enabled toggle state", async () => {
    const onSave = jest.fn();
    render(
      <NotificationSettingsForm
        settings={baseSettings}
        onSave={onSave}
        onTest={jest.fn()}
      />,
    );
    fireEvent.click(screen.getByText("Save settings"));
    await waitFor(() => expect(onSave).toHaveBeenCalledTimes(1));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ is_wati_enabled: true }),
    );
  });
});

describe("NotificationLogsTable", () => {
  it("renders log rows with customer, type, status and timestamp", () => {
    render(<NotificationLogsTable logs={[baseLog]} onRowClick={jest.fn()} />);
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.getByText("Check-in")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
  });

  it("calls onRowClick when a row is clicked", () => {
    const onRowClick = jest.fn();
    render(<NotificationLogsTable logs={[baseLog]} onRowClick={onRowClick} />);
    fireEvent.click(screen.getByText("Arjun Kumar"));
    expect(onRowClick).toHaveBeenCalledWith(baseLog);
  });
});

describe("LogDetailModal", () => {
  it("renders nothing when no log is selected", () => {
    const { container } = render(<LogDetailModal log={null} onClose={jest.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows message content, error and close button", () => {
    const onClose = jest.fn();
    render(<LogDetailModal log={baseLog} onClose={onClose} />);
    expect(screen.getByText("Notification detail")).toBeInTheDocument();
    expect(screen.getByText(/you've checked in/)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText("Close"));
    expect(onClose).toHaveBeenCalled();
  });

  it("displays error message when present", () => {
    render(
      <LogDetailModal
        log={{ ...baseLog, status: "failed", error_message: "401 Unauthorized" }}
        onClose={jest.fn()}
      />,
    );
    expect(screen.getByText("401 Unauthorized")).toBeInTheDocument();
  });
});
