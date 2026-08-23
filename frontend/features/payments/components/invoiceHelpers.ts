import type { InvoiceStatus } from "@/types/payment";

export function getInvoiceStatusLabel(status: InvoiceStatus): string {
  const labels: Record<InvoiceStatus, string> = {
    draft: "Draft",
    issued: "Issued",
    paid: "Paid",
    overdue: "Overdue",
    cancelled: "Cancelled",
  };
  return labels[status];
}

export function formatInvoiceDate(date: string | null): string {
  if (!date) return "—";
  return new Date(date).toLocaleDateString();
}
