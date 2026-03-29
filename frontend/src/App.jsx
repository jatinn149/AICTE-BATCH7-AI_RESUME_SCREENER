import React, { useRef, useState } from "react";
import Layout from "./components/Layout";
import JDInput from "./components/JDInput";
import ResumeUpload from "./components/ResumeUpload";
import RankedTable from "./components/RankedTable";
import RAGChatbot from "./components/RAGChatbot";
import api from "./api/axios";

function App() {
  // 🔥 FIX: session starts as null (backend will assign)
  const [sessionId, setSessionId] = useState(null);
  const [jd, setJD] = useState(null);
  const [refreshRank, setRefreshRank] = useState(false);
  const [processing, setProcessing] = useState(false);

  // 🔒 Track the currently valid session
  const activeSessionRef = useRef(null);

  const systemStatus = processing
    ? "processing"
    : jd
    ? "ready"
    : "idle";

  const resetSession = async () => {
    try {
      setProcessing(true);

      // Reset backend
      await api.post("/reset");

      // 🔥 FIX: clear frontend session completely
      activeSessionRef.current = null;
      setSessionId(null);
      setJD(null);
      setRefreshRank(false);
    } catch (err) {
      console.error("Failed to reset session:", err);
    } finally {
      setProcessing(false);
    }
  };

  return (
    <Layout systemStatus={systemStatus} onReset={resetSession}>
      <section className="space-y-6">
        <div className="surface-panel p-4 md:p-5">
          <p className="section-kicker mb-2">Onboarding</p>
          <p className="text-sm text-secondary">
            Complete each step in sequence: set the job description, upload resumes, review
            ranked candidates, then use chat for deeper insights.
          </p>
        </div>

        <JDInput
          sessionId={sessionId}
          locked={!!jd}
          onJDSet={(jdData) => {
            // 🔥 CRITICAL FIX — sync backend session globally
            const newSessionId = jdData?.sessionId;

            if (!newSessionId) {
              console.error("No sessionId received from backend");
              return;
            }

            activeSessionRef.current = newSessionId;
            setSessionId(newSessionId);

            setProcessing(true);
            setJD(jdData);
            setProcessing(false);
          }}
        />
      </section>

      {jd && (
        <ResumeUpload
          sessionId={sessionId}
          onUploadComplete={() => {
            // 🔒 DO NOT continue if session was reset mid-upload
            if (!sessionId || activeSessionRef.current !== sessionId) return;

            setProcessing(true);
            setRefreshRank(true);
            setProcessing(false);
          }}
        />
      )}

      {jd && refreshRank && (
        <RankedTable sessionId={sessionId} refresh={refreshRank} />
      )}

      {jd && refreshRank && (
        <RAGChatbot sessionId={sessionId} />
      )}
    </Layout>
  );
}

export default App;
