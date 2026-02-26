import React, { useRef, useState, useEffect } from "react";
import api from "../api/axios";
import Card from "./Card";

export default function JDInput({ onJDSet, locked = false, sessionId }) {
  const [jdText, setJDText] = useState("");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // 🔒 Prevent duplicate submissions (StrictMode-safe)
  const hasSubmittedRef = useRef(false);

  // =====================================================
  // 🔥 CRITICAL FIX — reset guards when session changes
  // =====================================================
  useEffect(() => {
    hasSubmittedRef.current = false;
    setSubmitting(false);
    setMessage("");
    setJDText("");
  }, [sessionId]);

  const handleSubmit = async (e) => {
    e.preventDefault();

    if (locked || submitting || hasSubmittedRef.current) return;

    if (!jdText.trim()) {
      setMessage("Job Description cannot be empty.");
      return;
    }

    setSubmitting(true);
    setMessage("");
    hasSubmittedRef.current = true;

    try {
      const formData = new FormData();
      formData.append("jd_text", jdText.trim());

      const res = await api.post("/set_jd", formData);

      // ⭐ capture backend session
      const newSessionId = res?.data?.session_id;

      if (!newSessionId) {
        throw new Error("No session_id returned from backend");
      }

      // ✅ send BOTH text + session upward
      onJDSet({
        text: jdText,
        sessionId: newSessionId,
      });

      setMessage("Job description locked for this session.");
    } catch (err) {
      const detail = err?.response?.data?.detail;

      // ✅ StrictMode duplicate submit → treat as success
      if (
        err?.response?.status === 400 &&
        typeof detail === "string" &&
        detail.includes("already set")
      ) {
        onJDSet({
          text: jdText,
          sessionId, // keep current session
        });

        setMessage("Job description locked for this session.");
      } else {
        console.error(err);
        setMessage("Failed to set Job Description.");
        hasSubmittedRef.current = false; // allow retry on real failure
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card
      title="Reference Job Description"
      subtitle={
        locked
          ? "Session anchor · This job description is locked"
          : "This text is converted into a semantic vector representation"
      }
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <textarea
          rows={7}
          value={jdText}
          onChange={(e) => setJDText(e.target.value)}
          placeholder="Paste the complete job description here…"
          disabled={submitting || locked}
          className={`
            w-full rounded-2xl px-5 py-4 resize-none
            border
            ${
              locked
                ? "border-green-500/30 bg-slate-800 text-slate-300"
                : "border-white/10 bg-slate-900 text-white"
            }
            placeholder-slate-500
            focus:outline-none focus:ring-2 focus:ring-indigo-500
          `}
        />

        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">
            {locked
              ? "This job description defines the entire screening session."
              : "Used as the semantic reference for candidate ranking."}
          </p>

          <button
            type="submit"
            disabled={submitting || locked}
            className={`
              rounded-xl px-6 py-2.5 text-sm font-semibold transition-all
              ${
                locked
                  ? "bg-green-600/40 text-green-300 cursor-not-allowed"
                  : "bg-gradient-to-r from-emerald-500 to-green-500 text-white hover:from-emerald-600 hover:to-green-600"
              }
            `}
          >
            {locked
              ? "Session Locked"
              : submitting
              ? "Embedding…"
              : "Set Job Description"}
          </button>
        </div>

        {message && (
          <p className="text-sm font-medium text-indigo-400">
            {message}
          </p>
        )}
      </form>
    </Card>
  );
}
