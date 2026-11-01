"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuthStore } from "@/store/auth";
import { api, ApiError, Listing, isOwnerListing } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string };

export default function DialoguePage() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { accessToken } = useAuthStore();

  const [listing, setListing] = useState<Listing | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(true);
  const [aiLoading, setAiLoading] = useState(false);
  const [finalizing, setFinalizing] = useState(false);
  const [error, setError] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!accessToken) return;
    const init = async () => {
      try {
        const l = await api.listings.get(accessToken, id);
        // The BOM dialogue is an owner-only authoring flow; a teaser response
        // means this listing belongs to someone else.
        if (!isOwnerListing(l)) {
          setError("This isn't your listing.");
          return;
        }
        setListing(l);

        // Try to load existing conversation first
        const existing = await api.listings.getDialogue(accessToken, id);
        if (existing.length > 0) {
          setMessages(existing as Message[]);
        } else {
          // No conversation yet — start with AI greeting
          setAiLoading(true);
          const greet = await api.listings.startDialogue(accessToken, id);
          setMessages(greet.messages as Message[]);
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Failed to load dialogue");
      } finally {
        setLoading(false);
        setAiLoading(false);
      }
    };
    init();
  }, [accessToken, id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || aiLoading) return;
    const userMsg = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);
    setAiLoading(true);
    setError("");
    try {
      const resp = await api.listings.sendDialogue(accessToken!, id, userMsg);
      setMessages(resp.messages as Message[]);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "AI error");
    } finally {
      setAiLoading(false);
    }
  };

  const handleFinalize = async () => {
    setFinalizing(true);
    setError("");
    try {
      await api.listings.finalizeBOM(accessToken!, id);
      router.push(`/dashboard/listings/${id}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Finalization failed");
      setFinalizing(false);
    }
  };

  if (loading) {
    return <p className="text-sm text-muted">Loading session…</p>;
  }

  return (
    <div className="flex flex-col h-[calc(100vh-8rem)]">
      <div className="flex items-center justify-between mb-4 shrink-0">
        <div>
          <Link href={`/dashboard/listings/${id}`} className="text-xs text-muted hover:text-ink-soft mb-0.5 inline-block">
            ← {listing?.title ?? "Back"}
          </Link>
          <p className="text-xs text-muted">AI BOM Documentation Session</p>
        </div>
        <div className="flex flex-col items-end gap-1">
          {messages.length < 6 && messages.length > 0 && (
            <p className="text-xs text-muted">Keep chatting to build a complete BOM</p>
          )}
          <button
            onClick={handleFinalize}
            disabled={finalizing || messages.length < 4}
            title={messages.length < 4 ? "Have at least 2 exchanges before finalizing" : ""}
            className="bg-green-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-green-700 disabled:opacity-40 transition-colors"
          >
            {finalizing ? "Generating BOM…" : "Finalize BOM"}
          </button>
        </div>
      </div>

      {error && (
        <div className="mb-3 bg-red-50 border border-red-200 rounded-lg p-3 text-red-700 text-sm shrink-0">{error}</div>
      )}

      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {messages.map((m, i) => (
          <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] px-4 py-3 rounded-2xl text-sm whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-accent text-white rounded-br-sm"
                  : "bg-white border border-line text-ink rounded-bl-sm"
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {aiLoading && (
          <div className="flex justify-start">
            <div className="bg-white border border-line rounded-2xl rounded-bl-sm px-4 py-3">
              <span className="text-muted text-sm">Thinking…</span>
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="shrink-0 flex gap-2 pt-3 border-t border-line">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && sendMessage()}
          disabled={aiLoading}
          className="flex-1 px-3 py-2 border border-line-strong rounded-lg text-sm focus:ring-2 focus:ring-accent"
          placeholder="Type your message and press Enter…"
        />
        <button
          onClick={sendMessage}
          disabled={aiLoading || !input.trim()}
          className="bg-accent text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-accent-hover disabled:opacity-40 transition-colors"
        >
          Send
        </button>
      </div>
    </div>
  );
}
