"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { CalendarClock, Plus } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, DeletedUserBadge, Button, Card, CardBody, Spinner } from "@/components/ui";
import {
  bookTrainerSession,
  cancelTrainerSession,
  completeTrainerSession,
  errorMessage,
  fetchTrainerSessions,
  fetchTrainers,
  noShowTrainerSession,
} from "@/lib/api";
import { getToken, getStoredUser } from "@/lib/auth";
import { canAccessRoute, hasPermission } from "@/lib/permissions";
import { ConfirmDialog } from "@/features/admin/components/ConfirmDialog";
import { BookSessionDialog } from "@/features/trainers/components/BookSessionDialog";
import {
  dayLabel,
  rangeBounds,
  sessionDayKey,
  sessionTimeLabel,
} from "@/features/trainers/components/sessionBoardHelpers";
import { trainerName } from "@/features/trainers/components/trainers-shared";
import type { SessionStatus, Trainer, TrainerSession } from "@/types/trainer";

type RangeKey = "today" | "week";
type StatusFilter = "all" | SessionStatus;

const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: "all", label: "All" },
  { key: "booked", label: "Booked" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
  { key: "no_show", label: "No-show" },
];

const STATUS_BADGES: Record<SessionStatus, { label: string; variant: "default" | "info" | "success" | "warning" }> = {
  booked: { label: "booked", variant: "info" },
  completed: { label: "completed", variant: "success" },
  cancelled: { label: "cancelled", variant: "default" },
  no_show: { label: "no-show", variant: "warning" },
};

type ActionKind = "complete" | "no_show" | "cancel";

/** Confirm copy per action — cancel mentions credit restoration when redeemed. */
function actionCopy(action: ActionKind, session: TrainerSession): string {
  const who = `${session.customer_name} × ${session.trainer_email}`;
  switch (action) {
    case "complete":
      return `Mark ${who} as completed? One session credit is redeemed from the member's PT pack.`;
    case "no_show":
      return `Mark ${who} as a no-show? One session credit is redeemed from the member's PT pack.`;
    case "cancel":
      return session.status === "booked"
        ? `Cancel this session? No credit is redeemed and the slot frees up.`
        : `Cancel this session? The redeemed credit is restored to the member's pack.`;
  }
}

export default function PtSessionsPage() {
  const router = useRouter();
  const [user] = useState(() => (typeof window !== "undefined" ? getStoredUser() : null));
  const [sessions, setSessions] = useState<TrainerSession[]>([]);
  const [trainers, setTrainers] = useState<Trainer[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [range, setRange] = useState<RangeKey>("today");
  const [trainerFilter, setTrainerFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const [bookingOpen, setBookingOpen] = useState(false);
  const [actionTarget, setActionTarget] = useState<{ action: ActionKind; session: TrainerSession } | null>(null);
  const [acting, setActing] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (user && !canAccessRoute(user.role, "/pt-sessions")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/pt-sessions");
      return;
    }
    fetchTrainers(token, { is_active: true })
      .then(setTrainers)
      .catch(() => setTrainers([]));
  }, [router, user]);

  useEffect(() => {
    const token = getToken();
    if (!token) return;
    const authToken: string = token;
    fetchTrainerSessions(authToken, {
      trainer: trainerFilter === "all" ? undefined : Number(trainerFilter),
      status: statusFilter === "all" ? undefined : statusFilter,
    })
      .then((list) => {
        setSessions(list);
        setError(null);
        setLoading(false);
      })
      .catch((err) => {
        setError(errorMessage(err));
        setLoading(false);
      });
  }, [trainerFilter, statusFilter, reloadKey]);

  const trainerById = useMemo(() => {
    const map = new Map<number, Trainer>();
    for (const t of trainers) map.set(t.id, t);
    return map;
  }, [trainers]);

  /** Day-grouped sessions within the selected range, chronological. */
  const grouped = useMemo(() => {
    const { start, end } = rangeBounds(range);
    const inRange = sessions.filter((s) => {
      const at = new Date(s.scheduled_at);
      return at >= start && at < end;
    });
    inRange.sort((a, b) => a.scheduled_at.localeCompare(b.scheduled_at));
    const map = new Map<string, TrainerSession[]>();
    for (const s of inRange) {
      const key = sessionDayKey(s.scheduled_at);
      const list = map.get(key) ?? [];
      list.push(s);
      map.set(key, list);
    }
    return [...map.entries()];
  }, [sessions, range]);

  const reload = useCallback(() => setReloadKey((k) => k + 1), []);

  async function handleBook(payload: Parameters<typeof bookTrainerSession>[0]) {
    const token = getToken();
    if (!token) return;
    await bookTrainerSession(payload, token); // conflicts throw → dialog shows copy
    toast.success("Session booked");
    reload();
  }

  async function runAction(action: ActionKind, session: TrainerSession) {
    const token = getToken();
    if (!token) return;
    setActing(true);
    // Optimistic: apply the status change inline, roll back on failure.
    setSessions((prev) =>
      prev.map((s) => (s.id === session.id ? { ...s, status: targetStatus(action) } : s)),
    );
    setActionTarget(null);
    try {
      const updated =
        action === "complete"
          ? await completeTrainerSession(session.id, token)
          : action === "no_show"
            ? await noShowTrainerSession(session.id, token)
            : await cancelTrainerSession(session.id, token);
      setSessions((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      toast.success(
        action === "complete"
          ? "Session completed — pack credit redeemed."
          : action === "no_show"
            ? "Marked as no-show — pack credit redeemed."
            : "Session cancelled.",
      );
    } catch (err) {
      setSessions((prev) => prev.map((s) => (s.id === session.id ? session : s)));
      toast.error(errorMessage(err));
    } finally {
      setActing(false);
    }
  }

  const canEdit = user ? hasPermission(user.role, "trainers.edit_session") : false;

  return (
    <DashboardLayout
      title="PT Sessions"
      actions={
        canEdit ? (
          <Button onClick={() => setBookingOpen(true)}>
            <Plus className="mr-2 h-4 w-4" /> New booking
          </Button>
        ) : null
      }
    >
      <div className="mb-4 flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="inline-flex rounded-lg border border-gray-300 bg-white p-1" role="group" aria-label="Date range">
          {(["today", "week"] as RangeKey[]).map((r) => (
            <button
              key={r}
              type="button"
              onClick={() => setRange(r)}
              aria-pressed={range === r}
              className={`rounded-md px-3 py-1.5 text-sm font-medium ${
                range === r ? "bg-brand-600 text-white" : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              {r === "today" ? "Today" : "This week"}
            </button>
          ))}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={trainerFilter}
            onChange={(e) => setTrainerFilter(e.target.value)}
            aria-label="Filter by trainer"
            className="rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none"
          >
            <option value="all">All trainers</option>
            {trainers.map((t) => (
              <option key={t.id} value={t.id}>
                {t.first_name} {t.last_name}
              </option>
            ))}
          </select>
          <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by status">
            {STATUS_FILTERS.map((s) => (
              <button
                key={s.key}
                type="button"
                onClick={() => setStatusFilter(s.key)}
                aria-pressed={statusFilter === s.key}
                className={`rounded-full px-3 py-1.5 text-xs font-medium ${
                  statusFilter === s.key
                    ? "bg-brand-600 text-white"
                    : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                }`}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && (
        <Card className="mb-4">
          <CardBody className="text-sm text-red-600">{error}</CardBody>
        </Card>
      )}

      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : grouped.length === 0 && !error ? (
        <Card>
          <CardBody className="py-12 text-center" data-testid="sessions-empty">
            <CalendarClock className="mx-auto mb-3 h-8 w-8 text-gray-300" />
            <p className="text-sm text-gray-500">
              {sessions.length === 0
                ? "No PT sessions booked yet. Use “New booking” to schedule the first one."
                : "No sessions in this range match your filters."}
            </p>
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-6">
          {grouped.map(([dayKey, daySessions]) => (
            <div key={dayKey}>
              <h2
                className="mb-2 text-sm font-semibold text-gray-900"
                data-testid={`day-group-${dayKey}`}
              >
                {dayLabel(dayKey)}
              </h2>
              <Card>
                <CardBody className="p-0">
                  <ul className="divide-y divide-gray-100">
                    {daySessions.map((session) => {
                      const badge = STATUS_BADGES[session.status];
                      const trainer = trainerById.get(session.trainer);
                      return (
                        <li
                          key={session.id}
                          className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"
                          data-testid="session-row"
                        >
                          <div className="flex items-center gap-4">
                            <div className="w-24 text-sm font-semibold text-gray-900">
                              {sessionTimeLabel(session.scheduled_at)}
                              <div className="text-xs font-normal text-gray-500">
                                {session.duration_minutes} min
                              </div>
                            </div>
                            <div>
                              <p
                                className="text-sm font-medium text-gray-900"
                                data-testid="session-parties"
                              >
                                {session.customer_name}
                                {session.customer_is_deleted ? (
                                  <DeletedUserBadge className="ml-2 align-middle" />
                                ) : null}
                                <span className="text-gray-400"> × </span>
                                {trainer ? trainerName(trainer) : session.trainer_email}
                              </p>
                              <p className="text-xs text-gray-500">
                                {session.branch_name ?? "—"}
                                {session.notes ? ` · ${session.notes}` : ""}
                              </p>
                            </div>
                          </div>
                          <div className="flex items-center gap-2">
                            <Badge variant={badge.variant} data-testid="session-status">
                              {badge.label}
                            </Badge>
                            {canEdit && session.status === "booked" && (
                              <>
                                <Button
                                  size="sm"
                                  variant="outline"
                                  onClick={() => setActionTarget({ action: "complete", session })}
                                >
                                  Complete
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  onClick={() => setActionTarget({ action: "no_show", session })}
                                >
                                  No-show
                                </Button>
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="text-red-600 hover:bg-red-50"
                                  onClick={() => setActionTarget({ action: "cancel", session })}
                                >
                                  Cancel
                                </Button>
                              </>
                            )}
                            {canEdit &&
                              (session.status === "completed" || session.status === "no_show") && (
                                <Button
                                  size="sm"
                                  variant="ghost"
                                  className="text-red-600 hover:bg-red-50"
                                  onClick={() => setActionTarget({ action: "cancel", session })}
                                >
                                  Cancel
                                </Button>
                              )}
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                </CardBody>
              </Card>
            </div>
          ))}
        </div>
      )}

      {bookingOpen && (
        <BookSessionDialog
          onSubmit={handleBook}
          onClose={() => setBookingOpen(false)}
        />
      )}

      {actionTarget && (
        <ConfirmDialog
          title={
            actionTarget.action === "complete"
              ? "Complete session?"
              : actionTarget.action === "no_show"
                ? "Mark no-show?"
                : "Cancel session?"
          }
          destructive={actionTarget.action === "cancel"}
          busy={acting}
          confirmLabel={
            actionTarget.action === "complete"
              ? "Complete session"
              : actionTarget.action === "no_show"
                ? "Mark no-show"
                : "Cancel session"
          }
          onConfirm={() => runAction(actionTarget.action, actionTarget.session)}
          onClose={() => setActionTarget(null)}
        >
          <p>{actionCopy(actionTarget.action, actionTarget.session)}</p>
        </ConfirmDialog>
      )}
    </DashboardLayout>
  );
}

function targetStatus(action: ActionKind): SessionStatus {
  if (action === "complete") return "completed";
  if (action === "no_show") return "no_show";
  return "cancelled";
}
