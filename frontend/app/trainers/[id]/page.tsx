"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { toast } from "sonner";
import { ArrowLeft, Pencil, Star, Users } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, DeletedUserBadge, Button, Card, CardBody, CardHeader, Spinner } from "@/components/ui";
import {
  errorMessage,
  fetchTrainer,
  fetchTrainerAssignments,
  updateTrainer,
} from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import { canAccessRoute, hasPermission } from "@/lib/permissions";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { TrainerFormDialog } from "@/features/trainers/components/TrainerFormDialog";
import { TrainerScheduleSection } from "@/features/trainers/components/TrainerScheduleSection";
import {
  certificationLabel,
  formatRating,
  resolveTrainerPhoto,
  trainerInitials,
  trainerName,
} from "@/features/trainers/components/trainers-shared";
import type {
  BranchTrainerAssignment,
  Trainer,
} from "@/types/trainer";

type ProfileTab = "overview" | "customers" | "schedule";

const TABS: { key: ProfileTab; label: string }[] = [
  { key: "overview", label: "Overview" },
  { key: "customers", label: "Customers" },
  { key: "schedule", label: "Schedule" },
];

export default function TrainerProfilePage() {
  const router = useRouter();
  const params = useParams<{ id: string }>();
  const id = params.id;

  const [trainer, setTrainer] = useState<Trainer | null>(null);
  const [assignments, setAssignments] = useState<BranchTrainerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<ProfileTab>("overview");
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));
  const [assignmentFilter, setAssignmentFilter] = useState<"all" | "active" | "inactive">("all");
  const [formOpen, setFormOpen] = useState(false);
  const [confirmToggle, setConfirmToggle] = useState(false);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (user && !canAccessRoute(user.role, "/trainers")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace(`/login?next=/trainers/${id}`);
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [trainerData, assignmentData] = await Promise.all([
          fetchTrainer(id, authToken),
          // Non-fatal: the tab degrades to an error note when unavailable.
          fetchTrainerAssignments(authToken).catch(() => null),
        ]);
        setTrainer(trainerData);
        setAssignments(assignmentData ?? []);
        if (assignmentData === null) {
          setError("Could not load assignments.");
        }
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [id, router, user]);

  const trainerAssignments = useMemo(
    () => assignments.filter((a) => a.trainer === Number(id)),
    [assignments, id],
  );

  const filteredAssignments = useMemo(
    () =>
      trainerAssignments.filter((a) => {
        if (assignmentFilter === "active") return a.is_active;
        if (assignmentFilter === "inactive") return !a.is_active;
        return true;
      }),
    [trainerAssignments, assignmentFilter],
  );

  const activeClientCount = trainerAssignments.filter((a) => a.is_active).length;

  const replaceTrainer = useCallback((updated: Trainer) => {
    setTrainer(updated);
  }, []);

  async function toggleActive() {
    if (!trainer) return;
    const token = getToken();
    if (!token) return;
    setToggling(true);
    try {
      const updated = await updateTrainer(
        trainer.id,
        { is_active: !trainer.is_active },
        token,
      );
      replaceTrainer(updated);
      setConfirmToggle(false);
      toast.success(
        updated.is_active
          ? `${trainerName(updated)} reactivated.`
          : `${trainerName(updated)} deactivated.`,
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setToggling(false);
    }
  }

  const canEdit = user ? hasPermission(user.role, "users.edit_user") : false;
  const photo = trainer ? resolveTrainerPhoto(trainer) : null;

  return (
    <DashboardLayout
      title="Trainer profile"
      actions={
        trainer && canEdit ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" size="sm" onClick={() => setFormOpen(true)}>
              <Pencil className="mr-2 h-4 w-4" /> Edit
            </Button>
            <Button
              variant={trainer.is_active ? "danger" : "primary"}
              size="sm"
              onClick={() => setConfirmToggle(true)}
            >
              {trainer.is_active ? "Deactivate" : "Reactivate"}
            </Button>
          </div>
        ) : null
      }
    >
      <div className="mb-4">
        <Link
          href="/trainers"
          className="inline-flex items-center gap-2 text-sm font-medium text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="h-4 w-4" /> Back to trainers
        </Link>
      </div>

      {loading && (
        <div className="flex h-48 items-center justify-center">
          <Spinner />
        </div>
      )}
      {!loading && error && !trainer && <Card><CardBody className="text-sm text-red-600">{error}</CardBody></Card>}
      {!loading && trainer && (
        <div className="space-y-6">
          <Card>
            <CardBody>
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-4">
                  {photo ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={photo}
                      alt=""
                      className="h-16 w-16 rounded-full object-cover"
                    />
                  ) : (
                    <div className="flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 text-xl font-semibold text-brand-700">
                      {trainerInitials(trainer)}
                    </div>
                  )}
                  <div>
                    <h2 className="text-xl font-semibold text-gray-900">
                      {trainerName(trainer)}
                    </h2>
                    {trainer.specialization && (
                      <p className="text-sm text-gray-500">{trainer.specialization}</p>
                    )}
                    <div className="mt-1 flex flex-wrap items-center gap-2">
                      <Badge variant={trainer.is_active ? "success" : "default"}>
                        {trainer.is_active ? "Active" : "Inactive"}
                      </Badge>
                      <span className="text-sm text-gray-500">{trainer.email}</span>
                      {trainer.phone && (
                        <span className="text-sm text-gray-500">· {trainer.phone}</span>
                      )}
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-6">
                  <div className="flex items-center gap-2">
                    <Star className="h-4 w-4 text-amber-500" />
                    <div>
                      <p className="text-lg font-semibold text-gray-900" data-testid="rating">
                        {formatRating(trainer.rating)}
                      </p>
                      <p className="text-xs text-gray-500">Rating</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Users className="h-4 w-4 text-brand-600" />
                    <div>
                      <p className="text-lg font-semibold text-gray-900" data-testid="clients">
                        {activeClientCount} / {trainer.max_clients}
                      </p>
                      <p className="text-xs text-gray-500">Clients</p>
                    </div>
                  </div>
                  <div>
                    <p className="text-lg font-semibold text-gray-900">
                      {trainer.experience_years != null ? trainer.experience_years : "—"}
                    </p>
                    <p className="text-xs text-gray-500">Years experience</p>
                  </div>
                </div>
              </div>
            </CardBody>
          </Card>

          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-6" aria-label="Trainer profile tabs">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  type="button"
                  onClick={() => setActiveTab(tab.key)}
                  aria-current={activeTab === tab.key ? "page" : undefined}
                  className={`whitespace-nowrap border-b-2 px-1 pb-3 text-sm font-medium ${
                    activeTab === tab.key
                      ? "border-brand-500 text-brand-700"
                      : "border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>

          {activeTab === "overview" && (
            <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
              <Card>
                <CardHeader>
                  <h3 className="text-lg font-semibold text-gray-900">Profile</h3>
                </CardHeader>
                <CardBody>
                  <dl className="space-y-3 text-sm">
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Max clients</dt>
                      <dd className="text-gray-900">{trainer.max_clients}</dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Experience</dt>
                      <dd className="text-gray-900">
                        {trainer.experience_years != null
                          ? `${trainer.experience_years} years`
                          : "—"}
                      </dd>
                    </div>
                    <div className="flex justify-between">
                      <dt className="text-gray-500">Joined</dt>
                      <dd className="text-gray-900">
                        {new Date(trainer.created_at).toLocaleDateString()}
                      </dd>
                    </div>
                    {trainer.bio && (
                      <div>
                        <dt className="mb-1 text-gray-500">Bio</dt>
                        <dd className="whitespace-pre-line text-gray-700">{trainer.bio}</dd>
                      </div>
                    )}
                  </dl>
                </CardBody>
              </Card>

              <Card>
                <CardHeader>
                  <h3 className="text-lg font-semibold text-gray-900">Certifications</h3>
                </CardHeader>
                <CardBody>
                  {trainer.certifications.length === 0 ? (
                    <p className="text-sm text-gray-500">No certifications listed.</p>
                  ) : (
                    <ul className="space-y-2">
                      {trainer.certifications.map((cert, i) => (
                        <li
                          key={i}
                          className="rounded-lg border border-gray-200 px-3 py-2 text-sm text-gray-700"
                        >
                          {certificationLabel(cert)}
                        </li>
                      ))}
                    </ul>
                  )}
                </CardBody>
              </Card>
            </div>
          )}

          {activeTab === "customers" && (
            <Card>
              <CardHeader className="flex flex-wrap items-center justify-between gap-3">
                <h3 className="text-lg font-semibold text-gray-900">
                  Assigned customers
                </h3>
                <select
                  value={assignmentFilter}
                  onChange={(e) =>
                    setAssignmentFilter(e.target.value as typeof assignmentFilter)
                  }
                  aria-label="Filter assignments"
                  className="rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
                >
                  <option value="all">All</option>
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                </select>
              </CardHeader>
              <CardBody className="p-0">
                {filteredAssignments.length === 0 ? (
                  <p className="px-4 py-10 text-center text-sm text-gray-500">
                    {trainerAssignments.length === 0
                      ? "No customers assigned yet. Assign one from the customer's profile."
                      : "No assignments match this filter."}
                  </p>
                ) : (
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-4 py-3 text-left font-medium text-gray-500">Customer</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-500">Branch</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-500">Assigned</th>
                        <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {filteredAssignments.map((a) => (
                        <tr key={a.id} className="hover:bg-gray-50">
                          <td className="px-4 py-3">
                            <Link
                              href={`/customers/${a.customer}`}
                              className="font-medium text-gray-900 hover:text-brand-700"
                            >
                              {a.customer_name}
                              {a.customer_is_deleted ? <DeletedUserBadge className="ml-2" /> : null}
                            </Link>
                          </td>
                          <td className="px-4 py-3 text-gray-700">{a.branch_name ?? "—"}</td>
                          <td className="px-4 py-3 text-xs text-gray-500">
                            {new Date(a.assigned_at).toLocaleDateString()}
                          </td>
                          <td className="px-4 py-3">
                            <Badge variant={a.is_active ? "success" : "default"}>
                              {a.is_active ? "active" : "inactive"}
                            </Badge>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </CardBody>
            </Card>
          )}

          {activeTab === "schedule" && (
            <TrainerScheduleSection trainerId={id} canManage={canEdit} />
          )}
        </div>
      )}

      {formOpen && trainer && (
        <TrainerFormDialog
          trainer={trainer}
          onClose={() => setFormOpen(false)}
          onSaved={(saved) => {
            setFormOpen(false);
            replaceTrainer(saved);
            toast.success(`${trainerName(saved)} updated`);
          }}
        />
      )}

      {confirmToggle && trainer && (
        <ConfirmDialog
          title={
            trainer.is_active ? `Deactivate ${trainerName(trainer)}?` : `Reactivate ${trainerName(trainer)}?`
          }
          destructive={trainer.is_active}
          busy={toggling}
          confirmLabel={trainer.is_active ? "Deactivate" : "Reactivate"}
          onConfirm={toggleActive}
          onClose={() => setConfirmToggle(false)}
        >
          <p data-testid="profile-toggle-impact">
            {trainer.is_active
              ? `This trainer currently has ${activeClientCount} active client assignment(s). Deactivating hides them from the trainers list and blocks new assignments — existing history is kept.`
              : "The trainer will reappear in the trainers list and can take new client assignments."}
          </p>
        </ConfirmDialog>
      )}
    </DashboardLayout>
  );
}
