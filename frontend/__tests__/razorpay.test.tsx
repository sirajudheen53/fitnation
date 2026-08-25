import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { paiseToRupees } from "@/features/razorpay/lib/razorpayCheckout";
import {
  formatRazorpayDate,
  getRazorpayMethodLabel,
  RazorpayStatusBadge,
} from "@/features/razorpay/components/RazorpayStatusBadge";
import { PaymentHistoryTable } from "@/features/razorpay/components/PaymentHistoryTable";
import type { RazorpayPayment } from "@/types/razorpay";

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  usePathname: () => "/",
}));

const samplePayment = (overrides: Partial<RazorpayPayment> = {}): RazorpayPayment => ({
  id: 1,
  customer: 7,
  membership: null,
  amount: "1999.00",
  payment_method: "online",
  status: "completed",
  transaction_id: "pay_123",
  razorpay_order_id: "order_123",
  razorpay_payment_id: "pay_123",
  paid_at: "2026-08-25T05:00:00Z",
  notes: "",
  created_at: "2026-08-25T05:00:00Z",
  updated_at: "2026-08-25T05:00:00Z",
  ...overrides,
});

describe("razorpayCheckout lib helpers", () => {
  it("converts paise to rupees with INR formatting", () => {
    expect(paiseToRupees(199900)).toBe("1,999.00");
    expect(paiseToRupees(5000)).toBe("50.00");
  });
});

describe("RazorpayStatusBadge helpers", () => {
  it("maps payment methods to labels", () => {
    expect(getRazorpayMethodLabel("online")).toBe("Online");
    expect(getRazorpayMethodLabel("upi")).toBe("UPI");
    expect(getRazorpayMethodLabel("card")).toBe("Card");
  });

  it("formats an ISO date and returns em dash for empty", () => {
    expect(formatRazorpayDate("2026-08-25T05:00:00Z")).toMatch(/Aug 2026/);
    expect(formatRazorpayDate(null)).toBe("—");
    expect(formatRazorpayDate("not-a-date")).toBe("—");
  });

  it("renders a status badge with the right label", () => {
    const { container } = render(<RazorpayStatusBadge status="completed" />);
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(container.querySelector(".bg-green-100")).toBeTruthy();
  });
});

describe("PaymentHistoryTable", () => {
  it("renders an empty state when there are no payments", () => {
    render(
      <PaymentHistoryTable
        payments={[]}
        loading={false}
        status="all"
        onStatusChange={() => {}}
      />,
    );
    expect(screen.getByText("No payments found")).toBeInTheDocument();
  });

  it("renders payments with status badges and method labels", () => {
    const payments = [
      samplePayment({ id: 2, amount: "4999.00", payment_method: "upi", status: "pending" }),
      samplePayment({ id: 3, status: "refunded" }),
    ];
    render(
      <PaymentHistoryTable
        payments={payments}
        loading={false}
        status="all"
        onStatusChange={() => {}}
      />,
    );
    expect(screen.getByText("#2")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
    // "Pending" and "Refunded" appear both as filter buttons and status badges.
    expect(screen.getAllByText("Pending").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Refunded").length).toBeGreaterThan(0);
    expect(screen.getByText("UPI")).toBeInTheDocument();
    expect(screen.getByText("₹4,999")).toBeInTheDocument();
  });

  it("shows a spinner while loading", () => {
    render(
      <PaymentHistoryTable
        payments={[]}
        loading={true}
        status="all"
        onStatusChange={() => {}}
      />,
    );
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("calls onStatusChange when a filter is clicked", () => {
    const onStatusChange = jest.fn();
    render(
      <PaymentHistoryTable
        payments={[samplePayment()]}
        loading={false}
        status="all"
        onStatusChange={onStatusChange}
      />,
    );
    fireEvent.click(screen.getByText("Paid"));
    expect(onStatusChange).toHaveBeenCalledWith("completed");
  });
});
