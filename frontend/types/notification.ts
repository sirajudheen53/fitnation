/**
 * Wati WhatsApp notification type definitions — FBOS-022.
 */

export type NotificationStatus = "sent" | "failed" | "pending" | "skipped";
export type NotificationType =
  | "check_in"
  | "membership_expiry"
  | "workout_assigned"
  | "payment_received";

/** Wati configuration for the tenant (settings endpoint). */
export interface WatiSettings {
  is_wati_enabled: boolean;
  wati_endpoint: string;
  wati_api_key_configured: boolean;
}

/** Payload to update Wati settings (api key is write-only on the backend). */
export interface WatiSettingsUpdate {
  wati_api_key?: string;
  wati_endpoint?: string;
  is_wati_enabled?: boolean;
}

/** A single notification log entry. */
export interface NotificationLog {
  id: number;
  customer: number | null;
  customer_name: string;
  notification_type: NotificationType;
  status: NotificationStatus;
  content: string;
  wati_message_id: string;
  error_message: string;
  created_at: string;
  updated_at: string;
}

export interface NotificationLogListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: NotificationLog[];
}

/** Response from the test-notification endpoint. */
export interface TestNotificationResult {
  status: NotificationStatus;
  message?: string;
  wati_message_id?: string;
  error_message?: string;
}

/** Human-readable labels + badge variant for each notification status. */
export function getNotificationStatusMeta(
  status: NotificationStatus,
): { label: string; variant: "success" | "danger" | "warning" | "default" } {
  switch (status) {
    case "sent":
      return { label: "Sent", variant: "success" };
    case "failed":
      return { label: "Failed", variant: "danger" };
    case "pending":
      return { label: "Pending", variant: "warning" };
    case "skipped":
      return { label: "Skipped", variant: "default" };
    default:
      return { label: status, variant: "default" };
  }
}

/** Human-readable labels for each notification type. */
export function getNotificationTypeLabel(type: NotificationType): string {
  switch (type) {
    case "check_in":
      return "Check-in";
    case "membership_expiry":
      return "Membership expiry";
    case "workout_assigned":
      return "Workout assigned";
    case "payment_received":
      return "Payment received";
    default:
      return type;
  }
}
