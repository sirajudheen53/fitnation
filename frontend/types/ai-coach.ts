/**
 * AI Coach type definitions — FBOS-017.
 */

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: number;
  conversation: number;
  role: ChatRole;
  content: string;
  created_at: string;
}

export interface Conversation {
  id: number;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}

export interface ConversationListResponse {
  count: number;
  next: string | null;
  previous: string | null;
  results: Conversation[];
}

export interface AiChatRequest {
  message: string;
  conversation_id?: number;
}

export interface AiChatResponse {
  conversation_id: number;
  message: ChatMessage;
  response: string;
}
