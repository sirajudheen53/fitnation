/**
 * FBOS-020 — Razorpay payment integration types.
 *
 * These types model the actual backend contract exposed by Forge's
 * ``apps/payments`` (RazorpayOrderView, RazorpayVerifyView, RazorpayConfigView
 * and the Payment/Invoice serializers), which differ from the legacy Sprint 2
 * manual-payment types in ``types/payment.ts``.
 */

/* ── Payment (backend PaymentSerializer) ──────────────────────── */

export type RazorpayPaymentMethod = "cash" | "card" | "online" | "upi";

export type RazorpayPaymentStatus =
  | "pending"
  | "completed"
  | "failed"
  | "refunded";

export interface RazorpayPayment {
  id: number;
  customer: number;
  membership: number | null;
  amount: string;
  payment_method: RazorpayPaymentMethod;
  status: RazorpayPaymentStatus;
  transaction_id: string;
  razorpay_order_id: string;
  razorpay_payment_id: string;
  paid_at: string | null;
  notes: string;
  created_at: string;
  updated_at: string;
}

export interface RazorpayPaymentListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: RazorpayPayment[];
}

/* ── Create order ────────────────────────────────────────────── */

export interface CreateRazorpayOrderRequest {
  customer: number;
  membership?: number | null;
  amount: number;
  notes?: string;
}

export interface CreateRazorpayOrderResponse {
  payment: RazorpayPayment;
  razorpay_order_id: string;
  amount: number;
  currency: string;
}

/* ── Verify payment ──────────────────────────────────────────── */

export interface VerifyRazorpayPaymentRequest {
  razorpay_order_id: string;
  razorpay_payment_id: string;
  razorpay_signature: string;
}

/* ── Razorpay config (admin) ─────────────────────────────────── */

export interface RazorpayConfig {
  id: number;
  api_key: string;
  is_active: boolean;
}

/** Fields the tenant admin can update (secrets are write-only). */
export interface RazorpayConfigUpdate {
  api_key?: string;
  api_secret?: string;
  webhook_secret?: string;
  is_active?: boolean;
}

/* ── Razorpay Checkout.js options ────────────────────────────── */

export interface RazorpayCheckoutOptions {
  key: string;
  amount: number;
  currency: string;
  name: string;
  description?: string;
  order_id: string;
  prefill?: {
    name?: string;
    email?: string;
    contact?: string;
  };
  handler: (response: {
    razorpay_payment_id: string;
    razorpay_order_id: string;
    razorpay_signature: string;
  }) => void;
  modal?: {
    ondismiss?: () => void;
  };
  theme?: {
    color?: string;
  };
}

/** Global Razorpay Checkout.js instance (injected via <script>). */
export interface RazorpayInstance {
  open: () => void;
}

export interface RazorpayGlobal {
  new (options: RazorpayCheckoutOptions): RazorpayInstance;
}

/* ── Payment status/method labels (shared by UI) ─────────────── */

export const RAZORPAY_STATUS_LABELS: Record<RazorpayPaymentStatus, string> = {
  pending: "Pending",
  completed: "Completed",
  failed: "Failed",
  refunded: "Refunded",
};

export const RAZORPAY_METHOD_LABELS: Record<RazorpayPaymentMethod, string> = {
  cash: "Cash",
  card: "Card",
  online: "Online",
  upi: "UPI",
};
