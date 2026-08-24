"use client";

import { useState } from "react";
import { Star, Send } from "lucide-react";
import { Button, Alert } from "@/components/ui";
import { errorMessage } from "@/lib/api";
import type { FeedbackCategory, FeedbackFormData } from "@/types/feedback";
import { CATEGORY_OPTIONS, getCategoryLabel } from "./feedbackHelpers";

interface FeedbackFormProps {
  onSubmit: (data: FeedbackFormData) => void | Promise<void>;
  submitLabel?: string;
  error?: unknown;
  loading?: boolean;
}

export function FeedbackForm({
  onSubmit,
  submitLabel = "Submit feedback",
  error,
  loading = false,
}: FeedbackFormProps) {
  const [rating, setRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);
  const [category, setCategory] = useState<FeedbackCategory | "">("");
  const [comment, setComment] = useState("");
  const [isAnonymous, setIsAnonymous] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (rating < 1) {
      setValidationError("Please select a rating.");
      return;
    }
    if (!category) {
      setValidationError("Please select a category.");
      return;
    }
    if (!comment.trim()) {
      setValidationError("Please write a comment.");
      return;
    }
    setValidationError(null);
    await onSubmit({
      rating,
      category,
      comment: comment.trim(),
      is_anonymous: isAnonymous,
    });
  };

  return (
    <form onSubmit={handleSubmit} className="max-w-2xl space-y-6">
      {error != null && <Alert variant="error">{errorMessage(error)}</Alert>}
      {validationError && <Alert variant="warning">{validationError}</Alert>}

      {/* Rating selector */}
      <div className="space-y-2">
        <span className="block text-sm font-medium text-gray-700">Your rating</span>
        <div className="flex items-center gap-1">
          {[1, 2, 3, 4, 5].map((value) => {
            const active = value <= (hoverRating || rating);
            return (
              <button
                key={value}
                type="button"
                aria-label={`${value} star${value > 1 ? "s" : ""}`}
                onMouseEnter={() => setHoverRating(value)}
                onMouseLeave={() => setHoverRating(0)}
                onClick={() => setRating(value)}
                className="transition-colors"
              >
                <Star
                  className={`h-8 w-8 ${
                    active
                      ? "fill-amber-400 text-amber-400"
                      : "text-gray-300"
                  }`}
                />
              </button>
            );
          })}
          {rating > 0 && (
            <span className="ml-2 text-sm text-gray-500">{rating}/5</span>
          )}
        </div>
      </div>

      {/* Category dropdown */}
      <div className="space-y-1.5">
        <label htmlFor="category" className="block text-sm font-medium text-gray-700">
          Category
        </label>
        <select
          id="category"
          value={category}
          onChange={(e) => setCategory(e.target.value as FeedbackCategory | "")}
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        >
          <option value="">Select a category</option>
          {CATEGORY_OPTIONS.map((c) => (
            <option key={c} value={c}>
              {getCategoryLabel(c)}
            </option>
          ))}
        </select>
      </div>

      {/* Comment */}
      <div className="space-y-1.5">
        <label htmlFor="comment" className="block text-sm font-medium text-gray-700">
          Your feedback
        </label>
        <textarea
          id="comment"
          value={comment}
          onChange={(e) => setComment(e.target.value)}
          rows={5}
          placeholder="Tell us what you think…"
          className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        />
      </div>

      {/* Anonymous toggle */}
      <div className="flex items-center gap-3 rounded-lg border border-gray-200 bg-white p-4">
        <label className="flex cursor-pointer items-center gap-3">
          <input
            type="checkbox"
            checked={isAnonymous}
            onChange={(e) => setIsAnonymous(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-brand-600 focus:ring-brand-500"
          />
          <span className="text-sm font-medium text-gray-700">
            Submit anonymously
          </span>
        </label>
      </div>

      <div className="flex items-center gap-3">
        <Button type="submit" loading={loading}>
          <Send className="h-4 w-4" /> {submitLabel}
        </Button>
      </div>
    </form>
  );
}
