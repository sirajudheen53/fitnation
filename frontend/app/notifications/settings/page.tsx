"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { NotificationSettingsForm } from "@/features/notifications/components/NotificationSettingsForm";
import { Alert, Spinner } from "@/components/ui";
import {
  fetchNotificationSettings,
  sendTestNotification,
  updateNotificationSettings,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { WatiSettings, WatiSettingsUpdate } from "@/types/notification";

export default function NotificationSettingsPage() {
  const router = useRouter();
  const [settings, setSettings] = useState<WatiSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [testResult, setTestResult] = useState<
    { ok: boolean; message: string } | undefined
  >(undefined);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/settings")) {
      router.replace("/unauthorized");
      return;
    }

    const token = getToken();
    if (!token) {
      router.replace("/login?next=/notifications/settings");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const data = await fetchNotificationSettings(authToken);
        setSettings(data);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [router, userRole]);

  const handleSave = async (data: WatiSettingsUpdate) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      const updated = await updateNotificationSettings(data, authToken);
      setSettings(updated);
      toast.success("Settings saved");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async ({ to }: { to: string }) => {
    const token = getToken();
    if (!token) return;
    if (!to.trim()) {
      setTestResult({ ok: false, message: "Enter a recipient phone number." });
      return;
    }
    const authToken: string = token;
    setTesting(true);
    setTestResult(undefined);
    try {
      const result = await sendTestNotification({ to, notification_type: "check_in" }, authToken);
      if (result.status === "sent") {
        setTestResult({ ok: true, message: "Test message sent successfully." });
        toast.success("Test message sent");
      } else if (result.status === "failed") {
        setTestResult({
          ok: false,
          message: result.error_message || "Test message failed to send.",
        });
        toast.error("Test message failed");
      } else {
        setTestResult({ ok: false, message: "Test message was not sent (check Wati is enabled)." });
      }
    } catch (err) {
      setTestResult({ ok: false, message: errorMessage(err) });
      toast.error(errorMessage(err));
    } finally {
      setTesting(false);
    }
  };

  return (
    <DashboardLayout title="WhatsApp notifications">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && !settings && error != null && (
        <Alert variant="error">{errorMessage(error)}</Alert>
      )}
      {!loading && (
        <NotificationSettingsForm
          settings={settings}
          saving={saving}
          testing={testing}
          error={error}
          testResult={testResult}
          onSave={handleSave}
          onTest={handleTest}
        />
      )}
    </DashboardLayout>
  );
}
