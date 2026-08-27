/**
 * FBOS-020 — Razorpay Checkout.js loader and helpers.
 *
 * Loads the official Razorpay Checkout.js script on demand and exposes a small
 * wrapper for opening the checkout with an order id. Kept side-effect free so
 * it can be unit-tested.
 */

import type { RazorpayCheckoutOptions, RazorpayGlobal, RazorpayInstance } from "@/types/razorpay";

const CHECKOUT_SRC = "https://checkout.razorpay.com/v1/checkout.js";
const RAZORPAY_GLOBAL = "Razorpay";

let loadPromise: Promise<RazorpayGlobal> | null = null;

/** Inject the Checkout.js <script> tag and resolve with the Razorpay global. */
export function loadRazorpayScript(): Promise<RazorpayGlobal> {
  if (typeof window === "undefined") {
    return Promise.reject(new Error("Razorpay checkout can only run in the browser."));
  }

  const existing = (window as unknown as Record<string, unknown>)[RAZORPAY_GLOBAL];
  if (existing) {
    return Promise.resolve(existing as RazorpayGlobal);
  }

  if (loadPromise) {
    return loadPromise;
  }

  loadPromise = new Promise<RazorpayGlobal>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = CHECKOUT_SRC;
    script.async = true;
    script.onload = () => {
      const rzp = (window as unknown as Record<string, unknown>)[RAZORPAY_GLOBAL];
      if (rzp) {
        resolve(rzp as RazorpayGlobal);
      } else {
        reject(new Error("Razorpay Checkout.js loaded but Razorpay global is missing."));
      }
    };
    script.onerror = () => {
      loadPromise = null;
      reject(new Error("Failed to load Razorpay Checkout.js."));
    };
    document.head.appendChild(script);
  });

  return loadPromise;
}

/** Open the Razorpay checkout for a given set of options. */
export function openRazorpayCheckout(
  Razorpay: RazorpayGlobal,
  options: RazorpayCheckoutOptions,
): RazorpayInstance {
  const instance = new Razorpay(options);
  instance.open();
  return instance;
}

/** Format a paise amount (Razorpay sends amounts in paise) into rupees. */
export function paiseToRupees(paise: number): string {
  return (paise / 100).toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
