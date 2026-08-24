"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { LogForm } from "@/features/workouts/components/LogForm";
import { LogTable } from "@/features/workouts/components/LogTable";
import { Spinner, Alert, Card, CardHeader, CardBody } from "@/components/ui";
import {
  fetchCustomers,
  fetchWorkoutAssignments,
  fetchWorkoutPlans,
  fetchWorkoutLogs,
  createWorkoutLog,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Customer } from "@/types/customer";
import type {
  WorkoutExercise,
  WorkoutLog,
  WorkoutLogFormData,
  WorkoutPlan,
} from "@/types/workout";
import { getCustomerDisplayName } from "@/features/customers/components/CustomerTable";

export default function WorkoutLogPage() {
  const router = useRouter();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [plans, setPlans] = useState<WorkoutPlan[]>([]);
  const [logs, setLogs] = useState<WorkoutLog[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<number | "">("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/workouts/log")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/workouts/log");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [customerRes, planRes] = await Promise.all([
          fetchCustomers(authToken),
          fetchWorkoutPlans(authToken),
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
  }, [router, userRole]);

  const handleCustomerChange = async (customerId: number | "") => {
    setSelectedCustomer(customerId);
    setLogs([]);
    const token = getToken();
    if (!token || customerId === "") return;
    try {
      const logRes = await fetchWorkoutLogs(token, { customer: String(customerId) });
      setLogs(logRes.results);
    } catch (err) {
      setError(err);
    }
  };

  // Exercises available to log: from the customer's active assignment plan.
  const availableExercises: WorkoutExercise[] = (() => {
    if (selectedCustomer === "") return [];
    const result: WorkoutExercise[] = [];
    for (const plan of plans) {
      for (const day of plan.days) {
        for (const ex of day.exercises) {
          result.push(ex);
        }
      }
    }
    return result;
  })();

  const handleSubmit = async (data: WorkoutLogFormData) => {
    const token = getToken();
    if (!token) return;
    if (selectedCustomer === "") return;
    setSaving(true);
    setError(null);
    try {
      await createWorkoutLog(
        { ...data, customer: Number(selectedCustomer) },
        token,
      );
      toast.success("Workout logged");
      const authToken: string = token;
      const logRes = await fetchWorkoutLogs(authToken, {
        customer: String(selectedCustomer),
      });
      setLogs(logRes.results);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Workout log">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && (
        <div className="space-y-8">
          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Select customer</h2>
            </CardHeader>
            <CardBody>
              <div className="max-w-md space-y-1.5">
                <label
                  htmlFor="log-customer"
                  className="block text-sm font-medium text-gray-700"
                >
                  Customer
                </label>
                <select
                  id="log-customer"
                  value={selectedCustomer}
                  onChange={(e) =>
                    handleCustomerChange(
                      e.target.value ? Number(e.target.value) : "",
                    )
                  }
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">Select customer</option>
                  {customers.map((c) => (
                    <option key={c.id} value={c.id}>
                      {getCustomerDisplayName(c)}
                    </option>
                  ))}
                </select>
              </div>
            </CardBody>
          </Card>

          {selectedCustomer !== "" && (
            <>
              <Card>
                <CardHeader>
                  <h2 className="text-lg font-semibold text-gray-900">Log a set</h2>
                </CardHeader>
                <CardBody>
                  <LogForm
                    exercises={availableExercises}
                    onSubmit={handleSubmit}
                    error={error}
                    loading={saving}
                  />
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <h2 className="text-lg font-semibold text-gray-900">Progress</h2>
                </CardHeader>
                <CardBody>
                  <LogTable logs={logs} />
                </CardBody>
              </Card>
            </>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
