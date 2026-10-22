"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Dumbbell } from "lucide-react";
import { Badge, Button, Card, CardBody, CardHeader, Spinner } from "@/components/ui";
import {
  createTrainerAssignment,
  errorMessage,
  fetchPtRemaining,
  fetchTrainerAssignments,
  fetchTrainers,
  unassignTrainerAssignment,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { AssignTrainerModal } from "@/features/trainers/components/AssignTrainerModal";
import { PtPackBadge, ptPackCopy } from "@/features/trainers/components/PtPackBadge";
import {
  resolveTrainerPhoto,
  trainerInitials,
  trainerName,
} from "@/features/trainers/components/trainers-shared";
import type { Customer } from "@/types/customer";
import type { BranchTrainerAssignment, PtRemaining, Trainer } from "@/types/trainer";

interface TrainerSectionProps {
  customer: Customer;
}

/**
 * Customer detail → Trainer section (issue #54): the assigned trainer (photo,
 * specialization) with assign/unassign and the customer's PT pack badge.
 * Assign/unassign update optimistically and roll back with an error toast.
 */
export function TrainerSection({ customer }: TrainerSectionProps) {
  const [assignments, setAssignments] = useState<BranchTrainerAssignment[] | null>(null);
  const [assignmentsError, setAssignmentsError] = useState<string | null>(null);
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [pack, setPack] = useState<PtRemaining | null>(null);
  const [assignOpen, setAssignOpen] = useState(false);
  const [unassignTarget, setUnassignTarget] = useState<BranchTrainerAssignment | null>(null);
  const [unassigning, setUnassigning] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    Promise.all([
      fetchTrainerAssignments(token),
      fetchTrainers(token).catch(() => [] as Trainer[]),
    ])
      .then(([assignData, trainerData]) => {
        setAssignments(assignData);
        setTrainers(trainerData);
      })
      .catch((err) => {
        setAssignments([]);
        setAssignmentsError(errorMessage(err));
      });
    // The pack badge hides gracefully when the entitlement API is unavailable.
    fetchPtRemaining(customer.id, token)
      .then(setPack)
      .catch(() => setPack(null));
  }, [customer.id]);

  const activeAssignments = useMemo(
    () => (assignments ?? []).filter((a) => a.customer === customer.id && a.is_active),
    [assignments, customer.id],
  );

  const trainerById = useMemo(() => {
    const map = new Map<number, Trainer>();
    for (const t of trainers) map.set(t.id, t);
    return map;
  }, [trainers]);

  /** Optimistic assign: placeholder row now, server row on success, roll back on failure. */
  async function handleAssign(inputs: { trainer: number; branch: number | null }) {
    const token = getToken();
    if (!token) return;
    const trainer = trainerById.get(inputs.trainer);
    const temp: BranchTrainerAssignment = {
      id: -Date.now(),
      trainer: inputs.trainer,
      customer: customer.id,
      branch: inputs.branch,
      assigned_at: new Date().toISOString(),
      unassigned_at: null,
      is_active: true,
      trainer_email: trainer?.email ?? "",
      customer_name: customer.name,
      branch_name: null,
    };
    setAssignments((prev) => [temp, ...(prev ?? [])]);
    setAssignOpen(false);
    const trainerLabel = trainer ? trainerName(trainer) : "Trainer";
    try {
      const created = await createTrainerAssignment(
        { trainer: inputs.trainer, customer: customer.id, branch: inputs.branch },
        token,
      );
      setAssignments((prev) =>
        (prev ?? []).map((a) => (a.id === temp.id ? created : a)),
      );
      toast.success(`${trainerLabel} assigned to ${customer.name}`);
    } catch (err) {
      setAssignments((prev) => (prev ?? []).filter((a) => a.id !== temp.id));
      toast.error(errorMessage(err));
    }
  }

  /** Optimistic unassign: remove now, roll back on failure. */
  async function handleUnassign(target: BranchTrainerAssignment) {
    const token = getToken();
    if (!token) return;
    setUnassigning(true);
    setAssignments((prev) => (prev ?? []).filter((a) => a.id !== target.id));
    setUnassignTarget(null);
    try {
      await unassignTrainerAssignment(target.id, token);
      setUnassigning(false);
      const trainer = trainerById.get(target.trainer);
      toast.success(
        `${trainer ? trainerName(trainer) : "Trainer"} unassigned from ${customer.name}`,
      );
    } catch (err) {
      setAssignments((prev) => [target, ...(prev ?? [])]);
      setUnassigning(false);
      toast.error(errorMessage(err));
    }
  }

  return (
    <Card data-testid="trainer-section">
      <CardHeader className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="flex items-center gap-2 text-lg font-semibold text-gray-900">
            <Dumbbell className="h-5 w-5 text-brand-600" />
            Trainer
          </h2>
          <p className="text-sm text-gray-500">
            Personal-training assignment and session-pack status.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {pack && <PtPackBadge pack={pack} />}
          <Button size="sm" onClick={() => setAssignOpen(true)}>
            {activeAssignments.length > 0 ? "Change trainer" : "Assign trainer"}
          </Button>
        </div>
      </CardHeader>
      <CardBody className="space-y-3">
        {pack && !pack.can_book && (
          <p className="text-sm text-amber-700" data-testid="pt-pack-warning">
            {ptPackCopy(pack)}
          </p>
        )}

        {assignments === null && !assignmentsError && (
          <div className="flex justify-center py-4">
            <Spinner />
          </div>
        )}
        {assignmentsError && (
          <p className="text-sm text-red-600">{assignmentsError}</p>
        )}
        {assignments !== null && !assignmentsError && activeAssignments.length === 0 && (
          <p className="text-sm text-gray-500" data-testid="trainer-empty">
            No trainer assigned yet. Assign one to start booking PT sessions.
          </p>
        )}

        {activeAssignments.map((a) => {
          const trainer = trainerById.get(a.trainer);
          const photo = trainer ? resolveTrainerPhoto(trainer) : null;
          const name = trainer ? trainerName(trainer) : a.trainer_email || `Trainer #${a.trainer}`;
          return (
            <div
              key={a.id}
              className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-gray-200 p-3"
              data-testid="assigned-trainer"
            >
              <div className="flex items-center gap-3">
                {photo ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={photo} alt="" className="h-11 w-11 rounded-full object-cover" />
                ) : (
                  <div className="flex h-11 w-11 items-center justify-center rounded-full bg-brand-100 text-sm font-semibold text-brand-700">
                    {trainer ? trainerInitials(trainer) : "?"}
                  </div>
                )}
                <div>
                  <Link
                    href={`/trainers/${a.trainer}`}
                    className="font-medium text-gray-900 hover:text-brand-700"
                  >
                    {name}
                  </Link>
                  <div className="text-xs text-gray-500">
                    {trainer?.specialization || a.trainer_email}
                    {a.branch_name ? ` · ${a.branch_name}` : ""}
                  </div>
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                className="text-red-600 hover:bg-red-50"
                onClick={() => setUnassignTarget(a)}
                aria-label={`Unassign ${name}`}
              >
                Unassign
              </Button>
            </div>
          );
        })}
      </CardBody>

      {assignOpen && (
        <AssignTrainerModal
          customerBranchId={customer.branch}
          onSubmit={handleAssign}
          onClose={() => setAssignOpen(false)}
        />
      )}

      {unassignTarget && (
        <ConfirmDialog
          title="Unassign trainer?"
          destructive
          busy={unassigning}
          confirmLabel="Unassign"
          onConfirm={() => handleUnassign(unassignTarget)}
          onClose={() => setUnassignTarget(null)}
        >
          <p>
            {(() => {
              const trainer = trainerById.get(unassignTarget.trainer);
              return `${
                trainer ? trainerName(trainer) : "This trainer"
              } will no longer be listed as ${customer.name}'s coach. Booked sessions are kept; you can assign a trainer again anytime.`;
            })()}
          </p>
        </ConfirmDialog>
      )}
    </Card>
  );
}
