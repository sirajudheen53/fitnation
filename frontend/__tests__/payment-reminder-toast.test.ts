import { ApiError } from "@/lib/api";
import { paymentReminderErrorText, paymentReminderToast } from "@/features/payments/lib/reminders";
import type { SendPaymentLinkResponse } from "@/types/payment";

function outcome(overrides: Partial<SendPaymentLinkResponse> = {}): SendPaymentLinkResponse {
  return {
    status: "sent",
    channel: "whatsapp",
    provider: "gupshup",
    payment_link_url: "https://rzp.io/i/x1",
    ...overrides,
  };
}

describe("paymentReminderToast (issue #106)", () => {
  it("announces a sent link with the proper channel name", () => {
    const sent = paymentReminderToast(outcome(), "Meera Nair");
    expect(sent.kind).toBe("success");
    expect(sent.message).toBe("Payment link sent to Meera Nair over WhatsApp");

    const sms = paymentReminderToast(outcome({ channel: "sms", provider: "msg91" }), "Meera Nair");
    expect(sms.message).toBe("Payment link sent to Meera Nair over SMS");

    const email = paymentReminderToast(outcome({ channel: "email", provider: "sendgrid" }), "Meera Nair");
    expect(email.message).toBe("Payment link sent to Meera Nair over email");
  });

  it("reports already_sent as an info nudge, not an error", () => {
    const sent = paymentReminderToast(
      outcome({ status: "already_sent", channel: null, provider: null }),
      "Meera Nair",
    );
    expect(sent.kind).toBe("info");
    expect(sent.message).toContain("Meera Nair");
    expect(sent.message).toContain("recently");
  });

  it("surfaces the backend's skipped-gate reason verbatim — never silent (#106)", () => {
    // The Gupshup template gate (issue #79) skips with its own explicit copy.
    const gated = paymentReminderToast(
      outcome({
        status: "skipped",
        channel: null,
        reason:
          "No messaging channel is set up for this gym yet — connect WhatsApp, SMS, or email under Settings, then send the reminder again.",
      }),
      "Meera Nair",
    );
    expect(gated.kind).toBe("error");
    expect(gated.message).toContain("No messaging channel is set up");
    expect(gated.message).toContain("Settings");

    // An unknown skip shape still toasts, with a named fallback.
    const opaque = paymentReminderToast(outcome({ status: "skipped", channel: null, reason: null }), "Meera Nair");
    expect(opaque.kind).toBe("error");
    expect(opaque.message).toBe("Could not send a payment link to Meera Nair");
  });
});

describe("paymentReminderErrorText (issue #106)", () => {
  it("carries the 429 daily-cap detail verbatim (like AppInviteView)", () => {
    const err = new ApiError(
      429,
      { detail: "Daily payment-reminder limit reached for this gym. Try again tomorrow." },
      "Daily payment-reminder limit reached for this gym. Try again tomorrow.",
    );
    expect(paymentReminderErrorText(err)).toContain("Daily payment-reminder limit reached");
    expect(paymentReminderErrorText(err)).toContain("Try again tomorrow");
  });

  it("carries the 400 rejected-send detail verbatim", () => {
    const err = new ApiError(
      400,
      { detail: "Only pending payments can receive a payment link." },
      "Only pending payments can receive a payment link.",
    );
    expect(paymentReminderErrorText(err)).toContain("Only pending payments");
  });

  it("translates a network failure into an actionable line", () => {
    const err = new TypeError("Failed to fetch");
    expect(paymentReminderErrorText(err)).toContain("Could not reach the server");
  });
});
