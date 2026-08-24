/**
 * Feedback display helpers (FBOS-015).
 */

import type { Feedback, FeedbackCategory } from "@/types/feedback";

export const CATEGORY_LABELS: Record<FeedbackCategory, string> = {
  workout: "Workout",
  diet: "Diet",
  trainer: "Trainer",
  facility: "Facility",
  app: "App",
};

export const CATEGORY_OPTIONS: FeedbackCategory[] = [
  "workout",
  "diet",
  "trainer",
  "facility",
  "app",
];

export function getCategoryLabel(category: FeedbackCategory): string {
  return CATEGORY_LABELS[category] ?? category;
}

/** Display name for a feedback author, honoring anonymity. */
export function getFeedbackAuthorName(feedback: Feedback): string {
  if (feedback.is_anonymous) return "Anonymous";
  return feedback.customer_name || "Customer";
}

/** True when the feedback has a non-empty response. */
export function hasResponse(feedback: Feedback): boolean {
  return Boolean(feedback.response && feedback.response.trim().length > 0);
}

/** Format an ISO date string to a locale date, or an em dash when missing. */
export function formatFeedbackDate(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString();
}

/** Render a 1–5 star rating as a string of filled/empty star glyphs. */
export function renderStars(rating: number): string {
  const clamped = Math.max(1, Math.min(5, Math.round(rating)));
  return "★".repeat(clamped) + "☆".repeat(5 - clamped);
}

/** Map a rating to a semantic badge variant. */
export function getRatingVariant(
  rating: number,
): "success" | "warning" | "danger" | "default" {
  if (rating >= 4) return "success";
  if (rating >= 3) return "warning";
  return "danger";
}

/** Map a response status to a badge variant. */
export function getResponseVariant(
  feedback: Feedback,
): "success" | "default" {
  return hasResponse(feedback) ? "success" : "default";
}
