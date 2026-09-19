/**
 * Customer reviews & ratings type definitions — FBOS-034-FE (issue #7).
 *
 * Mirrors the backend `apps/reviews` serializers: the list endpoint
 * returns the paginated envelope plus top-level `average_rating` and
 * `count` aggregates.
 */

// ── Review response (staff reply) ──

/** A staff/trainer reply attached to a review (read-only nested). */
export interface ReviewResponse {
  id: number;
  review: number;
  text: string;
  author: number | null;
  author_name: string;
  created_at: string;
}

// ── Review ──

/** A customer's star rating + review for a branch (GET/POST /reviews/). */
export interface Review {
  id: number;
  customer: number;
  customer_detail: {
    id: number;
    name: string;
    email: string;
    phone: string;
  } | null;
  branch: number;
  rating: number;
  text: string;
  response: ReviewResponse | null;
  created_at: string;
  updated_at: string;
}

/** Body for POST /reviews/ (customer is inferred server-side for customer role). */
export interface ReviewFormData {
  branch: number;
  rating: number;
  text: string;
}

/** Body for POST /reviews/{id}/respond/ (trainer/manager only). */
export interface ReviewRespondData {
  text: string;
}

// ── List envelope (list endpoint adds aggregates on top of pagination) ──

/** GET /reviews/ response: paginated envelope + aggregate keys. */
export interface ReviewListEnvelope {
  count: number;
  next: string | null;
  previous: string | null;
  results: Review[];
  /** Average across the filtered queryset (1 decimal), null when no reviews. */
  average_rating: number | null;
}

// ── Helpers ──

/** Human-friendly date for review timestamps. */
export function formatReviewTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/** Star breakdown (5→1) from a list of reviews. */
export function starBreakdown(reviews: Review[]): { stars: number; count: number; pct: number }[] {
  const buckets = new Map<number, number>([
    [5, 0],
    [4, 0],
    [3, 0],
    [2, 0],
    [1, 0],
  ]);
  for (const review of reviews) {
    const clamped = Math.min(5, Math.max(1, Math.round(review.rating)));
    buckets.set(clamped, (buckets.get(clamped) ?? 0) + 1);
  }
  const total = reviews.length || 1;
  return [5, 4, 3, 2, 1].map((stars) => {
    const count = buckets.get(stars) ?? 0;
    return { stars, count, pct: Math.round((count / total) * 100) };
  });
}