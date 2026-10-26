"use client";

import { useMemo, useState } from "react";
import { toast } from "sonner";
import { Pencil, Plus, Trash2 } from "lucide-react";
import {
  Badge,
  Button,
  Card,
  CardBody,
  CardHeader,
  Spinner,
} from "@/components/ui";
import { errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import {
  useCreateScheduleSlot,
  useDeleteScheduleSlot,
  useTrainerSchedule,
  useUpdateScheduleSlot,
} from "../hooks/useTrainerSchedule";
import { formatDayLabel, formatTimeRange } from "./scheduleHelpers";
import { ScheduleSlotDialog } from "./ScheduleSlotDialog";
import { DAY_OF_WEEK } from "@/types/trainer";
import type {
  DayOfWeek,
  ScheduleSlotInput,
  TrainerScheduleSlot,
} from "@/types/trainer";

interface TrainerScheduleSectionProps {
  trainerId: number | string;
  /** Renders the add/edit/delete affordances (role-gated upstream). */
  canManage: boolean;
}

/**
 * Weekly schedule tab body on the trainer profile (issue #80).
 *
 * Lists the trainer's /trainer-schedules/ rows — one availability window per
 * weekday — with create/edit/delete for users holding users.edit_user.
 * Fetching and mutations go through React Query; the dialog pre-empts
 * duplicate-day and inverted-window submissions client-side, and the server's
 * unique constraint remains the backstop.
 */
export function TrainerScheduleSection({
  trainerId,
  canManage,
}: TrainerScheduleSectionProps) {
  const [token] = useState(() => getToken());
  const query = useTrainerSchedule(trainerId, token);
  const createMutation = useCreateScheduleSlot(trainerId, token ?? "");
  const updateMutation = useUpdateScheduleSlot(trainerId, token ?? "");
  const deleteMutation = useDeleteScheduleSlot(trainerId, token ?? "");

  const [dialog, setDialog] = useState<{
    slot: TrainerScheduleSlot | null;
    day?: DayOfWeek;
  } | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<TrainerScheduleSlot | null>(
    null,
  );

  const slots = useMemo(() => query.data ?? [], [query.data]);
  const byDay = useMemo(() => {
    const map = new Map<DayOfWeek, TrainerScheduleSlot>();
    for (const slot of slots) {
      // Backend guarantees at most one row per (trainer, day_of_week).
      if (!map.has(slot.day_of_week)) map.set(slot.day_of_week, slot);
    }
    return map;
  }, [slots]);

  function closeDialog() {
    setDialog(null);
    createMutation.reset();
    updateMutation.reset();
  }

  /** Throwing propagates the failure into the dialog's error rendering. */
  async function handleDialogSubmit(input: ScheduleSlotInput) {
    if (dialog?.slot) {
      await updateMutation.mutateAsync({ id: dialog.slot.id, data: input });
      toast.success(`${formatDayLabel(input.day_of_week)} slot updated.`);
    } else {
      await createMutation.mutateAsync(input);
      toast.success(`${formatDayLabel(input.day_of_week)} slot added.`);
    }
    closeDialog();
  }

  async function handleDeleteConfirm() {
    if (!deleteTarget) return;
    try {
      await deleteMutation.mutateAsync(deleteTarget.id);
      toast.success(`${formatDayLabel(deleteTarget.day_of_week)} slot removed.`);
      setDeleteTarget(null);
    } catch (err) {
      toast.error(errorMessage(err));
    }
  }

  if (query.isPending) {
    return (
      <Card>
        <CardBody>
          <div className="flex justify-center py-8">
            <Spinner />
          </div>
        </CardBody>
      </Card>
    );
  }

  if (query.isError) {
    return (
      <Card>
        <CardBody className="space-y-3 text-center">
          <p className="text-sm text-red-600" role="alert">
            {errorMessage(query.error)}
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={() => void query.refetch()}
          >
            Try again
          </Button>
        </CardBody>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Weekly availability
          </h3>
          <p className="text-sm text-gray-500">
            Recurring weekly slots from the trainer schedule.
          </p>
        </div>
        {canManage && (
          <Button
            size="sm"
            onClick={() => setDialog({ slot: null })}
            data-testid="schedule-add"
          >
            <Plus className="mr-2 h-4 w-4" /> Add slot
          </Button>
        )}
      </CardHeader>
      <CardBody className="space-y-3">
        {slots.length === 0 && (
          <p data-testid="schedule-empty" className="text-sm text-gray-500">
            No weekly schedule configured for this trainer yet.
          </p>
        )}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {DAY_OF_WEEK.map((day) => {
            const slot = byDay.get(day);
            return (
              <div
                key={day}
                className="rounded-xl border border-gray-200 p-3"
                data-testid={`schedule-day-${day}`}
              >
                <div className="mb-2 flex items-center justify-between">
                  <p className="text-sm font-semibold text-gray-900">
                    {formatDayLabel(day)}
                  </p>
                  {canManage && !slot && (
                    <button
                      type="button"
                      onClick={() => setDialog({ slot: null, day })}
                      aria-label={`Add ${formatDayLabel(day)} slot`}
                      className="inline-flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
                    >
                      <Plus className="h-3.5 w-3.5" /> Add
                    </button>
                  )}
                </div>
                {slot ? (
                  <div className="flex items-center justify-between gap-2 rounded-lg bg-gray-50 px-2.5 py-1.5 text-xs text-gray-700">
                    <span>{formatTimeRange(slot.start_time, slot.end_time)}</span>
                    <span className="flex items-center gap-1">
                      {slot.is_available ? (
                        <Badge variant="success">available</Badge>
                      ) : (
                        <Badge variant="default">off</Badge>
                      )}
                      {canManage && (
                        <>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Edit ${formatDayLabel(day)} slot`}
                            onClick={() => setDialog({ slot })}
                          >
                            <Pencil className="h-3.5 w-3.5" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            aria-label={`Delete ${formatDayLabel(day)} slot`}
                            className="text-gray-400 hover:text-red-600"
                            onClick={() => setDeleteTarget(slot)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </>
                      )}
                    </span>
                  </div>
                ) : (
                  <p className="text-xs text-gray-400">—</p>
                )}
              </div>
            );
          })}
        </div>
      </CardBody>

      {dialog && (
        <ScheduleSlotDialog
          slot={dialog.slot}
          defaultDay={dialog.day}
          slots={slots}
          saving={createMutation.isPending || updateMutation.isPending}
          onSubmit={handleDialogSubmit}
          onClose={closeDialog}
        />
      )}

      {deleteTarget && (
        <ConfirmDialog
          title={`Delete ${formatDayLabel(deleteTarget.day_of_week)} slot?`}
          destructive
          busy={deleteMutation.isPending}
          confirmLabel="Delete"
          onConfirm={handleDeleteConfirm}
          onClose={() => setDeleteTarget(null)}
        >
          <p>
            The {formatDayLabel(deleteTarget.day_of_week)}{" "}
            {formatTimeRange(deleteTarget.start_time, deleteTarget.end_time)}{" "}
            window is removed from the trainer&apos;s weekly schedule.
          </p>
        </ConfirmDialog>
      )}
    </Card>
  );
}
