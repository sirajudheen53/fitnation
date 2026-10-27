"use client";

import { useState } from "react";
import Link from "next/link";
import { User, CalendarDays, Mail, ChevronDown, ChevronRight } from "lucide-react";
import { Alert, Button, Input, PhoneInput } from "@/components/ui";
import type { Customer, Gender } from "@/types/customer";
import type { Branch } from "@/types/branch";
import { isValidPhoneE164, parsePhoneInput } from "@/lib/phone";
import { GENDER_OPTIONS } from "../lib/wizard";
import type { OnboardingFormState } from "../lib/wizard";

interface StepWhoProps {
  state: OnboardingFormState;
  branches: Branch[];
  onChange: (patch: Partial<OnboardingFormState>) => void;
  /**
   * Phone lookup on blur; the wizard owns the query (loading state).
   * Receives the bare national digits — the backend's search matches them
   * against both E.164 and legacy raw rows (issue #88).
   */
  onPhoneBlur: (phone: string) => void;
  lookupLoading: boolean;
  onNext: () => void;
}

export function StepWho({
  state,
  branches,
  onChange,
  onPhoneBlur,
  lookupLoading,
  onNext,
}: StepWhoProps) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [moreOpen, setMoreOpen] = useState(false);

  const handlePhoneBlur = () => {
    if (!isValidPhoneE164(state.phone)) return;
    // The search runs on the national digits so the backend's icontains
    // search matches both E.164 and legacy bare rows (issue #88).
    onPhoneBlur(parsePhoneInput(state.phone).national);
  };

  const validate = (): boolean => {
    const next: Record<string, string> = {};
    if (!isValidPhoneE164(state.phone)) {
      next.phone = "Enter a valid phone number";
    }
    if (state.name.trim() === "") next.name = "Name is required";
    if (state.branchId === null) next.branchId = "Select a branch";
    setErrors(next);
    return Object.keys(next).length === 0;
  };

  const handleNext = () => {
    if (validate()) onNext();
  };

  const returning = state.returningMember;

  return (
    <div className="space-y-5" data-testid="step-who">
      {returning && (
        <Alert variant="warning" data-testid="returning-member-banner">
          <span className="font-medium">Returning member</span> — their profile will be
          updated, not duplicated.{" "}
          <Link
            href={`/customers/${returning.id}`}
            className="font-medium underline"
          >
            Open existing profile
          </Link>
        </Alert>
      )}

      <div className="max-w-sm">
        <PhoneInput
          label="Phone number"
          error={errors.phone}
          hint={lookupLoading ? "Looking up…" : "The member's phone IS their login"}
          value={state.phone}
          onBlur={handlePhoneBlur}
          onChange={(value) => {
            // Editing the phone clears the returning-member banner (stale match).
            onChange({
              phone: value,
              returningMember: null,
            });
          }}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Full name"
          placeholder="Asha Nair"
          icon={<User className="h-4 w-4" />}
          error={errors.name}
          value={state.name}
          onChange={(e) => onChange({ name: e.target.value })}
        />
        <Input
          label="Date of birth"
          type="date"
          icon={<CalendarDays className="h-4 w-4" />}
          error={errors.dateOfBirth}
          value={state.dateOfBirth}
          onChange={(e) => onChange({ dateOfBirth: e.target.value })}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <div className="space-y-1.5">
          <span className="block text-sm font-medium text-gray-700">Gender</span>
          <div className="flex overflow-hidden rounded-lg border border-gray-300">
            {GENDER_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                onClick={() => onChange({ gender: option.value as Gender })}
                className={`flex-1 px-3 py-2.5 text-sm font-medium transition-colors ${
                  state.gender === option.value
                    ? "bg-brand-600 text-white"
                    : "bg-white text-gray-700 hover:bg-gray-50"
                }`}
              >
                {option.label}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-1.5">
          <label htmlFor="onboarding-branch" className="block text-sm font-medium text-gray-700">
            Branch
          </label>
          <select
            id="onboarding-branch"
            value={state.branchId ?? ""}
            onChange={(e) =>
              onChange({ branchId: e.target.value === "" ? null : Number(e.target.value) })
            }
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select a branch…</option>
            {branches.map((branch) => (
              <option key={branch.id} value={branch.id}>
                {branch.name}
              </option>
            ))}
          </select>
          {errors.branchId && <p className="text-sm text-red-600">{errors.branchId}</p>}
        </div>
      </div>

      <div className="max-w-sm">
        <Input
          label="Email (optional)"
          type="email"
          placeholder="Leave blank to use phone login"
          icon={<Mail className="h-4 w-4" />}
          value={state.email}
          onChange={(e) => onChange({ email: e.target.value })}
        />
      </div>

      <div>
        <button
          type="button"
          onClick={() => setMoreOpen((open) => !open)}
          className="inline-flex items-center gap-1 text-sm font-medium text-brand-600 hover:text-brand-700"
          aria-expanded={moreOpen}
        >
          {moreOpen ? (
            <ChevronDown className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          )}
          More (emergency contact)
        </button>
        {moreOpen && (
          <div className="mt-3 grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Emergency contact name"
              value={state.emergencyContactName}
              onChange={(e) => onChange({ emergencyContactName: e.target.value })}
            />
            <PhoneInput
              label="Emergency contact phone"
              value={state.emergencyContactPhone}
              onChange={(value) => onChange({ emergencyContactPhone: value })}
            />
          </div>
        )}
      </div>

      <div className="flex items-center gap-3">
        <Button type="button" onClick={handleNext}>
          Next: Plan &amp; payment
        </Button>
      </div>
    </div>
  );
}
