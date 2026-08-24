"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { MessageCircle, Send, Plus } from "lucide-react";
import { getToken } from "@/lib/auth";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { Button, Alert, Spinner, Input } from "@/components/ui";
import { aiChat, fetchConversations, errorMessage } from "@/lib/api";
import type { Conversation } from "@/types/ai-coach";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export default function AICoachPage() {
  const router = useRouter();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversation] = useState<number | null>(
    null,
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      router.replace("/login?next=/ai-coach");
      return;
    }
    fetchConversations(token)
      .then((data) => setConversations(data.results))
      .catch((err) => setError(errorMessage(err)))
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSelectConversation = (conv: Conversation) => {
    setActiveConversation(conv.id);
    setMessages(
      conv.messages.map((m) => ({ role: m.role, content: m.content })),
    );
    setError(null);
  };

  const handleNewChat = () => {
    setActiveConversation(null);
    setMessages([]);
    setInput("");
    setError(null);
  };

  const handleSend = async () => {
    const token = getToken();
    const trimmed = input.trim();
    if (!token || !trimmed || sending) return;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setInput("");
    setSending(true);
    setError(null);

    try {
      const response = await aiChat(token, trimmed, activeConversation ?? undefined);
      setActiveConversation(response.conversation_id);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.response },
      ]);
    } catch (err) {
      setError(errorMessage(err));
    } finally {
      setSending(false);
    }
  };

  return (
    <DashboardLayout
      title="AI Coach"
      actions={
        <Button variant="outline" size="sm" onClick={handleNewChat}>
          <Plus className="mr-1 h-4 w-4" /> New chat
        </Button>
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 h-[calc(100vh-14rem)]">
        {/* Conversation list */}
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-gray-100 px-4 py-3">
            <h3 className="font-semibold text-gray-900">Conversations</h3>
          </div>
          <div className="overflow-y-auto h-full">
            {loading ? (
              <div className="flex justify-center py-10">
                <Spinner className="h-6 w-6" />
              </div>
            ) : conversations.length === 0 ? (
              <p className="px-4 py-6 text-sm text-gray-500">
                No conversations yet. Start a new chat!
              </p>
            ) : (
              conversations.map((conv) => (
                <button
                  key={conv.id}
                  type="button"
                  onClick={() => handleSelectConversation(conv)}
                  className={`block w-full px-4 py-3 text-left text-sm hover:bg-gray-50 ${
                    activeConversation === conv.id
                      ? "bg-brand-50 text-brand-700"
                      : "text-gray-700"
                  }`}
                >
                  <span className="line-clamp-1 font-medium">
                    {conv.title || "Untitled chat"}
                  </span>
                  <span className="text-xs text-gray-400">
                    {new Date(conv.updated_at).toLocaleDateString("en-IN")}
                  </span>
                </button>
              ))
            )}
          </div>
        </div>

        {/* Chat area */}
        <div className="md:col-span-3 flex flex-col rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
            {messages.length === 0 && (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <MessageCircle className="h-12 w-12 text-gray-300" />
                <p className="mt-4 text-lg font-medium text-gray-900">
                  Welcome to AI Coach
                </p>
                <p className="mt-1 max-w-sm text-sm text-gray-500">
                  Ask me about workouts, nutrition, recovery, or anything
                  fitness-related.
                </p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-2 text-sm ${
                    msg.role === "user"
                      ? "bg-brand-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex justify-start">
                <div className="rounded-2xl bg-gray-100 px-4 py-2 text-sm text-gray-500">
                  <Spinner className="h-4 w-4" />
                </div>
              </div>
            )}
          </div>

          <div className="border-t border-gray-100 p-3">
            {error && <Alert variant="error" className="mb-2">{error}</Alert>}
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Type a message..."
                className="flex-1"
              />
              <Button onClick={handleSend} disabled={sending || !input.trim()}>
                Send
              </Button>
            </div>
          </div>
        </div>
      </div>
    </DashboardLayout>
  );
}
