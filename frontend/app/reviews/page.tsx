"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";
import { Plus, Star, X } from "lucide-react";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Badge, Button, Card, CardBody, CardHeader, Input, Spinner } from "@/components/ui";
import {
  createReview,
  errorMessage,
  fetchBranches,
  fetchReviews,
  respondToReview,
} from "@/lib/api";
import { getToken } from "@/lib/auth";
import { canAccessRoute } from "@/lib/permissions";
import type { Branch } from "@/types/branch";
import {
  formatReviewTimestamp,
  starBreakdown,
  type Review,
} from "@/types/reviews";

/* ── Star display ─────────────────────────────────────────────── */

function StarRow({ value, className = "" }: { value: number; className?: string }) {
  return (
    <div className={`flex gap-0.5 ${className}`}>
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`h-4 w-4 ${
            star <= Math.round(value)
              ? "fill-amber-400 text-amber-400"
              : "text-gray-300"
          }`}
        />
      ))}
    </div>
  );
}

/* ── Write-review form ────────────────────────────────────────── */

interface WriteReviewProps {
  branches: Branch[];
  onClose: () => void;
  onSaved: (review: Review) => void;
}

function WriteReviewDialog({ branches, onClose, onSaved }: WriteReviewProps) {
  const [branch, setBranch] = useState<number>(branches[0]?.id ?? 0);
  const [rating, setRating] = useState(5);
  const [hovered, setHovered] = useState(0);
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!branch) {
      toast.error("Select a branch.");
      return;
    }
    const token = getToken();
    if (!token) return;
    setSaving(true);
    try {
      const created = await createReview({ branch, rating, text }, token);
      toast.success("Review submitted — thank you!");
      onSaved(created);
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">Write a Review</h3>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Branch</label>
            <select
              className="block w-full rounded-lg border border-gray-300 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              value={branch || ""}
              onChange={(e) => setBranch(Number(e.target.value))}
            >
              {branches.map((b) => (
                <option key={b.id} value={b.id}>
                  {b.name}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="block text-sm font-medium text-gray-700">Your rating</label>
            <div className="flex gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onMouseEnter={() => setHovered(star)}
                  onMouseLeave={() => setHovered(0)}
                  onClick={() => setRating(star)}
                  aria-label={`${star} star${star > 1 ? "s" : ""}`}
                >
                  <Star
                    className={`h-8 w-8 transition-colors ${
                      star <= (hovered || rating)
                        ? "fill-amber-400 text-amber-400"
                        : "text-gray-300"
                    }`}
                  />
                </button>
              ))}
            </div>
          </div>
          <Input
            label="Your review"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="How was your experience?"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? "Submitting…" : "Submit Review"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

/* ── Respond dialog (staff) ───────────────────────────────────── */

function RespondDialog({
  review,
  onClose,
  onSaved,
}: {
  review: Review;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit() {
    if (!text.trim()) {
      toast.error("Write a response first.");
      return;
    }
    const token = getToken();
    if (!token) return;
    setSaving(true);
    try {
      await respondToReview(review.id, { text }, token);
      toast.success("Response posted");
      onSaved();
    } catch (err) {
      toast.error(errorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <Card className="w-full max-w-md">
        <CardBody className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-gray-900">
              Respond to Review
            </h3>
            <Button variant="ghost" size="sm" onClick={onClose}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="rounded-lg bg-gray-50 p-3 text-sm text-gray-700">
            <StarRow value={review.rating} className="mb-1" />
            {review.text || <span className="italic text-gray-400">(no text)</span>}
          </div>
          <Input
            label="Your response"
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Thank you for the feedback…"
          />
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? "Posting…" : "Post Response"}
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

/* ── Main page ────────────────────────────────────────────────── */

export default function ReviewsPage() {
  const router = useRouter();
  const [reviews, setReviews] = useState<Review[]>([]);
  const [average, setAverage] = useState<number | null>(null);
  const [branches, setBranches] = useState<Branch[]>([]);
  const [branchFilter, setBranchFilter] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showWrite, setShowWrite] = useState(false);
  const [responding, setResponding] = useState<Review | null>(null);

  const [userRole, setUserRole] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const storedUser = localStorage.getItem("fbos_user");
    return storedUser ? (JSON.parse(storedUser).role as string) : null;
  });

  const isStaff = useMemo(
    () => userRole === "gym_owner" || userRole === "manager" || userRole === "trainer" || userRole === "platform_admin",
    [userRole],
  );

  useEffect(() => {
    if (userRole && !canAccessRoute(userRole, "/reviews")) {
      router.replace("/unauthorized");
      return;
    }
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/reviews");
      return;
    }
    const authToken: string = token;

    async function load() {
      try {
        const [branchList, envelope] = await Promise.all([
          fetchBranches(authToken),
          fetchReviews(authToken, { branch_id: branchFilter || undefined }),
        ]);
        setBranches(branchList);
        setReviews(envelope.results ?? []);
        setAverage(envelope.average_rating);
      } catch (err) {
        setError(errorMessage(err));
      } finally {
        setLoading(false);
      }
    }
    void load();
  }, [router, userRole, branchFilter]);

  const breakdown = useMemo(() => starBreakdown(reviews), [reviews]);

  function reload() {
    const token = getToken();
    if (!token) return;
    fetchReviews(token, { branch_id: branchFilter || undefined })
      .then((env) => {
        setReviews(env.results ?? []);
        setAverage(env.average_rating);
      })
      .catch((err) => toast.error(errorMessage(err)));
  }

  return (
    <DashboardLayout
      title="Reviews & Ratings"
      actions={
        <Button onClick={() => setShowWrite(true)}>
          <Plus className="mr-2 h-4 w-4" /> Write Review
        </Button>
      }
    >
      {error && (
        <Card className="mb-4">
          <CardBody className="text-sm text-red-600">{error}</CardBody>
        </Card>
      )}

      {/* Average + breakdown */}
      <Card className="mb-4">
        <CardBody className="flex flex-col gap-6 sm:flex-row sm:items-center">
          <div className="text-center sm:border-r sm:border-gray-200 sm:pr-8">
            <div className="text-4xl font-bold text-gray-900">
              {average !== null ? average.toFixed(1) : "—"}
            </div>
            <StarRow value={Math.round(average ?? 0)} className="mt-1 justify-center" />
            <div className="mt-1 text-xs text-gray-500">
              {reviews.length} review{reviews.length === 1 ? "" : "s"}
            </div>
          </div>
          <div className="flex-1 space-y-1.5">
            {breakdown.map(({ stars, count, pct }) => (
              <div key={stars} className="flex items-center gap-2 text-xs">
                <span className="w-10 text-gray-600">{stars} ★</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-gray-200">
                  <div
                    className="h-full bg-amber-400"
                    style={{ width: `${pct}%` }}
                  />
                </div>
                <span className="w-8 text-right text-gray-500">{count}</span>
              </div>
            ))}
          </div>
          {isStaff && branches.length > 0 && (
            <div className="space-y-1.5 sm:w-48">
              <label className="block text-xs font-medium text-gray-700">Branch</label>
              <select
                className="block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
                value={branchFilter}
                onChange={(e) => setBranchFilter(e.target.value)}
              >
                <option value="">All branches</option>
                {branches.map((b) => (
                  <option key={b.id} value={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </div>
          )}
        </CardBody>
      </Card>

      {/* Review list */}
      {loading ? (
        <div className="flex justify-center py-12">
          <Spinner className="h-8 w-8" />
        </div>
      ) : reviews.length === 0 ? (
        <Card>
          <CardBody className="py-12 text-center text-sm text-gray-500">
            No reviews yet{branchFilter ? " for this branch" : ""}.
          </CardBody>
        </Card>
      ) : (
        <div className="space-y-3">
          {reviews.map((review) => (
            <Card key={review.id}>
              <CardBody className="space-y-2">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-gray-900">
                        {review.customer_detail?.name ?? `Customer #${review.customer}`}
                      </span>
                      <StarRow value={review.rating} />
                      <span className="text-xs text-gray-400">
                        {formatReviewTimestamp(review.created_at)}
                      </span>
                    </div>
                    {review.text && (
                      <p className="mt-1.5 text-sm text-gray-700">{review.text}</p>
                    )}
                  </div>
                  {isStaff && !review.response && (
                    <Button variant="outline" size="sm" onClick={() => setResponding(review)}>
                      Respond
                    </Button>
                  )}
                </div>
                {review.response && (
                  <div className="rounded-lg border-l-4 border-brand-500 bg-gray-50 p-3 text-sm">
                    <div className="mb-0.5 text-xs font-medium text-gray-500">
                      Response · {review.response.author_name}
                    </div>
                    <div className="text-gray-700">{review.response.text}</div>
                  </div>
                )}
              </CardBody>
            </Card>
          ))}
        </div>
      )}

      {showWrite && (
        <WriteReviewDialog
          branches={branches}
          onClose={() => setShowWrite(false)}
          onSaved={() => {
            setShowWrite(false);
            reload();
          }}
        />
      )}

      {responding && (
        <RespondDialog
          review={responding}
          onClose={() => setResponding(null)}
          onSaved={() => {
            setResponding(null);
            reload();
          }}
        />
      )}
    </DashboardLayout>
  );
}