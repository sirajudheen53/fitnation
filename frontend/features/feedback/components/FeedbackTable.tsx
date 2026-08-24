"use client";

import { useState } from "react";
import { MessageSquare, Send } from "lucide-react";
import { Button, Badge } from "@/components/ui";
import type { Feedback } from "@/types/feedback";
import {
  getCategoryLabel,
  getFeedbackAuthorName,
  getRatingVariant,
  getResponseVariant,
  hasResponse,
  renderStars,
  formatFeedbackDate,
} from "./feedbackHelpers";

interface FeedbackTableProps {
  feedback: Feedback[];
  onRespond: (feedback: Feedback, response: string) => void | Promise<void>;
  respondingId?: number | null;
}

export function FeedbackTable({
  feedback,
  onRespond,
  respondingId = null,
}: FeedbackTableProps) {
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [openId, setOpenId] = useState<number | null>(null);

  const toggleRespond = (id: number) => {
    setOpenId((prev) => (prev === id ? null : id));
  };

  const handleSubmit = async (item: Feedback) => {
    const response = (drafts[item.id] ?? "").trim();
    if (!response) return;
    await onRespond(item, response);
    setDrafts((prev) => ({ ...prev, [item.id]: "" }));
    setOpenId(null);
  };

  if (feedback.length === 0) {
    return (
      <div className="flex h-48 flex-col items-center justify-center rounded-xl border border-gray-200 bg-white">
        <p className="text-sm text-gray-500">No feedback found.</p>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {feedback.map((item) => {
        const responded = hasResponse(item);
        const isOpen = openId === item.id;
        const isResponding = respondingId === item.id;
        return (
          <div
            key={item.id}
            className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium text-gray-900">
                    {getFeedbackAuthorName(item)}
                  </span>
                  <span className="text-amber-500" aria-label={`${item.rating} out of 5 stars`}>
                    {renderStars(item.rating)}
                  </span>
                  <Badge variant={getRatingVariant(item.rating)}>
                    {item.rating}/5
                  </Badge>
                </div>
                <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-gray-500">
                  <Badge variant="info">{getCategoryLabel(item.category)}</Badge>
                  <span>{formatFeedbackDate(item.created_at)}</span>
                  <Badge variant={getResponseVariant(item)}>
                    {responded ? "Responded" : "Pending"}
                  </Badge>
                </div>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => toggleRespond(item.id)}
                aria-expanded={isOpen}
              >
                <MessageSquare className="h-4 w-4" />
                {responded ? "Edit response" : "Respond"}
              </Button>
            </div>

            <p className="mt-3 text-sm text-gray-700">{item.comment}</p>

            {responded && item.response && (
              <div className="mt-3 rounded-lg bg-brand-50 p-3">
                <p className="text-xs font-medium text-brand-700">Your response</p>
                <p className="mt-1 text-sm text-gray-800">{item.response}</p>
                {item.response_at && (
                  <p className="mt-1 text-xs text-gray-500">
                    {formatFeedbackDate(item.response_at)}
                  </p>
                )}
              </div>
            )}

            {isOpen && (
              <div className="mt-3 space-y-2">
                <textarea
                  value={drafts[item.id] ?? ""}
                  onChange={(e) =>
                    setDrafts((prev) => ({ ...prev, [item.id]: e.target.value }))
                  }
                  rows={3}
                  placeholder="Write a response to this customer…"
                  className="block w-full rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 placeholder:text-gray-400 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
                />
                <div className="flex justify-end">
                  <Button
                    size="sm"
                    loading={isResponding}
                    disabled={!(drafts[item.id] ?? "").trim()}
                    onClick={() => handleSubmit(item)}
                  >
                    <Send className="h-4 w-4" /> Submit response
                  </Button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
