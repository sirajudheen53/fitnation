/**
 * Payment & Invoice type definitions — FBOS-005.
 */

export type PaymentMethod = "cash" | "card" | "upi" | "bank_transfer" | "other";

export type PaymentStatus = "pending" | "completed" | "failed" | "refunded";

/** What the payment is for: a membership charge or an admission fee (msg 2438). */
export type PaymentKind = "membership" | "admission";

export type InvoiceStatus = "draft" | "issued" | "paid" | "overdue" | "cancelled";

export interface Payment {
  id: number;
  customer_id: number;
  customer_name: string;
  amount: string;
  method: PaymentMethod;
  status: PaymentStatus;
  /** Defaults to "membership" backend-side; admission fees carry kind=admission. */
  kind: PaymentKind;
  membership_id: number | null;
  invoice_id: number | null;
  notes: string | null;
  payment_date: string;
  created_at: string;
  updated_at: string;
}

export interface PaymentFormData {
  customer_id: number;
  amount: number;
  method: PaymentMethod;
  status?: PaymentStatus;
  kind?: PaymentKind;
  membership_id?: number;
  notes?: string;
  /** Optional: the backend stamps paid_at when a payment is completed. */
  payment_date?: string;
}

export interface Invoice {
  id: number;
  invoice_number: string;
  customer_id: number;
  customer_name: string;
  amount: string;
  tax_amount: string;
  total_amount: string;
  status: InvoiceStatus;
  issue_date: string;
  due_date: string | null;
  paid_date: string | null;
  payment_id: number | null;
  created_at: string;
  updated_at: string;
}

/** One revenue split (today / week / month totals). */
export interface RevenueSplit {
  today: number;
  this_week: number;
  this_month: number;
}

export interface RevenueSummary {
  today: number;
  this_week: number;
  this_month: number;
  /** Additive (msg 2438): admission-kind completed payments, same split. */
  admission?: RevenueSplit;
}

export interface PaymentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Payment[];
}

export interface InvoiceListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Invoice[];
}
