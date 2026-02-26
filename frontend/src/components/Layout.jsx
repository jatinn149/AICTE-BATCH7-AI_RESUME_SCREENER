import React, { useEffect, useState } from "react";
import SystemStatus from "./SystemStatus";

export default function Layout({
  children,
  systemStatus = "idle",
  onReset,
}) {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    const stored = localStorage.getItem("theme");
    if (stored) {
      setTheme(stored);
      document.documentElement.classList.toggle("dark", stored === "dark");
    }
  }, []);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <div
      className="
        min-h-screen transition-colors
        bg-gradient-to-br
        from-emerald-100 via-green-100 to-lime-100
        dark:from-slate-950 dark:via-slate-900 dark:to-slate-800
        text-slate-900 dark:text-slate-100
      "
    >
      {/* DARK DEPTH */}
      <div
        className="
          pointer-events-none fixed inset-0 hidden dark:block
          bg-[radial-gradient(ellipse_at_top,_rgba(99,102,241,0.12),_transparent_60%)]
        "
      />

      {/* HERO */}
      <header className="relative overflow-hidden">
        <div
          className="
            absolute inset-0
            bg-gradient-to-br
            from-emerald-200/70 via-green-200/50 to-transparent
            dark:from-indigo-900/40 dark:via-slate-900/70
          "
        />

        <div className="relative mx-auto max-w-6xl px-6 pt-28 pb-20 text-center">
          {/* TOP CONTROLS */}
          <div className="absolute right-6 top-6 flex items-center gap-4">
            <SystemStatus status={systemStatus} />

            <button
              onClick={onReset}
              className="
                rounded-lg px-3 py-1.5 text-sm font-medium
                border border-red-300 dark:border-red-500/30
                bg-red-50 dark:bg-red-900/30
                text-red-600 dark:text-red-300
                hover:shadow transition
              "
            >
              ⟳ New Session
            </button>

            <button
              onClick={toggleTheme}
              className="
                rounded-lg px-3 py-1.5 text-sm font-medium
                border border-slate-300 dark:border-white/10
                bg-white/70 dark:bg-slate-900/70
                hover:shadow transition
              "
            >
              {theme === "light" ? "🌙 Dark" : "☀️ Light"}
            </button>
          </div>

          <h1 className="text-4xl md:text-6xl font-extrabold tracking-tight">
            AI-Powered{" "}
            <span
              className="
                bg-gradient-to-r
                from-emerald-600 to-green-500
                dark:from-indigo-400 dark:to-cyan-400
                bg-clip-text text-transparent
              "
            >
              Resume Screening
            </span>
          </h1>

          <p className="mt-6 mx-auto max-w-3xl text-lg text-slate-600 dark:text-slate-400">
            An AIML-driven system that ranks candidates using semantic similarity,
            vector embeddings, and retrieval-augmented generation.
          </p>
        </div>

        <div className="h-px w-full bg-gradient-to-r from-transparent via-slate-300 dark:via-white/10 to-transparent" />
      </header>

      {/* APP */}
      <main className="relative mx-auto max-w-6xl px-6 py-24">
        <div
          className="
            relative ml-10 rounded-3xl
            bg-white/80 dark:bg-slate-900/80
            backdrop-blur-xl
            border border-slate-200 dark:border-white/10
            shadow-[0_0_0_1px_rgba(255,255,255,0.02),0_30px_60px_rgba(0,0,0,0.7)]
          "
        >
          <div className="p-10 md:p-14 space-y-24">
            {children}
          </div>
        </div>
      </main>

      <footer className="py-8 text-center text-xs text-slate-500 dark:text-slate-400">
        Final AIML Internship Project • Semantic Search • Vector Databases • RAG
      </footer>
    </div>
  );
}
