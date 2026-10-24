"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { MessageCircle } from "lucide-react";
import { Badge, Card, CardBody } from "@/components/ui";
import {
  errorMessage,
  fetchNotificationLogs,
  fetchTenant,
  unwrapNotificationLogs,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Communication-channels WhatsApp cards for the settings index (issue #73).
 *
 * Both WhatsApp cards (WATI + Gupshup) show the live configured state as the
 * backend returns it — enabled badge, endpoint/source/app name, keyed-or-not,
 * and the last test-send result — instead of static descriptions that stayed
 * "not configured" after a successful save. Fetched on mount, so returning
 * here after saving on /settings/whatsapp or /settings/gupshup shows fresh
 * state. Cards link through to their dedicated config pages.
 */

interface ChannelState {
  enabled: boolean;
  keyConfigured: boolean;
  /** Provider-specific display lines (endpoint / source+app). */
  details: string[];
}

interface LastTest {
  status: string;
  provider: string;
  error_message: string;
  created_at: string;
}

type ChannelKey = "wati" | "gupshup";

const CHANNEL_HREFS: Record<ChannelKey, string> = {
  wati: "/settings/whatsapp",
  gupshup: "/settings/gupshup",
};

const CHANNEL_TITLES: Record<ChannelKey, string> = {
  wati: "WhatsApp (WATI)",
  gupshup: "Gupshup WhatsApp",
};

function formatTestRow(row: LastTest): string {
  const when = new Date(row.created_at).toLocaleString();
  if (row.status === "sent") return `sent ${when}`;
  if (row.status === "failed") {
    return `failed ${when}${row.error_message ? ` — ${row.error_message}` : ""}`;
  }
  return `${row.status} ${when}`;
}

function channelDetails(
  provider: ChannelKey,
  tenant: Awaited<ReturnType<typeof fetchTenant>>,
): ChannelState {
  if (provider === "wati") {
    return {
      enabled: Boolean(tenant.is_wati_enabled),
      keyConfigured: Boolean(tenant.wati_api_key_configured),
      details: tenant.wati_endpoint ? [`Endpoint: ${tenant.wati_endpoint}`] : [],
    };
  }
  return {
    enabled: Boolean(tenant.is_gupshup_enabled),
    keyConfigured: Boolean(tenant.gupshup_api_key_configured),
    details: [`Source: ${tenant.gupshup_source || "—"}`, `App: ${tenant.gupshup_app_name || "—"}`],
  };
}

function ChannelCard({
  provider,
  state,
  lastTest,
}: {
  provider: ChannelKey;
  state: ChannelState | null;
  lastTest: LastTest | null;
}) {
  return (
    <Link href={CHANNEL_HREFS[provider]} className="group" data-testid={`${provider}-channel-card`}>
      <Card className="h-full transition-colors group-hover:border-brand-400">
        <CardBody className="space-y-2">
          <div className="flex items-start justify-between gap-2">
            <MessageCircle className="h-6 w-6 text-brand-600" />
            {state &&
              (state.enabled ? (
                <Badge variant="success" data-testid={`${provider}-channel-active`}>
                  Enabled
                </Badge>
              ) : (
                <Badge variant="default" data-testid={`${provider}-channel-inactive`}>
                  Not enabled
                </Badge>
              ))}
          </div>
          <h2 className="font-semibold text-gray-900">{CHANNEL_TITLES[provider]}</h2>
          {!state && <p className="text-sm text-gray-400">Loading configuration…</p>}
          {state && (
            <>
              {state.details.map((line) => (
                <p key={line} className="text-sm text-gray-500" data-testid={`${provider}-channel-detail`}>
                  {line}
                </p>
              ))}
              <p className="text-sm text-gray-500">
                API key:{" "}
                {state.keyConfigured ? (
                  <span className="font-medium text-gray-700" data-testid={`${provider}-channel-key-configured`}>
                    Configured
                  </span>
                ) : (
                  <span className="text-amber-600" data-testid={`${provider}-channel-key-missing`}>
                    Not configured
                  </span>
                )}
              </p>
              <p
                className="text-xs text-gray-500"
                data-testid={`${provider}-channel-last-test`}
                title="The last welcome-message test send for this provider (from the audit log)."
              >
                {lastTest ? `Last test: ${formatTestRow(lastTest)}` : "Last test: none yet"}
              </p>
            </>
          )}
        </CardBody>
      </Card>
    </Link>
  );
}

/** The settings-index grid of both WhatsApp channel cards. */
export function WhatsAppChannels() {
  const [states, setStates] = useState<Partial<Record<ChannelKey, ChannelState>>>({});
  const [lastTests, setLastTests] = useState<Partial<Record<ChannelKey, LastTest | null>>>({});
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    fetchTenant(authToken)
      .then((tenant) => {
        setStates({ wati: channelDetails("wati", tenant), gupshup: channelDetails("gupshup", tenant) });
      })
      .catch((err) => setLoadError(errorMessage(err)));
    // Last welcome test-send attempt per provider (audit rows, newest first);
    // failure degrades to "none yet" — the links work without the logs API.
    for (const provider of ["wati", "gupshup"] as const) {
      fetchNotificationLogs(authToken, { notification_type: "welcome", provider })
        .then((res) => unwrapNotificationLogs(res)[0])
        .then((row) =>
          setLastTests((prev) => ({
            ...prev,
            [provider]: row
              ? {
                  status: row.status,
                  provider: row.provider ?? provider,
                  error_message: row.error_message,
                  created_at: row.created_at,
                }
              : null,
          })),
        )
        .catch(() => setLastTests((prev) => ({ ...prev, [provider]: null })));
    }
  }, []);

  return (
    <section>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-gray-500">
        Communication channels
      </h2>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {loadError && <p className="text-sm text-red-600">{loadError}</p>}
        <ChannelCard provider="wati" state={states.wati ?? null} lastTest={lastTests.wati ?? null} />
        <ChannelCard provider="gupshup" state={states.gupshup ?? null} lastTest={lastTests.gupshup ?? null} />
      </div>
    </section>
  );
}