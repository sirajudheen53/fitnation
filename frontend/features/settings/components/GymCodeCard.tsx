"use client";

import { useEffect, useState } from "react";
import { Check, Copy } from "lucide-react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui";
import { errorMessage, fetchTenant } from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Gym code — the short code members type when the app asks "Specify your gym
 * to continue" during phone-OTP login (issue #60), including first-time
 * members joining from scratch (issue #87: the typed code now anchors their
 * sign-in). Shown on the settings page so owners/front-desk can copy it and
 * share it with members.
 */
export function GymCodeCard() {
  const [gymCode, setGymCode] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchTenant(token)
      .then((tenant) => setGymCode(tenant.gym_code ?? null))
      .catch((err) => setError(errorMessage(err)));
  }, []);

  function copyGymCode() {
    if (!gymCode) return;
    navigator.clipboard.writeText(gymCode).then(
      () => {
        setCopied(true);
        toast.success("Gym code copied");
        setTimeout(() => setCopied(false), 2000);
      },
      () => toast.error("Copy failed — select the code manually"),
    );
  }

  return (
    <Card data-testid="gym-code-card">
      <CardBody className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="space-y-1">
          <h2 className="font-semibold text-gray-900">Gym code</h2>
          <p className="text-sm text-gray-500" data-testid="gym-code-help">
            First-time members type this code when the app asks them to specify
            their gym — it signs them into your gym. Share it with your members.
          </p>
          {error && (
            <p className="text-sm text-red-600" data-testid="gym-code-error">
              {error}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2">
          {gymCode ? (
            <>
              <code
                data-testid="gym-code-value"
                className="rounded-lg bg-gray-100 px-3 py-2 font-mono text-lg font-semibold tracking-widest text-gray-900"
              >
                {gymCode}
              </code>
              <button
                type="button"
                onClick={copyGymCode}
                aria-label={`Copy gym code ${gymCode}`}
                data-testid="gym-code-copy"
                className="rounded-lg border border-gray-300 p-2 text-gray-500 transition-colors hover:border-brand-400 hover:text-brand-600 focus:outline-none focus:ring-2 focus:ring-brand-500"
              >
                {copied ? (
                  <Check className="h-4 w-4 text-green-600" aria-hidden="true" />
                ) : (
                  <Copy className="h-4 w-4" aria-hidden="true" />
                )}
              </button>
            </>
          ) : (
            !error && (
              <span className="text-sm text-gray-400" data-testid="gym-code-loading">
                Loading…
              </span>
            )
          )}
        </div>
      </CardBody>
    </Card>
  );
}
