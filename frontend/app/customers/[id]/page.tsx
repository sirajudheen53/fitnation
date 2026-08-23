"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { HealthProfileForm } from "@/features/customers/components/HealthProfileForm";
import { Spinner, Alert, Card, CardBody, CardHeader, Button } from "@/components/ui";
import { fetchCustomer, updateHealthProfile, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import type { Customer, HealthProfileFormData } from "@/types/customer";
import {
  getCustomerDisplayName,
  getCustomerMembershipStatus,
} from "@/features/customers/components/CustomerTable";

type Tab = "profile" | "health" | "measurements" | "goals";

const TABS: { value: Tab; label: string }[] = [
  { value: "profile", label: "Profile" },
  { value: "health", label: "Health" },
  { value: "measurements", label: "Measurements" },
  { value: "goals", label: "Goals" },
];

export default function CustomerDetailPage() {
  const params = useParams();
  const router = useRouter();
  const searchParams = useSearchParams();
  const id = Number(params.id);
  const initialTab = (searchParams.get("tab") as Tab) || "profile";
  const [activeTab, setActiveTab] = useState<Tab>(initialTab);
  const [customer, setCustomer] = useState<Customer | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthError, setHealthError] = useState<unknown>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/customers/" + id);
      return;
    }

    const authToken: string = token;

    async function load() {
      try {
        const data = await fetchCustomer(id, authToken);
        setCustomer(data);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const handleHealthSubmit = async (data: HealthProfileFormData) => {
    const token = getToken();
    if (!token || !customer) return;
    setHealthLoading(true);
    setHealthError(null);
    try {
      const updated = await updateHealthProfile(customer.id, data, token);
      setCustomer(updated);
    } catch (err) {
      setHealthError(err);
    } finally {
      setHealthLoading(false);
    }
  };

  const statusBadge = customer
    ? getCustomerMembershipStatus(customer)
    : { label: "—", variant: "default" as const };

  return (
    <DashboardLayout
      title={customer ? getCustomerDisplayName(customer) : "Customer detail"}
      actions={
        customer ? (
          <Button variant="outline" size="sm" onClick={() => router.push(`/customers/${customer.id}/edit`)} >
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
      {error && <Alert variant="error">{error}</Alert>}
      {customer && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-4 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex-1">
              <p className="text-sm text-gray-500">{customer.email}</p>
              <p className="text-sm text-gray-500">Phone: {customer.phone || "—"}</p>
            </div>
            <div className="text-right">
              <p className="text-sm text-gray-500">Status</p>
              <span className={`inline-flex rounded-full px-2.5 py-0.5 text-xs font-medium ${
                statusBadge.variant === "success"
                  ? "bg-green-100 text-green-800"
                  : statusBadge.variant === "danger"
                  ? "bg-red-100 text-red-800"
                  : "bg-gray-100 text-gray-800"
              }`}>
                {statusBadge.label}
              </span>
            </div>
          </div>

          <div className="border-b border-gray-200">
            <nav className="-mb-px flex gap-6" aria-label="Customer tabs">
              {TABS.map((tab) => (
                <button
                  key={tab.value}
                  onClick={() => setActiveTab(tab.value)}
                  className={`border-b-2 px-1 pb-3 text-sm font-medium ${
                    activeTab === tab.value
                      ? "border-brand-600 text-brand-600"
                      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                  }`}
                  aria-current={activeTab === tab.value ? "page" : undefined}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {activeTab === "profile" && (
            <Card>
              <CardHeader>
                <h3 className="text-base font-semibold text-gray-900">Profile</h3>
              </CardHeader>
              <CardBody className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div>
                  <p className="text-sm text-gray-500">First name</p>
                  <p className="font-medium text-gray-900">{customer.first_name}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Last name</p>
                  <p className="font-medium text-gray-900">{customer.last_name}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Date of birth</p>
                  <p className="font-medium text-gray-900">{customer.date_of_birth || "—"}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Gender</p>
                  <p className="font-medium text-gray-900">{customer.gender || "—"}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Emergency contact</p>
                  <p className="font-medium text-gray-900">
                    {customer.emergency_contact_name || "—"}
                  </p>
                  <p className="text-sm text-gray-500">{customer.emergency_contact_phone || "—"}</p>
                </div>
                <div>
                  <p className="text-sm text-gray-500">Branch ID</p>
                  <p className="font-medium text-gray-900">{customer.branch_id || "—"}</p>
                </div>
              </CardBody>
            </Card>
          )}

          {activeTab === "health" && (
            <HealthProfileForm
              customer={customer}
              onSubmit={handleHealthSubmit}
              error={healthError}
              loading={healthLoading}
            />
          )}

          {activeTab === "measurements" && (
            <Card>
              <CardHeader>
                <h3 className="text-base font-semibold text-gray-900">Measurements</h3>
              </CardHeader>
              <CardBody>
                <p className="text-sm text-gray-500">
                  Body measurements tracking will be available here.
                </p>
              </CardBody>
            </Card>
          )}

          {activeTab === "goals" && (
            <Card>
              <CardHeader>
                <h3 className="text-base font-semibold text-gray-900">Goals</h3>
              </CardHeader>
              <CardBody>
                <p className="text-sm text-gray-500">
                  Fitness goals and milestones will be available here.
                </p>
              </CardBody>
            </Card>
          )}
        </div>
      )}
    </DashboardLayout>
  );
}
