"use client";

import { Card, CardHeader, CardBody } from "@/components/ui";
import type { FeedbackAnalytics } from "@/types/feedback";
import { getCategoryLabel } from "./feedbackHelpers";

interface FeedbackAnalyticsDashboardProps {
  data: FeedbackAnalytics | null;
  loading?: boolean;
}

const SENTIMENT_COLORS: Record<string, string> = {
  positive: "bg-green-500",
  neutral: "bg-amber-500",
  negative: "bg-red-500",
};

const BAR_COLORS = ["#4f46e5", "#7c3aed", "#0ea5e9", "#f59e0b", "#10b981"];

export function FeedbackAnalyticsDashboard({
  data,
  loading = false,
}: FeedbackAnalyticsDashboardProps) {
  if (loading) {
    return (
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {[0, 1, 2, 3].map((i) => (
          <Card key={i}>
            <CardBody>
              <div className="h-48 animate-pulse rounded-lg bg-gray-100" />
            </CardBody>
          </Card>
        ))}
      </div>
    );
  }

  if (!data) {
    return (
      <Card>
        <CardBody>
          <p className="text-sm text-gray-500">No analytics data available.</p>
        </CardBody>
      </Card>
    );
  }

  const ratingDist = data.rating_distribution ?? [];
  const categoryBreakdown = data.category_breakdown ?? [];
  const sentiment = data.sentiment ?? { positive: 0, neutral: 0, negative: 0 };
  const trend = data.trend_30_days ?? [];

  const maxRatingCount = Math.max(1, ...ratingDist.map((r) => r.count));
  const maxCategoryCount = Math.max(1, ...categoryBreakdown.map((c) => c.count));
  const maxTrendCount = Math.max(1, ...trend.map((t) => t.count));
  const sentimentTotal = Math.max(
    1,
    sentiment.positive + sentiment.neutral + sentiment.negative,
  );

  return (
    <div className="space-y-6">
      {/* Summary cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card>
          <CardBody>
            <p className="text-sm text-gray-500">Total feedback</p>
            <p className="mt-1 text-3xl font-semibold text-gray-900">
              {data.total_feedback ?? 0}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-sm text-gray-500">Average rating</p>
            <p className="mt-1 text-3xl font-semibold text-gray-900">
              {data.average_rating != null
                ? Number(data.average_rating).toFixed(1)
                : "—"}
            </p>
          </CardBody>
        </Card>
        <Card>
          <CardBody>
            <p className="text-sm text-gray-500">Sentiment</p>
            <div className="mt-2 flex h-3 w-full overflow-hidden rounded-full bg-gray-100">
              <div
                className="bg-green-500"
                style={{ width: `${(sentiment.positive / sentimentTotal) * 100}%` }}
              />
              <div
                className="bg-amber-500"
                style={{ width: `${(sentiment.neutral / sentimentTotal) * 100}%` }}
              />
              <div
                className="bg-red-500"
                style={{ width: `${(sentiment.negative / sentimentTotal) * 100}%` }}
              />
            </div>
            <div className="mt-2 flex flex-wrap gap-3 text-xs text-gray-600">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-green-500" /> Positive{" "}
                {sentiment.positive}
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-amber-500" /> Neutral{" "}
                {sentiment.neutral}
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-red-500" /> Negative{" "}
                {sentiment.negative}
              </span>
            </div>
          </CardBody>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Rating distribution */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Rating distribution</h2>
          </CardHeader>
          <CardBody>
            {ratingDist.length === 0 ? (
              <p className="text-sm text-gray-500">No rating data.</p>
            ) : (
              <div className="space-y-3">
                {ratingDist.map((r) => (
                  <div key={r.rating} className="flex items-center gap-3">
                    <span className="w-8 text-sm font-medium text-gray-700">
                      {r.rating}★
                    </span>
                    <div className="h-4 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className="h-full rounded-full bg-brand-600"
                        style={{ width: `${(r.count / maxRatingCount) * 100}%` }}
                      />
                    </div>
                    <span className="w-8 text-right text-sm text-gray-500">
                      {r.count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>

        {/* Category breakdown */}
        <Card>
          <CardHeader>
            <h2 className="text-lg font-semibold text-gray-900">Category breakdown</h2>
          </CardHeader>
          <CardBody>
            {categoryBreakdown.length === 0 ? (
              <p className="text-sm text-gray-500">No category data.</p>
            ) : (
              <div className="space-y-3">
                {categoryBreakdown.map((c, i) => (
                  <div key={c.category} className="flex items-center gap-3">
                    <span className="w-20 text-sm font-medium text-gray-700">
                      {getCategoryLabel(c.category)}
                    </span>
                    <div className="h-4 flex-1 overflow-hidden rounded-full bg-gray-100">
                      <div
                        className="h-full rounded-full"
                        style={{
                          width: `${(c.count / maxCategoryCount) * 100}%`,
                          backgroundColor: BAR_COLORS[i % BAR_COLORS.length],
                        }}
                      />
                    </div>
                    <span className="w-8 text-right text-sm text-gray-500">
                      {c.count}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {/* 30-day trend */}
      <Card>
        <CardHeader>
          <h2 className="text-lg font-semibold text-gray-900">30-day trend</h2>
        </CardHeader>
        <CardBody>
          {trend.length === 0 ? (
            <p className="text-sm text-gray-500">No trend data.</p>
          ) : (
            <div className="flex h-48 items-end gap-1">
              {trend.map((t) => (
                <div
                  key={t.date}
                  className="group relative flex flex-1 flex-col items-center justify-end"
                >
                  <div
                    className="w-full rounded-t bg-brand-600 transition-colors hover:bg-brand-700"
                    style={{
                      height: `${Math.max(4, (t.count / maxTrendCount) * 100)}%`,
                    }}
                    title={`${t.date}: ${t.count} feedback`}
                  />
                </div>
              ))}
            </div>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
