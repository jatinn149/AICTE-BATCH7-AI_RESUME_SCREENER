import React, { useRef, useState, useEffect } from "react";
import api from "../api/axios";
import Card from "./Card";
import Button from "./UI/Button";

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

    // ✅ Client-side validation to provide immediate feedback
    const trimmedJD = jdText.trim();
    if (trimmedJD.length < 50) {
      setMessage("Job Description must be at least 50 characters.");
      return;
    }

    if (trimmedJD.split(/\s+/).length < 10) {
      setMessage("Job Description must have at least 10 words.");
      return;
    }

    setSubmitting(true);
    setMessage("");
    hasSubmittedRef.current = true;

    try {
      const formData = new FormData();
      formData.append("jd_text", trimmedJD);

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

      setMessage("✨ Job description locked for this session.");
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

        setMessage("✨ Job description locked for this session.");
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
      title="Job Description"
      subtitle={
        locked
          ? "Session anchor configured. This description now drives matching and ranking."
          : "Paste the role requirements to initialize semantic matching for this session."
      }
      icon="1"
      step="01"
    >
      <form onSubmit={handleSubmit} className="space-y-6">
        <div className="surface-panel p-3 md:p-4">
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-muted">
            Job Description Input
          </p>

        <textarea
            rows={8}
            value={jdText}
            onChange={(e) => setJDText(e.target.value)}
            placeholder="Include role scope, required skills, years of experience, and expectations..."
            disabled={submitting || locked}
            className={`input-premium min-h-[220px] resize-y font-mono text-[13px] ${
              locked ? "cursor-not-allowed opacity-65" : ""
            }`}
          />
        </div>

        <div className="flex flex-col items-start justify-between gap-3 border-t border-slate-200/80 pt-4 dark:border-slate-700/70 md:flex-row md:items-center">
          <div className="text-xs text-secondary">
            {locked ? (
              <span className="inline-flex items-center gap-2 font-semibold text-emerald-700 dark:text-emerald-300">
                <span className="h-2 w-2 rounded-full bg-emerald-500" />
                Session active: JD is locked as the ranking baseline.
              </span>
            ) : (
              <span>This becomes the semantic reference used across all uploaded resumes.</span>
            )}
          </div>

          <Button
            type="submit"
            disabled={submitting || locked}
            variant={locked ? "ghost" : "primary"}
            size="md"
          >
            {locked
              ? "Locked"
              : submitting
              ? "Embedding"
              : "Set Description"}
          </Button>
        </div>

        {message && (
          <div
            className={`
              rounded-xl border px-4 py-3 text-sm font-semibold
              ${message.includes("locked") || message.includes("✨")
                ? "border-emerald-300/80 bg-emerald-100/70 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
                : "border-red-300/80 bg-red-100/70 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-300"
              }
            `}
          >
            {message}
          </div>
        )}
      </form>
    </Card>
  );
}
