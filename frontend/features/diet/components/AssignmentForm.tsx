"use client";

import { useState } from "react";
import { Users, Apple, Calendar, StickyNote } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Customer } from "@/types/customer";
import type { DietAssignmentFormData, DietPlan } from "@/types/diet";
import { errorMessage } from "@/lib/api";
import { getCustomerDisplayName } from "@/features/customers/components/CustomerTable";

interface AssignmentFormProps {
  customers: Customer[];
  plans: DietPlan[];
  submitLabel?: string;
  onSubmit: (data: DietAssignmentFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function AssignmentForm({
  customers,
  plans,
  submitLabel = "Assign plan",
  onSubmit,
  error,
  loading = false,
}: AssignmentFormProps) {
  const [customer, setCustomer] = useState<number | "">("");
  const [dietPlan, setDietPlan] = useState<number | "">("");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (customer === "" || dietPlan === "" || !startDate) {
      setFormError("Customer, plan and start date are required.");
      return;
    }
    if (endDate && new Date(endDate) < new Date(startDate)) {
      setFormError("End date must be on or after the start date.");
      return;
    }
    setFormError(null);
    void onSubmit({
      customer: Number(customer),
      diet_plan: Number(dietPlan),
      start_date: startDate,
      end_date: endDate || undefined,
      notes: notes || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {formError && <Alert variant="error">{formError}</Alert>}

      <div className="space-y-1.5">
        <label htmlFor="customer" className="block text-sm font-medium text-gray-700">
          Customer
        </label>
        <div className="relative">
          <Users className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <select
            id="customer"
            value={customer}
            onChange={(e) => setCustomer(e.target.value ? Number(e.target.value) : "")}
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select customer</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>
                {getCustomerDisplayName(c)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="diet_plan" className="block text-sm font-medium text-gray-700">
          Diet plan
        </label>
        <div className="relative">
          <Apple className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <select
            id="diet_plan"
            value={dietPlan}
            onChange={(e) => setDietPlan(e.target.value ? Number(e.target.value) : "")}
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select plan</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} — {p.daily_calories} kcal/day
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Start date"
          type="date"
          value={startDate}
          onChange={(e) => setStartDate(e.target.value)}
          icon={<Calendar className="h-4 w-4" />}
        />
        <Input
          label="End date (optional)"
          type="date"
          value={endDate}
          onChange={(e) => setEndDate(e.target.value)}
          icon={<Calendar className="h-4 w-4" />}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="notes" className="block text-sm font-medium text-gray-700">
          Notes
        </label>
        <div className="relative">
          <StickyNote className="pointer-events-none absolute left-3 top-3 text-gray-400" />
          <textarea
            id="notes"
            rows={3}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Optional notes for this assignment"
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
