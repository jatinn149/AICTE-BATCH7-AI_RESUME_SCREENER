import React, { useEffect, useState } from "react";
import SystemStatus from "./SystemStatus";

export default function Layout({
  children,
  systemStatus = "idle",
  onReset,
}) {
  const [theme, setTheme] = useState(() => localStorage.getItem("theme") || "light");

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const toggleTheme = () => {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  };

  return (
    <div className="min-h-screen text-slate-900 transition-colors duration-300 dark:text-slate-100">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -top-32 -right-16 h-80 w-80 rounded-full bg-brand-500/15 blur-3xl" />
        <div className="absolute left-0 top-1/3 h-72 w-72 rounded-full bg-teal-500/15 blur-3xl" />
        <div className="absolute -bottom-28 right-1/4 h-72 w-72 rounded-full bg-orange-400/10 blur-3xl" />
      </div>

      <header className="sticky top-0 z-40 border-b border-slate-200/80 bg-white/75 backdrop-blur-xl dark:border-slate-800 dark:bg-slate-950/75">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between px-4 py-4 md:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-brand-200 bg-brand-600 text-white shadow-soft dark:border-brand-700">
              RS
            </div>

            <div>
              <h1 className="font-display text-xl font-bold tracking-tight md:text-2xl">
                Resume Screener
              </h1>
              <p className="text-xs text-muted">Hiring Intelligence Platform</p>
            </div>
          </div>

          <div className="flex items-center gap-2 md:gap-3">
            <SystemStatus status={systemStatus} />

            <button
              onClick={toggleTheme}
              className="h-10 rounded-xl border border-slate-300/80 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800"
              title="Toggle theme"
            >
              {theme === "light" ? "Dark" : "Light"}
            </button>

            <button
              onClick={onReset}
              className="h-10 rounded-xl border border-red-200 bg-red-600 px-4 text-sm font-semibold text-white transition hover:bg-red-700 dark:border-red-900"
            >
              Reset
            </button>
          </div>
        </div>
      </header>

      <section className="relative px-4 pt-12 md:px-6 md:pt-16">
        <div className="mx-auto max-w-6xl">
          <div className="surface-main rounded-3xl border border-slate-200/80 p-6 shadow-soft dark:border-slate-800 md:p-10">
            <p className="section-kicker mb-3">Smart Candidate Workflow</p>

            <div className="grid gap-8 md:grid-cols-[1.1fr_0.9fr] md:items-end">
              <div>
                <h2 className="font-display text-3xl font-bold leading-tight md:text-5xl">
                  Build a shortlist with
                  <span className="gradient-headline"> confidence and speed</span>
                </h2>

                <p className="mt-4 max-w-2xl text-base leading-relaxed text-secondary md:text-lg">
                  Define the role once, upload resumes in bulk, get ranked candidates, and ask
                  natural-language questions to validate your hiring decisions.
                </p>
              </div>

              <div className="surface-panel border-slate-200/80 p-4 dark:border-slate-700/70 md:p-5">
                <p className="text-xs font-bold uppercase tracking-[0.14em] text-muted">Workflow</p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
                  <div className="rounded-lg bg-slate-100/80 px-3 py-2 dark:bg-slate-800/70">1. Set JD</div>
                  <div className="rounded-lg bg-slate-100/80 px-3 py-2 dark:bg-slate-800/70">2. Upload PDFs</div>
                  <div className="rounded-lg bg-slate-100/80 px-3 py-2 dark:bg-slate-800/70">3. Review Rankings</div>
                  <div className="rounded-lg bg-slate-100/80 px-3 py-2 dark:bg-slate-800/70">4. Ask AI</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto mt-8 h-px w-full max-w-6xl brand-divider" />

      <main className="relative mx-auto w-full max-w-6xl px-4 py-10 md:px-6 md:py-12">
        <div className="space-y-8 md:space-y-10">{children}</div>
      </main>

      <footer className="mt-16 border-t border-slate-200/80 px-4 py-10 dark:border-slate-800 md:px-6">
        <div className="mx-auto max-w-6xl">
          <div className="text-center">
            <p className="font-semibold text-slate-800 dark:text-slate-200">Resume Screener</p>
            <p className="mt-1 text-xs text-muted">
              Semantic ranking, structured screening, and candidate intelligence in one streamlined interface.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
}
