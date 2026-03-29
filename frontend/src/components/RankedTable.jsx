import React, { useCallback, useEffect, useState } from "react";
import api from "../api/axios";
import Card from "./Card";
import Button from "./UI/Button";

export default function RankedTable({ refresh, sessionId }) {
  const [candidates, setCandidates] = useState([]);
  const [statusMsg, setStatusMsg] = useState("");
  const [sending, setSending] = useState(false);
  const [decisions, setDecisions] = useState({});
  const [loadingRank, setLoadingRank] = useState(false);

  const fetchCandidates = useCallback(async () => {
    try {
      setLoadingRank(true);
      setStatusMsg("");

      const res = await api.get("/ranked_candidates", {
        params: { session_id: sessionId },
      });

      setCandidates(res.data || []);
    } catch (err) {
      console.error(err);
      setStatusMsg("Failed to fetch ranked candidates.");
    } finally {
      setLoadingRank(false);
    }
  }, [sessionId]);

  useEffect(() => {
    if (refresh && sessionId) {
      fetchCandidates();
    }
  }, [fetchCandidates, refresh, sessionId]);

  const sendEmail = async (email, name, type) => {
    if (!email || email === "N/A") {
      setStatusMsg("Invalid candidate email.");
      return;
    }

    setSending(true);
    setStatusMsg("");

    try {
      const formData = new FormData();
      formData.append("email", email);
      formData.append("name", name);
      formData.append("decision", type === "confirmation" ? "confirm" : "reject");

      await api.post("/send_email", formData);

      setDecisions((prev) => ({
        ...prev,
        [email]: type,
      }));

      setStatusMsg(`${type === "confirmation" ? "✨ Confirmed" : "↩️ Rejected"} ${name}`);
    } catch (err) {
      console.error(err);
      setStatusMsg(`Failed to send ${type} email to ${name}`);
    } finally {
      setSending(false);
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return "from-emerald-500 to-teal-500";
    if (score >= 60) return "from-cyan-500 to-blue-500";
    return "from-amber-500 to-orange-500";
  };

  return (
    <Card
      title="Ranked Candidates"
      subtitle="Candidates are ranked by semantic match against your locked role description."
      icon="3"
      step="03"
    >
      <div className="space-y-8">
        {statusMsg && (
          <div className="rounded-xl border border-brand-300/80 bg-brand-100/70 p-4 text-sm font-semibold text-brand-700 dark:border-brand-800 dark:bg-brand-950/50 dark:text-brand-300">
            {statusMsg}
          </div>
        )}

        {/* LOADING STATE */}
        {loadingRank && (
          <div className="space-y-4">
            <p className="text-secondary">Computing candidate rankings...</p>
            <div className="h-1.5 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <div className="h-full w-1/3 animate-pulse rounded-full bg-gradient-to-r from-brand-500 to-teal-500" />
            </div>
          </div>
        )}

        {/* NO DATA */}
        {!loadingRank && candidates.length === 0 && (
          <div className="py-16 text-center">
            <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl border border-slate-300 bg-slate-100 text-sm font-bold text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200">
              0
            </div>
            <p className="mb-2 font-semibold text-slate-800 dark:text-slate-200">No ranked candidates yet</p>
            <p className="text-sm text-secondary">Upload resumes to view AI ranking results.</p>
          </div>
        )}

        {/* TABLE */}
        {!loadingRank && candidates.length > 0 && (
          <div className="grid gap-4">
            {candidates.map((c, idx) => {
              const decision = decisions[c.email];
              const score = typeof c.score === "number" ? c.score.toFixed(0) : c.score;
              const scoreColor = getScoreColor(score);

              return (
                <div
                  key={`${c.email}-${idx}`}
                  className="group rounded-xl border border-slate-200/80 bg-white/70 p-5 transition-all duration-200 hover:border-slate-300 hover:bg-white dark:border-slate-700 dark:bg-slate-900/60"
                >
                  <div className="mb-4 flex items-start justify-between gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="mb-2 flex items-center gap-3">
                        <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg border border-brand-200 bg-brand-600 text-xs font-bold text-white dark:border-brand-700">
                          #{idx + 1}
                        </div>

                        <div className="min-w-0 flex-1">
                          <h4 className="truncate text-lg font-bold text-slate-900 dark:text-slate-100">{c.name}</h4>
                          <p className="truncate text-sm text-secondary">{c.email}</p>
                        </div>
                      </div>
                    </div>

                    <div className="text-center">
                      <div className={`bg-gradient-to-r ${scoreColor} bg-clip-text text-3xl font-black text-transparent`}>
                        {score}%
                      </div>
                      <p className="mt-1 text-xs text-muted">Match Score</p>
                    </div>
                  </div>

                  <div className="flex gap-3">
                    {!decision ? (
                      <>
                        <Button
                          disabled={sending}
                          onClick={() => sendEmail(c.email, c.name, "confirmation")}
                          variant="success"
                          size="md"
                          className="flex-1"
                        >
                          ✓ Confirm
                        </Button>
                        <Button
                          disabled={sending}
                          onClick={() => sendEmail(c.email, c.name, "rejection")}
                          variant="danger"
                          size="md"
                          className="flex-1"
                        >
                          ✕ Reject
                        </Button>
                      </>
                    ) : (
                      <div className={`flex items-center justify-center w-full py-2 rounded-lg font-semibold ${
                        decision === "confirmation"
                          ? "border border-emerald-300/80 bg-emerald-100/70 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
                          : "border border-red-300/80 bg-red-100/70 text-red-800 dark:border-red-800 dark:bg-red-950/50 dark:text-red-300"
                      }`}>
                        {decision === "confirmation" ? "✓ Confirmed" : "✕ Rejected"}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Card>
  );
}
