"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { MessageCircle, KeyRound, Link2, Send } from "lucide-react";
import { Button, Input, Alert, Badge } from "@/components/ui";
import type { WatiSettings, WatiSettingsUpdate } from "@/types/notification";
import { errorMessage } from "@/lib/api";

const settingsSchema = z.object({
  wati_endpoint: z.preprocess(
    (v) => (typeof v === "string" && v.trim() === "" ? undefined : v),
    z
      .string()
      .url("Enter a valid URL (e.g. https://api.wati.io/api/v1/...)")
      .optional(),
  ),
  wati_api_key: z.preprocess(
    (v) => (typeof v === "string" && v.trim() === "" ? undefined : v),
    z.string().min(1, "API key is required").optional(),
  ),
});

type SettingsSchemaData = z.infer<typeof settingsSchema>;

interface NotificationSettingsFormProps {
  settings: WatiSettings | null;
  loading?: boolean;
  saving?: boolean;
  testing?: boolean;
  error?: unknown;
  testResult?: TestResultState;
  onSave: (data: WatiSettingsUpdate) => void | Promise<void>;
  onTest: (data: { to: string }) => void | Promise<void>;
}

interface TestResultState {
  ok: boolean;
  message: string;
}

export function NotificationSettingsForm({
  settings,
  loading = false,
  saving = false,
  testing = false,
  error,
  testResult,
  onSave,
  onTest,
}: NotificationSettingsFormProps) {
  const {
    register,
    handleSubmit,
    reset,
    setValue,
    formState: { errors },
  } = useForm<SettingsSchemaData>({
    resolver: zodResolver(settingsSchema),
    defaultValues: {
      wati_endpoint: "",
      wati_api_key: "",
    },
  });

  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    if (settings) {
      setValue("wati_endpoint", settings.wati_endpoint);
      // Deriving toggle state from the fetched settings is a legitimate
      // props-to-state sync; the React Compiler hint is a perf note only.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setEnabled(settings.is_wati_enabled);
    }
  }, [settings, setValue]);

  const handleSave = (data: SettingsSchemaData) => {
    const payload: WatiSettingsUpdate = {};
    if (data.wati_endpoint) payload.wati_endpoint = data.wati_endpoint;
    if (data.wati_api_key) payload.wati_api_key = data.wati_api_key;
    payload.is_wati_enabled = enabled;
    onSave(payload);
  };

  const connectionVariant: "success" | "danger" | "default" = !settings
    ? "default"
    : settings.is_wati_enabled
      ? "success"
      : "danger";

  return (
    <form onSubmit={handleSubmit(handleSave)} className="max-w-2xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      {/* Connection status indicator */}
      <div className="flex items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-green-50 text-green-600">
            <MessageCircle className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-medium text-gray-900">
              {loading
                ? "Loading connection status…"
                : settings?.is_wati_enabled
                  ? "WhatsApp notifications enabled"
                  : "WhatsApp notifications disabled"}
            </p>
            <p className="text-xs text-gray-500">
              {settings?.wati_api_key_configured
                ? "API key configured"
                : "No API key configured yet"}
            </p>
          </div>
        </div>
        <Badge variant={connectionVariant}>
          {settings?.is_wati_enabled ? "Connected" : "Disconnected"}
        </Badge>
      </div>

      {/* Enable / disable toggle */}
      <label className="flex cursor-pointer items-center justify-between rounded-lg border border-gray-200 bg-white p-4">
        <div>
          <p className="text-sm font-medium text-gray-900">Enable WhatsApp notifications</p>
          <p className="text-xs text-gray-500">
            Send automated reminders for check-ins, membership expiry, workouts and payments.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          aria-label="Enable WhatsApp notifications"
          onClick={() => setEnabled((v) => !v)}
          className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors ${
            enabled ? "bg-green-600" : "bg-gray-300"
          }`}
        >
          <span
            className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
              enabled ? "translate-x-6" : "translate-x-1"
            }`}
          />
        </button>
      </label>

      <Input
        label="Wati Endpoint URL"
        placeholder="https://api.wati.io/api/v1/sendSessionMessage"
        icon={<Link2 className="h-4 w-4" />}
        hint="Your Wati API base URL. Leave blank to keep the current value."
        error={errors.wati_endpoint?.message}
        {...register("wati_endpoint")}
      />

      <Input
        label="Wati API Key"
        type="password"
        placeholder="Paste a new API key (optional)"
        icon={<KeyRound className="h-4 w-4" />}
        hint={
          settings?.wati_api_key_configured
            ? "An API key is already configured. Leave blank to keep it."
            : "Enter your Wati API key."
        }
        autoComplete="off"
        error={errors.wati_api_key?.message}
        {...register("wati_api_key")}
      />

      <div className="flex items-center gap-3">
        <Button type="submit" loading={saving}>
          Save settings
        </Button>
      </div>

      {/* Test message */}
      <div className="space-y-3 rounded-lg border border-gray-200 bg-white p-4">
        <h3 className="text-sm font-medium text-gray-900">Send a test message</h3>
        <p className="text-xs text-gray-500">
          Verify your Wati integration by sending a test WhatsApp message to a phone number.
        </p>
        <div className="flex flex-col gap-3 sm:flex-row">
          <Input
            placeholder="Recipient phone (e.g. +91 98765 43210)"
            id="test-recipient"
            className="flex-1"
          />
          <Button
            type="button"
            variant="outline"
            loading={testing}
            onClick={(e) => {
              const input = document.getElementById("test-recipient") as HTMLInputElement | null;
              onTest({ to: input?.value ?? "" });
              e.preventDefault();
            }}
          >
            <Send className="h-4 w-4" /> Send test
          </Button>
        </div>
        {testResult && (
          <Alert variant={testResult.ok ? "success" : "error"}>{testResult.message}</Alert>
        )}
      </div>
    </form>
  );
}
