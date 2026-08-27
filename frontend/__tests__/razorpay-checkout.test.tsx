import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { RazorpayCheckout } from "@/features/razorpay/components/RazorpayCheckout";
import { RazorpayConfigForm } from "@/features/razorpay/components/RazorpayConfigForm";
import {
  createRazorpayOrder,
  errorMessage,
  fetchRazorpayConfig,
  verifyRazorpayPayment,
  updateRazorpayConfig,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

jest.mock("@/lib/auth", () => ({
  getToken: jest.fn(),
}));

const mockRouter = { push: jest.fn(), replace: jest.fn(), back: jest.fn(), prefetch: jest.fn() };
jest.mock("next/navigation", () => ({
  useRouter: () => mockRouter,
  useParams: () => ({}),
  usePathname: () => "/",
}));

jest.mock("@/lib/api", () => ({
  createRazorpayOrder: jest.fn(),
  verifyRazorpayPayment: jest.fn(),
  fetchRazorpayConfig: jest.fn(),
  updateRazorpayConfig: jest.fn(),
  errorMessage: jest.fn((err) => (err instanceof Error ? err.message : "error")),
}));

const mockedGetToken = getToken as jest.Mock;
const mockedCreateOrder = createRazorpayOrder as jest.Mock;
const mockedVerify = verifyRazorpayPayment as jest.Mock;
const mockedFetchConfig = fetchRazorpayConfig as jest.Mock;
const mockedUpdateConfig = updateRazorpayConfig as jest.Mock;

// Mock the checkout loader so no real script is injected during tests.
jest.mock("@/features/razorpay/lib/razorpayCheckout", () => ({
  loadRazorpayScript: jest.fn().mockResolvedValue({
    new: jest.fn(() => ({ open: jest.fn() })),
  }),
  openRazorpayCheckout: jest.fn(),
  paiseToRupees: jest.fn((p: number) => String(p / 100)),
}));

beforeEach(() => {
  jest.clearAllMocks();
  mockedGetToken.mockReturnValue("test-token");
});

describe("RazorpayCheckout", () => {
  it("shows a config error when Razorpay is inactive", async () => {
    mockedFetchConfig.mockResolvedValue({ id: 1, api_key: "rzp_key", is_active: false });
    render(<RazorpayCheckout />);
    await waitFor(() =>
      expect(
        screen.getByText(/Razorpay is not enabled/i),
      ).toBeInTheDocument(),
    );
  });

  it("creates an order and verifies on payment success", async () => {
    mockedFetchConfig.mockResolvedValue({ id: 1, api_key: "rzp_key", is_active: true });
    mockedCreateOrder.mockResolvedValue({
      payment: { id: 5, status: "pending" },
      razorpay_order_id: "order_99",
      amount: 199900,
      currency: "INR",
    });
    mockedVerify.mockResolvedValue({ id: 5, status: "completed" });

    // Import the mocked openRazorpayCheckout to capture the handler.
    const {
      openRazorpayCheckout,
    } = require("@/features/razorpay/lib/razorpayCheckout");

    render(<RazorpayCheckout defaultAmount={1999} />);

    await waitFor(() => expect(screen.getByText(/Pay with Razorpay/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Customer ID/i), {
      target: { value: "7" },
    });
    fireEvent.change(screen.getByLabelText(/Amount/i), {
      target: { value: "1999" },
    });
    fireEvent.click(screen.getByText(/Pay with Razorpay/i));

    await waitFor(() => expect(mockedCreateOrder).toHaveBeenCalledTimes(1));
    expect(mockedCreateOrder).toHaveBeenCalledWith(
      { customer: 7, membership: null, amount: 1999, notes: undefined },
      "test-token",
    );

    await waitFor(() => expect(openRazorpayCheckout).toHaveBeenCalledTimes(1));
    const options = (openRazorpayCheckout as jest.Mock).mock.calls[0][1];
    expect(options.key).toBe("rzp_key");
    expect(options.order_id).toBe("order_99");
    expect(options.amount).toBe(199900);

    // Simulate the checkout success handler.
    await act(async () => {
      await options.handler({
        razorpay_order_id: "order_99",
        razorpay_payment_id: "pay_99",
        razorpay_signature: "sig_99",
      });
    });

    await waitFor(() => expect(mockedVerify).toHaveBeenCalledTimes(1));
    expect(mockedVerify).toHaveBeenCalledWith(
      {
        razorpay_order_id: "order_99",
        razorpay_payment_id: "pay_99",
        razorpay_signature: "sig_99",
      },
      "test-token",
    );

    await waitFor(() => expect(screen.getByText(/Payment successful/i)).toBeInTheDocument());
  });

  it("surfaces an error when order creation fails", async () => {
    mockedFetchConfig.mockResolvedValue({ id: 1, api_key: "rzp_key", is_active: true });
    mockedCreateOrder.mockRejectedValue(new Error("Razorpay order failed"));

    render(<RazorpayCheckout defaultAmount={100} />);
    await waitFor(() => expect(screen.getByText(/Pay with Razorpay/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/Customer ID/i), { target: { value: "1" } });
    fireEvent.change(screen.getByLabelText(/Amount/i), { target: { value: "100" } });
    fireEvent.click(screen.getByText(/Pay with Razorpay/i));

    await waitFor(() => expect(screen.getByText(/Razorpay order failed/i)).toBeInTheDocument());
  });
});

describe("RazorpayConfigForm", () => {
  it("loads and displays the existing config", async () => {
    mockedFetchConfig.mockResolvedValue({ id: 1, api_key: "rzp_live_key", is_active: true });
    render(<RazorpayConfigForm />);
    await waitFor(() => expect(screen.getByLabelText(/API Key/i)).toHaveValue("rzp_live_key"));
  });

  it("saves the config and shows a success alert", async () => {
    mockedFetchConfig.mockResolvedValue({ id: 1, api_key: "rzp_live_key", is_active: true });
    mockedUpdateConfig.mockResolvedValue({ is_active: true });
    render(<RazorpayConfigForm />);
    await waitFor(() => expect(screen.getByLabelText(/API Key/i)).toHaveValue("rzp_live_key"));

    fireEvent.change(screen.getByLabelText(/API Key/i), { target: { value: "rzp_new_key" } });
    fireEvent.change(screen.getByLabelText(/API Secret/i), { target: { value: "new_secret" } });
    fireEvent.click(screen.getByText(/Save configuration/i));

    await waitFor(() => expect(mockedUpdateConfig).toHaveBeenCalled());
    expect(mockedUpdateConfig).toHaveBeenCalledWith(
      { api_key: "rzp_new_key", is_active: true, api_secret: "new_secret" },
      "test-token",
    );
    await waitFor(() => expect(screen.getByText(/Configuration saved/i)).toBeInTheDocument());
  });
});
