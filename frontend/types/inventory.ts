/**
 * Equipment & inventory type definitions — FBOS-033-FE (issue #6).
 *
 * Field sets mirror the backend `apps/inventory` serializers exactly:
 * Equipment → InventoryItem is OneToOne, MaintenanceLog is FK to
 * equipment. List endpoints are paginated ({count, results}).
 */

// ── Enums ──

export const MAINTENANCE_STATUSES = ["scheduled", "completed", "cancelled"] as const;
export type MaintenanceStatus = (typeof MAINTENANCE_STATUSES)[number];

// ── Equipment ──

/** A gym equipment unit (GET/POST/PATCH /inventory/equipment/). */
export interface Equipment {
  id: number;
  uuid: string;
  name: string;
  description: string;
  serial_number: string;
  purchase_date: string | null;
  created_at: string;
  updated_at: string;
}

/** Body for POST/PATCH /inventory/equipment/. */
export interface EquipmentFormData {
  name: string;
  description: string;
  serial_number: string;
  purchase_date: string | null;
}

// ── Inventory (stock per equipment) ──

/** Stock record for an equipment unit (GET/POST /inventory/inventory-items/). */
export interface InventoryItem {
  id: number;
  equipment: number;
  equipment_name: string;
  stock_quantity: number;
  low_stock_threshold: number;
  track_inventory: boolean;
  /** Computed server-side: stock below threshold. */
  is_low_stock: boolean;
  created_at: string;
  updated_at: string;
}

/** Body for POST/PATCH /inventory/inventory-items/. */
export interface InventoryItemFormData {
  equipment: number;
  stock_quantity: number;
  low_stock_threshold: number;
  track_inventory: boolean;
}

// ── Maintenance logs ──

/** A maintenance event on an equipment unit (GET/POST /inventory/maintenance-logs/). */
export interface MaintenanceLog {
  id: number;
  equipment: number;
  equipment_name: string;
  performed_at: string;
  description: string;
  status: (typeof MAINTENANCE_STATUSES)[number];
  created_at: string;
  updated_at: string;
}

/** Body for POST /inventory/maintenance-logs/. */
export interface MaintenanceLogFormData {
  equipment: number;
  performed_at: string;
  description: string;
  status: (typeof MAINTENANCE_STATUSES)[number];
}

// ── Label helpers ──

export const MAINTENANCE_STATUS_LABELS: Record<string, string> = {
  scheduled: "Scheduled",
  completed: "Completed",
  cancelled: "Cancelled",
};