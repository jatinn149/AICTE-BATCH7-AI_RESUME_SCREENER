import React, { useState, useRef, useEffect } from "react";
import api from "../api/axios";
import Card from "./Card";
import Button from "./UI/Button";

export default function RAGChatbot({ sessionId }) {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);
  const quickPrompts = [
    "Who is the top candidate and why?",
    "Compare top 3 candidates for this JD",
    "Who has Python and FastAPI experience?",
    "Which candidate has the strongest project relevance?",
    "Show full ranking with match percentages",
  ];

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const detectQueryType = (text) => {
    const q = text.toLowerCase();

    if (
      q.includes("how many") ||
      q.includes("list all") ||
      q.includes("names") ||
      q.includes("candidates")
    ) return "meta";

    if (
      q.includes("top") ||
      q.includes("highest") ||
      q.includes("most experience")
    ) return "aggregation";

    return "content";
  };

  const handleAsk = async (forcedQuery = null) => {
    if (loading) return;

    const userText = (forcedQuery || query).trim();
    if (!userText || userText.length > 1000) return;

    const queryType = detectQueryType(userText);
    const nextMessages = [...messages, { role: "user", content: userText }];

    setMessages(nextMessages);
    setQuery("");
    setLoading(true);
    setError("");

    try {
      const res = await api.post("/rag_query", {
          query: userText,
          query_type: queryType,
          top_k: 6,
          session_id: sessionId,
          chat_history: nextMessages.slice(-8),
      });

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.data.response || "No response." },
      ]);
    } catch (err) {
      const backendError = err?.response?.data?.detail;
      setError(typeof backendError === "string" ? backendError : "Failed to get response.");
    } finally {
      setLoading(false);
    }
  };

  const handleClear = () => {
    if (loading) return;
    setMessages([]);
    setError("");
  };

  return (
    <Card
      title="Resume Intelligence Chat"
      subtitle="Ask focused questions about candidate fit, ranking rationale, JD alignment, and resume evidence."
      icon="4"
      step="04"
    >
      <div className="flex flex-col space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-muted">
            Session-aware assistant
          </p>
          <div className="flex items-center gap-2">
            <span className="rounded-full border border-slate-300/80 bg-white/70 px-3 py-1 text-xs font-semibold text-slate-700 dark:border-slate-700 dark:bg-slate-900/60 dark:text-slate-200">
              {messages.length} messages
            </span>
            <Button
              onClick={handleClear}
              disabled={loading || messages.length === 0}
              variant="secondary"
              size="sm"
            >
              Clear Chat
            </Button>
          </div>
        </div>

        <div className="surface-panel border-slate-200/80 p-3 dark:border-slate-700/70 md:p-4">
          <p className="mb-2 text-xs font-bold uppercase tracking-[0.14em] text-muted">Quick prompts</p>
          <div className="flex flex-wrap gap-2">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                onClick={() => {
                  setQuery(prompt);
                }}
                className="rounded-lg border border-slate-300/80 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:border-brand-400 hover:text-brand-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-brand-500 dark:hover:text-brand-300"
                disabled={loading}
              >
                {prompt}
              </button>
            ))}
          </div>
        </div>

        {/* Chat Area */}
        <div className="surface-panel h-[460px] space-y-4 overflow-y-auto p-4 md:h-[500px] md:p-6">
          {messages.length === 0 && !loading && (
            <div className="flex h-full items-center justify-center text-center">
              <div>
                <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-300 bg-slate-100 text-sm font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                  AI
                </div>
                <h4 className="mb-2 text-lg font-bold text-slate-800 dark:text-slate-100">Start asking questions</h4>
                <p className="mb-4 text-sm leading-relaxed text-secondary">
                  Get concise, evidence-based answers from uploaded resumes and ranking data.
                </p>
                <div className="space-y-1 text-xs text-muted">
                  <p>• "Who is ranked first and why?"</p>
                  <p>• "Compare Alex and Priya for this JD"</p>
                  <p>• "Who matches Kubernetes and Docker requirements?"</p>
                </div>
              </div>
            </div>
          )}

          {messages.map((m, i) => (
            <div key={`${m.role}-${i}`} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] px-5 py-3.5 rounded-2xl text-sm leading-relaxed ${
                  m.role === "user"
                    ? "rounded-br-md border border-brand-700 bg-brand-600 text-white"
                    : "rounded-bl-md border border-slate-200 bg-white text-slate-800 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-100"
                }`}
              >
                <p className={`mb-1 text-[10px] font-bold uppercase tracking-[0.12em] ${m.role === "user" ? "text-white/80" : "text-muted"}`}>
                  {m.role === "user" ? "You" : "Recruiter AI"}
                </p>
                {m.content}
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl rounded-bl-md border border-slate-200 bg-white px-5 py-3.5 text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
                <div className="flex gap-2">
                  <div className="h-2 w-2 animate-bounce rounded-full bg-slate-400" />
                  <div className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "0.1s" }} />
                  <div className="h-2 w-2 animate-bounce rounded-full bg-slate-400" style={{ animationDelay: "0.2s" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {error && (
          <div className="rounded-xl border border-red-300/80 bg-red-100/70 p-4 text-sm font-semibold text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-300">
            {error}
          </div>
        )}

        {/* Input Area */}
        <div className="flex gap-3">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="input-premium flex-1 resize-none"
            placeholder="Ask about candidates, rankings, JD fit, skills, experience..."
            rows="3"
            maxLength={1000}
            disabled={loading}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
          />
          <div className="flex flex-col items-end gap-2">
            <span className="text-xs text-muted">{query.length}/1000</span>
            <Button
              onClick={() => handleAsk()}
              disabled={loading || !query.trim()}
              variant="primary"
              size="md"
              className="self-end px-4"
            >
              Ask
            </Button>
          </div>
        </div>
      </div>
    </Card>
  );
}
