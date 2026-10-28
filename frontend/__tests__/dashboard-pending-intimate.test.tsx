import { PendingPayments } from "@/features/dashboard/components/PendingPayments";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { PendingPayment } from "@/types/dashboard";

function pendingPayment(overrides: Partial<PendingPayment> = {}): PendingPayment {
  return {
    id: 7,
    customer_name: "Meera Nair",
    amount: "2500.00",
    due_date: "2026-10-20T00:00:00Z",
    ...overrides,
  };
}

describe("Dashboard PendingPayments intimate button (issue #79)", () => {
  it("renders member, amount, and due date rows", () => {
    render(<PendingPayments payments={[pendingPayment()]} />);
    expect(screen.getByText("Meera Nair")).toBeInTheDocument();
    expect(screen.getByText("₹2,500")).toBeInTheDocument();
    expect(screen.getByText(/due /i)).toBeInTheDocument();
  });

  it("hides the intimate action without the send permission", () => {
    render(<PendingPayments payments={[pendingPayment()]} onSend={jest.fn()} />);
    const button = screen.queryByRole("button", { name: /intimate on whatsapp/i });
    expect(button).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /record payment/i })).toBeInTheDocument();
  });

  it("fires onSend with the payment when Intimate on WhatsApp is clicked", async () => {
    const onSend = jest.fn();
    const user = userEvent.setup();
    render(<PendingPayments payments={[pendingPayment()]} onSend={onSend} canSend />);
    const button = screen.getByRole("button", { name: /intimate on whatsapp/i });
    await user.click(button);
    expect(onSend).toHaveBeenCalledTimes(1);
    expect(onSend).toHaveBeenCalledWith(pendingPayment());
  });

  it("disables only the sending row's action", () => {
    const payments = [
      pendingPayment(),
      pendingPayment({ id: 8, customer_name: "Arjun Kumar" }),
    ];
    render(
      <PendingPayments
        payments={payments}
        onSend={jest.fn()}
        sendingPaymentId={7}
        canSend={true}
      />,
    );
    const sending = screen.getByRole("button", { name: /sending/i });
    expect(sending).toBeDisabled();
    const other = screen.getByRole("button", { name: /intimate on whatsapp/i });
    expect(other).toBeEnabled();
  });

  it("shows the empty state when nothing is pending", () => {
    render(<PendingPayments payments={[]} />);
    expect(screen.getByText(/no pending payments/i)).toBeInTheDocument();
  });
});
