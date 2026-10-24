import {
  getPendingDays,
  getPendingPaymentRef,
  PendingPaymentTable,
} from "@/features/payments/components/PendingPaymentTable";
import { sendPaymentLink } from "@/lib/api";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { Payment } from "@/types/payment";

const NOW = new Date("2026-10-24T10:00:00Z");

function pendingPayment(overrides: Partial<Payment> = {}): Payment {
  return {
    id: 1,
    customer_id: 1,
    customer_name: "Arjun Kumar",
    customer_phone: "+919876543210",
    amount: "5000.00",
    method: "online",
    status: "pending",
    kind: "membership",
    membership_id: 3,
    plan_name: "Monthly Pro",
    invoice_id: null,
    notes: null,
    payment_date: "2026-10-20T00:00:00Z",
    created_at: "2026-10-20T00:00:00Z",
    updated_at: "2026-10-20T00:00:00Z",
    ...overrides,
  };
}

describe("PendingPaymentTable helpers (issue #72)", () => {
  it("counts whole days since the payment was created", () => {
    const payment = { created_at: "2026-10-21T10:00:00Z" };
    expect(getPendingDays(payment, NOW)).toBe(3);
  });

  it("reports zero days for today's pending payments", () => {
    expect(getPendingDays({ created_at: NOW.toISOString() }, NOW)).toBe(0);
  });

  it("never reports negative days (future timestamps), and handles junk dates", () => {
    expect(getPendingDays({ created_at: "2026-10-25T10:00:00Z" }, NOW)).toBe(0);
    expect(getPendingDays({ created_at: "not-a-date" }, NOW)).toBe(0);
  });

  it("prefers the plan name, then the invoice ref, then an em dash", () => {
    expect(getPendingPaymentRef(pendingPayment({ plan_name: "Monthly Pro", invoice_id: 7 }))).toBe("Monthly Pro");
    expect(getPendingPaymentRef(pendingPayment({ plan_name: null, invoice_id: 7 }))).toBe("Invoice #7");
    expect(getPendingPaymentRef(pendingPayment({ plan_name: null, invoice_id: null }))).toBe("—");
  });
});

describe("PendingPaymentTable rendering", () => {
  it("renders member, phone, amount, plan ref, and days pending", () => {
    render(
      <PendingPaymentTable payments={[pendingPayment()]} sendingPaymentId={null} onSend={jest.fn()} />,
    );
    expect(screen.getByText("Arjun Kumar")).toBeInTheDocument();
    expect(screen.getByText("+919876543210")).toBeInTheDocument();
    expect(screen.getByText("₹5,000")).toBeInTheDocument();
    expect(screen.getByText("Monthly Pro")).toBeInTheDocument();
    // 20th → 24th is four days pending.
    expect(screen.getByText(/4 days/)).toBeInTheDocument();
  });

  it("labels same-day payments as pending today", () => {
    render(
      <PendingPaymentTable
        payments={[pendingPayment({ created_at: NOW.toISOString() })]}
        sendingPaymentId={null}
        onSend={jest.fn()}
      />,
    );
    expect(screen.getByText("Today")).toBeInTheDocument();
  });

  it("shows the empty state when the queue is clear", () => {
    render(<PendingPaymentTable payments={[]} sendingPaymentId={null} onSend={jest.fn()} />);
    expect(screen.getByText(/No pending payments/i)).toBeInTheDocument();
  });

  it("fires onSend with the payment when the row action is clicked", async () => {
    const onSend = jest.fn();
    const user = userEvent.setup();
    render(<PendingPaymentTable payments={[pendingPayment()]} sendingPaymentId={null} onSend={onSend} />);
    await user.click(screen.getByRole("button", { name: /send payment link/i }));
    expect(onSend).toHaveBeenCalledWith(pendingPayment());
  });

  it("disables the row action while that payment's link is sending", () => {
    render(<PendingPaymentTable payments={[pendingPayment()]} sendingPaymentId={1} onSend={jest.fn()} />);
    const button = screen.getByRole("button", { name: /sending/i });
    expect(button).toBeDisabled();
  });

  it("hides the send action without the record-payment permission", () => {
    render(
      <PendingPaymentTable
        payments={[pendingPayment()]}
        sendingPaymentId={null}
        onSend={jest.fn()}
        canSend={false}
      />,
    );
    expect(screen.queryByRole("button", { name: /send payment link/i })).not.toBeInTheDocument();
  });
});

describe("sendPaymentLink API wire format (issue #72)", () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it("POSTs to the payments send-link endpoint with the auth token", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: () =>
        Promise.resolve({ status: "sent", channel: "whatsapp", provider: "gupshup", payment_link_url: "https://rzp.io/i/x" }),
    });
    global.fetch = fetchMock as unknown as typeof fetch;

    const outcome = await sendPaymentLink(9, "tok");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toContain("/payments/9/send-link/");
    expect(init.method).toBe("POST");
    expect(init.headers && (init.headers as Record<string, string>).Authorization).toBe("Token tok");
    expect(outcome.status).toBe("sent");
    expect(outcome.payment_link_url).toBe("https://rzp.io/i/x");
  });
});