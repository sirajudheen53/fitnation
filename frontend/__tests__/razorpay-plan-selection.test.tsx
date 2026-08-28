import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { PlanSelection } from "@/features/razorpay/components/PlanSelection";
import { CheckoutFlow } from "@/features/razorpay/components/CheckoutFlow";
import { fetchMembershipPlans } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { MembershipPlan } from "@/types/membership";

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(),
}));

jest.mock("@/lib/api", () => ({
  fetchMembershipPlans: jest.fn(),
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
}));

// The CheckoutFlow renders RazorpayCheckout after selection; mock it out so we
// only assert on the flow orchestration, not the checkout internals.
jest.mock("@/features/razorpay/components/RazorpayCheckout", () => ({
  RazorpayCheckout: ({ defaultAmount, defaultCustomer }: { defaultAmount?: number; defaultCustomer?: number }) => (
    <div data-testid="checkout">
      checkout amount={defaultAmount} customer={defaultCustomer}
    </div>
  ),
}));

const mockedGetToken = getToken as jest.Mock;
const mockedFetchPlans = fetchMembershipPlans as jest.Mock;

const plan = (overrides: Partial<MembershipPlan> = {}): MembershipPlan => ({
  id: 1,
  name: "Gold",
  price: "1999.00",
  duration_days: 30,
  plan_type: "monthly",
  description: null,
  is_active: true,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  ...overrides,
});

beforeEach(() => {
  jest.clearAllMocks();
  mockedGetToken.mockReturnValue("test-token");
});

describe("PlanSelection", () => {
  it("shows a spinner while loading plans", () => {
    mockedFetchPlans.mockReturnValue(new Promise(() => {}));
    render(<PlanSelection onSelect={jest.fn()} />);
    expect(screen.getByLabelText("Loading")).toBeInTheDocument();
  });

  it("shows an error when plans fail to load", async () => {
    mockedFetchPlans.mockRejectedValue(new Error("Failed to load plans"));
    render(<PlanSelection onSelect={jest.fn()} />);
    await waitFor(() =>
      expect(screen.getByText("Failed to load plans")).toBeInTheDocument(),
    );
  });

  it("shows an empty state when there are no active plans", async () => {
    mockedFetchPlans.mockResolvedValue({ count: 0, next: null, previous: null, results: [] });
    render(<PlanSelection onSelect={jest.fn()} />);
    await waitFor(() => expect(screen.getByText("No active plans")).toBeInTheDocument());
  });

  it("filters out inactive plans", async () => {
    mockedFetchPlans.mockResolvedValue({
      count: 2,
      next: null,
      previous: null,
      results: [plan({ id: 1, name: "Gold" }), plan({ id: 2, name: "Silver", is_active: false })],
    });
    render(<PlanSelection onSelect={jest.fn()} />);
    await waitFor(() => expect(screen.getByText("Gold")).toBeInTheDocument());
    expect(screen.queryByText("Silver")).not.toBeInTheDocument();
  });

  it("requires a customer id before continuing", async () => {
    mockedFetchPlans.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [plan()],
    });
    const onSelect = jest.fn();
    render(<PlanSelection onSelect={onSelect} />);
    await waitFor(() => expect(screen.getByText("Gold")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Gold"));
    fireEvent.click(screen.getByText("Continue to payment"));

    expect(screen.getByText("Customer ID is required")).toBeInTheDocument();
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("calls onSelect with the plan and customer id", async () => {
    mockedFetchPlans.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [plan()],
    });
    const onSelect = jest.fn();
    render(<PlanSelection onSelect={onSelect} />);
    await waitFor(() => expect(screen.getByText("Gold")).toBeInTheDocument());

    fireEvent.click(screen.getByText("Gold"));
    fireEvent.change(screen.getByLabelText(/Customer ID/i), { target: { value: "7" } });
    fireEvent.click(screen.getByText("Continue to payment"));

    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ id: 1 }), 7);
  });
});

describe("CheckoutFlow", () => {
  it("starts on plan selection and advances to checkout", async () => {
    mockedFetchPlans.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [plan({ id: 1, name: "Gold", price: "1999.00" })],
    });
    render(<CheckoutFlow onComplete={jest.fn()} />);

    await waitFor(() => expect(screen.getByText("Gold")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Gold"));
    fireEvent.change(screen.getByLabelText(/Customer ID/i), { target: { value: "7" } });
    fireEvent.click(screen.getByText("Continue to payment"));

    await waitFor(() => expect(screen.getByTestId("checkout")).toBeInTheDocument());
    expect(screen.getByTestId("checkout")).toHaveTextContent("amount=1999");
    expect(screen.getByTestId("checkout")).toHaveTextContent("customer=7");
  });

  it("returns to plan selection when back is clicked", async () => {
    mockedFetchPlans.mockResolvedValue({
      count: 1,
      next: null,
      previous: null,
      results: [plan()],
    });
    render(<CheckoutFlow onComplete={jest.fn()} />);

    await waitFor(() => expect(screen.getByText("Gold")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Gold"));
    fireEvent.change(screen.getByLabelText(/Customer ID/i), { target: { value: "7" } });
    fireEvent.click(screen.getByText("Continue to payment"));

    await waitFor(() => expect(screen.getByTestId("checkout")).toBeInTheDocument());
    fireEvent.click(screen.getByText("Back to plan selection"));

    await waitFor(() => expect(screen.getByText("Select a plan")).toBeInTheDocument());
  });
});
