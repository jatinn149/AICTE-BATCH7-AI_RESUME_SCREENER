import React, { useEffect, useRef, useState } from "react";
import api from "../api/axios";
import Card from "./Card";
import Button from "./ui/Button";

export default function ResumeUpload({ onUploadComplete, sessionId }) {
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);

  // 🔥 Abort controller for current upload batch
  const abortControllerRef = useRef(null);
  const activeSessionRef = useRef(sessionId);

  // 🔴 HARD CANCEL when sessionId changes (Reset clicked)
  useEffect(() => {
    if (uploading && abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    activeSessionRef.current = sessionId;
    setUploading(false);
    setFiles([]);
    setCompletedCount(0);
    setMessage("");
  }, [sessionId]);

  const handleFileChange = (e) => {
    const selectedFiles = Array.from(e.target.files);
    const pdfFiles = selectedFiles.filter((file) =>
      file.name.toLowerCase().endsWith(".pdf")
    );

    if (pdfFiles.length !== selectedFiles.length) {
      setMessage("Only PDF resumes are supported.");
    } else {
      setMessage("");
    }

    setFiles(pdfFiles);
    setCompletedCount(0);
  };

  const removeFile = (index) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (!files.length) {
      setMessage("Please select at least one PDF resume.");
      return;
    }

    setUploading(true);
    setMessage("");
    setCompletedCount(0);

    // Create fresh controller for this batch
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const uploadPromises = files.map((file) => {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("session_id", sessionId);

        return api
          .post("/upload_resume", formData, {
            headers: { "Content-Type": "multipart/form-data" },
            signal: controller.signal,
          })
          .then(() => {
            setCompletedCount((prev) => prev + 1);
          });
      });

      const results = await Promise.allSettled(uploadPromises);

      // If aborted, do nothing further
      if (controller.signal.aborted) return;

      const failed = results.filter((r) => r.status === "rejected").length;

      if (failed > 0) {
        setMessage(
          `${files.length - failed} resumes uploaded successfully, ${failed} failed.`
        );
      } else {
        setMessage("All resumes uploaded and indexed successfully.");
      }

      setFiles([]);
      onUploadComplete();
    } catch (err) {
      if (err.name === "CanceledError") {
        console.log("Upload cancelled due to session reset.");
      } else {
        console.error(err);
        setMessage("Unexpected error during resume upload.");
      }
    } finally {
      setUploading(false);
    }
  };

  const progressPercent =
    files.length > 0
      ? Math.round((completedCount / files.length) * 100)
      : 0;

  return (
    <Card>
      <div className="mx-auto max-w-3xl space-y-6">
        {/* Drop zone */}
        <label
          className="
            flex flex-col items-center justify-center
            w-full
            rounded-xl
            border border-dashed border-white/15
            bg-slate-900/60
            px-6 py-10
            text-center
            cursor-pointer
            transition
            hover:border-indigo-400
          "
        >
          <input
            type="file"
            multiple
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />

          <p className="text-lg font-medium text-white">
            Upload candidate resumes
          </p>
          <p className="mt-1 text-sm text-slate-400">
            PDF only • Cancellable parallel ingestion
          </p>
        </label>

        {/* FILE LIST */}
        {files.length > 0 && (
          <div
            className="
              rounded-lg
              border border-white/10
              bg-slate-900/70
              p-4
              max-h-40
              overflow-y-auto
            "
          >
            <p className="mb-2 text-xs uppercase tracking-wide text-slate-400">
              Selected files
            </p>

            <ul className="space-y-2 text-sm text-slate-300">
              {files.map((file, idx) => (
                <li
                  key={idx}
                  className="flex items-center justify-between gap-3"
                >
                  <span className="truncate">• {file.name}</span>

                  {!uploading && (
                    <button
                      onClick={() => removeFile(idx)}
                      className="
                        flex h-5 w-5 items-center justify-center
                        rounded-full
                        border border-white/20
                        text-xs text-slate-300
                        hover:bg-red-500 hover:text-white
                        transition
                      "
                      title="Remove file"
                    >
                      ✕
                    </button>
                  )}
                </li>
              ))}
            </ul>
          </div>
        )}

        {/* PROGRESS */}
        {uploading && (
          <div className="space-y-2">
            <div className="flex justify-between text-xs text-slate-400">
              <span>Uploading resumes</span>
              <span>
                {completedCount} / {files.length}
              </span>
            </div>

            <div className="h-2 w-full rounded-full bg-slate-800 overflow-hidden">
              <div
                className="
                  h-full
                  bg-gradient-to-r from-indigo-500 to-cyan-500
                  transition-all duration-300
                "
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Action row */}
        <div className="flex items-center justify-between">
          <p className="text-sm text-slate-400">
            Uploads stop instantly if the session is reset.
          </p>

          <Button onClick={handleUpload} disabled={uploading || !files.length}>
            {uploading ? "Uploading…" : "Submit"}
          </Button>
        </div>

        {/* Message */}
        {message && (
          <p className="text-sm font-medium text-indigo-400">
            {message}
          </p>
        )}
      </div>
    </Card>
  );
}
