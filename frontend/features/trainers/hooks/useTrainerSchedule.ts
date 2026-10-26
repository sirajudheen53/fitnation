"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createTrainerScheduleSlot,
  deleteTrainerScheduleSlot,
  fetchTrainerSchedule,
  updateTrainerScheduleSlot,
} from "@/lib/api";
import type { ScheduleSlotInput } from "@/types/trainer";

/**
 * React Query hooks for a trainer's weekly schedule (issue #80).
 *
 * One query per trainer; the create/update/delete mutations invalidate it so
 * the profile's Schedule tab refetches after every change.
 */

export function useTrainerSchedule(
  trainerId: number | string,
  token: string | null,
) {
  return useQuery({
    queryKey: ["trainer-schedule", String(trainerId)],
    queryFn: () => fetchTrainerSchedule(trainerId, token as string),
    enabled: !!token,
  });
}

export function useCreateScheduleSlot(
  trainerId: number | string,
  token: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: ScheduleSlotInput) =>
      createTrainerScheduleSlot({ ...data, trainer: Number(trainerId) }, token),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["trainer-schedule", String(trainerId)],
      }),
  });
}

export function useUpdateScheduleSlot(
  trainerId: number | string,
  token: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: ScheduleSlotInput }) =>
      updateTrainerScheduleSlot(id, { ...data, trainer: Number(trainerId) }, token),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["trainer-schedule", String(trainerId)],
      }),
  });
}

export function useDeleteScheduleSlot(
  trainerId: number | string,
  token: string,
) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteTrainerScheduleSlot(id, token),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["trainer-schedule", String(trainerId)],
      }),
  });
}
