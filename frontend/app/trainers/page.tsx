"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Search, Star, Users } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Button, Card, CardBody, Spinner } from "@/components/ui";
import {
  errorMessage,
  fetchTrainerAssignments,
  fetchTrainers,
  updateTrainer,
} from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import { canAccessRoute, hasPermission } from "@/lib/permissions";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { TrainerFormDialog } from "@/features/trainers/components/TrainerFormDialog";
import {
  formatRating,
  resolveTrainerPhoto,
  trainerInitials,
  trainerName,
} from "@/features/trainers/components/trainers-shared";
import type { BranchTrainerAssignment, Trainer } from "@/types/trainer";

export default function TrainersPage() {
  const router = useRouter();
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [assignments, setAssignments] = useState<BranchTrainerAssignment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [specializationFilter, setSpecializationFilter] = useState("all");

  const [formTarget, setFormTarget] = useState<Trainer | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [deactivateTarget, setDeactivateTarget] = useState<Trainer | null>(null);
  const [toggling, setToggling] = useState(false);

  useEffect(() => {
    if (user && !canAccessRoute(user.role, "/trainers")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/trainers");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [list, assigns] = await Promise.all([
          fetchTrainers(authToken),
          // Non-fatal: view-only roles may lack trainers.edit_trainer.
          fetchTrainerAssignments(authToken).catch(() => []),
        ]);
        setTrainers(list);
        setAssignments(assigns);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [router, user]);

  /** Active branch-scoped assignments per trainer id. */
  const activeClientsByTrainer = useMemo(() => {
    const counts = new Map<number, number>();
    for (const a of assignments) {
      if (a.is_active) counts.set(a.trainer, (counts.get(a.trainer) ?? 0) + 1);
    }
    return counts;
  }, [assignments]);

  const specializations = useMemo(() => {
    const set = new Set<string>();
    for (const t of trainers) {
      if (t.specialization?.trim()) set.add(t.specialization.trim());
    }
    return [...set].sort((a, b) => a.localeCompare(b));
  }, [trainers]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return trainers.filter((t) => {
      if (statusFilter === "active" && !t.is_active) return false;
      if (statusFilter === "inactive" && t.is_active) return false;
      if (
        specializationFilter !== "all" &&
        (t.specialization ?? "").trim() !== specializationFilter
      ) {
        return false;
      }
      if (q) {
        const haystack = `${t.first_name} ${t.last_name} ${t.email}`.toLowerCase();
        if (!haystack.includes(q)) return false;
      }
      return true;
    });
  }, [trainers, search, statusFilter, specializationFilter]);

  const replaceTrainer = useCallback((updated: Trainer) => {
    setTrainers((list) => list.map((t) => (t.id === updated.id ? updated : t)));
  }, []);

  async function toggleActive(trainer: Trainer) {
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
      setDeactivateTarget(null);
      toast.success(
        updated.is_active
          ? `${trainerName(updated)} reactivated.`
          : `${trainerName(updated)} deactivated — they no longer appear as assignable.`,
      );
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setToggling(false);
    }
  }

  const canCreate = user ? hasPermission(user.role, "users.create_user") : false;
  const canEdit = user ? hasPermission(user.role, "users.edit_user") : false;

  return (
    <DashboardLayout
      title="Trainers"
      actions={
        canCreate ? (
          <Button
            onClick={() => {
              setFormTarget(null);
              setFormOpen(true);
            }}
          >
            <Plus className="mr-2 h-4 w-4" /> New trainer
          </Button>
        ) : null
      }
    >
      {error && (
        <Card className="mb-4">
          <CardBody className="text-sm text-red-600">{error}</CardBody>
        </Card>
      )}

      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center">
        <div className="relative w-full lg:max-w-xs">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name or email…"
            aria-label="Search trainers"
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as typeof statusFilter)}
            aria-label="Filter by status"
            className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="all">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
          <select
            value={specializationFilter}
            onChange={(e) => setSpecializationFilter(e.target.value)}
            aria-label="Filter by specialization"
            className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="all">All specializations</option>
            {specializations.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : filtered.length === 0 && !error ? (
        <Card>
          <CardBody className="py-12 text-center text-sm text-gray-500">
            {trainers.length === 0
              ? "No trainers yet. Use “New trainer” to add your first coach."
              : "No trainers match your filters."}
          </CardBody>
        </Card>
      ) : (
        <Card>
          <CardBody className="p-0">
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm" data-testid="trainers-table">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Trainer</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Specialization</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Clients</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Experience</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Rating</th>
                    <th className="px-4 py-3 text-left font-medium text-gray-500">Status</th>
                    <th className="px-4 py-3 text-right font-medium text-gray-500">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filtered.map((trainer) => {
                    const activeClients = activeClientsByTrainer.get(trainer.id) ?? 0;
                    const photo = resolveTrainerPhoto(trainer);
                    return (
                      <tr
                        key={trainer.id}
                        className={trainer.is_active ? "hover:bg-gray-50" : "bg-gray-50/60"}
                        data-testid="trainer-row"
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-3">
                            {photo ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={photo}
                                alt=""
                                className="h-10 w-10 rounded-full object-cover"
                              />
                            ) : (
                              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
                                {trainerInitials(trainer)}
                              </div>
                            )}
                            <div>
                              <Link
                                href={`/trainers/${trainer.id}`}
                                className="font-medium text-gray-900 hover:text-brand-700"
                              >
                                {trainerName(trainer)}
                              </Link>
                              <div className="text-xs text-gray-500">{trainer.email}</div>
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {trainer.specialization || "—"}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 text-gray-700">
                            <Users className="h-4 w-4 text-gray-400" />
                            <span data-testid="clients-count">
                              {activeClients} / {trainer.max_clients}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-gray-700">
                          {trainer.experience_years != null ? `${trainer.experience_years} yr` : "—"}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1 text-gray-700">
                            <Star className="h-4 w-4 text-amber-500" />
                            {formatRating(trainer.rating)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant={trainer.is_active ? "success" : "default"}>
                            {trainer.is_active ? "active" : "inactive"}
                          </Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center justify-end gap-1">
                            {canEdit && (
                              <>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => {
                                    setFormTarget(trainer);
                                    setFormOpen(true);
                                  }}
                                  aria-label={`Edit ${trainerName(trainer)}`}
                                >
                                  Edit
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  className={
                                    trainer.is_active
                                      ? "text-red-600 hover:bg-red-50"
                                      : "text-green-700 hover:bg-green-50"
                                  }
                                  onClick={() => setDeactivateTarget(trainer)}
                                  aria-label={
                                    trainer.is_active
                                      ? `Deactivate ${trainerName(trainer)}`
                                      : `Reactivate ${trainerName(trainer)}`
                                  }
                                >
                                  {trainer.is_active ? "Deactivate" : "Reactivate"}
                                </Button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      {formOpen && (
        <TrainerFormDialog
          trainer={formTarget}
          onClose={() => setFormOpen(false)}
          onSaved={(saved) => {
            setFormOpen(false);
            if (formTarget) {
              replaceTrainer(saved);
              toast.success(`${trainerName(saved)} updated`);
            } else {
              setTrainers((list) => [saved, ...list]);
              toast.success(`${trainerName(saved)} created`);
            }
          }}
        />
      )}

      {deactivateTarget && (
        <ConfirmDialog
          title={
            deactivateTarget.is_active
              ? `Deactivate ${trainerName(deactivateTarget)}?`
              : `Reactivate ${trainerName(deactivateTarget)}?`
          }
          destructive={deactivateTarget.is_active}
          busy={toggling}
          confirmLabel={deactivateTarget.is_active ? "Deactivate" : "Reactivate"}
          onConfirm={() => toggleActive(deactivateTarget)}
          onClose={() => setDeactivateTarget(null)}
        >
          <p data-testid="deactivate-impact">
            {deactivateTarget.is_active
              ? `This trainer currently has ${activeClientsByTrainer.get(deactivateTarget.id) ?? 0} active client assignment(s). Deactivating hides them from the trainers list and blocks new assignments — existing history is kept.`
              : "The trainer will reappear in the trainers list and can take new client assignments."}
          </p>
          <p>You can change this again anytime.</p>
        </ConfirmDialog>
      )}
    </DashboardLayout>
  );
}
