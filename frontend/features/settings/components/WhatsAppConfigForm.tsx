"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { KeyRound, Lock, MessageCircle, Save, Send, Webhook } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardFooter,
  CardHeader,
  Input,
  Spinner,
} from "@/components/ui";
import {
  errorMessage,
  fetchTenant,
  fetchWhatsappStatus,
  sendWhatsappTest,
  updateTenantWhatsappConfig,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

const configSchema = z.object({
  wati_endpoint: z
    .string()
    .trim()
    .optional()
    .or(z.literal(""))
    .refine((v) => !v || /^https?:\/\//.test(v), "Enter a valid https URL"),
  wati_api_key: z.string().optional().or(z.literal("")),
});

type ConfigSchemaData = z.infer<typeof configSchema>;

/**
 * Tenant WhatsApp (WATI) configuration — FBOS-011 §6 / F4.
 *
 * Backend status: `GET /tenants/me/` exists but does not yet serialize the
 * WATI fields, and `PATCH /tenants/me/`, `POST /tenants/whatsapp/test/`,
 * `GET /tenants/whatsapp/status/` (task B9) are not implemented yet — the UI
 * is coded against the FBOS-011 §6 contract and degrades gracefully (fields
 * read as absent, usage line hidden) until B9 lands.
 */
export function WhatsAppConfigForm() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const [enabled, setEnabled] = useState(false);
  const [keyConfigured, setKeyConfigured] = useState(false);

  const [testPhone, setTestPhone] = useState("");
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ ok: boolean; message: string } | null>(null);

  const [usage, setUsage] = useState<{
    otp_sent_today: number;
    invites_sent_today: number;
    daily_cap: number;
  } | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ConfigSchemaData>({
    resolver: zodResolver(configSchema),
    defaultValues: { wati_endpoint: "", wati_api_key: "" },
  });

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    fetchTenant(authToken)
      .then((tenant) => {
        // Pre-B9 payloads lack the WATI fields entirely — treat as unconfigured.
        setEnabled(Boolean(tenant.is_wati_enabled));
        setKeyConfigured(Boolean(tenant.wati_api_key_configured));
        reset({
          wati_endpoint: tenant.wati_endpoint ?? "",
          wati_api_key: "",
        });
      })
      .catch((err) => setLoadError(errorMessage(err)))
      .finally(() => setLoading(false));
    // Usage counters are optional (endpoint lands with B9).
    fetchWhatsappStatus(authToken)
      .then(setUsage)
      .catch(() => setUsage(null));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async (data: ConfigSchemaData) => {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    const token = getToken();
    if (!token) {
      setSaveError("You must be logged in.");
      setSaving(false);
      return;
    }
    // The API key is write-only: send it only when the owner typed a new one.
    const payload = {
      is_wati_enabled: enabled,
      wati_endpoint: data.wati_endpoint ?? "",
      ...(data.wati_api_key ? { wati_api_key: data.wati_api_key } : {}),
    };
    try {
      const tenant = await updateTenantWhatsappConfig(payload, token);
      setKeyConfigured(
        data.wati_api_key ? true : Boolean(tenant.wati_api_key_configured),
      );
      reset({ wati_endpoint: data.wati_endpoint ?? "", wati_api_key: "" });
      setSaved(true);
    } catch (err) {
      setSaveError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleTestSend = async () => {
    const token = getToken();
    if (!token) return;
    setTesting(true);
    setTestResult(null);
    try {
      const result = await sendWhatsappTest(testPhone.trim(), token);
      const ok = result.status === "sent";
      setTestResult({
        ok,
        message: ok
          ? `Test message sent to +91${testPhone.trim()} — check the phone.`
          : `Send finished with status "${result.status}"${result.detail ? `: ${result.detail}` : ""}.`,
      });
    } catch (err) {
      setTestResult({ ok: false, message: errorMessage(err) });
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center py-20">
        <Spinner className="h-8 w-8" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">WhatsApp (WATI)</h2>
          <p className="text-sm text-gray-500">
            Member app invites and OTPs go out over WhatsApp when configured, falling
            back to SMS. The API key is stored encrypted and never shown again.
          </p>
        </CardHeader>
        <CardBody>
          {loadError && <Alert variant="error">{loadError}</Alert>}
          {saveError && <Alert variant="error">{saveError}</Alert>}
          {saved && <Alert variant="success">WhatsApp configuration saved.</Alert>}

          <div className="mb-5 flex items-center gap-2 text-sm">
            <span className="text-gray-700">WATI API key:</span>
            {keyConfigured ? (
              <Badge variant="success" data-testid="wati-key-configured">
                Configured (••••)
              </Badge>
            ) : (
              <Badge variant="warning" data-testid="wati-key-missing">
                Not configured
              </Badge>
            )}
          </div>

          <form onSubmit={handleSubmit(handleSave)} className="space-y-5">
            <Input
              label="WATI endpoint"
              placeholder="https://api.wati.io"
              hint="Paste your WATI API base — the full sendSessionMessage URL works too."
              icon={<Webhook className="h-4 w-4" />}
              error={errors.wati_endpoint?.message}
              {...register("wati_endpoint")}
            />
            <Input
              label="WATI API key"
              type="password"
              placeholder={keyConfigured ? "Leave blank to keep the configured key" : "Your WATI API key"}
              icon={<KeyRound className="h-4 w-4" />}
              error={errors.wati_api_key?.message}
              {...register("wati_api_key")}
            />

            <label className="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="mt-1 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
              />
              <span>
                <span className="block text-sm font-medium text-gray-900">
                  Enable WhatsApp for this gym
                </span>
                <span className="block text-xs text-gray-500">
                  Without this, app invites and OTPs fall back to SMS.
                </span>
              </span>
            </label>

            <Button type="submit" loading={saving}>
              <Save className="h-4 w-4" />
              Save configuration
            </Button>
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">Test send</h2>
          <p className="text-sm text-gray-500">
            Sends the welcome template to a phone number so you can see WhatsApp work
            before inviting members.
          </p>
        </CardHeader>
        <CardBody className="space-y-4">
          {testResult && (
            <Alert variant={testResult.ok ? "success" : "error"}>{testResult.message}</Alert>
          )}
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <div className="flex-1">
              <Input
                label="Phone to message"
                type="tel"
                inputMode="numeric"
                maxLength={10}
                placeholder="9876543210"
                icon={<Lock className="h-4 w-4 opacity-0" />}
                value={testPhone}
                onChange={(e) => setTestPhone(e.target.value.replace(/\D/g, ""))}
              />
            </div>
            <Button
              type="button"
              variant="outline"
              loading={testing}
              disabled={!/^\d{10}$/.test(testPhone)}
              onClick={handleTestSend}
            >
              <Send className="h-4 w-4" />
              Send test message
            </Button>
          </div>
          {usage && (
            <p className="text-xs text-gray-500" data-testid="whatsapp-usage">
              <MessageCircle className="mr-1 inline h-3 w-3" />
              Today: {usage.otp_sent_today} OTPs · {usage.invites_sent_today} invites · cap{" "}
              {usage.daily_cap}
            </p>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
