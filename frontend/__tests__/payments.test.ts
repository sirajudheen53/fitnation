import {
  getPaymentStatusLabel,
  getPaymentMethodLabel,
  formatPaymentDate,
} from "@/features/payments/components/PaymentTable";
import { formatCurrency } from "@/features/payments/components/RevenueSummary";
import {
  getInvoiceStatusLabel,
  formatInvoiceDate,
} from "@/features/payments/components/invoiceHelpers";

describe("PaymentTable helpers", () => {
  it("returns the correct label for each payment status", () => {
    expect(getPaymentStatusLabel("completed")).toBe("Completed");
    expect(getPaymentStatusLabel("pending")).toBe("Pending");
    expect(getPaymentStatusLabel("failed")).toBe("Failed");
    expect(getPaymentStatusLabel("refunded")).toBe("Refunded");
  });

  it("returns the correct label for each payment method", () => {
    expect(getPaymentMethodLabel("cash")).toBe("Cash");
    expect(getPaymentMethodLabel("upi")).toBe("UPI");
    expect(getPaymentMethodLabel("bank_transfer")).toBe("Bank transfer");
  });

  it("formats an ISO date to a locale string", () => {
    const formatted = formatPaymentDate("2026-02-10T00:00:00Z");
    expect(formatted).not.toBe("—");
    expect(formatted).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });

  it("returns an em dash for null dates", () => {
    expect(formatPaymentDate(null)).toBe("—");
  });
});

describe("RevenueSummary helper", () => {
  it("formats currency with rupee symbol and two decimals", () => {
    expect(formatCurrency(1999)).toBe("₹1,999.00");
  });

  it("handles string numbers", () => {
    expect(formatCurrency("5000")).toBe("₹5,000.00");
  });

  it("returns zero for invalid values", () => {
    expect(formatCurrency("abc")).toBe("₹0.00");
  });
});

describe("Invoice helpers", () => {
  it("returns the correct label for each invoice status", () => {
    expect(getInvoiceStatusLabel("draft")).toBe("Draft");
    expect(getInvoiceStatusLabel("issued")).toBe("Issued");
    expect(getInvoiceStatusLabel("paid")).toBe("Paid");
    expect(getInvoiceStatusLabel("overdue")).toBe("Overdue");
    expect(getInvoiceStatusLabel("cancelled")).toBe("Cancelled");
  });

  it("formats an ISO date to a locale string", () => {
    const formatted = formatInvoiceDate("2026-03-01T00:00:00Z");
    expect(formatted).not.toBe("—");
    expect(formatted).toMatch(/\d{1,2}\/\d{1,2}\/\d{4}/);
  });

  it("returns an em dash for null dates", () => {
    expect(formatInvoiceDate(null)).toBe("—");
  });
});
