/**
 * Feedback type definitions (FBOS-015).
 */

export type FeedbackCategory =
  | "workout"
  | "diet"
  | "trainer"
  | "facility"
  | "app";

export interface Feedback {
  id: number;
  customer: number | null;
  customer_name?: string | null;
  rating: number;
  category: FeedbackCategory;
  comment: string;
  is_anonymous: boolean;
  response: string | null;
  response_by: number | null;
  response_by_name?: string | null;
  response_at: string | null;
  created_at: string;
}

export interface FeedbackFormData {
  customer?: number | null;
  rating: number;
  category: FeedbackCategory;
  comment: string;
  is_anonymous: boolean;
}

export interface FeedbackResponseData {
  response: string;
}

export interface FeedbackListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Feedback[];
}

export interface RatingDistribution {
  rating: number;
  count: number;
}

export interface CategoryBreakdown {
  category: FeedbackCategory;
  count: number;
}

export interface SentimentSummary {
  positive: number;
  neutral: number;
  negative: number;
}

export interface TrendPoint {
  date: string;
  count: number;
  average_rating: number;
}

export interface FeedbackAnalytics {
  total_feedback: number;
  average_rating: number;
  rating_distribution: RatingDistribution[];
  category_breakdown: CategoryBreakdown[];
  sentiment: SentimentSummary;
  trend_30_days: TrendPoint[];
}

export interface FeedbackSurvey {
  id: number;
  title: string;
  description: string | null;
  is_active: boolean;
  created_at: string;
}

export interface FeedbackSurveyFormData {
  title: string;
  description?: string;
  is_active?: boolean;
}

export interface FeedbackSurveyListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FeedbackSurvey[];
}

export interface FeedbackResponse {
  id: number;
  survey: number;
  customer: number | null;
  answers: Record<string, unknown>;
  submitted_at: string;
}

export interface FeedbackResponseFormData {
  survey: number;
  customer?: number | null;
  answers: Record<string, unknown>;
}

export interface FeedbackResponseListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: FeedbackResponse[];
}
