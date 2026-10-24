"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AppWindow, KeyRound, Save, Send, Smartphone } from "lucide-react";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Input,
  Spinner,
} from "@/components/ui";
import {
  errorMessage,
  fetchTenant,
  sendWhatsappTest,
  updateTenantGupshupConfig,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

const configSchema = z.object({
  gupshup_source: z.string().trim().max(20, "Max 20 characters").optional().or(z.literal("")),
  gupshup_app_name: z.string().trim().max(100, "Max 100 characters").optional().or(z.literal("")),
  gupshup_api_key: z.string().optional().or(z.literal("")),
});

type ConfigSchemaData = z.infer<typeof configSchema>;

/**
 * Tenant Gupshup WhatsApp configuration — issue #67 (contract #66).
 *
 * Mirrors WhatsAppConfigForm: the API key is write-only (send only when the
 * owner types a new one), reads surface a "configured" badge, and the test
 * send targets the same endpoint with provider: "gupshup". Per the #66
 * channel policy, whichever WhatsApp channel is configured carries all
 * communications — this card is where the gym opts into Gupshup.
 */
export function GupshupConfigForm() {
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

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ConfigSchemaData>({
    resolver: zodResolver(configSchema),
    defaultValues: { gupshup_source: "", gupshup_app_name: "", gupshup_api_key: "" },
  });

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    fetchTenant(authToken)
      .then((tenant) => {
        // Pre-#66 payloads lack the Gupshup fields entirely — treat as unconfigured.
        setEnabled(Boolean(tenant.is_gupshup_enabled));
        setKeyConfigured(Boolean(tenant.gupshup_api_key_configured));
        reset({
          gupshup_source: tenant.gupshup_source ?? "",
          gupshup_app_name: tenant.gupshup_app_name ?? "",
          gupshup_api_key: "",
        });
      })
      .catch((err) => setLoadError(errorMessage(err)))
      .finally(() => setLoading(false));
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
      is_gupshup_enabled: enabled,
      gupshup_source: data.gupshup_source ?? "",
      gupshup_app_name: data.gupshup_app_name ?? "",
      ...(data.gupshup_api_key ? { gupshup_api_key: data.gupshup_api_key } : {}),
    };
    try {
      const tenant = await updateTenantGupshupConfig(payload, token);
      setKeyConfigured(
        data.gupshup_api_key ? true : Boolean(tenant.gupshup_api_key_configured),
      );
      reset({
        gupshup_source: data.gupshup_source ?? "",
        gupshup_app_name: data.gupshup_app_name ?? "",
        gupshup_api_key: "",
      });
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
      const result = await sendWhatsappTest(testPhone.trim(), token, "gupshup");
      const ok = result.status === "sent";
      setTestResult({
        ok,
        message: ok
          ? `Test message sent to +91${testPhone.trim()} — check the phone.` +
            `${result.provider_status ? ` Provider accepted it (status: ${result.provider_status}).` : ""}` +
            `${result.message_id ? ` Message id: ${result.message_id}.` : ""}`
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
          <h2 className="text-lg font-semibold text-gray-900">Gupshup WhatsApp</h2>
          <p className="text-sm text-gray-500">
            Configure Gupshup as the gym&apos;s WhatsApp channel — when set up, app
            invites and OTPs go out over Gupshup. The API key is stored encrypted
            and never shown again.
          </p>
        </CardHeader>
        <CardBody>
          {loadError && <Alert variant="error">{loadError}</Alert>}
          {saveError && <Alert variant="error">{saveError}</Alert>}
          {saved && <Alert variant="success">Gupshup configuration saved.</Alert>}

          <div className="mb-5 flex items-center gap-2 text-sm">
            <span className="text-gray-700">Gupshup API key:</span>
            {keyConfigured ? (
              <Badge variant="success" data-testid="gupshup-key-configured">
                Configured (••••)
              </Badge>
            ) : (
              <Badge variant="warning" data-testid="gupshup-key-missing">
                Not configured
              </Badge>
            )}
          </div>

          <form onSubmit={handleSubmit(handleSave)} className="space-y-5">
            <Input
              label="Gupshup source number"
              placeholder="917899876543"
              hint="The WhatsApp sender number registered in Gupshup (the “source” form field)."
              icon={<Smartphone className="h-4 w-4" />}
              error={errors.gupshup_source?.message}
              {...register("gupshup_source")}
            />
            <Input
              label="Gupshup app name"
              placeholder="FitNation App"
              hint="The Gupshup app messages are sent through (the “src.name” form field)."
              icon={<AppWindow className="h-4 w-4" />}
              error={errors.gupshup_app_name?.message}
              {...register("gupshup_app_name")}
            />
            <Input
              label="Gupshup API key"
              type="password"
              placeholder={keyConfigured ? "Leave blank to keep the configured key" : "Your Gupshup API key"}
              icon={<KeyRound className="h-4 w-4" />}
              error={errors.gupshup_api_key?.message}
              {...register("gupshup_api_key")}
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
                  Enable Gupshup for this gym
                </span>
                <span className="block text-xs text-gray-500">
                  Whichever WhatsApp channel is configured carries all communications;
                  without either, invites and OTPs fall back to SMS.
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
            Sends the welcome template through your Gupshup app to a phone number so
            you can verify the connection before inviting members.
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
        </CardBody>
      </Card>
    </div>
  );
}
