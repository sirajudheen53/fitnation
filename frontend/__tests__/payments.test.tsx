import {
  getPaymentStatusLabel,
  getPaymentMethodLabel,
  getPaymentKindLabel,
  getPaymentKindBadgeVariant,
  PaymentTable,
  formatPaymentDate,
} from "@/features/payments/components/PaymentTable";
import { formatCurrency } from "@/features/payments/components/RevenueSummary";
import {
  getInvoiceStatusLabel,
  formatInvoiceDate,
} from "@/features/payments/components/invoiceHelpers";
import { fetchPayments, updatePayment, createPayment } from "@/lib/api";
import { render, screen } from "@testing-library/react";
import type { Payment } from "@/types/payment";

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

describe("Payment kind labels (msg 2438)", () => {
  it("labels admission and membership kinds", () => {
    expect(getPaymentKindLabel("admission")).toBe("Admission");
    expect(getPaymentKindLabel("membership")).toBe("Membership");
  });

  it("treats a missing kind as membership (legacy rows)", () => {
    expect(getPaymentKindLabel(undefined)).toBe("Membership");
  });

  it("picks distinct badge variants per kind", () => {
    expect(getPaymentKindBadgeVariant("admission")).toBe("info");
    expect(getPaymentKindBadgeVariant("membership")).toBe("default");
  });

  const basePayment: Payment = {
    id: 1,
    customer_id: 1,
    customer_name: "Arjun Kumar",
    amount: "5000.00",
    method: "cash",
    status: "completed",
    kind: "membership",
    membership_id: null,
    invoice_id: null,
    notes: null,
    payment_date: "2026-02-10T00:00:00Z",
    created_at: "2026-02-10T00:00:00Z",
    updated_at: "2026-02-10T00:00:00Z",
  };

  it("renders a kind badge on every payment row", () => {
    render(
      <PaymentTable
        payments={[
          basePayment,
          { ...basePayment, id: 2, kind: "admission", amount: "1000.00" },
        ]}
        filters={{}}
        onFilterChange={jest.fn()}
      />,
    );
    expect(screen.getByText("Membership")).toBeInTheDocument();
    expect(screen.getByText("Admission")).toBeInTheDocument();
  });
});

describe("Payment API wire format", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  function mockFetch(payload: unknown) {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () => Promise.resolve(payload),
    });
    global.fetch = fetchMock as unknown as typeof fetch;
    return fetchMock;
  }

  it("fetchPayments passes customer/kind/status filters as query params", async () => {
    const fetchMock = mockFetch({ count: 0, next: null, previous: null, results: [] });
    await fetchPayments("tok", { customer: 5, kind: "admission" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/payments/?customer=5&kind=admission");
    expect(init.headers && (init.headers as Record<string, string>).Authorization).toBe(
      "Token tok",
    );
  });

  it("fetchPayments without params hits the bare endpoint", async () => {
    const fetchMock = mockFetch({ count: 0, next: null, previous: null, results: [] });
    await fetchPayments("tok");
    expect(fetchMock.mock.calls[0][0]).toContain("/payments/");
  });

  it("createPayment posts the admission-fee contract fields", async () => {
    const fetchMock = mockFetch({ id: 9 });
    await createPayment(
      {
        customer_id: 5,
        amount: 5000,
        method: "cash",
        status: "completed",
        kind: "admission",
      },
      "tok",
    );
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/payments/");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      customer_id: 5,
      amount: 5000,
      method: "cash",
      status: "completed",
      kind: "admission",
    });
  });

  it("updatePayment PATCHes a pending payment to completed", async () => {
    const fetchMock = mockFetch({ id: 7 });
    await updatePayment(7, { status: "completed", method: "upi", amount: 2500 }, "tok");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/payments/7/");
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      status: "completed",
      method: "upi",
      amount: 2500,
    });
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
