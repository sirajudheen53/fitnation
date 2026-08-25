"use client";

import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { KeyRound, Lock, Webhook, Save } from "lucide-react";
import { Alert, Button, Card, CardBody, CardFooter, CardHeader, Input, Spinner } from "@/components/ui";
import { errorMessage, fetchRazorpayConfig, updateRazorpayConfig } from "@/lib/api";
import { getToken } from "@/lib/auth";

const configSchema = z.object({
  api_key: z.string().min(1, "API key is required"),
  api_secret: z.string().optional().or(z.literal("")),
  webhook_secret: z.string().optional().or(z.literal("")),
  is_active: z.boolean(),
});

type ConfigSchemaData = z.infer<typeof configSchema>;

export function RazorpayConfigForm() {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    watch,
    formState: { errors },
  } = useForm<ConfigSchemaData>({
    resolver: zodResolver(configSchema),
    defaultValues: {
      api_key: "",
      api_secret: "",
      webhook_secret: "",
      is_active: false,
    },
  });

  const isActive = watch("is_active");

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchRazorpayConfig(token)
      .then((config) => {
        reset({
          api_key: config.api_key,
          api_secret: "",
          webhook_secret: "",
          is_active: config.is_active,
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

    // Only send secrets if the admin provided new values; the backend keeps
    // existing secrets otherwise (write-only fields).
    const payload = {
      api_key: data.api_key,
      is_active: data.is_active,
      ...(data.api_secret ? { api_secret: data.api_secret } : {}),
      ...(data.webhook_secret ? { webhook_secret: data.webhook_secret } : {}),
    };

    try {
      await updateRazorpayConfig(payload, token);
      setSaved(true);
      reset({
        api_key: data.api_key,
        api_secret: "",
        webhook_secret: "",
        is_active: data.is_active,
      });
    } catch (err) {
      setSaveError(errorMessage(err));
    } finally {
      setSaving(false);
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
    <Card>
      <CardHeader>
        <h2 className="text-lg font-semibold text-gray-900">Razorpay configuration</h2>
        <p className="text-sm text-gray-500">
          Connect your Razorpay account to accept online payments for memberships and
          services. Secrets are stored encrypted and never returned by the API.
        </p>
      </CardHeader>
      <CardBody>
        {loadError && <Alert variant="error">{loadError}</Alert>}
        {saveError && <Alert variant="error">{saveError}</Alert>}
        {saved && <Alert variant="success">Configuration saved.</Alert>}

        <form onSubmit={handleSubmit(handleSave)} className="space-y-5">
          <Input
            label="API Key (Key ID)"
            placeholder="rzp_live_..."
            icon={<KeyRound className="h-4 w-4" />}
            error={errors.api_key?.message}
            {...register("api_key")}
          />
          <Input
            label="API Secret (Key Secret)"
            type="password"
            placeholder="Leave blank to keep the current secret"
            icon={<Lock className="h-4 w-4" />}
            error={errors.api_secret?.message}
            {...register("api_secret")}
          />
          <Input
            label="Webhook Secret"
            type="password"
            placeholder="Leave blank to keep the current secret"
            icon={<Webhook className="h-4 w-4" />}
            error={errors.webhook_secret?.message}
            {...register("webhook_secret")}
          />

          <label className="flex items-start gap-3 rounded-lg border border-gray-200 bg-gray-50 p-4">
            <input
              type="checkbox"
              checked={isActive}
              onChange={(e) => setValue("is_active", e.target.checked)}
              className="mt-1 h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            />
            <span>
              <span className="block text-sm font-medium text-gray-900">
                Enable Razorpay payments
              </span>
              <span className="block text-xs text-gray-500">
                When enabled, the checkout will be available to staff with payment
                permissions.
              </span>
            </span>
          </label>
        </form>
      </CardBody>
      <CardFooter className="flex items-center gap-3">
        <Button type="submit" onClick={handleSubmit(handleSave)} loading={saving}>
          <Save className="h-4 w-4" />
          Save configuration
        </Button>
      </CardFooter>
    </Card>
  );
}
