import React, { useEffect, useState } from "react";
import api from "../api/axios";
import Card from "./Card";

export default function RankedTable({ refresh, sessionId }) {
  const [candidates, setCandidates] = useState([]);
  const [statusMsg, setStatusMsg] = useState("");
  const [sending, setSending] = useState(false);
  const [decisions, setDecisions] = useState({});
  const [loadingRank, setLoadingRank] = useState(false);

  const fetchCandidates = async () => {
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
  };

  useEffect(() => {
    // ✅ SAFE GUARD ADDED
    if (refresh && sessionId) {
      fetchCandidates();
    }
  }, [refresh, sessionId]);

  const sendEmail = async (email, name, type) => {
    if (!email || email === "N/A") {
      setStatusMsg("Invalid candidate email.");
      return;
    }

    setSending(true);
    setStatusMsg("");

    try {
      const formData = new FormData();

      // ✅ FIXED TO MATCH BACKEND
      formData.append("email", email);
      formData.append("name", name);
      formData.append(
        "decision",
        type === "confirmation" ? "confirm" : "reject"
      );

      await api.post("/send_email", formData);

      setDecisions((prev) => ({
        ...prev,
        [email]: type,
      }));

      setStatusMsg(
        `${type === "confirmation" ? "Confirmed" : "Rejected"} ${name}`
      );
    } catch (err) {
      console.error(err);
      setStatusMsg(`Failed to send ${type} email to ${name}`);
    } finally {
      setSending(false);
    }
  };

  return (
    <Card
      title="Candidate Ranking Results"
      subtitle="Semantic similarity scores computed using vector embeddings"
    >
      <div className="space-y-6">
        {statusMsg && (
          <p className="text-sm font-medium text-indigo-400">
            {statusMsg}
          </p>
        )}

        {/* 🔄 LOADING STATE */}
        {loadingRank && (
          <div className="space-y-3">
            <p className="text-sm text-slate-400">
              Computing candidate rankings…
            </p>

            <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
              <div
                className="
                  h-full
                  w-2/3
                  animate-pulse
                  bg-gradient-to-r
                  from-indigo-500
                  to-cyan-500
                "
              />
            </div>
          </div>
        )}

        {/* ❌ NO DATA */}
        {!loadingRank && candidates.length === 0 && (
          <p className="text-center text-slate-400">
            No ranked candidates available yet.
          </p>
        )}

        {/* ✅ TABLE */}
        {!loadingRank && candidates.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse">
              <thead>
                <tr className="text-left text-xs uppercase tracking-wider text-slate-400 border-b border-white/10">
                  <th className="px-4 py-4 font-medium">Rank</th>
                  <th className="px-4 py-4 font-medium">Candidate</th>
                  <th className="px-4 py-4 font-medium">Email</th>
                  <th className="px-4 py-4 font-medium">Match Score</th>
                  <th className="px-4 py-4 font-medium">Predicted Role</th>
                  <th className="px-4 py-4 font-medium">Decision</th>
                </tr>
              </thead>

              <tbody>
                {candidates.map((c, idx) => {
                  const decision = decisions[c.email];
                  const score =
                    typeof c.score === "number"
                      ? c.score.toFixed(1)
                      : c.score;

                  const confidenceColor =
                    score >= 80
                      ? "text-green-400 bg-green-500/15"
                      : score >= 60
                      ? "text-indigo-400 bg-indigo-500/15"
                      : "text-amber-400 bg-amber-500/15";

                  return (
                    <tr
                      key={`${c.email}-${idx}`}
                      className="
                        border-b border-white/5
                        hover:bg-indigo-500/5
                        transition
                      "
                    >
                      <td className="px-4 py-4 text-sm text-slate-400">
                        #{idx + 1}
                      </td>

                      <td className="px-4 py-4 font-medium text-white">
                        {c.name}
                      </td>

                      <td className="px-4 py-4 text-sm text-slate-400">
                        {c.email}
                      </td>

                      <td className="px-4 py-4">
                        <span
                          className={`inline-flex items-center rounded-full px-3 py-1 text-sm font-semibold ${confidenceColor}`}
                        >
                          {score}%
                        </span>
                      </td>

                      <td className="px-4 py-4 text-sm text-slate-300">
                        {c.role}
                      </td>

                      <td className="px-4 py-4">
                        {!decision ? (
                          <div className="flex gap-2">
                            <button
                              disabled={sending}
                              onClick={() =>
                                sendEmail(c.email, c.name, "confirmation")
                              }
                              className="
                                rounded-md
                                bg-green-600
                                px-3 py-1.5
                                text-sm font-semibold text-white
                                hover:bg-green-700
                                disabled:opacity-50
                              "
                            >
                              Confirm
                            </button>

                            <button
                              disabled={sending}
                              onClick={() =>
                                sendEmail(c.email, c.name, "rejection")
                              }
                              className="
                                rounded-md
                                bg-red-600
                                px-3 py-1.5
                                text-sm font-semibold text-white
                                hover:bg-red-700
                                disabled:opacity-50
                              "
                            >
                              Reject
                            </button>
                          </div>
                        ) : (
                          <span
                            className={`text-sm font-semibold ${
                              decision === "confirmation"
                                ? "text-green-400"
                                : "text-red-400"
                            }`}
                          >
                            {decision === "confirmation"
                              ? "Confirmed ✓"
                              : "Rejected ✕"}
                          </span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Card>
  );
}
