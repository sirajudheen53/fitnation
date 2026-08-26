"use client";

import { useMemo, useState } from "react";
import {
  Plus,
  Trash2,
  CalendarDays,
  Dumbbell,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { Exercise } from "@/types/exercise";
import type {
  DayOfWeek,
  WorkoutDay,
  WorkoutDayFormData,
  WorkoutDifficulty,
  WorkoutExercise,
  WorkoutExerciseFormData,
  WorkoutGoal,
  WorkoutPlan,
  WorkoutPlanFormData,
} from "@/types/workout";
import { errorMessage } from "@/lib/api";
import {
  DAY_OF_WEEK_LABELS,
  DAY_OF_WEEK_OPTIONS,
  DIFFICULTY_LABELS,
  DIFFICULTY_OPTIONS,
  GOAL_LABELS,
  GOAL_OPTIONS,
  dayLabel,
} from "./helpers";

interface DraftExercise extends WorkoutExerciseFormData {
  exercise_name?: string;
  alternate_exercise_name?: string;
}

interface DraftDay {
  day_of_week: DayOfWeek | "";
  day_number: number | null;
  focus: string;
  notes: string;
  exercises: DraftExercise[];
}

interface WorkoutPlanFormProps {
  plan?: WorkoutPlan;
  exercises: Exercise[];
  submitLabel?: string;
  onSubmit: (data: WorkoutPlanFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function WorkoutPlanForm({
  plan,
  exercises,
  submitLabel = "Save plan",
  onSubmit,
  error,
  loading = false,
}: WorkoutPlanFormProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [goal, setGoal] = useState<WorkoutGoal>("general_fitness");
  const [difficulty, setDifficulty] = useState<WorkoutDifficulty>("beginner");
  const [durationWeeks, setDurationWeeks] = useState(4);
  const [isTemplate, setIsTemplate] = useState(false);
  const [days, setDays] = useState<DraftDay[]>([]);

  // Exercise draft state
  const [activeDay, setActiveDay] = useState<number>(0);
  const [exerciseId, setExerciseId] = useState<number | "">("");
  const [sets, setSets] = useState(3);
  const [reps, setReps] = useState("8-12");
  const [restSeconds, setRestSeconds] = useState(60);
  const [tempo, setTempo] = useState("");
  const [rpe, setRpe] = useState<number | "">("");
  const [exerciseNotes, setExerciseNotes] = useState("");
  const [alternateExerciseId, setAlternateExerciseId] = useState<number | "">("");

  // Pre-populate from existing plan (adjust state during render when the
  // `plan` prop changes, instead of syncing it inside an effect).
  const [prevPlan, setPrevPlan] = useState<WorkoutPlan | undefined>(plan);
  if (plan !== prevPlan) {
    setPrevPlan(plan);
    if (plan) {
      setName(plan.name);
      setDescription(plan.description);
      setGoal(plan.goal);
      setDifficulty(plan.difficulty);
      setDurationWeeks(plan.duration_weeks);
      setIsTemplate(plan.is_template);
      setDays(
        plan.days.map((d: WorkoutDay) => ({
          day_of_week: d.day_of_week,
          day_number: d.day_number,
          focus: d.focus,
          notes: d.notes ?? "",
          exercises: d.exercises.map((e: WorkoutExercise) => ({
            exercise: e.exercise,
            exercise_name: e.exercise_name,
            sets: e.sets,
            reps: e.reps,
            rest_seconds: e.rest_seconds,
            tempo: e.tempo ?? "",
            rpe: e.rpe,
            notes: e.notes ?? "",
            order: e.order,
            alternate_exercise: e.alternate_exercise,
            alternate_exercise_name: e.alternate_exercise_name ?? undefined,
          })),
        })),
      );
    }
  }

  const selectedExercise = useMemo(
    () => exercises.find((e) => e.id === Number(exerciseId)),
    [exercises, exerciseId],
  );

  const addDay = () => {
    setDays((prev) => [
      ...prev,
      {
        day_of_week: "",
        day_number: prev.length + 1,
        focus: "",
        notes: "",
        exercises: [],
      },
    ]);
    setActiveDay(days.length);
  };

  const removeDay = (index: number) => {
    setDays((prev) => prev.filter((_, i) => i !== index));
    setActiveDay((prev) => Math.max(0, Math.min(prev, days.length - 2)));
  };

  const updateDay = (index: number, patch: Partial<DraftDay>) => {
    setDays((prev) => prev.map((d, i) => (i === index ? { ...d, ...patch } : d)));
  };

  const addExercise = () => {
    if (!selectedExercise || exerciseId === "") return;
    const exercise: DraftExercise = {
      exercise: selectedExercise.id,
      exercise_name: selectedExercise.name,
      sets,
      reps,
      rest_seconds: restSeconds,
      tempo: tempo || undefined,
      rpe: rpe === "" ? null : Number(rpe),
      notes: exerciseNotes || undefined,
      order: days[activeDay]?.exercises.length ?? 0,
      alternate_exercise:
        alternateExerciseId === "" ? null : Number(alternateExerciseId),
      alternate_exercise_name: alternateExerciseId
        ? exercises.find((e) => e.id === Number(alternateExerciseId))?.name
        : undefined,
    };
    setDays((prev) =>
      prev.map((d, i) =>
        i === activeDay ? { ...d, exercises: [...d.exercises, exercise] } : d,
      ),
    );
    setExerciseId("");
    setSets(3);
    setReps("8-12");
    setRestSeconds(60);
    setTempo("");
    setRpe("");
    setExerciseNotes("");
    setAlternateExerciseId("");
  };

  const removeExercise = (dayIndex: number, exerciseIndex: number) => {
    setDays((prev) =>
      prev.map((d, i) =>
        i === dayIndex
          ? {
              ...d,
              exercises: d.exercises
                .filter((_, ei) => ei !== exerciseIndex)
                .map((ex, ei) => ({ ...ex, order: ei })),
            }
          : d,
      ),
    );
  };

  const moveExercise = (dayIndex: number, exerciseIndex: number, direction: -1 | 1) => {
    setDays((prev) =>
      prev.map((d, i) => {
        if (i !== dayIndex) return d;
        const target = exerciseIndex + direction;
        if (target < 0 || target >= d.exercises.length) return d;
        const next = [...d.exercises];
        const [moved] = next.splice(exerciseIndex, 1);
        next.splice(target, 0, moved);
        return { ...d, exercises: next.map((ex, ei) => ({ ...ex, order: ei })) };
      }),
    );
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (days.length === 0) return;
    const payload: WorkoutPlanFormData = {
      name,
      description: description || undefined,
      goal,
      difficulty,
      duration_weeks: durationWeeks,
      is_template: isTemplate,
      days: days.map((d): WorkoutDayFormData => ({
        day_of_week: d.day_of_week || undefined,
        day_number: d.day_number,
        focus: d.focus || undefined,
        notes: d.notes || undefined,
        exercises: d.exercises.map((ex) => ({
          exercise: ex.exercise,
          sets: ex.sets,
          reps: ex.reps,
          rest_seconds: ex.rest_seconds,
          tempo: ex.tempo || undefined,
          rpe: ex.rpe,
          notes: ex.notes || undefined,
          order: ex.order,
          alternate_exercise: ex.alternate_exercise || null,
        })),
      })),
    };
    void onSubmit(payload);
  };

  const activeDayData = days[activeDay];
  const totalExercises = days.reduce((acc, d) => acc + d.exercises.length, 0);

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}

      {/* Plan details */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 text-lg font-semibold text-gray-900">Plan details</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Input
            label="Plan name"
            placeholder="Push / Pull / Legs"
            value={name}
            onChange={(e) => setName(e.target.value)}
            required
          />
          <div className="space-y-1.5">
            <label htmlFor="goal" className="block text-sm font-medium text-gray-700">
              Goal
            </label>
            <select
              id="goal"
              value={goal}
              onChange={(e) => setGoal(e.target.value as WorkoutGoal)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {GOAL_OPTIONS.map((g) => (
                <option key={g.value} value={g.value}>
                  {g.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div className="mt-4 space-y-1.5">
          <label htmlFor="description" className="block text-sm font-medium text-gray-700">
            Description
          </label>
          <textarea
            id="description"
            rows={2}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="What is this plan for?"
            className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          />
        </div>

        <div className="mt-4 grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="space-y-1.5">
            <label
              htmlFor="difficulty"
              className="block text-sm font-medium text-gray-700"
            >
              Difficulty
            </label>
            <select
              id="difficulty"
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as WorkoutDifficulty)}
              className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            >
              {DIFFICULTY_OPTIONS.map((d) => (
                <option key={d.value} value={d.value}>
                  {d.label}
                </option>
              ))}
            </select>
          </div>
          <Input
            label="Duration (weeks)"
            type="number"
            min="1"
            value={durationWeeks}
            onChange={(e) => setDurationWeeks(Number(e.target.value))}
          />
          <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-gray-200 p-4">
            <input
              type="checkbox"
              checked={isTemplate}
              onChange={(e) => setIsTemplate(e.target.checked)}
              className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
            />
            <span className="text-sm font-medium text-gray-700">Template plan</span>
          </label>
        </div>
      </div>

      {/* Day & exercise builder */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-900">Days & exercises</h2>
          <Button type="button" variant="outline" size="sm" onClick={addDay}>
            <Plus className="h-4 w-4" /> Add day
          </Button>
        </div>

        {days.length === 0 ? (
          <div className="rounded-lg border border-dashed border-gray-300 p-8 text-center">
            <CalendarDays className="mx-auto h-8 w-8 text-gray-300" />
            <p className="mt-2 text-sm text-gray-500">
              No days yet. Add a day to start building exercises.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Day tabs */}
            <div className="flex flex-wrap gap-2">
              {days.map((d, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => setActiveDay(i)}
                  className={`inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    i === activeDay
                      ? "bg-brand-600 text-white"
                      : "bg-gray-100 text-gray-700 hover:bg-gray-200"
                  }`}
                >
                  {dayLabel(d)}
                  <span className="text-xs opacity-70">
                    {d.exercises.length} ex
                  </span>
                  <span
                    role="button"
                    tabIndex={0}
                    onClick={(e) => {
                      e.stopPropagation();
                      removeDay(i);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        e.stopPropagation();
                        removeDay(i);
                      }
                    }}
                    className="ml-1 rounded p-0.5 hover:bg-black/10"
                    aria-label={`Remove day ${dayLabel(d)}`}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </span>
                </button>
              ))}
            </div>

            {activeDayData && (
              <div className="rounded-lg border border-gray-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <h3 className="font-medium text-gray-900">{dayLabel(activeDayData)}</h3>
                  <span className="text-sm text-gray-500">
                    {activeDayData.exercises.length} exercises
                  </span>
                </div>

                {/* Day settings */}
                <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                  <div className="space-y-1.5">
                    <label
                      htmlFor={`day-of-week-${activeDay}`}
                      className="block text-xs font-medium text-gray-600"
                    >
                      Day of week
                    </label>
                    <select
                      id={`day-of-week-${activeDay}`}
                      value={activeDayData.day_of_week}
                      onChange={(e) =>
                        updateDay(activeDay, {
                          day_of_week: e.target.value as DayOfWeek | "",
                        })
                      }
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    >
                      <option value="">Day {activeDayData.day_number ?? activeDay + 1}</option>
                      {DAY_OF_WEEK_OPTIONS.map((d) => (
                        <option key={d.value} value={d.value}>
                          {d.label}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1.5">
                    <label
                      htmlFor={`focus-${activeDay}`}
                      className="block text-xs font-medium text-gray-600"
                    >
                      Focus
                    </label>
                    <input
                      id={`focus-${activeDay}`}
                      type="text"
                      value={activeDayData.focus}
                      onChange={(e) => updateDay(activeDay, { focus: e.target.value })}
                      placeholder="e.g. Push Day"
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label
                      htmlFor={`day-notes-${activeDay}`}
                      className="block text-xs font-medium text-gray-600"
                    >
                      Notes
                    </label>
                    <input
                      id={`day-notes-${activeDay}`}
                      type="text"
                      value={activeDayData.notes}
                      onChange={(e) => updateDay(activeDay, { notes: e.target.value })}
                      placeholder="Optional day notes"
                      className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                    />
                  </div>
                </div>

                {/* Exercise add form */}
                <div className="mt-4 rounded-lg bg-gray-50 p-4">
                  <h4 className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-700">
                    <Dumbbell className="h-4 w-4 text-brand-600" /> Add exercise
                  </h4>
                  <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`exercise-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Exercise
                      </label>
                      <select
                        id={`exercise-${activeDay}`}
                        value={exerciseId}
                        onChange={(e) =>
                          setExerciseId(e.target.value ? Number(e.target.value) : "")
                        }
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      >
                        <option value="">Select exercise…</option>
                        {exercises.map((ex) => (
                          <option key={ex.id} value={ex.id}>
                            {ex.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`sets-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Sets
                      </label>
                      <input
                        id={`sets-${activeDay}`}
                        type="number"
                        min="1"
                        value={sets}
                        onChange={(e) => setSets(Number(e.target.value))}
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`reps-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Reps
                      </label>
                      <input
                        id={`reps-${activeDay}`}
                        type="text"
                        value={reps}
                        onChange={(e) => setReps(e.target.value)}
                        placeholder="8-12"
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`rest-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Rest (sec)
                      </label>
                      <input
                        id={`rest-${activeDay}`}
                        type="number"
                        min="0"
                        value={restSeconds}
                        onChange={(e) => setRestSeconds(Number(e.target.value))}
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                  <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-4">
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`tempo-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Tempo
                      </label>
                      <input
                        id={`tempo-${activeDay}`}
                        type="text"
                        value={tempo}
                        onChange={(e) => setTempo(e.target.value)}
                        placeholder="3-1-2"
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`rpe-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        RPE (1-10)
                      </label>
                      <input
                        id={`rpe-${activeDay}`}
                        type="number"
                        min="1"
                        max="10"
                        value={rpe}
                        onChange={(e) =>
                          setRpe(e.target.value === "" ? "" : Number(e.target.value))
                        }
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`alternate-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Alternate exercise
                      </label>
                      <select
                        id={`alternate-${activeDay}`}
                        value={alternateExerciseId}
                        onChange={(e) =>
                          setAlternateExerciseId(
                            e.target.value ? Number(e.target.value) : "",
                          )
                        }
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      >
                        <option value="">None</option>
                        {exercises.map((ex) => (
                          <option key={ex.id} value={ex.id}>
                            {ex.name}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1.5">
                      <label
                        htmlFor={`ex-notes-${activeDay}`}
                        className="block text-xs font-medium text-gray-600"
                      >
                        Notes
                      </label>
                      <input
                        id={`ex-notes-${activeDay}`}
                        type="text"
                        value={exerciseNotes}
                        onChange={(e) => setExerciseNotes(e.target.value)}
                        placeholder="Optional"
                        className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                      />
                    </div>
                  </div>
                  <div className="mt-3">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={addExercise}
                      disabled={!selectedExercise}
                    >
                      <Plus className="h-4 w-4" /> Add exercise
                    </Button>
                  </div>
                </div>

                {/* Exercises list */}
                {activeDayData.exercises.length === 0 ? (
                  <p className="mt-4 text-sm text-gray-400">
                    No exercises in this day yet.
                  </p>
                ) : (
                  <div className="mt-4 overflow-x-auto">
                    <table className="w-full text-left text-sm">
                      <thead className="border-b border-gray-100 text-xs uppercase text-gray-500">
                        <tr>
                          <th className="py-2 pr-3 font-medium">#</th>
                          <th className="py-2 pr-3 font-medium">Exercise</th>
                          <th className="py-2 pr-3 font-medium">Sets</th>
                          <th className="py-2 pr-3 font-medium">Reps</th>
                          <th className="py-2 pr-3 font-medium">Rest</th>
                          <th className="py-2 pr-3 font-medium">Tempo</th>
                          <th className="py-2 pr-3 font-medium">RPE</th>
                          <th className="py-2 pr-3 font-medium">Alternate</th>
                          <th className="py-2 text-right font-medium"></th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {activeDayData.exercises.map((ex, ei) => (
                          <tr key={ei}>
                            <td className="py-2 pr-3 text-gray-500">{ei + 1}</td>
                            <td className="py-2 pr-3 font-medium text-gray-900">
                              {ex.exercise_name ?? `Exercise #${ex.exercise}`}
                            </td>
                            <td className="py-2 pr-3 text-gray-600">{ex.sets}</td>
                            <td className="py-2 pr-3 text-gray-600">{ex.reps}</td>
                            <td className="py-2 pr-3 text-gray-600">
                              {ex.rest_seconds}s
                            </td>
                            <td className="py-2 pr-3 text-gray-600">{ex.tempo || "—"}</td>
                            <td className="py-2 pr-3 text-gray-600">{ex.rpe ?? "—"}</td>
                            <td className="py-2 pr-3 text-gray-600">
                              {ex.alternate_exercise_name ?? "—"}
                            </td>
                            <td className="py-2 text-right">
                              <div className="flex items-center justify-end gap-1">
                                <button
                                  type="button"
                                  onClick={() => moveExercise(activeDay, ei, -1)}
                                  disabled={ei === 0}
                                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-30"
                                  aria-label="Move exercise up"
                                >
                                  <ArrowUp className="h-4 w-4" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => moveExercise(activeDay, ei, 1)}
                                  disabled={ei === activeDayData.exercises.length - 1}
                                  className="rounded p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-700 disabled:opacity-30"
                                  aria-label="Move exercise down"
                                >
                                  <ArrowDown className="h-4 w-4" />
                                </button>
                                <button
                                  type="button"
                                  onClick={() => removeExercise(activeDay, ei)}
                                  className="rounded p-1 text-red-500 hover:bg-red-50"
                                  aria-label="Remove exercise"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Summary */}
      <div className="rounded-xl border border-gray-200 bg-white p-6">
        <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-gray-900">
          <Dumbbell className="h-5 w-5 text-brand-600" /> Plan summary
        </h2>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
          {[
            { label: "Days", value: String(days.length) },
            { label: "Exercises", value: String(totalExercises) },
            { label: "Duration", value: `${durationWeeks} weeks` },
          ].map((row) => (
            <div key={row.label} className="rounded-lg bg-gray-50 p-4">
              <p className="text-xs text-gray-500">{row.label}</p>
              <p className="mt-1 text-lg font-semibold text-gray-900">{row.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading} disabled={days.length === 0}>
          {submitLabel}
        </Button>
        {days.length === 0 && (
          <span className="text-sm text-gray-500">
            Add at least one day to save.
          </span>
        )}
      </div>
    </form>
  );
}
