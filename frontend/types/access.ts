/**
 * Access control type definitions — Sprint 8 (issues #23, #25, #26).
 *
 * Field sets mirror the backend `apps/access` serializers exactly:
 * the list endpoints return IDs for related objects (branch, customer,
 * device), so display names are resolved client-side from the
 * branches/customers/devices lists.
 */

// ── Enums (kept as const tuples so zod can reuse them directly) ──

export const ACCESS_VENDORS = [
  "generic",
  "hikvision",
  "zkteco",
  "essl",
  "matrix",
  "supervision",
] as const;
export type AccessVendor = (typeof ACCESS_VENDORS)[number];

export const ACCESS_CONNECTION_TYPES = ["webhook", "agent", "cloud_api"] as const;
export type AccessConnectionType = (typeof ACCESS_CONNECTION_TYPES)[number];

export const ACCESS_CREDENTIAL_TYPES = [
  "fingerprint",
  "face",
  "card",
  "pin",
  "qr",
] as const;
export type AccessCredentialType = (typeof ACCESS_CREDENTIAL_TYPES)[number];

export const ACCESS_EVENT_TYPES = ["entry", "exit", "denied", "error"] as const;
export type AccessEventType = (typeof ACCESS_EVENT_TYPES)[number];

export const ACCESS_OVERRIDE_REASONS = [
  "grace_period",
  "vip",
  "payment_issue",
  "violation",
  "staff",
] as const;
export type AccessOverrideReason = (typeof ACCESS_OVERRIDE_REASONS)[number];

// ── Devices ──────────────────────────────────────────────────────

/** A biometric door device registered at a branch (GET/POST/PATCH /access/devices/). */
export interface AccessDevice {
  id: number;
  branch: number;
  vendor: AccessVendor;
  model: string;
  serial_number: string;
  name: string;
  connection_type: AccessConnectionType;
  api_endpoint: string;
  is_active: boolean;
  last_sync_at: string | null;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Payload for device create/update. */
export interface AccessDeviceFormData {
  branch: number;
  vendor: AccessVendor;
  model: string;
  serial_number: string;
  name: string;
  connection_type: AccessConnectionType;
  api_endpoint: string;
  is_active: boolean;
}

/** POST /access/devices/{id}/test-connection/ result. */
export interface DeviceTestResult {
  online: boolean;
  detail: string;
}

/** POST /access/devices/{id}/sync/ result. */
export interface DeviceSyncResult {
  synced: boolean;
  pushed?: number;
  detail: string;
}

/** POST /access/devices/{id}/fetch-events/ result. */
export interface DeviceEventsResult {
  fetched: boolean;
  recorded: number;
  detail: string;
}

// ── Credentials (enrollment records) ─────────────────────────────

/** A customer's biometric credential on a specific device. */
export interface AccessCredential {
  id: number;
  customer: number;
  device: number;
  credential_type: AccessCredentialType;
  device_user_id: string;
  enrolled_at: string;
  is_active: boolean;
}

/** Body for POST /access/devices/enroll/. */
export interface EnrollCredentialData {
  customer: number;
  device: number;
  credential_type: AccessCredentialType;
  device_user_id: string;
}

/** Response for the enroll action (credential + immediate device sync). */
export interface EnrollCredentialResult {
  credential: AccessCredential;
  sync: DeviceSyncResult;
}

// ── Owner overrides ──────────────────────────────────────────────

/** A grant/deny access override for a customer at a device. */
export interface AccessOverride {
  id: number;
  customer: number;
  device: number;
  allow_access: boolean;
  reason: string;
  reason_notes: string;
  expires_at: string | null;
  created_by: number | null;
}

/** Body for POST /access/overrides/. `expires_at: null` means permanent. */
export interface AccessOverrideFormData {
  customer: number;
  device: number;
  allow_access: boolean;
  reason: AccessOverrideReason | string;
  reason_notes: string;
  expires_at: string | null;
}

// ── Access logs (entry/exit events) ──────────────────────────────

/** An entry/exit event recorded from a device (GET /access/logs/). */
export interface AccessLog {
  id: number;
  device: number;
  customer: number | null;
  device_user_id: string;
  credential_type: AccessCredentialType;
  event_type: AccessEventType;
  event_timestamp: string;
  raw_payload: Record<string, unknown>;
}

// ── Display helpers ──────────────────────────────────────────────

export const VENDOR_LABELS: Record<AccessVendor, string> = {
  generic: "Generic",
  hikvision: "Hikvision",
  zkteco: "ZKTeco",
  essl: "eSSL",
  matrix: "Matrix",
  supervision: "Supervision",
};

export const CONNECTION_TYPE_LABELS: Record<AccessConnectionType, string> = {
  webhook: "Webhook Push",
  agent: "Agent Pull",
  cloud_api: "Cloud Sync",
};

export const CREDENTIAL_TYPE_LABELS: Record<AccessCredentialType, string> = {
  fingerprint: "Fingerprint",
  face: "Face Recognition",
  card: "RFID Card",
  pin: "PIN Code",
  qr: "QR Code",
};

export const OVERRIDE_REASON_LABELS: Record<string, string> = {
  grace_period: "Grace period",
  vip: "VIP",
  payment_issue: "Payment issue",
  violation: "Violation",
  staff: "Staff",
};

/** Select options for the override reason dropdown. */
export const OVERRIDE_REASON_OPTIONS: { value: AccessOverrideReason; label: string }[] =
  ACCESS_OVERRIDE_REASONS.map((value) => ({
    value,
    label: OVERRIDE_REASON_LABELS[value],
  }));

/** Badge metadata for an access event type. */
export function getEventTypeMeta(eventType: AccessEventType): {
  label: string;
  variant: "success" | "info" | "danger" | "warning";
} {
  switch (eventType) {
    case "entry":
      return { label: "Entry", variant: "success" };
    case "exit":
      return { label: "Exit", variant: "info" };
    case "denied":
      return { label: "Denied", variant: "danger" };
    case "error":
      return { label: "Error", variant: "warning" };
  }
}

/**
 * A device counts as online when it is active AND its last_seen_at is
 * fresher than this window (adapters stamp last_seen_at on every
 * successful round-trip).
 */
export const DEVICE_ONLINE_FRESHNESS_MINUTES = 5;

/** True when the device was seen within the freshness window. */
export function isDeviceOnline(
  device: Pick<AccessDevice, "is_active" | "last_seen_at">,
  now: Date = new Date(),
): boolean {
  if (!device.is_active || !device.last_seen_at) return false;
  const seen = new Date(device.last_seen_at).getTime();
  if (Number.isNaN(seen)) return false;
  return now.getTime() - seen < DEVICE_ONLINE_FRESHNESS_MINUTES * 60_000;
}

/** Status badge metadata derived from is_active + last_seen_at freshness. */
export function getDeviceStatus(
  device: Pick<AccessDevice, "is_active" | "last_seen_at">,
  now: Date = new Date(),
): { label: "Online" | "Offline" | "Inactive"; variant: "success" | "danger" | "default" } {
  if (!device.is_active) return { label: "Inactive", variant: "default" };
  return isDeviceOnline(device, now)
    ? { label: "Online", variant: "success" }
    : { label: "Offline", variant: "danger" };
}

/** Format an ISO timestamp for tables; "—" for null/undefined. */
export function formatAccessTimestamp(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}
