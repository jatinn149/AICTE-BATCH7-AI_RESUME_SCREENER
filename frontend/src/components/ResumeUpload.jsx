import React, { useEffect, useRef, useState } from "react";
import api from "../api/axios";
import Card from "./Card";
import Button from "./UI/Button";

export default function ResumeUpload({ onUploadComplete, sessionId }) {
  const [files, setFiles] = useState([]);
  const [message, setMessage] = useState("");
  const [uploading, setUploading] = useState(false);
  const [completedCount, setCompletedCount] = useState(0);
  const [dragActive, setDragActive] = useState(false);

  const abortControllerRef = useRef(null);
  const uploadingRef = useRef(false);
  const activeSessionRef = useRef(sessionId);
  const fileInputRef = useRef(null);

  useEffect(() => {
    uploadingRef.current = uploading;
  }, [uploading]);

  useEffect(() => {
    if (uploadingRef.current && abortControllerRef.current) {
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

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    const pdfFiles = droppedFiles.filter((file) =>
      file.name.toLowerCase().endsWith(".pdf")
    );
    setFiles(pdfFiles);
  };

  const handleUpload = async () => {
    if (!files.length) {
      setMessage("Please select at least one PDF resume.");
      return;
    }

    // ✅ Validate file sizes before uploading
    const maxSizeMB = 10;
    const maxSizeBytes = maxSizeMB * 1024 * 1024;
    
    for (const file of files) {
      if (file.size > maxSizeBytes) {
        setMessage(`File "${file.name}" exceeds ${maxSizeMB}MB limit (${(file.size / 1024 / 1024).toFixed(1)}MB).`);
        return;
      }
    }

    setUploading(true);
    setMessage("");
    setCompletedCount(0);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      const uploadPromises = files.map((file) => {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("session_id", sessionId);

        return api
          .post("/upload_resume", formData, {
            signal: controller.signal,
          })
          .then((response) => {
            setCompletedCount((prev) => prev + 1);
            return {
              file: file.name,
              success: true,
              data: response.data,
            };
          });
      });

      const results = await Promise.allSettled(uploadPromises);

      if (controller.signal.aborted) return;

      const successful = results.filter((r) => r.status === "fulfilled").map(r => r.value);
      const failed = results.filter((r) => r.status === "rejected");

      let feedbackMsg = "";
      
      if (successful.length > 0) {
        const totalSkills = successful.reduce((sum, item) => sum + (item.data.total_skills_found || 0), 0);
        const totalExp = successful.reduce((sum, item) => sum + (item.data.experience_years || 0), 0);
        
        feedbackMsg = `✨ Uploaded ${successful.length} resume${successful.length !== 1 ? 's' : ''} • ${totalSkills} skills • ${totalExp.toFixed(1)} years avg`;
      }

      if (failed.length > 0) {
        feedbackMsg += ` | ${failed.length} failed`;
      }

      setMessage(feedbackMsg || "All resumes uploaded and indexed!");
      setFiles([]);
      onUploadComplete();
    } catch (err) {
      if (err.name !== "CanceledError") {
        console.error(err);
        setMessage("Unexpected error during upload.");
      }
    } finally {
      setUploading(false);
    }
  };

  const progressPercent = files.length > 0 ? Math.round((completedCount / files.length) * 100) : 0;

  return (
    <Card
      title="Upload Resumes"
      icon="2"
      step="02"
      subtitle="Add candidate PDF resumes in bulk. Files are parsed and indexed automatically."
    >
      <div className="max-w-4xl space-y-8">
        {/* Drop zone */}
        <label
          onDragEnter={handleDrag}
          onDragLeave={handleDrag}
          onDragOver={handleDrag}
          onDrop={handleDrop}
          className={`
            flex w-full cursor-pointer flex-col items-center justify-center
            rounded-2xl border-2 border-dashed p-8 transition-all duration-200 md:p-12
            ${dragActive
              ? "border-brand-500 bg-brand-100/60 dark:bg-brand-950/30"
              : "border-slate-300/80 bg-white/60 hover:border-brand-400 hover:bg-white dark:border-slate-700 dark:bg-slate-900/55"
            }
          `}
        >
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf"
            onChange={handleFileChange}
            disabled={uploading}
            className="hidden"
          />

          <div className="text-center">
            <div
              className={`mb-4 inline-flex h-14 w-14 items-center justify-center rounded-2xl border text-2xl transition-transform ${
                dragActive
                  ? "scale-105 border-brand-400 bg-brand-600 text-white"
                  : "border-slate-300 bg-white text-slate-700 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200"
              }`}
            >
              UP
            </div>

            <h3 className="mb-2 text-xl font-bold text-slate-900 dark:text-slate-100">
              Upload candidate resumes
            </h3>

            <p className="text-sm leading-relaxed text-secondary">
              Drag & drop PDF files here or click to browse • Up to 10MB each
            </p>
          </div>
        </label>

        {/* FILE LIST */}
        {files.length > 0 && (
          <div className="surface-panel p-5 md:p-6">
            <p className="mb-4 text-xs font-bold uppercase tracking-[0.14em] text-muted">
              Selected Files ({files.length})
            </p>

            <ul className="space-y-3">
              {files.map((file, idx) => (
                <li
                  key={idx}
                  className="group flex items-center justify-between gap-4 rounded-xl border border-slate-200/80 bg-white/70 p-4 transition-all hover:border-slate-300 dark:border-slate-700 dark:bg-slate-900/60"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-3">
                    <span className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-slate-100 text-xs font-bold dark:border-slate-700 dark:bg-slate-800">
                      PDF
                    </span>
                    <span className="truncate text-sm font-medium text-slate-800 dark:text-slate-100">
                      {file.name}
                    </span>
                  </div>

                  {!uploading && (
                    <button
                      onClick={() => removeFile(idx)}
                      className="rounded-lg px-2 py-1 text-lg text-slate-400 opacity-0 transition-all group-hover:opacity-100 hover:bg-red-100 hover:text-red-600 dark:hover:bg-red-950/40"
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
          <div className="surface-panel space-y-4 border-brand-200/80 p-5 dark:border-brand-800/70">
            <div className="flex justify-between text-sm">
              <span className="font-semibold text-slate-700 dark:text-slate-200">Uploading resumes...</span>
              <span className="font-semibold text-brand-600 dark:text-brand-400">{completedCount} / {files.length}</span>
            </div>

            <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
              <div
                className="h-full rounded-full bg-gradient-to-r from-brand-500 to-teal-500 transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Action row */}
        <div className="flex flex-col items-start justify-between gap-4 border-t border-slate-200/80 pt-4 dark:border-slate-700/70 sm:flex-row sm:items-center">
          <p className="text-xs text-secondary">
            Uploads will stop if the session is reset
          </p>

          <Button 
            onClick={handleUpload} 
            disabled={uploading || !files.length}
            variant={files.length > 0 ? "primary" : "ghost"}
            size="md"
          >
            {uploading ? `Uploading... ${progressPercent}%` : "Upload Files"}
          </Button>
        </div>

        {/* Message */}
        {message && (
          <div className={`rounded-xl border px-4 py-3 text-sm font-semibold ${
            message.includes("Uploaded") || message.includes("✨")
              ? "border-emerald-300/80 bg-emerald-100/70 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/50 dark:text-emerald-300"
              : "border-amber-300/80 bg-amber-100/70 text-amber-800 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
          }`}>
            {message}
          </div>
        )}
      </div>
    </Card>
  );
}
