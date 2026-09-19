"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Copy, RotateCcw, Table2 } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Card, CardBody, Input } from "@/components/ui";
import { errorMessage, onboardGym } from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import { SUBSCRIPTION_PLANS, type AdminOnboardGymResult } from "@/types/admin";

const EMPTY_FORM = {
  gym_name: "",
  contact_name: "",
  owner_email: "",
  owner_phone: "",
  branch_name: "",
  plan_code: "starter",
};

export default function AdminOnboardGymPage() {
  const router = useRouter();
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [result, setResult] = useState<AdminOnboardGymResult | null>(null);

  useEffect(() => {
    if (user && user.role !== "platform_admin") {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) router.replace("/login?next=/admin/onboard");
  }, [router, user]);

  function setField<K extends keyof typeof EMPTY_FORM>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function submit() {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    setFieldErrors({});
    try {
      const res = await onboardGym(form, token);
      setResult(res);
      setForm(EMPTY_FORM);
      toast.success(`${res.tenant_name} onboarded!`);
    } catch (err) {
      const data = (err as { data?: unknown }).data;
      if (data && typeof data === "object" && !Array.isArray(data)) {
        const entries = Object.entries(data as Record<string, unknown>);
        if (entries.length) {
          setFieldErrors(
            Object.fromEntries(entries.map(([k, v]) => [k, Array.isArray(v) ? v : [String(v)]])),
          );
        }
      }
      setError(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  function copyPassword() {
    if (!result) return;
    navigator.clipboard.writeText(result.owner_password).then(
      () => toast.success("Password copied"),
      () => toast.error("Copy failed — select the password manually"),
    );
  }

  return (
    <DashboardLayout title="Onboard Gym — Platform Admin">
      {result ? (
        /* ── Success: credential handover ─────────────────────────── */
        <Card className="mx-auto max-w-xl">
          <CardBody className="space-y-4 text-center">
            <div className="text-3xl">🎉</div>
            <h2 className="text-lg font-semibold text-gray-900">
              {result.tenant_name} is live!
            </h2>
            <p className="text-sm text-gray-500">
              Share these credentials with the gym owner — the password is shown
              only once.
            </p>
            <div className="space-y-2 rounded-lg bg-gray-50 p-4 text-left text-sm">
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">Owner login</span>
                <span className="font-mono text-gray-900">{result.owner_email}</span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">Password</span>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-gray-900">{result.owner_password}</span>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={copyPassword}
                    aria-label="Copy password"
                  >
                    <Copy className="h-4 w-4" />
                  </Button>
                </span>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-gray-500">Plan</span>
                <span className="capitalize text-gray-900">{result.plan_code}</span>
              </div>
            </div>
            <div className="flex justify-center gap-2">
              <Button variant="outline" onClick={() => setResult(null)}>
                <RotateCcw className="mr-2 h-4 w-4" /> Onboard another
              </Button>
              <Button onClick={() => router.push("/admin")}>
                <Table2 className="mr-2 h-4 w-4" /> View gyms
              </Button>
            </div>
          </CardBody>
        </Card>
      ) : (
        /* ── Form ─────────────────────────────────────────────────── */
        <Card className="mx-auto max-w-xl">
          <CardBody className="space-y-4">
            {error && <p className="text-sm text-red-600">{error}</p>}
            <Input
              label="Gym name"
              value={form.gym_name}
              onChange={(e) => setField("gym_name", e.target.value)}
              error={fieldErrors.gym_name?.[0]}
              placeholder="Iron Temple Fitness"
            />
            <Input
              label="Owner full name"
              value={form.contact_name}
              onChange={(e) => setField("contact_name", e.target.value)}
              error={fieldErrors.contact_name?.[0]}
              placeholder="Ravi Kumar"
            />
            <Input
              label="Owner email (their login)"
              type="email"
              value={form.owner_email}
              onChange={(e) => setField("owner_email", e.target.value)}
              error={fieldErrors.owner_email?.[0]}
              placeholder="owner@gym.com"
            />
            <Input
              label="Owner phone (optional)"
              value={form.owner_phone}
              onChange={(e) => setField("owner_phone", e.target.value)}
              error={fieldErrors.owner_phone?.[0]}
              placeholder="+91 98765 43210"
            />
            <Input
              label="First branch name"
              value={form.branch_name}
              onChange={(e) => setField("branch_name", e.target.value)}
              error={fieldErrors.branch_name?.[0]}
              placeholder="Main Branch"
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-gray-700">
                Subscription plan
              </label>
              <select
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                value={form.plan_code}
                onChange={(e) => setField("plan_code", e.target.value)}
              >
                {SUBSCRIPTION_PLANS.map((p) => (
                  <option key={p.code} value={p.code}>
                    {p.label}
                  </option>
                ))}
              </select>
            </div>
            <Button onClick={submit} disabled={saving} className="w-full">
              {saving ? "Provisioning…" : "Onboard Gym"}
            </Button>
            <p className="text-xs text-gray-400">
              The gym goes live immediately — no email verification needed. The
              owner password is generated for you.
            </p>
          </CardBody>
        </Card>
      )}
    </DashboardLayout>
  );
}