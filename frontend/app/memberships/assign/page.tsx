"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { toast } from "sonner";
import { Users, CreditCard, Calendar, DollarSign } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Input, Alert, Spinner } from "@/components/ui";
import { fetchMembershipPlans, fetchCustomers, assignMembership, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { AssignMembershipData } from "@/types/membership";
import type { Customer } from "@/types/customer";
import type { MembershipPlan } from "@/types/membership";

const assignSchema = z
  .object({
    customer_id: z.coerce.number().int().positive("Select a customer"),
    plan_id: z.coerce.number().int().positive("Select a plan"),
    start_date: z.string().min(1, "Start date is required"),
    end_date: z.string().min(1, "End date is required"),
    coupon_code: z.string().max(50).optional().or(z.literal("")),
    amount_paid: z.coerce.number().min(0).optional().or(z.nan().transform(() => undefined)),
  })
  .refine((data) => new Date(data.end_date) >= new Date(data.start_date), {
    message: "End date must be on or after the start date",
    path: ["end_date"],
  });

type AssignSchemaData = z.infer<typeof assignSchema>;

export default function AssignMembershipPage() {
  const router = useRouter();
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [plans, setPlans] = useState<MembershipPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors },
  } = useForm<AssignSchemaData>({
    resolver: zodResolver(assignSchema),
    defaultValues: {
      customer_id: undefined,
      plan_id: undefined,
      start_date: "",
      end_date: "",
      coupon_code: "",
      amount_paid: undefined,
    },
  });

  const watchPlanId = watch("plan_id");
  const selectedPlan = useMemo(
    () => plans.find((p) => p.id === Number(watchPlanId)),
    [plans, watchPlanId],
  );

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/memberships/assign");
      return;
    }
    const authToken: string = token;
    async function load() {
      try {
        const [customerRes, planRes] = await Promise.all([
          fetchCustomers(authToken),
          fetchMembershipPlans(authToken),
        ]);
        setCustomers(customerRes.results);
        setPlans(planRes.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router]);

  const handleFormSubmit = async (data: AssignSchemaData) => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    setSaving(true);
    setError(null);
    try {
      const payload: AssignMembershipData = {
        customer_id: data.customer_id,
        plan_id: data.plan_id,
        start_date: data.start_date,
        end_date: data.end_date,
        coupon_code: data.coupon_code || undefined,
        amount_paid:
          data.amount_paid !== undefined && !Number.isNaN(data.amount_paid)
            ? data.amount_paid
            : undefined,
      };
      await assignMembership(payload, authToken);
      toast.success("Membership assigned");
      router.push("/memberships");
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Assign membership">
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <form onSubmit={handleSubmit(handleFormSubmit)} className="max-w-3xl space-y-6">
          {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

          <div className="space-y-1.5">
            <label htmlFor="customer_id" className="block text-sm font-medium text-gray-700">
              Customer
            </label>
            <div className="relative">
              <Users className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <select
                id="customer_id"
                {...register("customer_id")}
                className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select customer</option>
                {customers.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.first_name} {c.last_name} ({c.email})
                  </option>
                ))}
              </select>
            </div>
            {errors.customer_id?.message && (
              <p className="text-sm text-red-600">{errors.customer_id.message}</p>
            )}
          </div>

          <div className="space-y-1.5">
            <label htmlFor="plan_id" className="block text-sm font-medium text-gray-700">
              Plan
            </label>
            <div className="relative">
              <CreditCard className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <select
                id="plan_id"
                {...register("plan_id")}
                className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="">Select plan</option>
                {plans.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name} — ₹{Number(p.price).toLocaleString()} / {p.duration_days} days
                  </option>
                ))}
              </select>
            </div>
            {errors.plan_id?.message && (
              <p className="text-sm text-red-600">{errors.plan_id.message}</p>
            )}
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Start date"
              type="date"
              icon={<Calendar className="h-4 w-4" />}
              error={errors.start_date?.message}
              {...register("start_date")}
            />
            <Input
              label="End date"
              type="date"
              icon={<Calendar className="h-4 w-4" />}
              error={errors.end_date?.message}
              {...register("end_date")}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <Input
              label="Coupon code"
              placeholder="FIT10"
              error={errors.coupon_code?.message}
              {...register("coupon_code")}
            />
            <Input
              label="Amount paid"
              type="number"
              step="0.01"
              min="0"
              placeholder={
                selectedPlan ? String(Number(selectedPlan.price).toFixed(2)) : "Amount"
              }
              icon={<DollarSign className="h-4 w-4" />}
              error={errors.amount_paid?.message}
              {...register("amount_paid")}
            />
          </div>

          <div className="flex items-center gap-3">
            <Button type="submit" loading={saving}>
              Assign membership
            </Button>
          </div>
        </form>
      )}
    </DashboardLayout>
  );
}
