"use client";

import { useEffect, useMemo, useState } from "react";
import { Search, X } from "lucide-react";
import { Button, Card, CardBody, Spinner } from "@/components/ui";
import { errorMessage, fetchBranches, fetchTrainers } from "@/lib/api";
import { getToken } from "@/lib/auth";
import {
  resolveTrainerPhoto,
  trainerInitials,
  trainerName,
} from "./trainers-shared";
import type { Branch } from "@/types/branch";
import type { Trainer } from "@/types/trainer";

interface AssignTrainerModalProps {
  /** The customer's home branch — prefilled in the branch selector. */
  customerBranchId: number | null;
  onSubmit: (inputs: { trainer: number; branch: number | null }) => Promise<void>;
  onClose: () => void;
}

/**
 * Assign-trainer dialog (issue #54): searchable active-trainer select,
 * branch-scoped via the trainer-assignments API.
 */
export function AssignTrainerModal({
  customerBranchId,
  onSubmit,
  onClose,
}: AssignTrainerModalProps) {
  const [trainers, setTrainers] = useState<Trainer[] | null>(null);
  const [trainersError, setTrainersError] = useState<string | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchId, setBranchId] = useState<number | null>(customerBranchId);
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Trainer | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    fetchTrainers(token, { is_active: true })
      .then(setTrainers)
      .catch((err) => setTrainersError(errorMessage(err)));
    fetchBranches(token)
      .then((list) => {
        setBranches(list);
        setBranchId((prev) => prev ?? list[0]?.id ?? null);
      })
      .catch(() => setBranches([]));
  }, []);

  const filtered = useMemo(() => {
    const list = trainers ?? [];
    const q = search.trim().toLowerCase();
    if (!q) return list;
    return list.filter((t) =>
      `${t.first_name} ${t.last_name} ${t.email} ${t.specialization ?? ""}`
        .toLowerCase()
        .includes(q),
    );
  }, [trainers, search]);

  async function submit() {
    if (!selected) return;
    setSubmitting(true);
    setError(null);
    try {
      await onSubmit({ trainer: selected.id, branch: branchId });
    } catch (err) {
      setError(errorMessage(err));
      setSubmitting(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="max-h-[90vh] w-full max-w-lg overflow-y-auto">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Assign trainer</h3>
            <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close">
              <X className="h-4 w-4" />
            </Button>
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}

          {trainers === null && !trainersError ? (
            <div className="flex justify-center py-8">
              <Spinner />
            </div>
          ) : trainersError ? (
            <p className="text-sm text-red-600">{trainersError}</p>
          ) : (
            <>
              <div className="relative">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
                <input
                  type="search"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search active trainers…"
                  aria-label="Search active trainers"
                  className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-9 pr-3 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
              </div>

              <div className="max-h-64 space-y-1 overflow-y-auto" data-testid="trainer-options">
                {filtered.length === 0 ? (
                  <p className="py-6 text-center text-sm text-gray-500">
                    {(trainers ?? []).length === 0
                      ? "No active trainers available."
                      : "No trainers match your search."}
                  </p>
                ) : (
                  filtered.map((t) => {
                    const photo = resolveTrainerPhoto(t);
                    const active = selected?.id === t.id;
                    return (
                      <button
                        key={t.id}
                        type="button"
                        onClick={() => setSelected(t)}
                        aria-pressed={active}
                        className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2 text-left text-sm ${
                          active
                            ? "border-brand-500 bg-brand-50"
                            : "border-gray-200 hover:bg-gray-50"
                        }`}
                      >
                        {photo ? (
                          // eslint-disable-next-line @next/next/no-img-element
                          <img
                            src={photo}
                            alt=""
                            className="h-9 w-9 rounded-full object-cover"
                          />
                        ) : (
                          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                            {trainerInitials(t)}
                          </div>
                        )}
                        <span className="flex-1">
                          <span className="block font-medium text-gray-900">
                            {trainerName(t)}
                          </span>
                          <span className="block text-xs text-gray-500">
                            {t.specialization || t.email}
                          </span>
                        </span>
                      </button>
                    );
                  })
                )}
              </div>

              <div className="space-y-1.5">
                <label
                  htmlFor="assign-branch"
                  className="block text-sm font-medium text-gray-700"
                >
                  Branch
                </label>
                <select
                  id="assign-branch"
                  value={branchId ?? ""}
                  onChange={(e) =>
                    setBranchId(e.target.value ? Number(e.target.value) : null)
                  }
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                >
                  <option value="">No branch</option>
                  {branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
                <p className="text-xs text-gray-500">
                  Assignments are branch-scoped — pick where this trainer coaches the member.
                </p>
              </div>

              <div className="flex justify-end gap-2">
                <Button variant="outline" onClick={onClose} disabled={submitting}>
                  Cancel
                </Button>
                <Button
                  onClick={submit}
                  disabled={!selected || submitting}
                  loading={submitting}
                  aria-label="Confirm assignment"
                >
                  Assign trainer
                </Button>
              </div>
            </>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
