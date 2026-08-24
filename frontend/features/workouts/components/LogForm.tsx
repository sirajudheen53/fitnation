"use client";

import { useState } from "react";
import { Dumbbell, Calendar } from "lucide-react";
import { Button, Input, Alert } from "@/components/ui";
import type { WorkoutExercise, WorkoutLogFormData } from "@/types/workout";
import { errorMessage } from "@/lib/api";

interface LogFormProps {
  exercises: WorkoutExercise[];
  submitLabel?: string;
  onSubmit: (data: WorkoutLogFormData) => void | Promise<void>;
  error?: unknown;
  loading?: boolean;
}

export function LogForm({
  exercises,
  submitLabel = "Log set",
  onSubmit,
  error,
  loading = false,
}: LogFormProps) {
  const [workoutExercise, setWorkoutExercise] = useState<number | "">("");
  const [dateCompleted, setDateCompleted] = useState(
    () => new Date().toISOString().slice(0, 10),
  );
  const [setNumber, setSetNumber] = useState(1);
  const [actualReps, setActualReps] = useState<number | "">("");
  const [actualWeight, setActualWeight] = useState<number | "">("");
  const [actualRest, setActualRest] = useState<number | "">("");
  const [notes, setNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const selectedExercise = exercises.find((e) => e.id === Number(workoutExercise));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (workoutExercise === "" || !dateCompleted) {
      setFormError("Exercise and date are required.");
      return;
    }
    setFormError(null);
    void onSubmit({
      customer: 0, // filled by parent page
      workout_exercise: Number(workoutExercise),
      workout_day: selectedExercise?.workout_day ?? 0,
      date_completed: dateCompleted,
      set_number: setNumber,
      actual_reps: actualReps === "" ? null : Number(actualReps),
      actual_weight: actualWeight === "" ? null : Number(actualWeight),
      actual_rest_seconds: actualRest === "" ? null : Number(actualRest),
      notes: notes || undefined,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-3xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {formError && <Alert variant="error">{formError}</Alert>}

      <div className="space-y-1.5">
        <label htmlFor="workout_exercise" className="block text-sm font-medium text-gray-700">
          Exercise
        </label>
        <div className="relative">
          <Dumbbell className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
          <select
            id="workout_exercise"
            value={workoutExercise}
            onChange={(e) =>
              setWorkoutExercise(e.target.value ? Number(e.target.value) : "")
            }
            className="block w-full rounded-lg border border-gray-300 bg-white py-2.5 pl-10 pr-3 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
          >
            <option value="">Select exercise</option>
            {exercises.map((ex) => (
              <option key={ex.id} value={ex.id}>
                {ex.exercise_name} ({ex.sets}×{ex.reps})
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <Input
          label="Date completed"
          type="date"
          value={dateCompleted}
          onChange={(e) => setDateCompleted(e.target.value)}
          icon={<Calendar className="h-4 w-4" />}
        />
        <Input
          label="Set number"
          type="number"
          min="1"
          value={setNumber}
          onChange={(e) => setSetNumber(Number(e.target.value))}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Input
          label="Actual reps"
          type="number"
          min="0"
          value={actualReps}
          onChange={(e) =>
            setActualReps(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
        <Input
          label="Actual weight (kg)"
          type="number"
          min="0"
          step="0.5"
          value={actualWeight}
          onChange={(e) =>
            setActualWeight(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
        <Input
          label="Actual rest (sec)"
          type="number"
          min="0"
          value={actualRest}
          onChange={(e) =>
            setActualRest(e.target.value === "" ? "" : Number(e.target.value))
          }
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="log-notes" className="block text-sm font-medium text-gray-700">
          Notes
        </label>
        <textarea
          id="log-notes"
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Optional notes"
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>
          {submitLabel}
        </Button>
      </div>
    </form>
  );
}
