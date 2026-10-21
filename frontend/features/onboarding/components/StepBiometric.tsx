"use client";

import { Fingerprint } from "lucide-react";
import { Alert, Button } from "@/components/ui";
import type { AccessDevice, AccessCredentialType } from "@/types/access";
import { CREDENTIAL_TYPE_LABELS } from "@/types/access";
import type { OnboardingFormState } from "../lib/wizard";

interface StepBiometricProps {
  state: OnboardingFormState;
  /** Active devices at the selected branch (inactive ones filtered out). */
  devices: AccessDevice[];
  loading: boolean;
  onChange: (patch: Partial<OnboardingFormState>) => void;
  onBack: () => void;
  /** Enroll with the selected device — validates the device user id first. */
  onSubmitWithBiometrics: () => void;
  /** Skip enrollment (biometrics omitted from the payload). */
  onSkip: () => void;
  submitting: boolean;
}

export function StepBiometric({
  state,
  devices,
  loading,
  onChange,
  onBack,
  onSubmitWithBiometrics,
  onSkip,
  submitting,
}: StepBiometricProps) {
  const noDevice = !loading && devices.length === 0;
  const deviceError =
    state.deviceId !== null && state.deviceUserId.trim() === ""
      ? "Enter the device user ID shown after the scan"
      : null;

  return (
    <div className="space-y-5" data-testid="step-biometric">
      {loading && (
        <div className="flex h-32 items-center justify-center text-sm text-gray-500">
          Loading devices…
        </div>
      )}

      {noDevice && (
        <Alert variant="info" data-testid="no-device-empty-state">
          <span className="font-medium">No biometric device at this branch</span> — the
          member will check in via the app / QR. You can enroll them later from their
          profile&apos;s Access tab.
        </Alert>
      )}

      {!loading && !noDevice && (
        <>
          <div className="flex items-start gap-3 rounded-lg border border-blue-200 bg-blue-50 p-4 text-sm text-blue-800">
            <Fingerprint className="mt-0.5 h-5 w-5 shrink-0" />
            <span>
              Ask the member to place their finger on the scanner. The device assigns a
              user ID — confirm it below.
            </span>
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="space-y-1.5">
              <label htmlFor="onboarding-device" className="block text-sm font-medium text-gray-700">
                Device
              </label>
              <select
                id="onboarding-device"
                value={state.deviceId ?? ""}
                onChange={(e) =>
                  onChange({ deviceId: e.target.value === "" ? null : Number(e.target.value) })
                }
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select a device…</option>
                {devices.map((device) => (
                  <option key={device.id} value={device.id}>
                    {device.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="onboarding-credential" className="block text-sm font-medium text-gray-700">
                Credential type
              </label>
              <select
                id="onboarding-credential"
                value={state.credentialType}
                onChange={(e) =>
                  onChange({ credentialType: e.target.value as AccessCredentialType })
                }
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="fingerprint">{CREDENTIAL_TYPE_LABELS.fingerprint}</option>
                <option value="face">{CREDENTIAL_TYPE_LABELS.face}</option>
              </select>
            </div>
          </div>

          {state.deviceId !== null && (
            <div className="max-w-sm space-y-1.5">
              <label htmlFor="onboarding-device-user" className="block text-sm font-medium text-gray-700">
                Device user ID
              </label>
              <input
                id="onboarding-device-user"
                type="text"
                placeholder="e.g. 1017"
                value={state.deviceUserId}
                onChange={(e) => onChange({ deviceUserId: e.target.value })}
                className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              {deviceError && <p className="text-sm text-red-600">{deviceError}</p>}
            </div>
          )}
        </>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Button type="button" variant="outline" onClick={onBack} disabled={submitting}>
          Back
        </Button>
        {!noDevice && (
          <Button
            type="button"
            onClick={onSubmitWithBiometrics}
            loading={submitting}
            disabled={state.deviceId === null || deviceError !== null}
          >
            Finish onboarding
          </Button>
        )}
        <Button
          type="button"
          variant="ghost"
          onClick={onSkip}
          loading={submitting}
          data-testid="skip-biometric"
        >
          {noDevice ? "Finish onboarding" : "Skip for now"}
        </Button>
      </div>
    </div>
  );
}
