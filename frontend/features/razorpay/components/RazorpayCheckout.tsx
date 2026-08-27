"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { CreditCard, DollarSign, User, Wallet, StickyNote } from "lucide-react";
import { Alert, Button, Card, CardBody, CardHeader, Input, Spinner } from "@/components/ui";
import {
  createRazorpayOrder,
  errorMessage,
  fetchRazorpayConfig,
  verifyRazorpayPayment,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { RazorpayGlobal, RazorpayPaymentStatus } from "@/types/razorpay";
import { loadRazorpayScript, openRazorpayCheckout } from "../lib/razorpayCheckout";

const checkoutSchema = z.object({
  customer: z.coerce.number().int().positive("Customer ID is required"),
  membership: z
    .string()
    .optional()
    .or(z.literal(""))
    .transform((v) => {
      if (v === undefined || v === "") return undefined;
      const n = Number(v);
      return Number.isNaN(n) ? undefined : n;
    }),
  amount: z.coerce.number().positive("Amount must be greater than 0"),
  notes: z.string().max(500).optional().or(z.literal("")),
});

type CheckoutSchemaData = z.infer<typeof checkoutSchema>;

export type CheckoutPhase = "form" | "creating" | "paying" | "verifying" | "success" | "failed";

export interface CheckoutResult {
  paymentId: number;
  status: RazorpayPaymentStatus;
}

interface RazorpayCheckoutProps {
  onComplete?: (result: CheckoutResult) => void;
  /** Prefill the amount (e.g. from a selected membership plan). */
  defaultAmount?: number;
  /** Optional initial customer id (e.g. when launched from a customer page). */
  defaultCustomer?: number;
}

export function RazorpayCheckout({
  onComplete,
  defaultAmount,
  defaultCustomer,
}: RazorpayCheckoutProps) {
  const router = useRouter();
  const [phase, setPhase] = useState<CheckoutPhase>("form");
  const [error, setError] = useState<string | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configLoading, setConfigLoading] = useState(true);
  const [checkoutActive, setCheckoutActive] = useState(false);
  const [result, setResult] = useState<CheckoutResult | null>(null);
  const [razorpayKey, setRazorpayKey] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<CheckoutSchemaData>({
    resolver: zodResolver(checkoutSchema),
    defaultValues: {
      customer: defaultCustomer ?? undefined,
      membership: undefined,
      amount: (defaultAmount ?? 0) as number,
      notes: "",
    },
  });

  const amountValue = watch("amount");

  // On mount, verify Razorpay is configured so we can preflight the checkout.
  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/payments/razorpay");
      return;
    }
    fetchRazorpayConfig(token)
      .then((config) => {
        if (!config.is_active) {
          setConfigError("Razorpay is not enabled. Ask your administrator to configure it.");
        } else if (config.api_key) {
          setRazorpayKey(config.api_key);
        } else {
          setConfigError("Razorpay is enabled but the API key is missing.");
        }
      })
      .catch((err) => setConfigError(errorMessage(err)))
      .finally(() => setConfigLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePay = async (data: CheckoutSchemaData) => {
    setError(null);

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/payments/razorpay");
      return;
    }

    setPhase("creating");
    let order;
    try {
      order = await createRazorpayOrder(
        {
          customer: data.customer,
          membership: data.membership ?? null,
          amount: data.amount,
          notes: data.notes || undefined,
        },
        token,
      );
    } catch (err) {
      setError(errorMessage(err));
      setPhase("failed");
      return;
    }

    setPhase("paying");
    try {
      await runCheckout(order.razorpay_order_id, order.amount, token);
    } catch (err) {
      setError(errorMessage(err));
      setPhase("failed");
    }
  };

  const runCheckout = async (orderId: string, amountPaise: number, token: string) => {
    if (!razorpayKey) {
      throw new Error("Razorpay is not configured.");
    }

    const Razorpay: RazorpayGlobal = await loadRazorpayScript();

    setCheckoutActive(true);
    openRazorpayCheckout(Razorpay, {
      key: razorpayKey,
      amount: amountPaise,
      currency: "INR",
      name: "FitNation",
      description: "Gym membership payment",
      order_id: orderId,
      theme: { color: "#0f172a" },
      modal: {
        ondismiss: () => {
          setCheckoutActive(false);
          // Let the user retry — keep the order form intact.
          setPhase("form");
        },
      },
      handler: async (response) => {
        setCheckoutActive(false);
        setPhase("verifying");
        try {
          const payment = await verifyRazorpayPayment(
            {
              razorpay_order_id: response.razorpay_order_id,
              razorpay_payment_id: response.razorpay_payment_id,
              razorpay_signature: response.razorpay_signature,
            },
            token,
          );
          const res: CheckoutResult = { paymentId: payment.id, status: payment.status };
          setResult(res);
          setPhase("success");
          onComplete?.(res);
        } catch (err) {
          setError(errorMessage(err));
          setPhase("failed");
        }
      },
    });
  };

  if (configLoading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  if (configError) {
    return <Alert variant="error">{configError}</Alert>;
  }

  if (phase === "success" && result) {
    return (
      <Card>
        <CardBody className="text-center py-10">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-green-600">
            <Wallet className="h-7 w-7" />
          </div>
          <h3 className="mt-4 text-lg font-semibold text-gray-900">Payment successful</h3>
          <p className="mt-1 text-sm text-gray-500">
            Your payment has been recorded. Transaction #{result.paymentId}.
          </p>
          <div className="mt-6 flex justify-center gap-3">
            <Button variant="outline" onClick={() => router.push("/payments/razorpay")}>
              View payment history
            </Button>
          </div>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Razorpay checkout</h2>
        <p className="text-sm text-gray-500">
          Record a payment and collect it securely via Razorpay.
        </p>
      </CardHeader>
      <CardBody>
        {error && <Alert variant="error">{error}</Alert>}

        <form onSubmit={handleSubmit(handlePay)} className="space-y-5">
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Customer ID"
              type="number"
              min="1"
              placeholder="1"
              icon={<User className="h-4 w-4" />}
              error={errors.customer?.message}
              disabled={phase !== "form"}
              {...register("customer")}
            />
            <Input
              label="Amount (₹)"
              type="number"
              step="0.01"
              min="0"
              placeholder="1999"
              icon={<DollarSign className="h-4 w-4" />}
              error={errors.amount?.message}
              disabled={phase !== "form"}
              {...register("amount")}
            />
          </div>

          <Input
            label="Membership ID (optional)"
            type="number"
            min="1"
            placeholder="Link this payment to a membership"
            icon={<CreditCard className="h-4 w-4" />}
            error={errors.membership?.message}
            disabled={phase !== "form"}
            {...register("membership")}
          />

          <div className="space-y-1.5">
            <label htmlFor="notes" className="block text-sm font-medium text-gray-700">
              Notes
            </label>
            <div className="relative">
              <StickyNote className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-gray-400" />
              <textarea
                id="notes"
                rows={3}
                placeholder="Optional notes about this payment"
                disabled={phase !== "form"}
                {...register("notes")}
                className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500 disabled:bg-gray-50"
              />
            </div>
            {errors.notes?.message && (
              <p className="text-sm text-red-600">{errors.notes.message}</p>
            )}
          </div>

          <div className="flex items-center justify-between rounded-lg bg-gray-50 px-4 py-3">
            <span className="text-sm font-medium text-gray-700">Total</span>
            <span className="text-lg font-semibold text-gray-900">
              ₹{Number(amountValue || 0).toLocaleString("en-IN", { minimumFractionDigits: 2 })}
            </span>
          </div>

          <Button
            type="submit"
            fullWidth
            size="lg"
            loading={phase === "creating" || phase === "verifying"}
            disabled={phase === "paying"}
          >
            {phase === "creating"
              ? "Creating order…"
              : phase === "verifying"
                ? "Verifying payment…"
                : checkoutActive
                  ? "Waiting for payment…"
                  : "Pay with Razorpay"}
          </Button>
        </form>
      </CardBody>
    </Card>
  );
}
