/**
 * Payment & Invoice type definitions — FBOS-005.
 */

export type PaymentMethod = "cash" | "card" | "upi" | "bank_transfer" | "other";

export type PaymentStatus = "pending" | "completed" | "failed" | "refunded";

export type InvoiceStatus = "draft" | "issued" | "paid" | "overdue" | "cancelled";

export interface Payment {
  id: number;
  customer_id: number;
  customer_name: string;
  amount: string;
  method: PaymentMethod;
  status: PaymentStatus;
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
  membership_id?: number;
  notes?: string;
  payment_date: string;
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

export interface RevenueSummary {
  today: number;
  this_week: number;
  this_month: number;
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
