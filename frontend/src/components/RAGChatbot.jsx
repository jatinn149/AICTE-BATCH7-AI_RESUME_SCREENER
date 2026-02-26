import React, { useState, useRef, useEffect } from "react";
import api from "../api/axios";
import Card from "./Card";
import Button from "./ui/Button";

export default function RAGChatbot({ sessionId }) {
  const [messages, setMessages] = useState([]);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const bottomRef = useRef(null);

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

  const handleAsk = async () => {
    if (!query.trim() || loading) return;

    const userText = query.trim();
    const queryType = detectQueryType(userText);

    setMessages((prev) => [...prev, { role: "user", content: userText }]);
    setQuery("");
    setLoading(true);
    setError("");

    try {
      const res = await api.get("/rag_query", {
        params: {
          query: userText,
          query_type: queryType,
          top_k: 3,
          session_id: sessionId,
        },
      });

      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.data.response || "No response." },
      ]);
    } catch (err) {
      setError("Failed to get response.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card title="Resume Intelligence Chat">
      <div className="flex flex-col space-y-4">
        <div className="h-[420px] overflow-y-auto rounded-xl bg-slate-900/70 p-4 space-y-4">
          {messages.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div className={`px-4 py-2 rounded-xl text-sm ${m.role === "user" ? "bg-indigo-600 text-white" : "bg-slate-800 text-slate-200"}`}>
                {m.content}
              </div>
            </div>
          ))}
          {loading && <div className="text-slate-400 animate-pulse">Thinking…</div>}
          <div ref={bottomRef} />
        </div>

        {error && <p className="text-sm text-red-400">{error}</p>}

        <div className="flex gap-3">
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="flex-1 rounded-xl bg-slate-900 px-4 py-3 text-white"
            placeholder="Ask about candidates…"
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleAsk();
              }
            }}
          />
          <Button onClick={handleAsk} disabled={loading}>Send</Button>
        </div>
      </div>
    </Card>
  );
}
