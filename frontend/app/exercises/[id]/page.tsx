"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Spinner, Alert, Card, CardBody, CardHeader, Button, Badge } from "@/components/ui";
import { fetchExercise, errorMessage } from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Exercise } from "@/types/exercise";
import {
  formatDifficulty,
  difficultyBadgeVariant,
  formatMuscleGroup,
  formatEquipment,
  isMediaUrl,
  isVideoUrl,
  isImageUrl,
} from "@/features/exercises/components/helpers";

export default function ExerciseDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = Number(params.id);
  const [exercise, setExercise] = useState<Exercise | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/exercises/" + id);
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const data = await fetchExercise(id, authToken);
        setExercise(data);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id, router]);

  const canEdit = userRole ? canAccessRoute(userRole, "/exercises/new") : false;

  return (
    <DashboardLayout
      title={exercise ? exercise.name : "Exercise detail"}
      actions={
        exercise && canEdit ? (
          <Button
            variant="outline"
            size="sm"
            onClick={() => router.push(`/exercises/${exercise.id}/edit`)}
          >
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

      {exercise && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center gap-3 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <div className="flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-lg font-semibold text-gray-900">{exercise.name}</h2>
                <Badge variant={difficultyBadgeVariant(exercise.difficulty)}>
                  {formatDifficulty(exercise.difficulty)}
                </Badge>
                {exercise.category_name && (
                  <Badge variant="info">{exercise.category_name}</Badge>
                )}
              </div>
              {exercise.description && (
                <p className="mt-2 text-sm text-gray-600">{exercise.description}</p>
              )}
            </div>
          </div>

          {isMediaUrl(exercise.media_url) && (
            <Card>
              <CardHeader>
                <h3 className="text-base font-semibold text-gray-900">Media</h3>
              </CardHeader>
              <CardBody>
                {isVideoUrl(exercise.media_url) ? (
                  <video
                    controls
                    className="w-full rounded-lg"
                    src={exercise.media_url ?? undefined}
                    aria-label="Exercise video"
                  >
                    Your browser does not support the video tag.
                  </video>
                ) : isImageUrl(exercise.media_url) ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={exercise.media_url ?? undefined}
                    alt={exercise.name}
                    className="w-full rounded-lg object-cover"
                  />
                ) : (
                  <a
                    href={exercise.media_url ?? undefined}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm font-medium text-brand-600 hover:text-brand-700"
                  >
                    Open media link
                  </a>
                )}
              </CardBody>
            </Card>
          )}

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <Card>
              <CardHeader>
                <h3 className="text-base font-semibold text-gray-900">Muscle groups</h3>
              </CardHeader>
              <CardBody>
                {exercise.muscle_groups.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {exercise.muscle_groups.map((group) => (
                      <Badge key={group} variant="info">
                        {formatMuscleGroup(group)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No muscle groups specified.</p>
                )}
              </CardBody>
            </Card>

            <Card>
              <CardHeader>
                <h3 className="text-base font-semibold text-gray-900">Equipment needed</h3>
              </CardHeader>
              <CardBody>
                {exercise.equipment_needed.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {exercise.equipment_needed.map((equipment) => (
                      <Badge key={equipment} variant="default">
                        {formatEquipment(equipment)}
                      </Badge>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-gray-500">No equipment required.</p>
                )}
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <h3 className="text-base font-semibold text-gray-900">Instructions</h3>
            </CardHeader>
            <CardBody>
              {exercise.instructions.length > 0 ? (
                <ol className="space-y-3">
                  {exercise.instructions.map((step, index) => (
                    <li key={index} className="flex items-start gap-3">
                      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
                        {index + 1}
                      </span>
                      <span className="text-sm text-gray-700">{step}</span>
                    </li>
                  ))}
                </ol>
              ) : (
                <p className="text-sm text-gray-500">No instructions provided.</p>
              )}
            </CardBody>
          </Card>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {exercise.tips && (
              <Card>
                <CardHeader>
                  <h3 className="text-base font-semibold text-gray-900">Tips</h3>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-gray-700">{exercise.tips}</p>
                </CardBody>
              </Card>
            )}

            {exercise.contraindications && (
              <Card>
                <CardHeader>
                  <h3 className="text-base font-semibold text-gray-900">
                    Contraindications
                  </h3>
                </CardHeader>
                <CardBody>
                  <p className="text-sm text-gray-700">{exercise.contraindications}</p>
                </CardBody>
              </Card>
            )}
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}
