"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Card, CardBody } from "@/components/ui";
import {
  errorMessage,
  fetchTenantFeatureSettings,
  updateTenantFeatureFlags,
  type ModuleFeatureMeta,
} from "@/lib/api";
import { getToken } from "@/lib/auth";

/**
 * Modules — per-gym module feature toggles (issue #63; backend #46). Owners
 * switch product modules (marketplace, AI coach, …) on/off for their gym;
 * enforcement is server-side, this card is the control surface.
 */
export function ModulesCard() {
  const [flags, setFlags] = useState<Record<string, boolean> | null>(null);
  const [catalog, setCatalog] = useState<ModuleFeatureMeta[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savingKey, setSavingKey] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchTenantFeatureSettings(token)
      .then((settings) => {
        setFlags(settings.flags);
        setCatalog(settings.catalog);
      })
      .catch((err) => setLoadError(errorMessage(err)));
  }, []);

  async function toggle(meta: ModuleFeatureMeta) {
    const token = getToken();
    if (flags === null || savingKey !== null || !token) return;
    const previous = flags;
    const enabled = !flags[meta.key];
    setFlags({ ...flags, [meta.key]: enabled }); // optimistic
    setSaveError(null);
    setSavingKey(meta.key);
    try {
      const refreshed = await updateTenantFeatureFlags(
        { [meta.key]: enabled },
        token,
      );
      setFlags(refreshed.flags);
      setCatalog(refreshed.catalog);
      toast.success(`${meta.label} ${enabled ? "enabled" : "disabled"}`);
    } catch (err) {
      setFlags(previous); // rollback
      setSaveError(errorMessage(err));
    } finally {
      setSavingKey(null);
    }
  }

  return (
    <Card data-testid="modules-card">
      <CardBody className="space-y-3">
        <div className="space-y-1">
          <h2 className="font-semibold text-gray-900">Modules</h2>
          <p className="text-sm text-gray-500">
            Turn gym modules on or off for your members. Disabled modules are
            hidden in the app and blocked at the API.
          </p>
        </div>

        {(loadError || saveError) && (
          <p
            data-testid="modules-error"
            className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600"
            role="alert"
          >
            {loadError ?? saveError}
          </p>
        )}

        {flags === null && !loadError && (
          <span className="text-sm text-gray-400" data-testid="modules-loading">
            Loading…
          </span>
        )}

        <ul className="divide-y divide-gray-100">
          {catalog.map((meta) => {
            const enabled = flags?.[meta.key] ?? meta.default;
            const saving = savingKey !== null;
            return (
              <li
                key={meta.key}
                className="flex items-center justify-between gap-4 py-3 first:pt-0 last:pb-0"
              >
                <div>
                  <p className="text-sm font-medium text-gray-900">{meta.label}</p>
                  <p className="text-xs text-gray-500">{meta.description}</p>
                </div>
                <button
                  type="button"
                  role="switch"
                  aria-checked={enabled}
                  aria-label={meta.label}
                  disabled={saving || flags === null}
                  data-testid={`module-toggle-${meta.key}`}
                  onClick={() => toggle(meta)}
                  className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
                    enabled ? "bg-green-600" : "bg-gray-300"
                  }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
                      enabled ? "translate-x-6" : "translate-x-1"
                    }`}
                  />
                </button>
              </li>
            );
          })}
        </ul>
      </CardBody>
    </Card>
  );
}
