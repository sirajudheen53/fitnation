"use client";

import { Badge } from "@/components/ui";
import {
  RAZORPAY_METHOD_LABELS,
  RAZORPAY_STATUS_LABELS,
  type RazorpayPaymentMethod,
  type RazorpayPaymentStatus,
} from "@/types/razorpay";

const STATUS_VARIANTS: Record<RazorpayPaymentStatus, "default" | "info" | "success" | "warning" | "danger"> = {
  pending: "warning",
  completed: "success",
  failed: "danger",
  refunded: "info",
};

export function RazorpayStatusBadge({ status }: { status: RazorpayPaymentStatus }) {
  return <Badge variant={STATUS_VARIANTS[status]}>{RAZORPAY_STATUS_LABELS[status]}</Badge>;
}

export function getRazorpayMethodLabel(method: RazorpayPaymentMethod): string {
  return RAZORPAY_METHOD_LABELS[method];
}

export function formatRazorpayDate(iso: string | null): string {
  if (!iso) return "—";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}
