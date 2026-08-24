"use client";

import Link from "next/link";
import { Dumbbell, Pencil } from "lucide-react";
import { Card, CardBody, Badge } from "@/components/ui";
import type { Exercise } from "@/types/exercise";
import {
  formatDifficulty,
  difficultyBadgeVariant,
  formatMuscleGroup,
} from "./helpers";

interface ExerciseCardProps {
  exercise: Exercise;
  canEdit?: boolean;
}

export function ExerciseCard({ exercise, canEdit = false }: ExerciseCardProps) {
  return (
    <Card>
      <CardBody>
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-brand-100 text-brand-700">
              <Dumbbell className="h-5 w-5" />
            </div>
            <div>
              <h3 className="font-semibold text-gray-900">{exercise.name}</h3>
              {exercise.category_name && (
                <p className="text-sm text-gray-500">{exercise.category_name}</p>
              )}
            </div>
          </div>
          <Badge variant={difficultyBadgeVariant(exercise.difficulty)}>
            {formatDifficulty(exercise.difficulty)}
          </Badge>
        </div>

        {exercise.description && (
          <p className="mt-3 line-clamp-2 text-sm text-gray-600">
            {exercise.description}
          </p>
        )}

        {exercise.muscle_groups.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {exercise.muscle_groups.slice(0, 4).map((group) => (
              <Badge key={group} variant="info">
                {formatMuscleGroup(group)}
              </Badge>
            ))}
            {exercise.muscle_groups.length > 4 && (
              <Badge variant="default">
                +{exercise.muscle_groups.length - 4} more
              </Badge>
            )}
          </div>
        )}

        <div className="mt-4 flex items-center justify-end gap-2 border-t border-gray-100 pt-3">
          <Link
            href={`/exercises/${exercise.id}`}
            className="text-sm font-medium text-brand-600 hover:text-brand-700"
          >
            View details
          </Link>
          {canEdit && (
            <Link
              href={`/exercises/${exercise.id}/edit`}
              className="rounded-lg p-2 text-gray-500 hover:bg-gray-100 hover:text-gray-700"
              aria-label="Edit exercise"
            >
              <Pencil className="h-4 w-4" />
            </Link>
          )}
        </div>
      </CardBody>
    </Card>
  );
}
