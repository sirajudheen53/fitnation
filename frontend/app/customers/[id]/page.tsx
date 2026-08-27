"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { CustomerTabs, type CustomerTabKey } from "@/features/customers/components/CustomerTabs";
import { OverviewTab } from "@/features/customers/components/OverviewTab";
import { FitnessGoalsTab } from "@/features/customers/components/FitnessGoalsTab";
import { BodyMeasurementsTab } from "@/features/customers/components/BodyMeasurementsTab";
import { HealthProfileTab } from "@/features/customers/components/HealthProfileTab";
import { ProgressPhotosTab } from "@/features/customers/components/ProgressPhotosTab";
import { PaymentHistoryTab } from "@/features/customers/components/PaymentHistoryTab";
import { Spinner, Alert, Button, Badge } from "@/components/ui";
import { getToken } from "@/lib/auth";
import {
  fetchCustomer,
  fetchProgressSummary,
  fetchFitnessGoals,
  fetchBodyMeasurements,
  fetchHealthProfile,
  fetchProgressPhotos,
  createFitnessGoal,
  updateFitnessGoal,
  createBodyMeasurement,
  updateCustomerHealthProfile,
  createProgressPhoto,
  errorMessage,
} from "@/lib/api";
import { getCustomerDisplayName, getCustomerMembershipStatus } from "@/features/customers/components/CustomerTable";
import type { Customer } from "@/types/customer";
import type {
  BodyMeasurement,
  BodyMeasurementFormData,
  CustomerFitnessGoal,
  FitnessGoalFormData,
  HealthProfile,
  HealthProfileUpdate,
  ProgressPhoto,
  ProgressPhotoFormData,
  ProgressSummary,
} from "@/types/customer-detail";

export default function CustomerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);

  const [activeTab, setActiveTab] = useState<CustomerTabKey>("overview");
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [summary, setSummary] = useState<ProgressSummary | null>(null);
  const [goals, setGoals] = useState<CustomerFitnessGoal[]>([]);
  const [goalsLoaded, setGoalsLoaded] = useState(false);
  const [measurements, setMeasurements] = useState<BodyMeasurement[]>([]);
  const [measurementsLoaded, setMeasurementsLoaded] = useState(false);
  const [healthProfile, setHealthProfile] = useState<HealthProfile | null>(null);
  const [healthLoaded, setHealthLoaded] = useState(false);
  const [photos, setPhotos] = useState<ProgressPhoto[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/customers/" + id);
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [cust, sum] = await Promise.all([
          fetchCustomer(id, authToken),
          fetchProgressSummary(id, authToken),
        ]);
        setCustomer(cust);
        setSummary(sum);
        setGoals(sum.fitness_goals ?? []);
        setHealthProfile(sum.health_profile ?? null);
        if (sum.latest_measurement) {
          setMeasurements((prev) =>
            prev.some((m) => m.id === sum.latest_measurement!.id)
              ? prev
              : [sum.latest_measurement as BodyMeasurement, ...prev],
          );
        }
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  // Lazy-load full tab data on first visit (the summary only includes the latest measurement).
  useEffect(() => {
    if (!customer) return;
    const token = getToken();
    if (!token) return;
    const authToken: string = token;

    async function loadGoals() {
      try {
        const list = await fetchFitnessGoals(id, authToken);
        setGoals(list);
        setGoalsLoaded(true);
      } catch {
        /* summary already seeded goals; ignore list errors here */
      }
    }
    async function loadMeasurements() {
      try {
        const list = await fetchBodyMeasurements(id, authToken);
        setMeasurements(list);
        setMeasurementsLoaded(true);
      } catch {
        /* noop */
      }
    }
    async function loadHealth() {
      try {
        const profile = await fetchHealthProfile(id, authToken);
        setHealthProfile(profile);
        setHealthLoaded(true);
      } catch {
        setHealthProfile(null);
      }
    }
    async function loadPhotos() {
      try {
        const list = await fetchProgressPhotos(id, authToken);
        setPhotos(list);
      } catch {
        /* noop */
      }
    }

    if (activeTab === "goals" && !goalsLoaded) loadGoals();
    if (activeTab === "measurements" && !measurementsLoaded) loadMeasurements();
    if (activeTab === "health" && !healthLoaded) loadHealth();
    if (activeTab === "photos") loadPhotos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, customer, summary]);

  const updateGoal = async (goalId: number, data: Partial<FitnessGoalFormData>) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateFitnessGoal(id, goalId, data, token);
      setGoals((prev) => prev.map((g) => (g.id === updated.id ? updated : g)));
      toast.success("Goal updated");
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };
  const addGoal = async (data: FitnessGoalFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createFitnessGoal(id, data, token);
      setGoals((prev) => [created, ...prev]);
      toast.success("Goal added");
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const addMeasurement = async (data: BodyMeasurementFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createBodyMeasurement(id, data, token);
      setMeasurements((prev) => [...prev, created]);
      toast.success("Measurement saved");
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const saveHealthProfile = async (data: HealthProfileUpdate) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateCustomerHealthProfile(id, data, token);
      setHealthProfile(updated);
      toast.success("Health profile saved");
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const addPhoto = async (data: ProgressPhotoFormData) => {
    const token = getToken();
    if (!token) return;
    setSaving(true);
    setSaveError(null);
    try {
      const created = await createProgressPhoto(id, data, token);
      setPhotos((prev) => [...prev, created]);
      toast.success("Photo uploaded");
    } catch (err) {
      setSaveError(err);
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const statusBadge = customer
    ? getCustomerMembershipStatus(customer)
    : { label: "—", variant: "default" as const };

  /** Build a first-vs-latest comparison for the measurements tab. */
  function buildMeasurementComparison(
    list: BodyMeasurement[],
  ): { first: BodyMeasurement | null; latest: BodyMeasurement | null; diff: Record<string, string> } {
    if (list.length === 0) return { first: null, latest: null, diff: {} };
    const sorted = [...list].sort((a, b) => a.date_logged.localeCompare(b.date_logged));
    const first = sorted[0];
    const latest = sorted[sorted.length - 1];
    const diff: Record<string, string> = {};
    const fields: (keyof BodyMeasurement)[] = [
      "weight_kg", "bmi", "body_fat_percentage",
      "chest_cm", "waist_cm", "hips_cm", "biceps_cm", "thighs_cm", "neck_cm",
    ];
    for (const field of fields) {
      const f = first[field];
      const l = latest[field];
      if (f != null && l != null) {
        const delta = Number(l) - Number(f);
        if (delta !== 0) {
          diff[field] = `${delta > 0 ? "+" : ""}${Number(delta.toFixed(1))}`;
        }
      }
    }
    return { first, latest, diff };
  }

  return (
    <DashboardLayout
      title={customer ? getCustomerDisplayName(customer) : "Customer detail"}
      actions={
        customer ? (
          <Button variant="outline" size="sm" onClick={() => router.push(`/customers/${customer.id}/edit`)}>
            Edit
          </Button>
        ) : null
      }
    >
      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {error && !customer && <Alert variant="error">{error}</Alert>}
      {customer && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex-1">
              <p className="text-sm text-gray-500">{customer.email}</p>
              <p className="text-sm text-gray-500">Phone: {customer.phone || "—"}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Status</p>
              <Badge variant={statusBadge.variant}>{statusBadge.label}</Badge>
            </div>
          </div>

          <div className="border-b border-gray-200">
            <CustomerTabs active={activeTab} onChange={setActiveTab} />
          </div>

          <div>
            {activeTab === "overview" && <OverviewTab customer={customer} summary={summary} />}
            {activeTab === "goals" && (
              <FitnessGoalsTab
                goals={goals}
                saving={saving}
                error={saveError}
                onAdd={addGoal}
                onUpdate={updateGoal}
              />
            )}
            {activeTab === "measurements" && (
              <BodyMeasurementsTab
                measurements={measurements}
                saving={saving}
                error={saveError}
                onAdd={addMeasurement}
                measurementComparison={buildMeasurementComparison(measurements)}
              />
            )}
            {activeTab === "health" && (
              <HealthProfileTab
                profile={healthProfile}
                saving={saving}
                error={saveError}
                onSave={saveHealthProfile}
              />
            )}
            {activeTab === "photos" && (
              <ProgressPhotosTab
                photos={photos}
                saving={saving}
                error={saveError}
                onAdd={addPhoto}
              />
            )}
            {activeTab === "payments" && <PaymentHistoryTab customer={customer} />}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
