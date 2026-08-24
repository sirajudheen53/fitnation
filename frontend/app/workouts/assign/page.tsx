"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { AssignmentForm } from "@/features/workouts/components/AssignmentForm";
import { AssignmentTable } from "@/features/workouts/components/AssignmentTable";
import { Spinner, Alert, Card, CardHeader, CardBody } from "@/components/ui";
import {
  fetchCustomers,
  fetchWorkoutPlans,
  fetchWorkoutAssignments,
  assignWorkoutPlan,
  errorMessage,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Customer } from "@/types/customer";
import type {
  WorkoutAssignment,
  WorkoutAssignmentFormData,
  WorkoutPlan,
} from "@/types/workout";

export default function WorkoutAssignPage() {
  const router = useRouter();

  const [customers, setCustomers] = useState<Customer[]>([]);
  const [plans, setPlans] = useState<WorkoutPlan[]>([]);
  const [assignments, setAssignments] = useState<WorkoutAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/workouts/assign")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/workouts/assign");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [customerRes, planRes, assignRes] = await Promise.all([
          fetchCustomers(authToken),
          fetchWorkoutPlans(authToken),
          fetchWorkoutAssignments(authToken),
        ]);
        setCustomers(customerRes.results);
        setPlans(planRes.results);
        setAssignments(assignRes.results);
      } catch (err) {
        setError(err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [router, userRole]);

  const handleSubmit = async (data: WorkoutAssignmentFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setError(null);
    try {
      await assignWorkoutPlan(data, token);
      toast.success("Workout plan assigned");
      const authToken: string = token;
      const assignRes = await fetchWorkoutAssignments(authToken);
      setAssignments(assignRes.results);
    } catch (err) {
      setError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <DashboardLayout title="Assign workout plan">
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
              <h2 className="text-lg font-semibold text-gray-900">New assignment</h2>
            </CardHeader>
            <CardBody>
              <AssignmentForm
                customers={customers}
                plans={plans}
                onSubmit={handleSubmit}
                error={error}
                loading={saving}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader>
              <h2 className="text-lg font-semibold text-gray-900">Assignments</h2>
            </CardHeader>
            <CardBody>
              <AssignmentTable assignments={assignments} />
            </CardBody>
          </Card>
        </div>
      )}
    </DashboardLayout>
  );
}
